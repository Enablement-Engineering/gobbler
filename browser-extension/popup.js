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
const groupStatusText = document.getElementById('groupStatusText');
const groupBtn = document.getElementById('groupBtn');
const tabCountEl = document.getElementById('tabCount');
const tabListEl = document.getElementById('tabList');
const notInGroupWarning = document.getElementById('notInGroupWarning');

let currentMarkdown = '';
let isInGroup = false;

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

// Update group status
function updateGroupStatus() {
  chrome.runtime.sendMessage({ action: 'getGroupStatus' }, (response) => {
    if (response && response.hasTab) {
      isInGroup = response.isInGobblerGroup;

      // Handle restricted URLs (chrome://, edge://, etc.)
      if (response.isRestricted) {
        groupStatusText.textContent = '🚫 Browser page (restricted)';
        groupStatusText.className = 'group-status-text not-in-group';
        groupBtn.textContent = 'N/A';
        groupBtn.className = 'group-btn add';
        groupBtn.disabled = true;
        notInGroupWarning.textContent = '⚠️ Cannot access browser internal pages (chrome://, edge://, about:)';
        notInGroupWarning.classList.add('visible');
        extractBtn.disabled = true;
        extractWithSelectorBtn.disabled = true;
      } else if (response.isInGobblerGroup) {
        groupStatusText.textContent = '🦃 Tab in Gobbler group';
        groupStatusText.className = 'group-status-text in-group';
        groupBtn.textContent = 'Remove';
        groupBtn.className = 'group-btn remove';
        groupBtn.disabled = false;
        notInGroupWarning.classList.remove('visible');
        extractBtn.disabled = false;
        extractWithSelectorBtn.disabled = false;
      } else {
        // Not in group - show permission status
        const origin = response.origin ? new URL(response.origin.replace('/*', '')).host : 'this site';
        if (response.hasPermission) {
          groupStatusText.textContent = '⚪ Tab not in group';
        } else {
          groupStatusText.textContent = '🔒 Permission needed';
        }
        groupStatusText.className = 'group-status-text not-in-group';
        groupBtn.textContent = response.hasPermission ? 'Add Tab' : '🔓 Allow & Add';
        groupBtn.className = 'group-btn add';
        groupBtn.disabled = false;
        notInGroupWarning.textContent = response.hasPermission
          ? '⚠️ Current tab is not in Gobbler group. Add it to enable extraction.'
          : `🔒 Click "Allow & Add" to grant access to ${origin}`;
        notInGroupWarning.classList.add('visible');
        extractBtn.disabled = true;
        extractWithSelectorBtn.disabled = true;
      }

      // Show tab count and list
      if (response.groupTabCount > 0) {
        tabCountEl.textContent = `${response.groupTabCount} tab${response.groupTabCount > 1 ? 's' : ''} in group`;
        tabListEl.innerHTML = response.groupTabs
          .map(t => `<div class="tab-list-item${t.active ? ' active' : ''}" title="${t.url}">${t.title || 'Untitled'}</div>`)
          .join('');
      } else {
        tabCountEl.textContent = 'No tabs in group yet';
        tabListEl.innerHTML = '';
      }
    } else {
      groupStatusText.textContent = 'No tab detected';
      groupBtn.disabled = true;
      tabCountEl.textContent = '';
      tabListEl.innerHTML = '';
    }
  });
}

// Handle group button click
groupBtn.addEventListener('click', async () => {
  groupBtn.disabled = true;

  if (isInGroup) {
    // Remove from group
    chrome.runtime.sendMessage({ action: 'removeFromGroup' }, (response) => {
      if (response && response.success) {
        updateGroupStatus();
      }
      groupBtn.disabled = false;
    });
  } else {
    // Add to group (will request permission if needed)
    chrome.runtime.sendMessage({ action: 'addToGroup' }, (response) => {
      if (response && response.success) {
        showStatus(`✓ Added to Gobbler group`, 'success');
        updateGroupStatus();
      } else if (response && response.error) {
        if (response.permissionDenied) {
          showStatus('Permission denied. Click "Allow" when prompted.', 'error');
        } else {
          showStatus(`Error: ${response.error}`, 'error');
        }
      }
      groupBtn.disabled = false;
    });
  }
});

// Update status on load and every 2 seconds
updateConnectionStatus();
updateGroupStatus();
setInterval(updateConnectionStatus, 5000);
setInterval(updateGroupStatus, 2000);

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
