# Browser Automation Examples

These examples show how to use Gobbler MCP's bidirectional communication with the browser extension from Claude or any MCP client.

## Prerequisites

1. Gobbler MCP server is running
2. Browser extension is installed and connected
3. MCP client (Claude Code, Claude Desktop, etc.) is configured with Gobbler MCP

## Example 1: Extract Current Page

The simplest use case - extract the current browser page as markdown.

```
User: Extract the current page from my browser

Claude: I'll extract the current page for you.
```

Claude will use:
```python
await browser_extract_current_page()
```

Result: Full page content as markdown with frontmatter.

## Example 2: Extract Specific Content

Extract only a specific section of the page using CSS selectors.

```
User: Extract just the main article from the current page

Claude: I'll extract the main article content.
```

Claude will use:
```python
await browser_extract_current_page(selector="article.main")
```

Result: Just the article content as markdown.

## Example 3: Navigate and Extract

Navigate to a URL and then extract its content.

```
User: Go to https://docs.python.org/3/tutorial/ and extract the page

Claude: I'll navigate to the Python tutorial and extract it.
```

Claude will use:
```python
# Navigate
await browser_navigate_to_url("https://docs.python.org/3/tutorial/")

# Extract
markdown = await browser_extract_current_page()
```

## Example 4: Execute Custom JavaScript

Run JavaScript in the browser to get specific information.

```
User: Get all the image URLs from the current page

Claude: I'll extract all image URLs for you.
```

Claude will use:
```python
await browser_execute_script("""
  Array.from(document.querySelectorAll('img')).map(img => ({
    src: img.src,
    alt: img.alt
  }))
""")
```

Result: JSON array of image information.

## Example 5: Get Page Metadata

Get information about the current page without extracting all content.

```
User: What page am I currently on?

Claude: Let me check your current page.
```

Claude will use:
```python
await browser_get_page_info()
```

Result:
```json
{
  "url": "https://example.com/page",
  "title": "Example Page",
  "hostname": "example.com",
  "links_count": 42,
  "images_count": 10
}
```

## Example 6: Multi-Step Workflow

A complex workflow involving navigation, interaction, and extraction.

```
User: Go to Wikipedia, search for "Python programming", and extract the first result

Claude: I'll search Wikipedia for Python programming and extract the article.
```

Claude will use:
```python
# 1. Navigate to Wikipedia
await browser_navigate_to_url("https://en.wikipedia.org")

# 2. Fill search box and submit
await browser_execute_script("""
  document.querySelector('#searchInput').value = 'Python programming';
  document.querySelector('form').submit();
""")

# 3. Wait for results to load (could also use navigate with wait_for_load)
import asyncio
await asyncio.sleep(2)

# 4. Extract the article
markdown = await browser_extract_current_page(selector="#content")
```

## Example 7: Data Collection from Multiple Pages

Collect data from multiple pages programmatically.

```
User: Get the titles and URLs of all blog posts from the current page

Claude: I'll extract the blog post information.
```

Claude will use:
```python
# Get all blog post links
posts_json = await browser_execute_script("""
  Array.from(document.querySelectorAll('.blog-post')).map(post => ({
    title: post.querySelector('h2').textContent,
    url: post.querySelector('a').href,
    excerpt: post.querySelector('.excerpt').textContent
  }))
""")

# Parse results
import json
posts = json.loads(posts_json)

# Optionally: Visit each post and extract full content
for post in posts[:5]:  # First 5 posts
    await browser_navigate_to_url(post['url'])
    markdown = await browser_extract_current_page(selector='.post-content')
    # Process markdown...
```

## Example 8: Check Element Existence

Check if specific elements exist before interacting.

```
User: Check if there's a login button on the current page

Claude: I'll check for a login button.
```

Claude will use:
```python
result = await browser_execute_script("""
  const loginBtn = document.querySelector('button.login, a.login, #login-btn');
  if (loginBtn) {
    return {
      found: true,
      text: loginBtn.textContent.trim(),
      href: loginBtn.href || null
    };
  }
  return { found: false };
""")
```

## Example 9: Monitor Page Changes

Watch for changes on a page (useful for dashboards, live data, etc.).

```
User: Check if the stock price on this page changes in the next minute

Claude: I'll monitor the stock price for changes.
```

Claude will use:
```python
import asyncio

# Get initial price
initial = await browser_execute_script("""
  document.querySelector('.stock-price').textContent
""")

# Wait 60 seconds
await asyncio.sleep(60)

# Get current price
current = await browser_execute_script("""
  document.querySelector('.stock-price').textContent
""")

# Compare
if initial != current:
    return f"Price changed from {initial} to {current}"
else:
    return f"Price unchanged: {initial}"
```

## Example 10: Form Automation

Automate form filling (use with caution).

```
User: Fill out the contact form on this page

Claude: I'll help fill the contact form. What details should I use?

User: Name: John Doe, Email: john@example.com, Message: Test message

Claude: I'll fill the form with those details.
```

Claude will use:
```python
await browser_execute_script("""
  document.querySelector('#name').value = 'John Doe';
  document.querySelector('#email').value = 'john@example.com';
  document.querySelector('#message').value = 'Test message';
""")

# Optionally submit
# await browser_execute_script("document.querySelector('form').submit()")
```

## Example 11: Screenshot Data Extraction

Extract data that might be in images or canvases.

```
User: Get the text content from all headings on this page

Claude: I'll extract all heading text.
```

Claude will use:
```python
headings = await browser_execute_script("""
  Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => ({
    level: h.tagName.toLowerCase(),
    text: h.textContent.trim(),
    id: h.id || null
  }))
""")
```

## Example 12: Connection Status Check

Check if the browser extension is connected before attempting operations.

```
User: Is my browser extension connected?

Claude: Let me check the browser extension connection.
```

Claude will use:
```python
status = await browser_check_connection()
# Returns: "Browser extension is connected and ready."
# or "No browser extension connected. Please open the browser extension."
```

## Tips for Best Results

1. **Always check connection first** if unsure:
   ```python
   await browser_check_connection()
   ```

2. **Use selectors for targeted extraction**:
   - `selector="article"` - Main article
   - `selector=".content"` - Element with class "content"
   - `selector="#main"` - Element with id "main"

3. **Handle timeouts appropriately**:
   ```python
   # For slow pages, increase timeout
   await browser_navigate_to_url(url, timeout=60.0)
   ```

4. **Parse JavaScript results**:
   ```python
   import json
   result = await browser_execute_script("...")
   data = json.loads(result)
   ```

5. **Wait for dynamic content**:
   ```python
   import asyncio
   await browser_navigate_to_url(url)
   await asyncio.sleep(2)  # Wait for JS to load
   await browser_extract_current_page()
   ```

6. **Error handling**:
   ```python
   try:
       result = await browser_extract_current_page()
   except RuntimeError as e:
       # Handle connection errors
       pass
   ```

## Security Best Practices

1. **Never execute untrusted scripts** in `browser_execute_script()`
2. **Be cautious with form automation** - only automate your own forms
3. **Don't store sensitive data** in extracted markdown
4. **Use HTTPS** when navigating to pages programmatically
5. **Validate user input** before passing to JavaScript execution

## Troubleshooting

**Extension not connected**:
- Check extension is installed and enabled
- Verify MCP server is running on localhost:8080
- Open extension popup to see connection status

**Commands timing out**:
- Increase timeout parameter
- Check browser tab is active
- Verify page has loaded completely

**Script execution errors**:
- Check JavaScript syntax
- Verify selectors exist on page
- Use browser DevTools console to test scripts first

**Navigation not working**:
- Ensure URL is valid
- Check for popups or dialogs blocking navigation
- Try without `wait_for_load` for faster operations
