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

  // Debug mode
  const DEBUG = true;
  
  function debugLog(...args) {
    if (DEBUG) {
      console.log('[Gobbler Claude]', ...args);
    }
  }

  // Claude API object
  const ClaudeAPI = {
    // API version
    version: '1.2.0',

    // Check if we're on a conversation page
    isConversationPage() {
      return window.location.pathname.includes('/chat/');
    },

    // Get current conversation info
    getConversationInfo() {
      // Try to get title from the page - check for chat title button first
      const titleEl = document.querySelector('[data-testid="chat-title-button"], h1, .conversation-title');
      const title = titleEl?.textContent?.trim() || document.title.replace(' - Claude', '') || 'New Conversation';
      const url = window.location.href;
      const conversationId = url.match(/\/chat\/([^/?]+)/)?.[1] || null;

      // Count messages using the correct selectors (updated for current Claude.ai DOM)
      const userMessages = document.querySelectorAll('[data-testid="user-message"]').length;
      const assistantMessages = document.querySelectorAll('[data-is-streaming]').length;

      return {
        title,
        url,
        conversationId,
        isConversation: this.isConversationPage(),
        userMessages,
        assistantMessages
      };
    },

    // Find the chat input element
    _findInput() {
      // Claude.ai uses a ProseMirror editor with data-testid="chat-input"
      const selectors = [
        // Primary selector - data-testid is most reliable
        '[data-testid="chat-input"]',
        // Claude.ai specific selectors (fallbacks)
        'div[contenteditable="true"].ProseMirror',
        'div.ProseMirror[contenteditable="true"]',
        'div[contenteditable="true"][data-placeholder]',
        // Generic fallbacks
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
        // Primary selector - exact match for Claude.ai's current send button
        'button[aria-label="Send message"]',
        // Fallback variations
        'button[aria-label="Send Message"]',
        'button[aria-label*="Send"]',
        'button[aria-label*="send"]',
        // Generic fallbacks
        'button[type="submit"]',
        'button.send-button'
      ];

      for (const selector of selectors) {
        const btn = document.querySelector(selector);
        // Return button even if disabled - caller can check state
        if (btn) return btn;
      }

      // Fallback: find button near input in the chat-input-grid-container
      const inputGrid = document.querySelector('[data-testid="chat-input-grid-container"]');
      if (inputGrid) {
        const parent = inputGrid.closest('form') || inputGrid.parentElement;
        if (parent) {
          const btn = parent.querySelector('button[aria-label*="Send"], button[type="submit"]');
          if (btn) return btn;
        }
      }

      return null;
    },

    // Get all messages in the conversation
    async getChatContent() {
      try {
        // Claude.ai uses (updated Jan 2025):
        // - [data-testid="user-message"] for user messages
        // - [data-is-streaming] containers for assistant messages (content in .font-claude-response)
        const userMessages = document.querySelectorAll('[data-testid="user-message"]');
        const assistantContainers = document.querySelectorAll('[data-is-streaming]');

        const content = [];
        
        // Get all messages with their DOM positions for proper ordering
        const allElements = [];
        
        userMessages.forEach(msg => {
          const text = msg.textContent?.trim() || '';
          if (text) {
            allElements.push({
              element: msg,
              role: 'user',
              content: text.slice(0, 10000)
            });
          }
        });

        assistantContainers.forEach(container => {
          // Get the actual response text from .font-claude-response child
          const responseEl = container.querySelector('.font-claude-response');
          const text = responseEl?.textContent?.trim() || container.textContent?.trim() || '';
          if (text) {
            allElements.push({
              element: container,
              role: 'assistant',
              content: text.slice(0, 10000)
            });
          }
        });

        // Sort by DOM position using compareDocumentPosition
        allElements.sort((a, b) => {
          const position = a.element.compareDocumentPosition(b.element);
          if (position & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
          if (position & Node.DOCUMENT_POSITION_PRECEDING) return 1;
          return 0;
        });

        // Build final content array without the element references
        allElements.forEach((item, index) => {
          content.push({
            index,
            role: item.role,
            content: item.content
          });
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

    // Extract response text, excluding thinking sections
    _extractResponseText(container) {
      const responseEl = container.querySelector('.font-claude-response');
      if (!responseEl) {
        return container.textContent?.trim() || '';
      }
      
      // Claude has thinking in first div, response in subsequent divs
      // Get all direct children divs
      const children = Array.from(responseEl.children);
      
      if (children.length <= 1) {
        // Single child - just return its text
        return responseEl.textContent?.trim() || '';
      }
      
      // Multiple children - check if first is thinking section
      const firstChild = children[0];
      const hasThinking = firstChild?.textContent?.toLowerCase().includes('thinking') ||
                          firstChild?.className?.includes('thinking') ||
                          firstChild?.className?.includes('transition');
      
      if (hasThinking && children.length > 1) {
        // Skip first child (thinking), get text from remaining children
        const responseText = children.slice(1)
          .map(child => child.textContent?.trim())
          .filter(text => text && text.length > 0)
          .join('\n\n');
        debugLog('Extracted response (skipped thinking):', responseText.slice(0, 100));
        return responseText;
      }
      
      // No thinking section detected, return full text
      return responseEl.textContent?.trim() || '';
    },

    // Get the last assistant response
    async getLastResponse() {
      try {
        // Claude.ai uses data-is-streaming attribute on containers for assistant messages
        const containers = document.querySelectorAll('[data-is-streaming]');
        
        if (containers.length === 0) {
          return { success: false, error: 'No assistant response found' };
        }

        const lastContainer = containers[containers.length - 1];
        const text = this._extractResponseText(lastContainer);
        const isStreaming = lastContainer.dataset.isStreaming === 'true';

        return { 
          success: true, 
          response: text,
          isStreaming,
          totalMessages: containers.length
        };
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

    // Wait for response to complete
    // Claude.ai uses data-is-streaming="true"/"false" on assistant message containers
    async waitForResponse(timeout = 120000) {
      const startTime = Date.now();
      let lastText = '';
      let stableCount = 0;
      const STABLE_THRESHOLD = 3; // 3 consecutive checks with same text = done

      // Claude.ai uses data-is-streaming attribute on containers for assistant messages
      const getAssistantContainers = () => {
        return document.querySelectorAll('[data-is-streaming]');
      };

      const getLastMessageText = () => {
        const containers = getAssistantContainers();
        if (containers.length === 0) return '';
        const lastContainer = containers[containers.length - 1];
        // Use the extraction method that skips thinking sections
        return this._extractResponseText(lastContainer);
      };

      const isStillStreaming = () => {
        const containers = getAssistantContainers();
        if (containers.length === 0) return false;
        const lastContainer = containers[containers.length - 1];
        return lastContainer.dataset.isStreaming === 'true';
      };

      const initialCount = getAssistantContainers().length;
      debugLog('Starting waitForResponse, initial count:', initialCount, 'timeout:', timeout);

      while (Date.now() - startTime < timeout) {
        await delay(500); // Check more frequently

        const containers = getAssistantContainers();
        const currentCount = containers.length;
        const elapsed = Date.now() - startTime;
        
        // Wait for a new message to appear
        if (currentCount <= initialCount) {
          debugLog('Waiting for new message, count:', currentCount);
          stableCount = 0;
          continue;
        }

        // Check if still streaming
        const streaming = isStillStreaming();
        if (streaming) {
          debugLog('Still streaming, elapsed:', elapsed);
          stableCount = 0;
          lastText = getLastMessageText();
          continue;
        }

        const currentText = getLastMessageText();
        debugLog('Streaming stopped, text length:', currentText.length, 'stable count:', stableCount);

        // Skip if no actual response text yet (still loading or only thinking)
        if (currentText.length === 0) {
          stableCount = 0;
          continue;
        }

        // Check stability (text hasn't changed and not streaming)
        if (currentText === lastText && currentText.length > 0) {
          stableCount++;
          if (stableCount >= STABLE_THRESHOLD) {
            debugLog('Response complete (stable), length:', currentText.length);
            return {
              success: true,
              response: currentText,
              elapsed: elapsed
            };
          }
        } else {
          lastText = currentText;
          stableCount = 1;
        }
      }

      // Timeout - return partial if available
      const finalText = getLastMessageText();
      debugLog('Timeout reached, final text length:', finalText?.length || 0);
      
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

  console.log('[Gobbler] Claude API v' + ClaudeAPI.version + ' injected successfully (DEBUG=' + DEBUG + ')');
  console.log('[Gobbler] Available at window.gobblerClaude');
  console.log('[Gobbler] Methods: ask, sendMessage, waitForResponse, getChatContent, getLastResponse, getConversationInfo');
  
  // Log page structure for debugging
  debugLog('Page structure:', ClaudeAPI.getPageStructure());
})();
