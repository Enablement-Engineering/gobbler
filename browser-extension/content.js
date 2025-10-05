// Content script for Gobbler extension
// This runs in the context of web pages

// Listen for messages from popup or background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getPageContent') {
    sendResponse({
      url: window.location.href,
      title: document.title,
      html: document.documentElement.outerHTML,
      text: document.body.innerText
    });
  }
  return true;
});

console.log('Gobbler content script loaded');
