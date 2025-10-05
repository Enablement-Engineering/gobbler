// Background service worker for Gobbler extension

let ws = null;
let reconnectInterval = null;
const WS_URL = 'ws://localhost:8080/ws';

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

  ws.onclose = () => {
    console.log('WebSocket disconnected');
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
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

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
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

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
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

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
chrome.tabs.onRemoved.addListener((tabId) => {
  if (debuggerAttachedTabs.has(tabId)) {
    debuggerAttachedTabs.delete(tabId);
  }
});

async function getPageInfo(params) {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

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

// Initialize WebSocket connection on startup
chrome.runtime.onInstalled.addListener(() => {
  console.log('Gobbler extension installed');
  connectWebSocket();
});

chrome.runtime.onStartup.addListener(() => {
  console.log('Gobbler extension started');
  connectWebSocket();
});

// Connect immediately if service worker is running
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
  }
  return true;
});
