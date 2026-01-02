// Claude.ai Page-Specific API
// Injected automatically when a Claude.ai tab is added to the Gobbler group

(function() {
  'use strict';

  // Prevent double-injection
  if (window.__gobblerClaudeInjected) {
    console.log('[Gobbler] Claude API already injected');
    return;
  }
  window.__gobblerClaudeInjected = true;

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

  // Helper: Small delay
  function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Claude API object
  const ClaudeAPI = {
    // API version
    version: '1.0.0',

    // Check if we're on a conversation page
    isConversationPage() {
      return window.location.pathname.includes('/chat/');
    },

    // Get current conversation info
    getConversationInfo() {
      // Try to get title from the page
      const titleEl = document.querySelector('h1, [data-testid="conversation-title"], .conversation-title');
      const title = titleEl?.textContent?.trim() || 'New Conversation';
      const url = window.location.href;
      const conversationId = url.match(/\/chat\/([^/?]+)/)?.[1] || null;

      return {
        title,
        url,
        conversationId,
        isConversation: this.isConversationPage()
      };
    },

    // Find the chat input element
    _findInput() {
      // Claude.ai uses a contenteditable div or ProseMirror editor
      const selectors = [
        // Claude.ai specific selectors
        'div[contenteditable="true"].ProseMirror',
        'div[contenteditable="true"][data-placeholder]',
        'div.ProseMirror[contenteditable="true"]',
        // Fallbacks
        'div[contenteditable="true"]',
        'textarea[placeholder*="message"]',
        'textarea[placeholder*="Reply"]'
      ];

      for (const selector of selectors) {
        const el = document.querySelector(selector);
        if (el) return el;
      }
      return null;
    },

    // Find the send button
    _findSendButton() {
      const selectors = [
        // Claude.ai uses aria-label for the send button
        'button[aria-label="Send Message"]',
        'button[aria-label*="Send"]',
        'button[aria-label*="send"]',
        // Look for button with send icon (arrow)
        'button[type="submit"]',
        'button.send-button'
      ];

      for (const selector of selectors) {
        const btn = document.querySelector(selector);
        if (btn && !btn.disabled) return btn;
      }

      // Fallback: find button near input
      const input = this._findInput();
      if (input) {
        const form = input.closest('form');
        if (form) {
          const btn = form.querySelector('button[type="button"]:last-of-type, button:last-of-type');
          if (btn && !btn.disabled) return btn;
        }
      }

      return null;
    },

    // Get all messages in the conversation
    async getChatContent() {
      try {
        // Claude.ai uses specific data attributes for messages
        const messageSelectors = [
          '[data-testid="user-message"]',
          '[data-testid="assistant-message"]',
          '.message-content',
          '[class*="Message"]'
        ];

        // Try to find message containers
        let userMessages = document.querySelectorAll('[data-testid="user-message"], [class*="human-message"], [class*="user-message"]');
        let assistantMessages = document.querySelectorAll('[data-testid="assistant-message"], [class*="assistant-message"], [class*="claude-message"]');

        // If specific selectors don't work, try generic approach
        if (userMessages.length === 0 && assistantMessages.length === 0) {
          // Look for alternating message pattern in a container
          const container = document.querySelector('[class*="conversation"], [class*="messages"], main');
          if (container) {
            const allMessages = container.querySelectorAll('[class*="message"]');
            const content = [];
            allMessages.forEach((msg, index) => {
              const text = msg.textContent?.trim() || '';
              if (text.length > 0) {
                // Alternate between user and assistant based on position or class hints
                const isUser = msg.className.includes('human') || 
                               msg.className.includes('user') ||
                               msg.querySelector('[class*="human"]') !== null;
                content.push({
                  index,
                  role: isUser ? 'user' : 'assistant',
                  content: text.slice(0, 10000)
                });
              }
            });
            return { success: true, messages: content, count: content.length };
          }
        }

        const content = [];
        let index = 0;

        // Process user messages
        userMessages.forEach(msg => {
          const text = msg.textContent?.trim() || '';
          if (text) {
            content.push({ index: index++, role: 'user', content: text.slice(0, 10000) });
          }
        });

        // Process assistant messages
        assistantMessages.forEach(msg => {
          const text = msg.textContent?.trim() || '';
          if (text) {
            content.push({ index: index++, role: 'assistant', content: text.slice(0, 10000) });
          }
        });

        // Sort by DOM order if we can
        content.sort((a, b) => a.index - b.index);

        return {
          success: true,
          messages: content,
          count: content.length
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    // Get the last assistant response
    async getLastResponse() {
      try {
        // Find all assistant messages and get the last one
        const selectors = [
          '[data-testid="assistant-message"]:last-of-type',
          '[class*="assistant-message"]:last-of-type',
          '[class*="claude-message"]:last-of-type'
        ];

        for (const selector of selectors) {
          const msg = document.querySelector(selector);
          if (msg) {
            const text = msg.textContent?.trim() || '';
            return { success: true, response: text };
          }
        }

        // Fallback: get all message-like elements and find last assistant one
        const allMessages = document.querySelectorAll('[class*="message"]');
        for (let i = allMessages.length - 1; i >= 0; i--) {
          const msg = allMessages[i];
          const className = msg.className || '';
          if (className.includes('assistant') || className.includes('claude')) {
            return { success: true, response: msg.textContent?.trim() || '' };
          }
        }

        return { success: false, error: 'No assistant response found' };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    // Send a message to Claude
    async sendMessage(message) {
      try {
        const input = this._findInput();
        if (!input) {
          return { success: false, error: 'Could not find chat input field' };
        }

        // Clear and focus input
        input.focus();
        
        // For contenteditable divs (ProseMirror)
        if (input.getAttribute('contenteditable') === 'true') {
          // Clear existing content
          input.innerHTML = '';
          
          // Create a paragraph with the text
          const p = document.createElement('p');
          p.textContent = message;
          input.appendChild(p);
          
          // Dispatch input event
          input.dispatchEvent(new InputEvent('input', {
            bubbles: true,
            cancelable: true,
            inputType: 'insertText',
            data: message
          }));
        } else {
          // For textarea
          input.value = message;
          input.dispatchEvent(new Event('input', { bubbles: true }));
        }

        await delay(200);

        // Find and click send button
        const sendButton = this._findSendButton();
        if (!sendButton) {
          // Try pressing Enter
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

    // Wait for response to complete (text stability check)
    async waitForResponse(timeout = 120000) {
      const startTime = Date.now();
      let lastText = '';
      let stableCount = 0;
      const STABLE_THRESHOLD = 3; // 3 consecutive checks = 3 seconds

      // Get initial message count
      const getMessageCount = () => {
        const messages = document.querySelectorAll('[data-testid="assistant-message"], [class*="assistant-message"], [class*="claude-message"]');
        return messages.length;
      };

      const getLastMessageText = () => {
        const messages = document.querySelectorAll('[data-testid="assistant-message"], [class*="assistant-message"], [class*="claude-message"]');
        if (messages.length === 0) return '';
        return messages[messages.length - 1].textContent?.trim() || '';
      };

      const initialCount = getMessageCount();

      while (Date.now() - startTime < timeout) {
        await delay(1000);

        const currentCount = getMessageCount();
        
        // Wait for a new message to appear
        if (currentCount <= initialCount) {
          stableCount = 0;
          continue;
        }

        const currentText = getLastMessageText();

        // Skip if still showing loading indicators
        if (currentText.length < 20 || currentText.includes('...') || currentText.includes('Thinking')) {
          stableCount = 0;
          continue;
        }

        // Check stability
        if (currentText === lastText && currentText.length > 0) {
          stableCount++;
          if (stableCount >= STABLE_THRESHOLD) {
            return {
              success: true,
              response: currentText,
              elapsed: Date.now() - startTime
            };
          }
        } else {
          lastText = currentText;
          stableCount = 1;
        }
      }

      // Timeout - return partial if available
      const finalText = getLastMessageText();
      if (finalText && finalText.length > 0) {
        return {
          success: true,
          response: finalText,
          partial: true,
          elapsed: Date.now() - startTime
        };
      }

      return {
        success: false,
        error: 'Timeout waiting for response',
        elapsed: Date.now() - startTime
      };
    },

    // Combined: send message and wait for response
    async ask(message, timeout = 120000) {
      const startTime = Date.now();

      // Send the message
      const sendResult = await this.sendMessage(message);
      if (!sendResult.success) {
        return sendResult;
      }

      // Wait for response
      const responseResult = await this.waitForResponse(timeout);
      
      return {
        ...responseResult,
        messageSentVia: sendResult.method,
        totalElapsed: Date.now() - startTime
      };
    },

    // Get page structure for debugging
    getPageStructure() {
      const input = this._findInput();
      const sendButton = this._findSendButton();
      
      return {
        hasInput: !!input,
        inputType: input?.tagName || null,
        inputEditable: input?.getAttribute('contenteditable') || null,
        hasSendButton: !!sendButton,
        sendButtonDisabled: sendButton?.disabled || null,
        url: window.location.href,
        isConversation: this.isConversationPage()
      };
    }
  };

  // Expose API globally
  window.gobblerClaude = ClaudeAPI;

  console.log('[Gobbler] Claude API v' + ClaudeAPI.version + ' injected successfully');
  console.log('[Gobbler] Available at window.gobblerClaude');
  console.log('[Gobbler] Methods: ask, sendMessage, waitForResponse, getChatContent, getLastResponse, getConversationInfo');
})();
