// Background service worker for Gobbler extension

let ws = null;
let reconnectInterval = null;
const WS_URL = 'ws://localhost:8080/ws';

// Tab group management
const GOBBLER_GROUP_COLOR = 'orange';
const GOBBLER_GROUP_TITLE = 'Gobbler';

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

// Add current tab to Gobbler group
async function addCurrentTabToGroup() {
  const groupId = await getOrCreateGobblerGroup();
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (tab.groupId === groupId) {
    return { success: true, alreadyInGroup: true, tabId: tab.id };
  }

  await chrome.tabs.group({ tabIds: [tab.id], groupId });
  console.log(`Added tab ${tab.id} to Gobbler group`);
  return { success: true, alreadyInGroup: false, tabId: tab.id };
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

  // Apply filter if specified
  if (params.filter === 'notebooklm') {
    tabs = tabs.filter(t => t.url && t.url.includes('notebooklm.google.com'));
  }

  const tabList = tabs.map(t => ({
    tabId: t.id,
    title: t.title || 'Untitled',
    url: t.url,
    isActive: t.active
  }));

  return { success: true, tabs: tabList };
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

  return {
    hasTab: true,
    tabId: tab.id,
    tabTitle: tab.title,
    isInGobblerGroup: isInGroup,
    groupExists: !!stored.gobblerGroupId,
    groupTabCount: groupTabs.length,
    groupTabs: groupTabs
  };
}

// WebSocket connection management
function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    return;
  }

  console.log('Connecting to Gobbler server via WebSocket...');
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log('WebSocket connected to Gobbler server');
    // Send registration message
    ws.send(JSON.stringify({
      type: 'register',
      extension_version: '0.1.0'
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
    const response = await fetch('http://localhost:8080/extract', {
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

// Clean up debugger when tab is closed
chrome.tabs.onRemoved.addListener(async (tabId) => {
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
  }
  return true;
});
