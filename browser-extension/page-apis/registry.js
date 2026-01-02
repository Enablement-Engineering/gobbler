// Page-Specific API Registry
// Single source of truth for all page API definitions
// Used by: background.js (via importScripts), popup.js (via script tag)

/**
 * Registry of page-specific APIs
 *
 * Each entry contains:
 * - name: Human-readable name for logging and UI
 * - pattern: RegExp to match against URL
 * - apiFile: Path to API script (relative to extension root for background.js)
 * - enabled: Whether this API is active
 * - injectionMarker: Window property set when API is injected (for re-injection detection)
 * - domain: Display domain for popup UI
 * - description: Human-readable description
 * - globalVar: The window property name where API is exposed
 * - methods: Key methods available in the API
 */
const PAGE_API_REGISTRY = [
  {
    name: 'NotebookLM',
    pattern: /^https:\/\/notebooklm\.google\.com/,
    apiFile: 'page-apis/notebooklm.js',
    enabled: true,
    injectionMarker: '__gobblerNotebookLMInjected',
    // UI metadata
    domain: 'notebooklm.google.com',
    description: 'Interact with NotebookLM notebooks',
    globalVar: 'window.gobblerNotebookLM',
    methods: ['ask', 'sendMessage', 'getSources', 'getChatContent']
  },
  {
    name: 'Claude',
    pattern: /^https:\/\/claude\.ai/,
    apiFile: 'page-apis/claude.js',
    enabled: true,
    injectionMarker: '__gobblerClaudeInjected',
    // UI metadata
    domain: 'claude.ai',
    description: 'Interact with Claude.ai conversations',
    globalVar: 'window.gobblerClaude',
    methods: ['ask', 'sendMessage', 'getChatContent', 'getLastResponse']
  },
  {
    name: 'ChatGPT',
    pattern: /^https:\/\/(chat\.openai\.com|chatgpt\.com)/,
    apiFile: 'page-apis/chatgpt.js',
    enabled: true,
    injectionMarker: '__gobblerChatGPTInjected',
    // UI metadata
    domain: 'chatgpt.com',
    description: 'Interact with ChatGPT conversations',
    globalVar: 'window.gobblerChatGPT',
    methods: ['ask', 'sendMessage', 'getChatContent', 'getLastResponse']
  },
  {
    name: 'Gemini',
    pattern: /^https:\/\/gemini\.google\.com/,
    apiFile: 'page-apis/gemini.js',
    enabled: true,
    injectionMarker: '__gobblerGeminiInjected',
    // UI metadata
    domain: 'gemini.google.com',
    description: 'Interact with Google Gemini conversations',
    globalVar: 'window.gobblerGemini',
    methods: ['ask', 'sendMessage', 'getChatContent', 'getLastResponse']
  },
  // Future APIs can be added here:
  // {
  //   name: 'YouTube',
  //   pattern: /^https:\/\/(www\.)?youtube\.com/,
  //   apiFile: 'page-apis/youtube.js',
  //   enabled: false,
  //   injectionMarker: '__gobblerYouTubeInjected',
  //   domain: 'youtube.com',
  //   description: 'Control YouTube player and get video info',
  //   globalVar: 'window.gobblerYouTube',
  //   methods: ['getVideoInfo', 'getTranscript']
  // },
];

/**
 * Find matching API for a URL
 * @param {string} url - The page URL to check
 * @returns {object|null} - The matching registry entry or null
 */
function findMatchingApi(url) {
  if (!url) return null;

  for (const entry of PAGE_API_REGISTRY) {
    if (!entry.enabled) continue;

    if (entry.pattern instanceof RegExp) {
      if (entry.pattern.test(url)) {
        return entry;
      }
    } else if (typeof entry.pattern === 'string') {
      if (url.startsWith(entry.pattern)) {
        return entry;
      }
    }
  }

  return null;
}

/**
 * Get all enabled APIs
 * @returns {object[]} - Array of enabled registry entries
 */
function getEnabledApis() {
  return PAGE_API_REGISTRY.filter(entry => entry.enabled);
}

// Export for different contexts:
// - Service worker: uses importScripts(), reads from global scope
// - ES modules: uses export
// - Script tag in popup.html: reads from global scope
if (typeof globalThis !== 'undefined') {
  globalThis.PAGE_API_REGISTRY = PAGE_API_REGISTRY;
  globalThis.findMatchingApi = findMatchingApi;
  globalThis.getEnabledApis = getEnabledApis;
}

// ES module exports (for future use when Chrome fully supports ES modules in service workers)
if (typeof exports !== 'undefined') {
  exports.PAGE_API_REGISTRY = PAGE_API_REGISTRY;
  exports.findMatchingApi = findMatchingApi;
  exports.getEnabledApis = getEnabledApis;
}
