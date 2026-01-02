// Background service worker for Gobbler extension

// ============================================================================
// Page-Specific API Registry - loaded from single source of truth
// ============================================================================
// Import the registry which defines PAGE_API_REGISTRY and findMatchingApi
// in the global scope. This is the recommended way for MV3 service workers.
importScripts('page-apis/registry.js');

let ws = null;
let reconnectInterval = null;
const WS_URL = 'ws://localhost:4625/ws';

// Tab group management
const GOBBLER_GROUP_COLOR = 'orange';
const GOBBLER_GROUP_TITLE = 'Gobbler';

// Permission management - track granted origins
const grantedOrigins = new Set();

// Track which tabs have had APIs injected
const injectedTabs = new Map(); // tabId -> { apiName, timestamp }

/**
 * Inject page-specific API into a tab
 */
async function injectPageApi(tabId, apiEntry) {
  try {
    // Check if already injected for this API
    const existing = injectedTabs.get(tabId);
    if (existing && existing.apiName === apiEntry.name) {
      console.log(`[Gobbler] ${apiEntry.name} API already injected in tab ${tabId}`);
      return { success: true, alreadyInjected: true };
    }

    console.log(`[Gobbler] Injecting ${apiEntry.name} API into tab ${tabId}...`);

    // Inject the API script into the MAIN world (not the isolated content script world)
    // This makes window.gobblerNotebookLM accessible from the page console and other scripts
    await chrome.scripting.executeScript({
      target: { tabId: tabId },
      files: [apiEntry.apiFile],
      world: 'MAIN'  // Critical: inject into page's main world, not isolated world
    });

    // Track injection
    injectedTabs.set(tabId, {
      apiName: apiEntry.name,
      timestamp: Date.now()
    });

    console.log(`[Gobbler] ${apiEntry.name} API injected successfully into tab ${tabId}`);
    return { success: true, apiName: apiEntry.name };
  } catch (error) {
    console.error(`[Gobbler] Failed to inject ${apiEntry.name} API:`, error);
    return { success: false, error: error.message };
  }
}

/**
 * Check and inject API for a tab if it matches a registered pattern
 */
async function checkAndInjectApi(tabId) {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!tab.url) return { success: false, reason: 'no-url' };

    // Only inject for tabs in Gobbler group
    const isInGroup = await isTabInGobblerGroup(tabId);
    if (!isInGroup) {
      return { success: false, reason: 'not-in-group' };
    }

    const apiEntry = findMatchingApi(tab.url);
    if (!apiEntry) {
      return { success: false, reason: 'no-matching-api' };
    }

    return await injectPageApi(tabId, apiEntry);
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * Inject APIs into all tabs currently in the Gobbler group
 */
async function injectApisIntoAllGobblerTabs() {
  const tabs = await getGobblerGroupTabs();
  const results = [];

  for (const tab of tabs) {
    const result = await checkAndInjectApi(tab.id);
    results.push({ tabId: tab.id, url: tab.url, ...result });
  }

  return results;
}

// Extract origin pattern from a URL for permission requests
function getOriginPattern(url) {
  try {
    const urlObj = new URL(url);
    // Chrome requires patterns like "https://example.com/*"
    return `${urlObj.protocol}//${urlObj.host}/*`;
  } catch (e) {
    console.error('Invalid URL for origin extraction:', url);
    return null;
  }
}

// Check if we have permission for a specific origin
async function hasPermissionForOrigin(originPattern) {
  if (!originPattern) return false;

  // Check cache first
  if (grantedOrigins.has(originPattern)) {
    return true;
  }

  // Check with Chrome
  try {
    const result = await chrome.permissions.contains({
      origins: [originPattern]
    });
    if (result) {
      grantedOrigins.add(originPattern);
    }
    return result;
  } catch (e) {
    console.error('Error checking permission:', e);
    return false;
  }
}

// Request permission for a specific origin
async function requestPermissionForOrigin(originPattern) {
  if (!originPattern) {
    return { granted: false, error: 'Invalid URL' };
  }

  // Already have permission?
  if (await hasPermissionForOrigin(originPattern)) {
    return { granted: true, alreadyHad: true };
  }

  try {
    const granted = await chrome.permissions.request({
      origins: [originPattern]
    });

    if (granted) {
      grantedOrigins.add(originPattern);
      console.log(`Permission granted for ${originPattern}`);
    } else {
      console.log(`Permission denied for ${originPattern}`);
    }

    return { granted, alreadyHad: false };
  } catch (e) {
    console.error('Error requesting permission:', e);
    return { granted: false, error: e.message };
  }
}

// Check if a URL is a special browser page that can't be accessed
function isRestrictedUrl(url) {
  if (!url) return true;
  return url.startsWith('chrome://') ||
         url.startsWith('chrome-extension://') ||
         url.startsWith('edge://') ||
         url.startsWith('about:') ||
         url.startsWith('file://');
}

// Get or create the Gobbler tab group
async function getOrCreateGobblerGroup() {
  const stored = await chrome.storage.local.get('gobblerGroupId');

  if (stored.gobblerGroupId) {
    // Verify group still exists
    try {
      const groups = await chrome.tabGroups.query({ title: GOBBLER_GROUP_TITLE });
      const existingGroup = groups.find(g => g.id === stored.gobblerGroupId);
      if (existingGroup) {
        return stored.gobblerGroupId;
      }
    } catch (e) {
      console.log('Error checking existing group:', e);
    }
  }

  // Create new group with current active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) {
    throw new Error('No active tab found');
  }

  const groupId = await chrome.tabs.group({ tabIds: [tab.id] });
  await chrome.tabGroups.update(groupId, {
    title: GOBBLER_GROUP_TITLE,
    color: GOBBLER_GROUP_COLOR,
    collapsed: false
  });

  await chrome.storage.local.set({ gobblerGroupId: groupId });
  console.log(`Created Gobbler group ${groupId} with tab ${tab.id}`);
  return groupId;
}

// Check if a tab is in the Gobbler group
async function isTabInGobblerGroup(tabId) {
  const stored = await chrome.storage.local.get('gobblerGroupId');
  if (!stored.gobblerGroupId) {
    return false;
  }

  try {
    const tab = await chrome.tabs.get(tabId);
    return tab.groupId === stored.gobblerGroupId;
  } catch (e) {
    return false;
  }
}

// Get active tab only if it's in the Gobbler group
async function getActiveGobblerTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) {
    throw new Error('No active tab found');
  }

  const stored = await chrome.storage.local.get('gobblerGroupId');
  if (!stored.gobblerGroupId) {
    throw new Error('Gobbler group not created. Click the extension icon to set up.');
  }

  if (tab.groupId !== stored.gobblerGroupId) {
    throw new Error('Active tab is not in Gobbler group. Add it first via extension popup or right-click menu.');
  }

  return tab;
}

// Add current tab to Gobbler group (with permission request)
async function addCurrentTabToGroup() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab) {
    return { success: false, error: 'No active tab found' };
  }

  // Check for restricted URLs that can't be accessed
  if (isRestrictedUrl(tab.url)) {
    return {
      success: false,
      error: 'Cannot access browser internal pages (chrome://, edge://, about:, etc.)'
    };
  }

  // Get the origin pattern for permission request
  const originPattern = getOriginPattern(tab.url);
  if (!originPattern) {
    return { success: false, error: 'Could not determine site origin' };
  }

  // Request permission for this origin
  const permResult = await requestPermissionForOrigin(originPattern);
  if (!permResult.granted) {
    return {
      success: false,
      error: permResult.error || 'Permission denied for this site',
      permissionDenied: true
    };
  }

  // Now add to group
  const groupId = await getOrCreateGobblerGroup();

  if (tab.groupId === groupId) {
    return { success: true, alreadyInGroup: true, tabId: tab.id, origin: originPattern };
  }

  await chrome.tabs.group({ tabIds: [tab.id], groupId });
  console.log(`Added tab ${tab.id} to Gobbler group (origin: ${originPattern})`);

  // Inject page-specific API if available
  const apiResult = await checkAndInjectApi(tab.id);
  if (apiResult.success && apiResult.apiName) {
    console.log(`[Gobbler] Injected ${apiResult.apiName} API for tab ${tab.id}`);
  }

  return {
    success: true,
    alreadyInGroup: false,
    tabId: tab.id,
    origin: originPattern,
    injectedApi: apiResult.apiName || null
  };
}

// Remove current tab from Gobbler group
async function removeCurrentTabFromGroup() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const stored = await chrome.storage.local.get('gobblerGroupId');

  if (!stored.gobblerGroupId || tab.groupId !== stored.gobblerGroupId) {
    return { success: true, wasInGroup: false };
  }

  await chrome.tabs.ungroup([tab.id]);
  console.log(`Removed tab ${tab.id} from Gobbler group`);
  return { success: true, wasInGroup: true };
}

// Get list of tabs in Gobbler group
async function getGobblerGroupTabs() {
  const stored = await chrome.storage.local.get('gobblerGroupId');
  if (!stored.gobblerGroupId) {
    return [];
  }

  const tabs = await chrome.tabs.query({ groupId: stored.gobblerGroupId });
  return tabs.map(t => ({
    id: t.id,
    title: t.title,
    url: t.url,
    active: t.active
  }));
}

// List tabs in Gobbler group (for MCP command)
async function listGobblerTabs(params = {}) {
  const stored = await chrome.storage.local.get('gobblerGroupId');
  if (!stored.gobblerGroupId) {
    return { success: true, tabs: [], message: 'No Gobbler group exists yet' };
  }

  let tabs = await chrome.tabs.query({ groupId: stored.gobblerGroupId });

  // Apply filter if specified - match against registered API patterns
  if (params.filter) {
    const filterLower = params.filter.toLowerCase();
    
    // Define URL patterns for each filter type
    const filterPatterns = {
      'notebooklm': (url) => url && url.includes('notebooklm.google.com'),
      'claude': (url) => url && url.includes('claude.ai'),
      'chatgpt': (url) => url && (url.includes('chatgpt.com') || url.includes('chat.openai.com')),
      'gemini': (url) => url && url.includes('gemini.google.com')
    };
    
    const matchFn = filterPatterns[filterLower];
    if (matchFn) {
      tabs = tabs.filter(t => matchFn(t.url));
    }
  }

  const tabList = tabs.map(t => ({
    tabId: t.id,
    title: t.title || 'Untitled',
    url: t.url,
    isActive: t.active
  }));

  return { success: true, tabs: tabList };
}

// Get information about injected APIs (for MCP command)
async function getInjectedApis(params = {}) {
  const stored = await chrome.storage.local.get('gobblerGroupId');
  if (!stored.gobblerGroupId) {
    return { success: true, tabs: [], message: 'No Gobbler group exists yet' };
  }

  const tabs = await chrome.tabs.query({ groupId: stored.gobblerGroupId });
  const result = [];

  for (const tab of tabs) {
    const injection = injectedTabs.get(tab.id);
    const matchingApi = findMatchingApi(tab.url);

    result.push({
      tabId: tab.id,
      title: tab.title || 'Untitled',
      url: tab.url,
      isActive: tab.active,
      injectedApi: injection?.apiName || null,
      injectedAt: injection?.timestamp || null,
      availableApi: matchingApi?.name || null,
      hasMatchingApi: !!matchingApi
    });
  }

  return {
    success: true,
    tabs: result,
    registeredApis: PAGE_API_REGISTRY.filter(a => a.enabled).map(a => ({
      name: a.name,
      pattern: a.pattern.toString()
    }))
  };
}

// Manually inject API into a tab (for MCP command)
async function manuallyInjectApi(params) {
  const { tabId } = params;

  if (!tabId) {
    return { success: false, error: 'tabId is required' };
  }

  // Security check: Verify tab is in Gobbler group
  const isInGroup = await isTabInGobblerGroup(tabId);
  if (!isInGroup) {
    return {
      success: false,
      error: `Tab ${tabId} is not in Gobbler group. Add it first via extension popup or right-click menu.`
    };
  }

  const tab = await chrome.tabs.get(tabId);
  const apiEntry = findMatchingApi(tab.url);

  if (!apiEntry) {
    return {
      success: false,
      error: `No registered API matches URL: ${tab.url}`,
      registeredApis: PAGE_API_REGISTRY.filter(a => a.enabled).map(a => a.name)
    };
  }

  // Force re-injection by clearing the tracking
  injectedTabs.delete(tabId);
  return await injectPageApi(tabId, apiEntry);
}

// Execute script in a specific tab (must be in Gobbler group)
async function executeScriptInTab(params) {
  const { tabId, script } = params;

  if (!tabId) {
    return { success: false, error: 'tabId is required' };
  }

  if (!script) {
    return { success: false, error: 'script is required' };
  }

  // Security check: Verify tab is in Gobbler group
  const isInGroup = await isTabInGobblerGroup(tabId);
  if (!isInGroup) {
    return {
      success: false,
      error: `Tab ${tabId} is not in Gobbler group. Add it first via extension popup or right-click menu.`
    };
  }

  // Only attach debugger if we haven't already
  if (!debuggerAttachedTabs.has(tabId)) {
    try {
      await chrome.debugger.attach({ tabId: tabId }, '1.3');
      debuggerAttachedTabs.add(tabId);
    } catch (attachError) {
      // If attach fails due to another debugger, try to force detach and retry once
      if (attachError.message.includes('already attached')) {
        try {
          await chrome.debugger.detach({ tabId: tabId });
          await new Promise(resolve => setTimeout(resolve, 100));
          await chrome.debugger.attach({ tabId: tabId }, '1.3');
          debuggerAttachedTabs.add(tabId);
        } catch (retryError) {
          return { success: false, error: `Cannot attach debugger: ${retryError.message}` };
        }
      } else {
        return { success: false, error: `Cannot attach debugger: ${attachError.message}` };
      }
    }
  }

  // Use Chrome Debugger API to execute JavaScript - bypasses CSP
  try {
    const result = await chrome.debugger.sendCommand(
      { tabId: tabId },
      'Runtime.evaluate',
      {
        expression: script,
        returnByValue: true,
        awaitPromise: true
      }
    );

    if (result.exceptionDetails) {
      return {
        success: false,
        error: result.exceptionDetails.exception.description || 'Script execution error'
      };
    }

    return {
      success: true,
      result: result.result.value,
      tabId: tabId
    };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Get current tab's group status
async function getCurrentTabGroupStatus() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) {
    return { hasTab: false };
  }

  const stored = await chrome.storage.local.get('gobblerGroupId');
  const isInGroup = stored.gobblerGroupId && tab.groupId === stored.gobblerGroupId;
  const groupTabs = await getGobblerGroupTabs();

  // Check if this is a restricted URL
  const isRestricted = isRestrictedUrl(tab.url);

  // Check if we have permission for this origin
  let hasPermission = false;
  let originPattern = null;
  if (!isRestricted) {
    originPattern = getOriginPattern(tab.url);
    hasPermission = await hasPermissionForOrigin(originPattern);
  }

  return {
    hasTab: true,
    tabId: tab.id,
    tabTitle: tab.title,
    tabUrl: tab.url,
    isInGobblerGroup: isInGroup,
    groupExists: !!stored.gobblerGroupId,
    groupTabCount: groupTabs.length,
    groupTabs: groupTabs,
    isRestricted: isRestricted,
    hasPermission: hasPermission,
    origin: originPattern
  };
}

// WebSocket connection management
function connectWebSocket() {
  // Close existing connection if any (even if not fully open)
  if (ws) {
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      console.log('Closing existing WebSocket connection...');
      ws.close();
    }
    ws = null;
  }

  console.log('Connecting to Gobbler server via WebSocket...');
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log('WebSocket connected to Gobbler server');
    // Send registration message
    ws.send(JSON.stringify({
      type: 'register',
      extension_version: '0.2.0'
    }));

    // Clear reconnect interval if it exists
    if (reconnectInterval) {
      clearInterval(reconnectInterval);
      reconnectInterval = null;
    }

    // Send ping every 30 seconds to keep connection alive
    setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  };

  ws.onmessage = async (event) => {
    try {
      const message = JSON.parse(event.data);
      console.log('Received message from server:', message);

      if (message.type === 'command') {
        // Handle command from MCP server
        await handleCommand(message);
      } else if (message.type === 'registered') {
        console.log('Successfully registered with server:', message.server_version);
      } else if (message.type === 'pong') {
        // Pong response to keep-alive
        console.log('Received pong');
      }
    } catch (error) {
      console.error('Error processing message:', error);
    }
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  ws.onclose = async () => {
    console.log('WebSocket disconnected');

    // Detach all debuggers when connection is lost
    console.log(`Cleaning up ${debuggerAttachedTabs.size} debugger attachments...`);
    for (const tabId of debuggerAttachedTabs) {
      try {
        await chrome.debugger.detach({ tabId });
        console.log(`Debugger detached from tab ${tabId}`);
      } catch (error) {
        console.log(`Failed to detach debugger from tab ${tabId}:`, error.message);
      }
    }
    debuggerAttachedTabs.clear();

    // Try to reconnect after 5 seconds
    if (!reconnectInterval) {
      reconnectInterval = setInterval(() => {
        console.log('Attempting to reconnect...');
        connectWebSocket();
      }, 5000);
    }
  };
}

// Handle commands from MCP server
async function handleCommand(message) {
  const { command_id, command, params } = message;
  let result = { success: false, error: 'Unknown command' };

  try {
    switch (command) {
      case 'extract_page':
        result = await extractPage(params);
        break;

      case 'navigate':
        result = await navigateToUrl(params);
        break;

      case 'execute_script':
        result = await executeScript(params);
        break;

      case 'get_page_info':
        result = await getPageInfo(params);
        break;

      case 'list_gobbler_tabs':
        result = await listGobblerTabs(params);
        break;

      case 'execute_script_in_tab':
        result = await executeScriptInTab(params);
        break;

      case 'get_injected_apis':
        result = await getInjectedApis(params);
        break;

      case 'inject_api':
        result = await manuallyInjectApi(params);
        break;

      case 'open_tabs':
        result = await openTabs(params);
        break;

      default:
        result = { success: false, error: `Unknown command: ${command}` };
    }
  } catch (error) {
    result = { success: false, error: error.message };
  }

  // Send response back to server
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: 'command_response',
      command_id: command_id,
      result: result
    }));
  }
}

// Command handlers
async function extractPage(params) {
  try {
    // Access guard: Only allow extraction from tabs in Gobbler group
    const tab = await getActiveGobblerTab();

    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: (selector) => {
        const element = selector ? document.querySelector(selector) : document.documentElement;
        if (!element && selector) {
          throw new Error(`Selector "${selector}" not found on page`);
        }
        return {
          url: window.location.href,
          title: document.title,
          html: (element || document.documentElement).outerHTML,
          text: (element || document.body).innerText,
          selector: selector
        };
      },
      args: [params.selector || null]
    });

    const pageData = result.result;

    // Send to Gobbler server for conversion
    const response = await fetch('http://localhost:4625/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(pageData)
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const data = await response.json();
    return {
      success: true,
      markdown: data.markdown,
      metadata: data.metadata
    };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function navigateToUrl(params) {
  try {
    // Access guard: Only allow navigation in tabs in Gobbler group
    const tab = await getActiveGobblerTab();

    await chrome.tabs.update(tab.id, { url: params.url });

    if (params.wait_for_load) {
      // Wait for page to load
      await new Promise((resolve) => {
        const listener = (tabId, changeInfo) => {
          if (tabId === tab.id && changeInfo.status === 'complete') {
            chrome.tabs.onUpdated.removeListener(listener);
            resolve();
          }
        };
        chrome.tabs.onUpdated.addListener(listener);

        // Timeout after 30 seconds
        setTimeout(() => {
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }, 30000);
      });
    }

    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Open multiple URLs in new tabs within the Gobbler group
async function openTabs(params) {
  try {
    const { urls, activate_first = true } = params;
    
    if (!urls || !Array.isArray(urls) || urls.length === 0) {
      return { success: false, error: 'No URLs provided' };
    }

    // Get or create the Gobbler tab group
    const gobblerGroupId = await getOrCreateGobblerGroup();
    
    const openedTabs = [];
    
    for (let i = 0; i < urls.length; i++) {
      const url = urls[i];
      
      // Create the tab
      const tab = await chrome.tabs.create({
        url: url,
        active: activate_first && i === 0  // Only activate first tab if requested
      });
      
      // Add to Gobbler group
      await chrome.tabs.group({
        tabIds: [tab.id],
        groupId: gobblerGroupId
      });
      
      openedTabs.push({
        id: tab.id,
        url: url,
        title: tab.title || url
      });
    }
    
    return {
      success: true,
      tabs: openedTabs,
      count: openedTabs.length,
      group_id: gobblerGroupId
    };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Track which tabs have our debugger attached
const debuggerAttachedTabs = new Set();

async function executeScript(params) {
  try {
    // Access guard: Only allow script execution in tabs in Gobbler group
    const tab = await getActiveGobblerTab();

    // Only attach debugger if we haven't already
    if (!debuggerAttachedTabs.has(tab.id)) {
      try {
        await chrome.debugger.attach({ tabId: tab.id }, '1.3');
        debuggerAttachedTabs.add(tab.id);
      } catch (attachError) {
        // If attach fails due to another debugger, try to force detach and retry once
        if (attachError.message.includes('already attached')) {
          try {
            await chrome.debugger.detach({ tabId: tab.id });
            await new Promise(resolve => setTimeout(resolve, 100)); // Small delay
            await chrome.debugger.attach({ tabId: tab.id }, '1.3');
            debuggerAttachedTabs.add(tab.id);
          } catch (retryError) {
            return { success: false, error: `Cannot attach debugger: ${retryError.message}` };
          }
        } else {
          throw attachError;
        }
      }
    }

    // Use Chrome Debugger API to execute JavaScript - bypasses CSP
    const result = await chrome.debugger.sendCommand(
      { tabId: tab.id },
      'Runtime.evaluate',
      {
        expression: params.script,
        returnByValue: true,
        awaitPromise: true
      }
    );

    if (result.exceptionDetails) {
      return {
        success: false,
        error: result.exceptionDetails.exception.description || 'Script execution error'
      };
    }

    return {
      success: true,
      result: result.result.value
    };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Clean up debugger and injected APIs when tab is closed
chrome.tabs.onRemoved.addListener(async (tabId) => {
  // Clean up debugger
  if (debuggerAttachedTabs.has(tabId)) {
    try {
      await chrome.debugger.detach({ tabId });
      console.log(`Debugger detached from closed tab ${tabId}`);
    } catch (error) {
      // Ignore "tab not found" errors - Chrome already auto-detached the debugger
      if (!error.message.includes('No tab with given id')) {
        console.log(`Failed to detach debugger from tab ${tabId}:`, error.message);
      }
    }
    debuggerAttachedTabs.delete(tabId);
  }

  // Clean up injection tracking
  if (injectedTabs.has(tabId)) {
    injectedTabs.delete(tabId);
    console.log(`[Gobbler] Cleaned up injection tracking for closed tab ${tabId}`);
  }
});

// Re-inject APIs when tabs in Gobbler group navigate or refresh
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  // Only act when page load is complete
  if (changeInfo.status !== 'complete') return;

  // Check if tab is in Gobbler group
  const isInGroup = await isTabInGobblerGroup(tabId);
  if (!isInGroup) return;

  // Check if there's a matching API for this URL
  const apiEntry = findMatchingApi(tab.url);
  if (!apiEntry) {
    // URL no longer matches any API - clean up tracking
    if (injectedTabs.has(tabId)) {
      injectedTabs.delete(tabId);
      console.log(`[Gobbler] Tab ${tabId} no longer matches any API pattern`);
    }
    return;
  }

  // Actually check if API is already present in the page (not just in our tracking)
  // This handles SPAs where onUpdated fires without full page reloads
  try {
    // Use the injection marker from registry for dynamic multi-API support
    const markerName = apiEntry.injectionMarker || `__gobbler${apiEntry.name}Injected`;

    const results = await chrome.scripting.executeScript({
      target: { tabId },
      world: 'MAIN',
      func: (marker) => typeof window[marker] !== 'undefined',
      args: [markerName]
    });

    const alreadyInjected = results && results[0] && results[0].result === true;

    if (alreadyInjected) {
      // API still exists in page, update our tracking but don't re-inject
      if (!injectedTabs.has(tabId)) {
        injectedTabs.set(tabId, { apiName: apiEntry.name, timestamp: Date.now() });
      }
      return;
    }

    // API not in page - need to inject
    console.log(`[Gobbler] API not found in page, injecting ${apiEntry.name}...`);
    injectedTabs.delete(tabId);
    const result = await injectPageApi(tabId, apiEntry);
    if (result.success) {
      console.log(`[Gobbler] Injected ${apiEntry.name} API after page change`);
    }
  } catch (error) {
    console.error(`[Gobbler] Error checking/injecting API:`, error);
  }
});

// Listen for debugger detachment events (external detachment)
chrome.debugger.onDetach.addListener((source, reason) => {
  if (debuggerAttachedTabs.has(source.tabId)) {
    console.log(`Debugger externally detached from tab ${source.tabId}. Reason: ${reason}`);
    debuggerAttachedTabs.delete(source.tabId);
  }
});

async function getPageInfo(params) {
  try {
    // Access guard: Only allow page info from tabs in Gobbler group
    const tab = await getActiveGobblerTab();

    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        return {
          url: window.location.href,
          title: document.title,
          hostname: window.location.hostname,
          pathname: window.location.pathname,
          protocol: window.location.protocol,
          links_count: document.querySelectorAll('a').length,
          images_count: document.querySelectorAll('img').length,
          forms_count: document.querySelectorAll('form').length
        };
      }
    });

    return { success: true, info: result.result };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Context menu setup
function setupContextMenus() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: 'gobbler-add-tab',
      title: 'Add tab to Gobbler group',
      contexts: ['page', 'frame']
    });

    chrome.contextMenus.create({
      id: 'gobbler-remove-tab',
      title: 'Remove tab from Gobbler group',
      contexts: ['page', 'frame']
    });

    console.log('Context menus created');
  });
}

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'gobbler-add-tab') {
    try {
      const result = await addCurrentTabToGroup();
      console.log('Added tab via context menu:', result);
    } catch (error) {
      console.error('Failed to add tab:', error);
    }
  } else if (info.menuItemId === 'gobbler-remove-tab') {
    try {
      const result = await removeCurrentTabFromGroup();
      console.log('Removed tab via context menu:', result);
    } catch (error) {
      console.error('Failed to remove tab:', error);
    }
  }
});

// Initialize WebSocket connection on startup
chrome.runtime.onInstalled.addListener(() => {
  console.log('Gobbler extension installed');
  setupContextMenus();
  connectWebSocket();
});

chrome.runtime.onStartup.addListener(() => {
  console.log('Gobbler extension started');
  setupContextMenus();
  connectWebSocket();
});

// Connect immediately if service worker is running
setupContextMenus();
connectWebSocket();

// Handle messages from popup or content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extract') {
    // Forward extraction request
    sendResponse({ success: true });
  } else if (request.action === 'getConnectionStatus') {
    sendResponse({
      connected: ws && ws.readyState === WebSocket.OPEN
    });
  } else if (request.action === 'getGroupStatus') {
    // Get current tab's group status
    getCurrentTabGroupStatus().then(status => {
      sendResponse(status);
    }).catch(error => {
      sendResponse({ error: error.message });
    });
    return true; // Keep channel open for async response
  } else if (request.action === 'addToGroup') {
    // Add current tab to Gobbler group
    addCurrentTabToGroup().then(result => {
      sendResponse(result);
    }).catch(error => {
      sendResponse({ success: false, error: error.message });
    });
    return true;
  } else if (request.action === 'removeFromGroup') {
    // Remove current tab from Gobbler group
    removeCurrentTabFromGroup().then(result => {
      sendResponse(result);
    }).catch(error => {
      sendResponse({ success: false, error: error.message });
    });
    return true;
  } else if (request.action === 'getGroupTabs') {
    // Get all tabs in Gobbler group
    getGobblerGroupTabs().then(tabs => {
      sendResponse({ tabs });
    }).catch(error => {
      sendResponse({ error: error.message });
    });
    return true;
  } else if (request.action === 'injectApi') {
    // Inject API into a specific tab
    const { tabId, apiName } = request;
    if (!tabId) {
      sendResponse({ success: false, error: 'tabId is required' });
      return true;
    }

    // Find the API entry by name
    const apiEntry = PAGE_API_REGISTRY.find(a => a.name === apiName);
    if (!apiEntry) {
      sendResponse({ success: false, error: `Unknown API: ${apiName}` });
      return true;
    }

    // Verify tab is in Gobbler group
    isTabInGobblerGroup(tabId).then(isInGroup => {
      if (!isInGroup) {
        sendResponse({
          success: false,
          error: 'Tab is not in Gobbler group'
        });
        return;
      }

      // Force re-injection by clearing the tracking
      injectedTabs.delete(tabId);

      // Inject the API
      injectPageApi(tabId, apiEntry).then(result => {
        sendResponse(result);
      }).catch(error => {
        sendResponse({ success: false, error: error.message });
      });
    }).catch(error => {
      sendResponse({ success: false, error: error.message });
    });
    return true;
  }
  return true;
});
