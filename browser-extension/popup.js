// Popup script for Gobbler extension

// Element references
const connectionBadge = document.getElementById('connectionBadge');
const connectionText = document.getElementById('connectionText');
const tabList = document.getElementById('tabList');
const emptyTabList = document.getElementById('emptyTabList');
const tabCount = document.getElementById('tabCount');
const groupStatusIndicator = document.getElementById('groupStatusIndicator');
const groupStatusIcon = document.getElementById('groupStatusIcon');
const groupStatusText = document.getElementById('groupStatusText');
const groupBtn = document.getElementById('groupBtn');
const warningBanner = document.getElementById('warningBanner');
const warningText = document.getElementById('warningText');
const statusMessage = document.getElementById('statusMessage');
const statusIcon = document.getElementById('statusIcon');
const statusText = document.getElementById('statusText');
const resultCard = document.getElementById('resultCard');
const resultTitle = document.getElementById('resultTitle');
const resultPreview = document.getElementById('resultPreview');
const wordCountValue = document.getElementById('wordCountValue');
const extractBtn = document.getElementById('extractBtn');
const extractWithSelectorBtn = document.getElementById('extractWithSelector');
const copyBtn = document.getElementById('copyBtn');
const sendToClaudeBtn = document.getElementById('sendToClaudeBtn');
const settingsToggle = document.getElementById('settingsToggle');
const settingsContent = document.getElementById('settingsContent');
const serverUrlInput = document.getElementById('serverUrl');
const serverStatus = document.getElementById('serverStatus');

// API Injection elements
const apiSection = document.getElementById('apiSection');
const apiSelectContainer = document.getElementById('apiSelectContainer');
const apiSelect = document.getElementById('apiSelect');
const apiInjectBtn = document.getElementById('apiInjectBtn');
const apiInfo = document.getElementById('apiInfo');
const noApiMatch = document.getElementById('noApiMatch');

// API registry is loaded from page-apis/registry.js via script tag in popup.html
// This provides a single source of truth for all API definitions
// PAGE_API_REGISTRY is available as a global variable

let currentMarkdown = '';
let isInGroup = false;
let currentPageTitle = '';
let currentTabUrl = '';

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

// Settings toggle
settingsToggle.addEventListener('click', () => {
  const isExpanded = settingsToggle.getAttribute('aria-expanded') === 'true';
  settingsToggle.setAttribute('aria-expanded', !isExpanded);
  settingsContent.classList.toggle('visible', !isExpanded);
});

// Check WebSocket connection status
function updateConnectionStatus() {
  chrome.runtime.sendMessage({ action: 'getConnectionStatus' }, (response) => {
    if (response && response.connected) {
      connectionText.textContent = 'Connected';
      connectionBadge.className = 'connection-badge connected';
      serverStatus.style.display = 'inline-flex';
    } else {
      connectionText.textContent = 'Disconnected';
      connectionBadge.className = 'connection-badge disconnected';
      serverStatus.style.display = 'none';
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
        groupStatusIcon.textContent = '🚫';
        groupStatusText.textContent = 'Browser page (restricted)';
        groupStatusIndicator.className = 'group-status-indicator restricted';
        groupBtn.textContent = 'N/A';
        groupBtn.className = 'group-toggle-btn add';
        groupBtn.disabled = true;
        warningText.textContent = 'Cannot access browser internal pages (chrome://, edge://, about:)';
        warningBanner.classList.add('visible');
        extractBtn.disabled = true;
        extractWithSelectorBtn.disabled = true;
      } else if (response.isInGobblerGroup) {
        groupStatusIcon.textContent = '🦃';
        groupStatusText.textContent = 'In Gobbler group';
        groupStatusIndicator.className = 'group-status-indicator in-group';
        groupBtn.textContent = 'Remove';
        groupBtn.className = 'group-toggle-btn remove';
        groupBtn.disabled = false;
        warningBanner.classList.remove('visible');
        extractBtn.disabled = false;
        extractWithSelectorBtn.disabled = false;
      } else {
        // Not in group - show permission status
        const origin = response.origin ? new URL(response.origin.replace('/*', '')).host : 'this site';
        if (response.hasPermission) {
          groupStatusIcon.textContent = '⚪';
          groupStatusText.textContent = 'Not in group';
        } else {
          groupStatusIcon.textContent = '🔒';
          groupStatusText.textContent = 'Permission needed';
        }
        groupStatusIndicator.className = 'group-status-indicator not-in-group';
        groupBtn.textContent = response.hasPermission ? 'Add Tab' : 'Allow & Add';
        groupBtn.className = 'group-toggle-btn add';
        groupBtn.disabled = false;
        warningText.textContent = response.hasPermission
          ? 'Add this tab to the Gobbler group to enable extraction.'
          : `Grant access to ${origin} to use Gobbler.`;
        warningBanner.classList.add('visible');
        extractBtn.disabled = true;
        extractWithSelectorBtn.disabled = true;
      }

      // Show tab count and list
      if (response.groupTabCount > 0) {
        tabCount.textContent = `${response.groupTabCount} tab${response.groupTabCount > 1 ? 's' : ''}`;
        emptyTabList.style.display = 'none';
        tabList.innerHTML = response.groupTabs
          .map(t => {
            const icon = getTabIcon(t.url, t.title);
            const apiName = hasApiForUrl(t.url);
            const apiBadge = apiName ? `<span class="api-badge" title="${apiName} API available">API</span>` : '';
            return `<li class="tab-item${t.active ? '" aria-current="true' : ''}" title="${escapeHtml(t.url)}">
              <span class="tab-icon" aria-hidden="true">${icon}</span>
              <span class="tab-title">${escapeHtml(t.title || 'Untitled')}</span>
              ${apiBadge}
            </li>`;
          })
          .join('');
      } else {
        tabCount.textContent = '';
        emptyTabList.style.display = 'block';
        tabList.innerHTML = '';
      }

      // Update API section
      updateApiSection(response.tabUrl, response.tabId, response.isInGobblerGroup);
    } else {
      groupStatusIcon.textContent = '❓';
      groupStatusText.textContent = 'No tab detected';
      groupBtn.disabled = true;
      tabCount.textContent = '';
      tabList.innerHTML = '';
      emptyTabList.style.display = 'block';
      apiSection.classList.add('hidden');
    }
  });
}

// Get appropriate icon for tab based on URL/title
function getTabIcon(url, title) {
  const lowerUrl = (url || '').toLowerCase();
  const lowerTitle = (title || '').toLowerCase();

  if (lowerUrl.includes('notebooklm') || lowerTitle.includes('notebooklm')) {
    return '📓';
  } else if (lowerUrl.includes('github')) {
    return '🐙';
  } else if (lowerUrl.includes('youtube')) {
    return '📺';
  } else if (lowerUrl.includes('docs.') || lowerTitle.includes('documentation')) {
    return '📚';
  } else if (lowerTitle.includes('claude') || lowerUrl.includes('claude')) {
    return '🤖';
  }
  return '📄';
}

// Check if URL has an API available (returns API name or null)
function hasApiForUrl(url) {
  if (!url) return null;
  for (const api of PAGE_API_REGISTRY) {
    if (api.pattern.test(url)) {
      return api.name;
    }
  }
  return null;
}

// Get all APIs that match the given URL
function getMatchingApis(url) {
  if (!url) return [];
  return PAGE_API_REGISTRY.filter(api => api.pattern.test(url));
}

// Get all available APIs (for showing all options)
function getAllApis() {
  return PAGE_API_REGISTRY;
}

// Update the API section based on current tab
function updateApiSection(tabUrl, tabId, isInGobblerGroup) {
  // Only show API section if tab is in group
  if (!isInGobblerGroup) {
    apiSection.classList.add('hidden');
    return;
  }

  apiSection.classList.remove('hidden');

  // Skip rebuild if URL hasn't changed
  if (tabUrl === currentTabUrl) {
    return;
  }

  currentTabUrl = tabUrl;

  // Get matching APIs for this URL
  const matchingApis = getMatchingApis(tabUrl);
  const allApis = getAllApis();

  // Preserve current selection if possible
  const previousSelection = apiSelect.value;

  // Clear and populate select
  apiSelect.innerHTML = '<option value="">Select an API...</option>';

  if (matchingApis.length > 0) {
    // Add matching APIs first (highlighted)
    const matchGroup = document.createElement('optgroup');
    matchGroup.label = '✓ Available for this page';
    matchingApis.forEach(api => {
      const option = document.createElement('option');
      option.value = api.name;
      option.textContent = `${api.name}`;
      option.dataset.domain = api.domain;
      option.dataset.description = api.description;
      option.dataset.globalVar = api.globalVar;
      option.dataset.methods = api.methods.join(', ');
      matchGroup.appendChild(option);
    });
    apiSelect.appendChild(matchGroup);

    // Add other APIs (grayed out / different group)
    const otherApis = allApis.filter(api => !matchingApis.includes(api));
    if (otherApis.length > 0) {
      const otherGroup = document.createElement('optgroup');
      otherGroup.label = '○ Other APIs';
      otherApis.forEach(api => {
        const option = document.createElement('option');
        option.value = api.name;
        option.textContent = `${api.name} (${api.domain})`;
        option.dataset.domain = api.domain;
        option.dataset.description = api.description;
        option.dataset.globalVar = api.globalVar;
        option.dataset.methods = api.methods.join(', ');
        option.disabled = true; // Can't inject non-matching APIs
        otherGroup.appendChild(option);
      });
      apiSelect.appendChild(otherGroup);
    }

    apiSelectContainer.style.display = 'block';
    noApiMatch.style.display = 'none';

    // Restore previous selection if still valid, otherwise auto-select if only one
    const canRestorePrevious = previousSelection && matchingApis.some(api => api.name === previousSelection);
    if (canRestorePrevious) {
      apiSelect.value = previousSelection;
      updateApiInfo(matchingApis.find(api => api.name === previousSelection));
      apiInjectBtn.disabled = false;
    } else if (matchingApis.length === 1) {
      apiSelect.value = matchingApis[0].name;
      updateApiInfo(matchingApis[0]);
      apiInjectBtn.disabled = false;
    }
  } else if (allApis.length > 0) {
    // No matching APIs, show all as disabled
    const otherGroup = document.createElement('optgroup');
    otherGroup.label = '○ No match for this domain';
    allApis.forEach(api => {
      const option = document.createElement('option');
      option.value = api.name;
      option.textContent = `${api.name} (${api.domain})`;
      option.disabled = true;
      otherGroup.appendChild(option);
    });
    apiSelect.appendChild(otherGroup);

    apiSelectContainer.style.display = 'block';
    noApiMatch.style.display = 'none';
    apiInfo.innerHTML = '<span style="color: var(--warning-amber);">No APIs match this domain.</span>';
  } else {
    apiSelectContainer.style.display = 'none';
    noApiMatch.style.display = 'block';
  }
}

// Update the API info text when selection changes
function updateApiInfo(api) {
  if (!api) {
    apiInfo.innerHTML = '';
    return;
  }
  apiInfo.innerHTML = `
    ${api.description}<br>
    <code>${api.globalVar}</code> → ${api.methods.slice(0, 3).join(', ')}${api.methods.length > 3 ? '...' : ''}
  `;
}

// Handle API select change
apiSelect.addEventListener('change', () => {
  const selectedName = apiSelect.value;
  const selectedApi = PAGE_API_REGISTRY.find(api => api.name === selectedName);

  if (selectedApi) {
    updateApiInfo(selectedApi);
    apiInjectBtn.disabled = false;
  } else {
    apiInfo.innerHTML = '';
    apiInjectBtn.disabled = true;
  }
});

// Handle inject button click
apiInjectBtn.addEventListener('click', async () => {
  const selectedName = apiSelect.value;
  if (!selectedName) return;

  apiInjectBtn.disabled = true;
  apiInjectBtn.textContent = 'Injecting...';

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) {
      throw new Error('No active tab');
    }

    // Send message to background to inject API
    chrome.runtime.sendMessage({
      action: 'injectApi',
      tabId: tab.id,
      apiName: selectedName
    }, (response) => {
      if (response && response.success) {
        showStatus(`${selectedName} API injected! Use ${PAGE_API_REGISTRY.find(a => a.name === selectedName)?.globalVar} in console.`, 'success', '✓');
      } else {
        showStatus(`Failed: ${response?.error || 'Unknown error'}`, 'error', '✗');
      }
      apiInjectBtn.disabled = false;
      apiInjectBtn.textContent = 'Inject';
    });
  } catch (error) {
    showStatus(`Error: ${error.message}`, 'error', '✗');
    apiInjectBtn.disabled = false;
    apiInjectBtn.textContent = 'Inject';
  }
});

// Escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Helper to get origin pattern from URL (same logic as background.js)
function getOriginPattern(url) {
  try {
    const urlObj = new URL(url);
    return `${urlObj.protocol}//${urlObj.host}/*`;
  } catch {
    return null;
  }
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
    // First, get the current tab to determine if we need permission
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab || !tab.url) {
      showStatus('No active tab found', 'error', '✗');
      groupBtn.disabled = false;
      return;
    }

    const originPattern = getOriginPattern(tab.url);
    if (!originPattern) {
      showStatus('Could not determine site origin', 'error', '✗');
      groupBtn.disabled = false;
      return;
    }

    // Check if we already have permission
    let hasPermission = false;
    try {
      hasPermission = await chrome.permissions.contains({ origins: [originPattern] });
    } catch {
      hasPermission = false;
    }

    // Request permission in popup context (where user interaction is happening)
    // This is required for Chrome to show the permission prompt
    if (!hasPermission) {
      try {
        const granted = await chrome.permissions.request({ origins: [originPattern] });
        if (!granted) {
          showStatus('Permission denied. Please allow access to this site.', 'error', '✗');
          groupBtn.disabled = false;
          return;
        }
      } catch (err) {
        showStatus(`Permission error: ${err.message}`, 'error', '✗');
        groupBtn.disabled = false;
        return;
      }
    }

    // Now add to group (permission already granted)
    chrome.runtime.sendMessage({ action: 'addToGroup' }, (response) => {
      if (response && response.success) {
        showStatus('Added to Gobbler group', 'success', '✓');
        updateGroupStatus();
      } else if (response && response.error) {
        showStatus(`Error: ${response.error}`, 'error', '✗');
      }
      groupBtn.disabled = false;
    });
  }
});

// Update status on load and periodically
updateConnectionStatus();
updateGroupStatus();
setInterval(updateConnectionStatus, 5000);
setInterval(updateGroupStatus, 2000);

function showStatus(message, type = 'info', icon = 'ℹ') {
  statusIcon.textContent = icon;
  statusText.textContent = message;
  statusMessage.className = `status-message visible ${type}`;
}

function hideStatus() {
  statusMessage.classList.remove('visible');
}

function showResult(markdown, pageTitle) {
  currentMarkdown = markdown;
  currentPageTitle = pageTitle;

  // Count words (rough estimate)
  const wordCount = markdown.split(/\s+/).filter(w => w.length > 0).length;
  wordCountValue.textContent = `${wordCount.toLocaleString()} words`;

  // Set title
  resultTitle.textContent = pageTitle || 'Untitled Page';

  // Show preview (first ~500 chars of markdown)
  const preview = markdown.substring(0, 500) + (markdown.length > 500 ? '...' : '');
  resultPreview.textContent = preview;

  // Show the result card
  resultCard.classList.add('visible');
}

function hideResult() {
  resultCard.classList.remove('visible');
}

async function getCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function extractPage() {
  try {
    extractBtn.disabled = true;
    hideResult();
    hideStatus();
    showStatus('Extracting page content...', 'info', '⏳');

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

    showStatus('Sending to Gobbler server...', 'info', '⏳');

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

    hideStatus();
    showResult(data.markdown, pageData.title);

  } catch (error) {
    console.error('Extract error:', error);
    showStatus(`Error: ${error.message}`, 'error', '✗');
  } finally {
    extractBtn.disabled = false;
  }
}

async function extractWithSelector() {
  try {
    extractWithSelectorBtn.disabled = true;
    hideResult();
    hideStatus();

    const selector = prompt('Enter CSS selector (e.g., article, .main-content, #post):');
    if (!selector) {
      extractWithSelectorBtn.disabled = false;
      return;
    }

    showStatus('Extracting with selector...', 'info', '⏳');

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

    showStatus('Sending to Gobbler server...', 'info', '⏳');

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

    hideStatus();
    showResult(data.markdown, `${pageData.title} (${selector})`);

  } catch (error) {
    console.error('Extract error:', error);
    showStatus(`Error: ${error.message}`, 'error', '✗');
  } finally {
    extractWithSelectorBtn.disabled = false;
  }
}

function copyToClipboard() {
  navigator.clipboard.writeText(currentMarkdown)
    .then(() => {
      showStatus('Copied to clipboard!', 'success', '✓');
      // Auto-hide success message after 2 seconds
      setTimeout(() => {
        hideStatus();
      }, 2000);
    })
    .catch((error) => {
      showStatus(`Copy failed: ${error.message}`, 'error', '✗');
    });
}

function sendToClaude() {
  // Copy to clipboard and show message
  navigator.clipboard.writeText(currentMarkdown)
    .then(() => {
      showStatus('Copied! Paste in Claude to continue.', 'success', '✓');
      // Auto-hide after 3 seconds
      setTimeout(() => {
        hideStatus();
      }, 3000);
    })
    .catch((error) => {
      showStatus(`Copy failed: ${error.message}`, 'error', '✗');
    });
}

// Event listeners
extractBtn.addEventListener('click', extractPage);
extractWithSelectorBtn.addEventListener('click', extractWithSelector);
copyBtn.addEventListener('click', copyToClipboard);
sendToClaudeBtn.addEventListener('click', sendToClaude);

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  // Ctrl/Cmd + Enter to extract
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    if (!extractBtn.disabled) {
      extractPage();
    }
  }
  // Ctrl/Cmd + C when result is shown to copy
  if ((e.ctrlKey || e.metaKey) && e.key === 'c' && resultCard.classList.contains('visible')) {
    // Only if no text is selected
    if (!window.getSelection().toString()) {
      e.preventDefault();
      copyToClipboard();
    }
  }
  // Escape to close result card
  if (e.key === 'Escape' && resultCard.classList.contains('visible')) {
    hideResult();
  }
});
