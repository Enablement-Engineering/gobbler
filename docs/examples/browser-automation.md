# Browser Automation Examples

Examples showing how to use Gobbler's browser automation capabilities.

## Prerequisites

1. Gobbler MCP server or CLI installed
2. Browser extension installed and connected
3. Target tabs in the "Gobbler" tab group

## Example 1: Extract Current Page

The simplest use case - extract the current browser page as markdown.

```bash
gobbler browser extract -o page.md
```

**MCP Tool**: `browser_extract_current_page()`

## Example 2: Extract Specific Content

Extract only a specific section using CSS selectors.

```bash
gobbler browser extract --selector "article.main" -o article.md
```

Common selectors:

| Content Type | Selector |
|-------------|----------|
| Main article | `article`, `.post-content` |
| Documentation | `main`, `.docs-content` |
| GitHub README | `.markdown-body` |

## Example 3: Navigate and Extract

Navigate to a URL and extract its content.

```bash
# Navigate
gobbler browser navigate "https://docs.python.org/3/tutorial/"

# Extract
gobbler browser extract -o tutorial.md
```

## Example 4: Execute JavaScript

Run JavaScript in the browser to get specific information.

```bash
# Get page title
gobbler browser exec "document.title"

# Get all image URLs
gobbler browser exec "Array.from(document.querySelectorAll('img')).map(img => img.src)"

# Count elements
gobbler browser exec "document.querySelectorAll('h1').length"
```

## Example 5: Get Page Metadata

```bash
gobbler browser exec "({
  title: document.title,
  url: window.location.href,
  links: document.querySelectorAll('a').length,
  images: document.querySelectorAll('img').length
})"
```

## Example 6: Multi-Step Workflow

Search Wikipedia and extract the result:

```bash
# Navigate to Wikipedia
gobbler browser navigate "https://en.wikipedia.org"

# Fill search and submit
gobbler browser exec "
  document.querySelector('#searchInput').value = 'Python programming';
  document.querySelector('form').submit();
"

# Wait for page load, then extract
sleep 2
gobbler browser extract --selector "#content" -o python.md
```

## Example 7: Data Collection

Extract structured data from a page:

```bash
gobbler browser exec "
  Array.from(document.querySelectorAll('.blog-post')).map(post => ({
    title: post.querySelector('h2')?.textContent,
    url: post.querySelector('a')?.href,
    excerpt: post.querySelector('.excerpt')?.textContent
  }))
"
```

## Example 8: Check Element Existence

```bash
gobbler browser exec "
  const loginBtn = document.querySelector('button.login, a.login, #login-btn');
  loginBtn ? { found: true, text: loginBtn.textContent } : { found: false }
"
```

## Example 9: Form Automation

Fill out a form (use with caution):

```bash
gobbler browser exec "
  document.querySelector('#name').value = 'John Doe';
  document.querySelector('#email').value = 'john@example.com';
  document.querySelector('#message').value = 'Test message';
"
```

## Example 10: Connection Check

Always check connection before operations:

```bash
gobbler browser status
```

## Tips for Best Results

1. **Always check connection first**
   ```bash
   gobbler browser status
   ```

2. **Use selectors for targeted extraction**
   - `--selector "article"` - Main article
   - `--selector ".content"` - Element with class
   - `--selector "#main"` - Element with id

3. **Handle timeouts appropriately**
   ```bash
   gobbler browser exec "..." --timeout 60
   ```

4. **Wait for dynamic content**
   ```bash
   gobbler browser navigate "https://example.com"
   sleep 2  # Wait for JS to load
   gobbler browser extract
   ```

## Security Best Practices

1. **Never execute untrusted scripts**
2. **Be cautious with form automation** - only automate your own forms
3. **Don't store sensitive data** in extracted markdown
4. **Use HTTPS** when navigating programmatically
5. **Validate input** before passing to JavaScript execution

## Troubleshooting

**Extension not connected**:
- Check extension is installed at `chrome://extensions/`
- Verify extension popup shows "Connected"

**Commands timing out**:
- Increase timeout: `--timeout 60`
- Check browser tab is active
- Verify page has loaded completely

**Script execution errors**:
- Check JavaScript syntax
- Verify selectors exist on page
- Test scripts in browser DevTools first

**Navigation not working**:
- Ensure URL is valid and complete
- Check for popups blocking navigation
