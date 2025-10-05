// This script gets injected into the page and executes arbitrary code
// It runs in the page context, not the extension context
(function() {
  // Listen for messages from content script
  window.addEventListener('message', function(event) {
    if (event.source !== window) return;
    if (event.data.type !== 'GOBBLER_EXECUTE') return;

    try {
      // Execute the code in the page context
      const result = (new Function(event.data.script))();

      // Send result back
      window.postMessage({
        type: 'GOBBLER_RESULT',
        id: event.data.id,
        success: true,
        result: result
      }, '*');
    } catch (e) {
      window.postMessage({
        type: 'GOBBLER_RESULT',
        id: event.data.id,
        success: false,
        error: e.message
      }, '*');
    }
  });

  // Signal that we're ready
  window.__GOBBLER_EXECUTOR_READY__ = true;
})();
