// NotebookLM Page-Specific API
// Injected automatically when a NotebookLM tab is added to the Gobbler group

(function() {
  'use strict';

  // Prevent double-injection
  if (window.__gobblerNotebookLMInjected) {
    console.log('[Gobbler] NotebookLM API already injected');
    return;
  }
  window.__gobblerNotebookLMInjected = true;

  // Helper: Wait for element with timeout
  function waitForElement(selector, timeout = 10000) {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(selector);
      if (existing) {
        resolve(existing);
        return;
      }

      const observer = new MutationObserver((mutations, obs) => {
        const element = document.querySelector(selector);
        if (element) {
          obs.disconnect();
          resolve(element);
        }
      });

      observer.observe(document.body, {
        childList: true,
        subtree: true
      });

      setTimeout(() => {
        observer.disconnect();
        reject(new Error(`Element "${selector}" not found within ${timeout}ms`));
      }, timeout);
    });
  }

  // Helper: Wait for multiple elements
  function waitForElements(selector, minCount = 1, timeout = 10000) {
    return new Promise((resolve, reject) => {
      const check = () => {
        const elements = document.querySelectorAll(selector);
        if (elements.length >= minCount) {
          return elements;
        }
        return null;
      };

      const existing = check();
      if (existing) {
        resolve(Array.from(existing));
        return;
      }

      const observer = new MutationObserver((mutations, obs) => {
        const elements = check();
        if (elements) {
          obs.disconnect();
          resolve(Array.from(elements));
        }
      });

      observer.observe(document.body, {
        childList: true,
        subtree: true
      });

      setTimeout(() => {
        observer.disconnect();
        const elements = document.querySelectorAll(selector);
        if (elements.length > 0) {
          resolve(Array.from(elements));
        } else {
          reject(new Error(`Elements "${selector}" not found within ${timeout}ms`));
        }
      }, timeout);
    });
  }

  // Helper: Simulate user typing
  function simulateTyping(element, text) {
    element.focus();
    element.value = text;
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // Helper: Click element with retry
  async function clickElement(selector, timeout = 5000) {
    const element = await waitForElement(selector, timeout);
    element.click();
    return element;
  }

  // Helper: Small delay
  function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // NotebookLM API object
  const NotebookLMAPI = {
    // API version
    version: '1.2.0',

    // Preferred method for sending questions and getting responses
    // Usage: const result = await window.gobblerNotebookLM.ask("What are the key themes?")
    // Returns: { success: true, response: "...", elapsed: 5432 }

    // Check if we're on a notebook page
    isNotebookPage() {
      return window.location.href.includes('/notebook/');
    },

    // Get current notebook info
    getNotebookInfo() {
      const title = document.querySelector('h1, [data-testid="notebook-title"]')?.textContent?.trim();
      const url = window.location.href;
      const notebookId = url.match(/\/notebook\/([^/?]+)/)?.[1] || null;

      return {
        title: title || 'Untitled Notebook',
        url,
        notebookId,
        isNotebook: this.isNotebookPage()
      };
    },

    // Get all sources in the notebook
    async getSources() {
      try {
        // Sources are typically in a sidebar or panel
        // These selectors may need adjustment based on NotebookLM's actual DOM
        const sourceElements = document.querySelectorAll('[data-source-id], .source-item, [role="listitem"]');
        const sources = [];

        sourceElements.forEach((el, index) => {
          const titleEl = el.querySelector('.source-title, h3, [data-testid="source-title"]');
          const title = titleEl?.textContent?.trim() || el.textContent?.trim()?.slice(0, 50) || `Source ${index + 1}`;
          const sourceId = el.getAttribute('data-source-id') || `source-${index}`;

          sources.push({
            id: sourceId,
            title,
            element: el
          });
        });

        return {
          success: true,
          sources: sources.map(s => ({ id: s.id, title: s.title })),
          count: sources.length
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    // Get the current chat/notes content
    async getChatContent() {
      try {
        // NotebookLM uses custom elements and specific class names:
        // - chat-message elements with class "individual-message"
        // - User messages: "from-user-message-card-content"
        // - Assistant messages: "to-user-message-card-content"
        // - Content in ".message-content" or ".message-text-content"
        const messageSelectors = [
          'chat-message.individual-message',
          '.chat-message-pair',
          '[data-message-id]',
          '.chat-message'
        ];

        let messages = [];
        for (const selector of messageSelectors) {
          messages = document.querySelectorAll(selector);
          if (messages.length > 0) break;
        }

        const content = [];

        messages.forEach((msg, index) => {
          // Determine role based on NotebookLM's class names
          const isUser = msg.querySelector('.from-user-message-card-content') !== null ||
                         msg.classList.contains('from-user') ||
                         msg.getAttribute('data-role') === 'user';
          const role = isUser ? 'user' : 'assistant';

          // Get text from message content area
          const contentEl = msg.querySelector('.message-content, .message-text-content');
          const text = (contentEl?.textContent || msg.textContent)?.trim() || '';

          if (text) {
            content.push({
              index,
              role,
              content: text.slice(0, 5000) // Limit content size
            });
          }
        });

        return {
          success: true,
          messages: content,
          count: content.length
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    // Send a message/query to NotebookLM
    async sendMessage(message) {
      try {
        // Find the chat input field
        // IMPORTANT: NotebookLM has multiple textareas - we need the chat input specifically
        // The chat input has class "query-box-input" and placeholder "Start typing..."
        // NOT the "Search the web for new sources" textarea which is for adding sources
        const inputSelectors = [
          // NotebookLM-specific selectors (highest priority)
          'textarea.query-box-input',
          'textarea[placeholder*="Start typing"]',
          'textarea[placeholder*="typing"]',
          // Generic fallbacks
          'textarea[placeholder*="Ask"]',
          'textarea[placeholder*="message"]',
          '[contenteditable="true"]'
        ];

        let input = null;
        for (const selector of inputSelectors) {
          input = document.querySelector(selector);
          if (input) break;
        }

        if (!input) {
          return { success: false, error: 'Could not find chat input field. Make sure you are on a NotebookLM notebook page.' };
        }

        // Type the message
        if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {
          simulateTyping(input, message);
        } else {
          // contenteditable
          input.focus();
          input.textContent = message;
          input.dispatchEvent(new Event('input', { bubbles: true }));
        }

        await delay(100);

        // Find and click send button
        // NotebookLM uses aria-label="Submit" not "Send"
        const sendSelectors = [
          'button[aria-label="Submit"]',
          'button[aria-label*="Submit"]',
          'button[aria-label*="Send"]',
          'button[aria-label*="send"]',
          'button[type="submit"]',
          'button.send-button'
        ];

        let sendButton = null;
        for (const selector of sendSelectors) {
          try {
            sendButton = document.querySelector(selector);
            if (sendButton && !sendButton.disabled) break;
            sendButton = null; // Reset if disabled
          } catch (e) {
            // Some selectors might not be supported
          }
        }

        // Fallback: look for button near input
        if (!sendButton) {
          const form = input.closest('form');
          if (form) {
            sendButton = form.querySelector('button[type="submit"], button:not([type="button"])');
          }
        }

        // Wait a bit for the button to become enabled after typing
        if (!sendButton || sendButton.disabled) {
          await delay(200);
          // Try again to find enabled submit button
          for (const selector of sendSelectors) {
            try {
              sendButton = document.querySelector(selector);
              if (sendButton && !sendButton.disabled) break;
              sendButton = null;
            } catch (e) {}
          }
        }

        if (!sendButton || sendButton.disabled) {
          // Try pressing Enter as last resort
          const enterEvent = new KeyboardEvent('keydown', {
            key: 'Enter',
            code: 'Enter',
            keyCode: 13,
            which: 13,
            bubbles: true
          });
          input.dispatchEvent(enterEvent);
          return { success: true, method: 'enter-key' };
        }

        sendButton.click();
        return { success: true, method: 'button-click' };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    // Wait for response to complete using MutationObserver
    // This is more efficient than polling - it watches for DOM changes
    async waitForResponse(timeout = 60000) {
      const startTime = Date.now();

      // NotebookLM-specific message selectors
      const messageSelector = 'chat-message.individual-message, .chat-message-pair, [data-message-id], .chat-message';
      const initialMessageCount = document.querySelectorAll(messageSelector).length;

      return new Promise((resolve) => {
        let lastContent = '';
        let stableCount = 0;
        let responseStarted = false;
        let checkInterval = null;
        let observer = null;

        const cleanup = () => {
          if (observer) observer.disconnect();
          if (checkInterval) clearInterval(checkInterval);
        };

        const getLatestResponse = () => {
          const messages = document.querySelectorAll(messageSelector);
          if (messages.length > initialMessageCount) {
            const lastMsg = messages[messages.length - 1];
            // Get content from the proper content container
            const contentEl = lastMsg.querySelector('.message-content, .message-text-content, .to-user-message-inner-content');
            return (contentEl?.textContent || lastMsg.textContent)?.trim() || '';
          }
          return null;
        };

        const isStreaming = () => {
          // Check for various loading/streaming indicators
          // NotebookLM-specific indicators
          const loadingIndicators = [
            '.loading',
            '[data-loading="true"]',
            '.typing-indicator',
            '.streaming',
            '[aria-busy="true"]',
            '.cursor-blink',
            '.thinking',
            '.generating',
            'mat-spinner',
            '.mat-progress-spinner'
          ];
          for (const selector of loadingIndicators) {
            if (document.querySelector(selector)) return true;
          }
          return false;
        };

        const checkCompletion = () => {
          const elapsed = Date.now() - startTime;
          if (elapsed > timeout) {
            cleanup();
            const finalContent = getLatestResponse();
            resolve({
              success: false,
              error: 'Timeout waiting for response',
              timedOut: true,
              partialResponse: finalContent,
              elapsed
            });
            return;
          }

          const currentContent = getLatestResponse();

          // Response hasn't started yet
          if (currentContent === null) {
            stableCount = 0;
            return;
          }

          responseStarted = true;

          // Check if content is stable (hasn't changed)
          if (currentContent === lastContent && currentContent.length > 0) {
            stableCount++;
            // Content stable for 3 checks (1.5 seconds) AND not streaming = complete
            if (stableCount >= 3 && !isStreaming()) {
              cleanup();
              resolve({
                success: true,
                response: currentContent,
                elapsed: Date.now() - startTime
              });
              return;
            }
          } else {
            stableCount = 0;
            lastContent = currentContent;
          }
        };

        // Use MutationObserver for efficient change detection
        observer = new MutationObserver((mutations) => {
          // Reset stable count on any DOM change in the chat area
          stableCount = 0;
        });

        // Find chat container and observe it
        // NotebookLM uses section.chat-panel
        const chatContainer = document.querySelector('section.chat-panel, [role="log"], .chat-container, .messages, main');
        if (chatContainer) {
          observer.observe(chatContainer, {
            childList: true,
            subtree: true,
            characterData: true
          });
        }

        // Check every 500ms for completion
        checkInterval = setInterval(checkCompletion, 500);

        // Initial check after 1 second
        setTimeout(checkCompletion, 1000);
      });
    },

    /**
     * Combined ask method - sends message and waits for complete response
     * This is the recommended method for Claude to use
     * @param {string} message - The message to send
     * @param {number} timeout - Max time to wait for response (default 90s)
     * @returns {Promise<{success: boolean, response?: string, error?: string, elapsed?: number}>}
     */
    async ask(message, timeout = 90000) {
      const startTime = Date.now();

      // Step 1: Send the message
      const sendResult = await this.sendMessage(message);
      if (!sendResult.success) {
        return {
          success: false,
          error: `Failed to send message: ${sendResult.error}`,
          elapsed: Date.now() - startTime
        };
      }

      // Step 2: Wait for the response
      const responseResult = await this.waitForResponse(timeout);

      return {
        ...responseResult,
        messageSentVia: sendResult.method,
        totalElapsed: Date.now() - startTime
      };
    },

    // Generate Audio Overview (if available)
    async generateAudioOverview() {
      try {
        // Look for Audio Overview button
        const audioButtons = document.querySelectorAll('button');
        let audioButton = null;

        for (const btn of audioButtons) {
          const text = btn.textContent?.toLowerCase() || '';
          const ariaLabel = btn.getAttribute('aria-label')?.toLowerCase() || '';
          if (text.includes('audio') || text.includes('overview') || ariaLabel.includes('audio')) {
            audioButton = btn;
            break;
          }
        }

        if (!audioButton) {
          return { success: false, error: 'Audio Overview button not found' };
        }

        audioButton.click();
        return { success: true, message: 'Audio Overview generation initiated' };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    // Get selected text from sources
    getSelectedText() {
      const selection = window.getSelection();
      if (selection && selection.toString().trim()) {
        return {
          success: true,
          text: selection.toString().trim(),
          rangeCount: selection.rangeCount
        };
      }
      return { success: false, error: 'No text selected' };
    },

    // Get page structure for debugging
    getPageStructure() {
      const structure = {
        title: document.title,
        url: window.location.href,
        mainContent: null,
        sidebar: null,
        chatArea: null,
        inputs: [],
        buttons: []
      };

      // Find main sections
      const main = document.querySelector('main, [role="main"], .main-content');
      if (main) {
        structure.mainContent = {
          tag: main.tagName,
          classes: main.className,
          childCount: main.children.length
        };
      }

      // Find sidebar
      const sidebar = document.querySelector('aside, [role="complementary"], .sidebar');
      if (sidebar) {
        structure.sidebar = {
          tag: sidebar.tagName,
          classes: sidebar.className
        };
      }

      // Find chat area
      // NotebookLM uses section.chat-panel
      const chat = document.querySelector('section.chat-panel, [role="log"], .chat-container, .messages');
      if (chat) {
        structure.chatArea = {
          tag: chat.tagName,
          classes: chat.className,
          messageCount: chat.querySelectorAll('chat-message.individual-message, .chat-message-pair, [data-message-id], .message').length
        };
      }

      // Find inputs
      document.querySelectorAll('input, textarea, [contenteditable="true"]').forEach(el => {
        structure.inputs.push({
          tag: el.tagName,
          type: el.type || 'contenteditable',
          placeholder: el.placeholder || el.getAttribute('data-placeholder'),
          classes: el.className
        });
      });

      // Find buttons
      document.querySelectorAll('button').forEach(btn => {
        const text = btn.textContent?.trim().slice(0, 30);
        const ariaLabel = btn.getAttribute('aria-label');
        if (text || ariaLabel) {
          structure.buttons.push({
            text: text || '',
            ariaLabel: ariaLabel || '',
            disabled: btn.disabled
          });
        }
      });

      return structure;
    }
  };

  // Expose API globally
  window.gobblerNotebookLM = NotebookLMAPI;

  console.log('[Gobbler] NotebookLM API v' + NotebookLMAPI.version + ' injected successfully');
  console.log('[Gobbler] Recommended: await window.gobblerNotebookLM.ask("your question") - sends and waits for complete response');
  console.log('[Gobbler] All methods:', Object.keys(NotebookLMAPI).filter(k => typeof NotebookLMAPI[k] === 'function').join(', '));
})();
