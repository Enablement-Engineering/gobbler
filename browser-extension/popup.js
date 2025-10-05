// Popup script for Gobbler extension

const statusEl = document.getElementById('status');
const wsStatusEl = document.getElementById('wsStatus');
const outputEl = document.getElementById('output');
const actionsEl = document.getElementById('actions');
const extractBtn = document.getElementById('extractBtn');
const extractWithSelectorBtn = document.getElementById('extractWithSelector');
const copyBtn = document.getElementById('copyBtn');
const sendToClaudeBtn = document.getElementById('sendToClaudeBtn');
const serverUrlInput = document.getElementById('serverUrl');

let currentMarkdown = '';

// Load saved server URL
chrome.storage.sync.get(['serverUrl'], (result) => {
  if (result.serverUrl) {
    serverUrlInput.value = result.serverUrl;
  }
});

// Save server URL on change
serverUrlInput.addEventListener('change', () => {
  chrome.storage.sync.set({ serverUrl: serverUrlInput.value });
});

// Check WebSocket connection status
function updateConnectionStatus() {
  chrome.runtime.sendMessage({ action: 'getConnectionStatus' }, (response) => {
    if (response && response.connected) {
      wsStatusEl.textContent = '🟢 Connected to Gobbler MCP';
      wsStatusEl.className = 'ws-status connected';
    } else {
      wsStatusEl.textContent = '🔴 Not connected to Gobbler MCP';
      wsStatusEl.className = 'ws-status disconnected';
    }
  });
}

// Update status on load and every 5 seconds
updateConnectionStatus();
setInterval(updateConnectionStatus, 5000);

function showStatus(message, type = 'info') {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
}

function showOutput(markdown) {
  currentMarkdown = markdown;
  outputEl.textContent = markdown;
  outputEl.classList.add('visible');
  actionsEl.style.display = 'flex';
}

function hideOutput() {
  outputEl.classList.remove('visible');
  actionsEl.style.display = 'none';
}

async function getCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function extractPage() {
  try {
    extractBtn.disabled = true;
    hideOutput();
    showStatus('Extracting page content...', 'info');

    const tab = await getCurrentTab();

    // Inject content script to extract page data
    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        return {
          url: window.location.href,
          title: document.title,
          html: document.documentElement.outerHTML,
          text: document.body.innerText
        };
      }
    });

    const pageData = result.result;

    showStatus('Sending to Gobbler server...', 'info');

    // Send to Gobbler server
    const serverUrl = serverUrlInput.value;
    const response = await fetch(`${serverUrl}/extract`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(pageData)
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();

    showStatus('✓ Page extracted successfully!', 'success');
    showOutput(data.markdown);

  } catch (error) {
    console.error('Extract error:', error);
    showStatus(`Error: ${error.message}`, 'error');
  } finally {
    extractBtn.disabled = false;
  }
}

async function extractWithSelector() {
  try {
    extractWithSelectorBtn.disabled = true;
    hideOutput();

    const selector = prompt('Enter CSS selector (e.g., article, .main-content, #post):');
    if (!selector) {
      extractWithSelectorBtn.disabled = false;
      return;
    }

    showStatus('Extracting with selector...', 'info');

    const tab = await getCurrentTab();

    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: (sel) => {
        const element = document.querySelector(sel);
        if (!element) {
          throw new Error(`Selector "${sel}" not found on page`);
        }
        return {
          url: window.location.href,
          title: document.title,
          html: element.outerHTML,
          text: element.innerText,
          selector: sel
        };
      },
      args: [selector]
    });

    const pageData = result.result;

    showStatus('Sending to Gobbler server...', 'info');

    const serverUrl = serverUrlInput.value;
    const response = await fetch(`${serverUrl}/extract`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(pageData)
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();

    showStatus('✓ Content extracted successfully!', 'success');
    showOutput(data.markdown);

  } catch (error) {
    console.error('Extract error:', error);
    showStatus(`Error: ${error.message}`, 'error');
  } finally {
    extractWithSelectorBtn.disabled = false;
  }
}

function copyToClipboard() {
  navigator.clipboard.writeText(currentMarkdown)
    .then(() => {
      showStatus('✓ Copied to clipboard!', 'success');
    })
    .catch((error) => {
      showStatus(`Copy failed: ${error.message}`, 'error');
    });
}

function sendToClaude() {
  // TODO: Implement sending to Claude Code
  // This could use Claude Code's API or copy to a special format
  showStatus('Send to Claude - Coming soon!', 'info');
}

// Event listeners
extractBtn.addEventListener('click', extractPage);
extractWithSelectorBtn.addEventListener('click', extractWithSelector);
copyBtn.addEventListener('click', copyToClipboard);
sendToClaudeBtn.addEventListener('click', sendToClaude);
