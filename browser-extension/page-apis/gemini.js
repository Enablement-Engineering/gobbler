// Gemini Page-Specific API
// Injected automatically when a Gemini tab is added to the Gobbler group

(function() {
  'use strict';

  // Prevent double-injection
  if (window.__gobblerGeminiInjected) {
    console.log('[Gobbler] Gemini API already injected');
    return;
  }
  window.__gobblerGeminiInjected = true;

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

  // Gemini API object
  const GeminiAPI = {
    // API version
    version: '1.0.0',

    // Check if we're on a conversation page
    isConversationPage() {
      const url = window.location.href;
      return url.includes('gemini.google.com/app') || url.includes('gemini.google.com/chat');
    },

    // Get current conversation info
    getConversationInfo() {
      const title = document.title.replace(' - Google Gemini', '').replace(' | Gemini', '') || 'New Conversation';
      const url = window.location.href;
      // Gemini conversation IDs are in the URL path
      const conversationId = url.match(/\/app\/([^/?]+)/)?.[1] || url.match(/\/chat\/([^/?]+)/)?.[1] || null;

      // Count messages - Gemini uses different selectors
      const userMessages = document.querySelectorAll('user-query, [data-message-author="user"]').length;
      const assistantMessages = document.querySelectorAll('model-response, message-content').length;

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
        // Gemini uses rich-textarea with Quill editor
        'rich-textarea .ql-editor[contenteditable="true"]',
        '.ql-editor[contenteditable="true"]',
        'div[contenteditable="true"][aria-label*="prompt"]',
        'div[contenteditable="true"][aria-label*="Enter a prompt"]',
        // Fallback selectors
        'rich-textarea div[contenteditable="true"]',
        '.text-input-field_textarea div[contenteditable="true"]',
        'textarea[aria-label*="prompt"]'
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
        // Gemini specific selectors
        'button[aria-label="Send message"]',
        'button.send-button',
        'button[aria-label*="Send"]',
        'button mat-icon[fonticon="send"]',
        // Find button containing send icon
        'button:has(mat-icon[fonticon="send"])'
      ];

      for (const selector of selectors) {
        try {
          const btn = document.querySelector(selector);
          if (btn && !btn.disabled && btn.getAttribute('aria-disabled') !== 'true') {
            return btn;
          }
        } catch (e) {
          // :has() selector might not be supported in all browsers
          continue;
        }
      }

      // Fallback: find button with send icon by traversing
      const sendIcons = document.querySelectorAll('mat-icon[fonticon="send"]');
      for (const icon of sendIcons) {
        const btn = icon.closest('button');
        if (btn && !btn.disabled && btn.getAttribute('aria-disabled') !== 'true') {
          return btn;
        }
      }

      return null;
    },

    // Get all messages in the conversation
    async getChatContent() {
      try {
        const content = [];
        const allElements = [];

        // User messages - Gemini uses user-query or similar elements
        const userQueries = document.querySelectorAll('user-query, [data-turn="user"]');
        userQueries.forEach(msg => {
          const text = msg.textContent?.trim() || '';
          if (text) {
            allElements.push({
              element: msg,
              role: 'user',
              content: text.slice(0, 10000)
            });
          }
        });

        // Assistant messages - Gemini uses model-response or message-content
        const modelResponses = document.querySelectorAll('model-response message-content, structured-content-container message-content');
        modelResponses.forEach(msg => {
          // Get the markdown content
          const markdownEl = msg.querySelector('.markdown') || msg;
          const text = markdownEl.textContent?.trim() || '';
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
        // Try model-response first (more reliable)
        const modelResponses = document.querySelectorAll('model-response');
        
        if (modelResponses.length === 0) {
          return { success: false, error: 'No assistant response found' };
        }

        const lastMsg = modelResponses[modelResponses.length - 1];
        const markdownEl = lastMsg.querySelector('.markdown') || lastMsg.querySelector('message-content') || lastMsg;
        const text = markdownEl.textContent?.trim() || '';

        // Check for images in the response
        const imgs = lastMsg.querySelectorAll('img[alt*="Image"]');
        const images = Array.from(imgs).map(img => img.src).filter(src => src && src.includes('googleusercontent'));

        // Check if still streaming
        const ariaBusy = markdownEl.getAttribute('aria-busy');
        const loadingText = text.toLowerCase().includes('loading') || text.toLowerCase().includes('nano banana');
        const isStreaming = ariaBusy === 'true' || loadingText;

        return {
          success: true,
          response: text,
          images: images,
          hasImages: images.length > 0,
          isStreaming,
          totalMessages: modelResponses.length
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    // Send a message to Gemini
    async sendMessage(message) {
      try {
        const input = this._findInput();
        if (!input) {
          return { success: false, error: 'Could not find chat input field' };
        }

        // Clear and focus input
        input.focus();

        // Gemini uses Quill editor (contenteditable div)
        // Clear existing content using DOM methods (avoids TrustedHTML issues)
        while (input.firstChild) {
          input.removeChild(input.firstChild);
        }

        // Create a paragraph with the text
        const p = document.createElement('p');
        p.textContent = message;
        input.appendChild(p);

        // Dispatch input event to trigger framework updates
        input.dispatchEvent(new InputEvent('input', {
          bubbles: true,
          cancelable: true,
          inputType: 'insertText',
          data: message
        }));

        // Also dispatch a change event for Angular
        input.dispatchEvent(new Event('change', { bubbles: true }));

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
        // Try model-response elements
        const modelResponses = document.querySelectorAll('model-response');
        if (modelResponses.length > 0) return modelResponses;
        // Fallback to structured-content-container
        return document.querySelectorAll('structured-content-container.model-response-text');
      };

      const getLastMessageContent = () => {
        const messages = getAssistantMessages();
        if (messages.length === 0) return { text: '', images: [] };
        
        // Get the actual last message (not searching for text)
        const lastMsg = messages[messages.length - 1];
        const markdownEl = lastMsg.querySelector('.markdown') || lastMsg.querySelector('message-content') || lastMsg;
        const text = markdownEl.textContent?.trim() || '';
        
        // Check for images in the last message
        const imgs = lastMsg.querySelectorAll('img[alt*="Image"]');
        const images = Array.from(imgs).map(img => img.src).filter(src => src && src.includes('googleusercontent'));
        
        return { text, images };
      };

      const isStillStreaming = () => {
        // Check for aria-busy on markdown content
        const markdownEls = document.querySelectorAll('message-content .markdown, .markdown[aria-busy]');
        for (const el of markdownEls) {
          const ariaBusy = el.getAttribute('aria-busy');
          if (ariaBusy === 'true') return true;
        }
        
        // Check for image generation loading state (Nano Banana / Loading text)
        const modelResponses = document.querySelectorAll('model-response');
        if (modelResponses.length > 0) {
          const lastResponse = modelResponses[modelResponses.length - 1];
          const text = lastResponse.textContent?.toLowerCase() || '';
          if (text.includes('loading') || text.includes('nano banana')) {
            return true; // Still loading images
          }
        }
        
        return false;
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
          let content = getLastMessageContent();
          
          // Check for loading placeholders - if found, keep waiting
          if (content.text.toLowerCase().includes('loading') || content.text.toLowerCase().includes('nano banana')) {
            wasStreaming = false; // Reset and keep waiting
            continue;
          }
          
          // If still empty and no images, wait a bit more and retry
          if (!content.text && content.images.length === 0) {
            await delay(1000);
            content = getLastMessageContent();
          }
          
          return {
            success: true,
            response: content.text,
            images: content.images,
            hasImages: content.images.length > 0,
            elapsed: Date.now() - startTime
          };
        }

        // If a new message appeared and no streaming, it might be complete already
        if (currentCount > initialCount && !streaming) {
          const content = getLastMessageContent();
          if (content.text.length > 0 || content.images.length > 0) {
            return {
              success: true,
              response: content.text,
              images: content.images,
              hasImages: content.images.length > 0,
              elapsed: Date.now() - startTime
            };
          }
        }
      }

      // Timeout - return partial if available
      const finalContent = getLastMessageContent();
      if (finalContent.text.length > 0 || finalContent.images.length > 0) {
        return {
          success: true,
          response: finalContent.text,
          images: finalContent.images,
          hasImages: finalContent.images.length > 0,
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
        inputClass: input?.className || null,
        inputEditable: input?.getAttribute('contenteditable') || null,
        hasSendButton: !!sendButton,
        sendButtonClass: sendButton?.className || null,
        sendButtonDisabled: sendButton?.disabled || sendButton?.getAttribute('aria-disabled') === 'true',
        url: window.location.href,
        isConversation: this.isConversationPage(),
        modelResponseCount: document.querySelectorAll('structured-content-container.model-response-text').length,
        userQueryCount: document.querySelectorAll('user-query').length
      };
    }
  };

  // Expose API globally
  window.gobblerGemini = GeminiAPI;

  console.log('[Gobbler] Gemini API v' + GeminiAPI.version + ' injected successfully');
  console.log('[Gobbler] Available at window.gobblerGemini');
  console.log('[Gobbler] Methods: ask, sendMessage, waitForResponse, getChatContent, getLastResponse, getConversationInfo');
})();
