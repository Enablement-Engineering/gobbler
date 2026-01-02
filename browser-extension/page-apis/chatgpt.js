// ChatGPT Page-Specific API
// Injected automatically when a ChatGPT tab is added to the Gobbler group

(function() {
  'use strict';

  // Prevent double-injection
  if (window.__gobblerChatGPTInjected) {
    console.log('[Gobbler] ChatGPT API already injected');
    return;
  }
  window.__gobblerChatGPTInjected = true;

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

  // ChatGPT API object
  const ChatGPTAPI = {
    // API version
    version: '1.0.0',

    // Check if we're on a conversation page
    isConversationPage() {
      const url = window.location.href;
      return url.includes('/c/') || url.includes('/g/') || url === 'https://chatgpt.com/' || url === 'https://chat.openai.com/';
    },

    // Get current conversation info
    getConversationInfo() {
      const title = document.title.replace(' | ChatGPT', '').replace(' - ChatGPT', '') || 'New Conversation';
      const url = window.location.href;
      const conversationId = url.match(/\/c\/([^/?]+)/)?.[1] || url.match(/\/g\/([^/?]+)/)?.[1] || null;

      // Count messages
      const userMessages = document.querySelectorAll('[data-message-author-role="user"]').length;
      const assistantMessages = document.querySelectorAll('[data-message-author-role="assistant"]').length;

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
      const selectors = [
        // ChatGPT uses ProseMirror contenteditable div
        '#prompt-textarea',
        'div.ProseMirror[contenteditable="true"]',
        'div[contenteditable="true"][data-virtualkeyboard="true"]',
        // Fallback textarea (hidden but may be present)
        'textarea[name="prompt-textarea"]',
        'textarea[placeholder*="Ask anything"]',
        'textarea[placeholder*="Message"]'
      ];

      for (const selector of selectors) {
        const el = document.querySelector(selector);
        if (el && el.offsetParent !== null) return el; // Check if visible
      }
      
      // Return even hidden textarea as last resort
      for (const selector of selectors) {
        const el = document.querySelector(selector);
        if (el) return el;
      }
      return null;
    },

    // Find the send button
    _findSendButton() {
      const selectors = [
        // ChatGPT specific selectors
        '#composer-submit-button',
        'button[data-testid="send-button"]',
        'button[aria-label="Send prompt"]',
        'button[aria-label*="Send"]',
        'button.composer-submit-btn'
      ];

      for (const selector of selectors) {
        const btn = document.querySelector(selector);
        if (btn && !btn.disabled) return btn;
      }

      return null;
    },

    // Get all messages in the conversation
    async getChatContent() {
      try {
        const userMessages = document.querySelectorAll('[data-message-author-role="user"]');
        const assistantMessages = document.querySelectorAll('[data-message-author-role="assistant"]');

        const content = [];
        const allElements = [];

        userMessages.forEach(msg => {
          // Find the actual text content within the message
          const textEl = msg.querySelector('.markdown, .whitespace-pre-wrap') || msg;
          const text = textEl.textContent?.trim() || '';
          if (text) {
            allElements.push({
              element: msg,
              role: 'user',
              content: text.slice(0, 10000)
            });
          }
        });

        assistantMessages.forEach(msg => {
          // Find the markdown content
          const textEl = msg.querySelector('.markdown') || msg;
          const text = textEl.textContent?.trim() || '';
          if (text) {
            allElements.push({
              element: msg,
              role: 'assistant',
              content: text.slice(0, 10000)
            });
          }
        });

        // Sort by DOM position
        allElements.sort((a, b) => {
          const position = a.element.compareDocumentPosition(b.element);
          if (position & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
          if (position & Node.DOCUMENT_POSITION_PRECEDING) return 1;
          return 0;
        });

        // Build final content array without element references
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

    // Get the last assistant response (including images)
    async getLastResponse() {
      try {
        const messages = document.querySelectorAll('[data-message-author-role="assistant"]');

        if (messages.length === 0) {
          return { success: false, error: 'No assistant response found' };
        }

        const lastMsg = messages[messages.length - 1];
        const textEl = lastMsg.querySelector('.markdown') || lastMsg;
        const text = textEl.textContent?.trim() || '';

        // Check for generated images - search globally for "Generated image" alt tags
        // These may be outside the assistant message container
        const images = [];
        const generatedImgs = document.querySelectorAll('img[alt="Generated image"]');
        generatedImgs.forEach(img => {
          if (img.src && !images.includes(img.src)) {
            images.push(img.src);
          }
        });
        
        // Also check within the message for any estuary/oaiusercontent images
        const directImgs = lastMsg.querySelectorAll('img[src*="backend-api/estuary"], img[src*="oaiusercontent"]');
        directImgs.forEach(img => {
          if (img.src && !images.includes(img.src)) {
            images.push(img.src);
          }
        });
        
        // Deduplicate images
        const uniqueImages = [...new Set(images)];

        // Check if still streaming - look for stop button (most reliable)
        const isStreaming = !!document.querySelector('button[data-testid="stop-button"]') ||
                          !!document.querySelector('button[aria-label="Stop streaming"]') ||
                          !!document.querySelector('button[aria-label="Stop generating"]');

        return {
          success: true,
          response: text,
          images: uniqueImages,
          hasImages: uniqueImages.length > 0,
          isStreaming,
          totalMessages: messages.length
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    // Send a message to ChatGPT
    async sendMessage(message) {
      try {
        const input = this._findInput();
        if (!input) {
          return { success: false, error: 'Could not find chat input field' };
        }

        // Focus input
        input.focus();
        await delay(100);

        // For contenteditable divs (ProseMirror)
        if (input.getAttribute('contenteditable') === 'true') {
          // Clear existing content
          input.innerHTML = '';
          
          // Insert text
          const p = document.createElement('p');
          p.textContent = message;
          input.appendChild(p);
          
          // Dispatch input event to trigger React state update
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

        // Wait for React to process
        await delay(300);

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

        // Simple click - the script ends here and does NOT interact further
        sendButton.click();
        
        return { success: true, method: 'button-click' };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    // Wait for response to complete
    async waitForResponse(timeout = 120000) {
      const startTime = Date.now();
      let wasStreaming = false;

      const getAssistantMessages = () => {
        return document.querySelectorAll('[data-message-author-role="assistant"]');
      };

      const getLastMessageText = () => {
        const messages = getAssistantMessages();
        if (messages.length === 0) return '';
        // Find the last message with actual content (skip empty pending messages)
        for (let i = messages.length - 1; i >= 0; i--) {
          const msg = messages[i];
          const textEl = msg.querySelector('.markdown') || msg;
          const text = textEl.textContent?.trim() || '';
          if (text.length > 0) {
            return text;
          }
        }
        return '';
      };

      const isStillStreaming = () => {
        // Check for stop button (most reliable indicator of active generation)
        const stopBtn = document.querySelector('button[data-testid="stop-button"]') ||
                       document.querySelector('button[aria-label="Stop streaming"]') ||
                       document.querySelector('button[aria-label="Stop generating"]');
        return !!stopBtn;
      };

      const initialCount = getAssistantMessages().length;

      while (Date.now() - startTime < timeout) {
        await delay(500); // Check more frequently

        const currentCount = getAssistantMessages().length;
        const streaming = isStillStreaming();

        // Track if we've seen streaming start
        if (streaming) {
          wasStreaming = true;
          continue;
        }

        // If we were streaming and now stopped, response is complete
        if (wasStreaming && !streaming) {
          await delay(1500); // Wait for DOM to fully sync after streaming stops
          let response = getLastMessageText();
          // If still empty, wait a bit more and retry
          if (!response) {
            await delay(1000);
            response = getLastMessageText();
          }
          return {
            success: true,
            response: response,
            elapsed: Date.now() - startTime
          };
        }

        // If a new message appeared and no streaming, it might be complete already
        if (currentCount > initialCount && !streaming) {
          const response = getLastMessageText();
          if (response.length > 0) {
            return {
              success: true,
              response: response,
              elapsed: Date.now() - startTime
            };
          }
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
        inputId: input?.id || null,
        inputEditable: input?.getAttribute('contenteditable') || null,
        hasSendButton: !!sendButton,
        sendButtonId: sendButton?.id || null,
        sendButtonDisabled: sendButton?.disabled || null,
        url: window.location.href,
        isConversation: this.isConversationPage(),
        userMessageCount: document.querySelectorAll('[data-message-author-role="user"]').length,
        assistantMessageCount: document.querySelectorAll('[data-message-author-role="assistant"]').length
      };
    }
  };

  // Expose API globally
  window.gobblerChatGPT = ChatGPTAPI;

  console.log('[Gobbler] ChatGPT API v' + ChatGPTAPI.version + ' injected successfully');
  console.log('[Gobbler] Available at window.gobblerChatGPT');
  console.log('[Gobbler] Methods: ask, sendMessage, waitForResponse, getChatContent, getLastResponse, getConversationInfo');
})();
