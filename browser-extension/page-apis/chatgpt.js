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

  // Debug mode - set to true for verbose logging
  const DEBUG = true;
  
  function debugLog(...args) {
    if (DEBUG) {
      console.log('[Gobbler ChatGPT]', ...args);
    }
  }

  // ChatGPT API object
  const ChatGPTAPI = {
    // API version
    version: '1.4.1',

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
        // ChatGPT 2025 selectors (order matters - most specific first)
        'button[aria-label="Send prompt"]',
        'button.composer-submit-btn',
        // Legacy selectors as fallback
        '#composer-submit-button',
        'button[data-testid="send-button"]',
        'button[aria-label*="Send"]'
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

        // Check if still streaming - look for stop button or thinking state
        let isStreaming = !!document.querySelector('button[data-testid="stop-button"]') ||
                          !!document.querySelector('button[aria-label="Stop streaming"]') ||
                          !!document.querySelector('button[aria-label="Stop generating"]') ||
                          !!document.querySelector('button[aria-label*="Stop"]') ||
                          !!document.querySelector('button.composer-stop-btn');
        
        // Also check for thinking state (empty result-thinking element)
        if (!isStreaming) {
          const thinkingEl = lastMsg.querySelector('.result-thinking');
          if (thinkingEl && !thinkingEl.textContent?.trim()) {
            isStreaming = true;
          }
        }

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
      let stableTextCount = 0;
      let lastStableText = '';

      const getAssistantMessages = () => {
        return document.querySelectorAll('[data-message-author-role="assistant"]');
      };

      const getLastMessageText = () => {
        // Try multiple extraction methods
        
        // Method 1: Direct message query (most reliable)
        const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
        if (messages.length > 0) {
          const lastMsg = messages[messages.length - 1];
          const markdownEl = lastMsg.querySelector('.markdown');
          if (markdownEl) {
            const text = markdownEl.textContent?.trim() || '';
            if (text) {
              debugLog('Extracted text via .markdown, length:', text.length);
              return text;
            }
          }
          const text = lastMsg.textContent?.trim() || '';
          if (text) {
            debugLog('Extracted text via textContent, length:', text.length);
            return text;
          }
        }
        
        // Method 2: Use article structure with wildcard match
        const articles = document.querySelectorAll('article[data-testid^="conversation-turn"]');
        const assistantArticles = Array.from(articles).filter(a => 
          a.querySelector('[data-message-author-role="assistant"]')
        );
        
        if (assistantArticles.length > 0) {
          const lastArticle = assistantArticles[assistantArticles.length - 1];
          const msg = lastArticle.querySelector('[data-message-author-role="assistant"]');
          if (msg) {
            const markdownEl = msg.querySelector('.markdown');
            if (markdownEl) {
              const text = markdownEl.textContent?.trim() || '';
              debugLog('Extracted text via article .markdown, length:', text.length);
              return text;
            }
            const text = msg.textContent?.trim() || '';
            debugLog('Extracted text via article textContent, length:', text.length);
            return text;
          }
        }
        
        debugLog('No text found');
        return '';
      };

      const isStillStreaming = () => {
        // Check for stop button with multiple selectors (ChatGPT changes these frequently)
        const stopSelectors = [
          'button[data-testid="stop-button"]',
          'button[aria-label="Stop streaming"]',
          'button[aria-label="Stop generating"]',
          'button[aria-label="Stop response"]',
          'button[aria-label*="Stop"]',
          'button.composer-stop-btn',
          // SVG-based stop button (square icon in circular button)
          'button svg rect[width="10"]',
          // Check for any button with stop-related content
          'button[class*="stop"]'
        ];
        
        for (const selector of stopSelectors) {
          const el = document.querySelector(selector);
          if (el) {
            debugLog('Found stop button:', selector);
            return true;
          }
        }
        
        // Check for streaming indicator in the response itself
        const streamingCursor = document.querySelector('.result-streaming');
        if (streamingCursor) {
          debugLog('Found streaming cursor');
          return true;
        }
        
        return false;
      };
      
      const isResponseComplete = () => {
        // Check for action buttons on the last message
        // These appear only after response is fully complete
        const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
        if (messages.length === 0) return false;
        
        const lastMsg = messages[messages.length - 1];
        
        // Find the parent article/container that holds action buttons
        const container = lastMsg.closest('article') || lastMsg.closest('[data-testid]') || lastMsg.parentElement?.parentElement;
        
        if (container) {
          // Multiple selectors for action buttons
          const actionButtonSelectors = [
            'button[aria-label="Copy"]',
            'button[aria-label="Copy response"]', 
            'button[data-testid="copy-turn-action-button"]',
            'button[aria-label="Good response"]',
            'button[aria-label="Bad response"]',
            'button[aria-label="Read aloud"]',
            // Generic: any button group after the message
            '.flex button[aria-label]'
          ];
          
          for (const selector of actionButtonSelectors) {
            const btn = container.querySelector(selector);
            if (btn) {
              debugLog('Found action button:', selector);
              return true;
            }
          }
        }
        
        return false;
      };

      const initialCount = getAssistantMessages().length;
      const initialLastText = getLastMessageText();
      let newMessageAppeared = false;
      
      debugLog('Starting waitForResponse, initial count:', initialCount, 'timeout:', timeout);

      while (Date.now() - startTime < timeout) {
        await delay(500); // Check frequently

        const currentCount = getAssistantMessages().length;
        const streaming = isStillStreaming();
        const complete = isResponseComplete();
        const currentText = getLastMessageText();
        const elapsed = Date.now() - startTime;

        // Track if a new message appeared
        if (currentCount > initialCount) {
          if (!newMessageAppeared) {
            debugLog('New message appeared, count:', currentCount);
          }
          newMessageAppeared = true;
        }

        // Track if we've seen streaming start
        if (streaming) {
          wasStreaming = true;
          stableTextCount = 0; // Reset stability counter
          debugLog('Streaming active, elapsed:', elapsed);
          continue;
        }

        // Stability check: if text hasn't changed for 3 checks (1.5s) and we have content
        if (currentText && currentText === lastStableText && currentText !== initialLastText) {
          stableTextCount++;
          debugLog('Text stable for', stableTextCount, 'checks, length:', currentText.length);
          
          if (stableTextCount >= 3) {
            debugLog('Text stable, checking if complete...');
            // Give extra time for action buttons to appear
            await delay(500);
            if (isResponseComplete() || stableTextCount >= 6) {
              debugLog('Returning response (stable text), length:', currentText.length);
              return {
                success: true,
                response: currentText,
                elapsed: elapsed,
                method: stableTextCount >= 6 ? 'stability-timeout' : 'stability-complete'
              };
            }
          }
        } else {
          stableTextCount = 0;
          lastStableText = currentText;
        }

        // Best indicator: action buttons appeared (Copy, Good response, etc.)
        if (newMessageAppeared && complete) {
          await delay(300); // Brief wait for final DOM sync
          const response = getLastMessageText();
          if (response && response !== initialLastText) {
            debugLog('Returning response (action buttons), length:', response.length);
            return {
              success: true,
              response: response,
              elapsed: elapsed,
              method: 'action-buttons'
            };
          }
        }

        // Fallback: if we were streaming and now stopped, check for response
        if (wasStreaming && !streaming) {
          debugLog('Streaming stopped, waiting for DOM sync...');
          await delay(1000); // Wait for DOM to sync
          
          // Check if complete via action buttons
          if (isResponseComplete()) {
            const response = getLastMessageText();
            if (response && response !== initialLastText) {
              debugLog('Returning response (post-stream), length:', response.length);
              return {
                success: true,
                response: response,
                elapsed: elapsed,
                method: 'post-stream'
              };
            }
          }
          
          // Keep waiting - might still be processing
          wasStreaming = false;
        }

        // If a new message appeared with content and appears complete
        if (currentCount > initialCount && !streaming && complete) {
          const response = getLastMessageText();
          if (response && response.length > 0 && response !== initialLastText) {
            debugLog('Returning response (new message complete), length:', response.length);
            return {
              success: true,
              response: response,
              elapsed: elapsed,
              method: 'new-message-complete'
            };
          }
        }
      }

      // Timeout - return partial if available
      const finalText = getLastMessageText();
      debugLog('Timeout reached, final text length:', finalText?.length || 0);
      
      if (finalText && finalText.length > 0 && finalText !== initialLastText) {
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
        elapsed: Date.now() - startTime,
        debug: {
          initialCount,
          finalCount: getAssistantMessages().length,
          wasStreaming,
          newMessageAppeared
        }
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

  console.log('[Gobbler] ChatGPT API v' + ChatGPTAPI.version + ' injected successfully (DEBUG=' + DEBUG + ')');
  console.log('[Gobbler] Available at window.gobblerChatGPT');
  console.log('[Gobbler] Methods: ask, sendMessage, waitForResponse, getChatContent, getLastResponse, getConversationInfo');
  
  // Log page structure for debugging
  debugLog('Page structure:', ChatGPTAPI.getPageStructure());
})();
