"""Interactive browser session creator for authenticated crawling."""

import asyncio
import logging
from typing import Dict, Optional

from playwright.async_api import async_playwright

from .session_manager import SessionManager

logger = logging.getLogger(__name__)


async def create_interactive_session(
    session_id: str,
    start_url: str = "https://www.google.com",
    instructions: Optional[str] = None,
    timeout: int = 300,
) -> Dict:
    """
    Launch interactive browser for manual login and save session cookies.

    Opens a headed browser window, navigates to start_url, and waits for you to
    complete the login process. When done, close the instructions tab to signal
    completion. All cookies (including HttpOnly) will be extracted and saved.

    Args:
        session_id: Unique identifier for the session
        start_url: URL to navigate to (default: Google homepage)
        instructions: Custom instructions to display (optional)
        timeout: Maximum wait time in seconds (default: 300 / 5 minutes)

    Returns:
        Dictionary with session metadata

    Example:
        # Create YouTube session interactively
        result = await create_interactive_session(
            session_id="youtube",
            start_url="https://www.youtube.com"
        )
        # Browser opens, you log in, close instructions tab when done
        # Session saved with all cookies including HttpOnly
    """
    default_instructions = f"""
    <html>
    <head>
        <title>Gobbler Session Creator - {session_id}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                max-width: 600px;
                margin: 100px auto;
                padding: 40px;
                background: #f5f5f5;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #333;
                margin-top: 0;
            }}
            .step {{
                margin: 20px 0;
                padding: 15px;
                background: #f0f7ff;
                border-left: 4px solid #0066cc;
                border-radius: 4px;
            }}
            .session-id {{
                font-family: monospace;
                background: #eee;
                padding: 2px 6px;
                border-radius: 3px;
            }}
            .warning {{
                color: #d93025;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 Interactive Session Creator</h1>
            <p>Creating session: <span class="session-id">{session_id}</span></p>

            <div class="step">
                <strong>Step 1:</strong> Switch to the other browser tab and log into your account
            </div>

            <div class="step">
                <strong>Step 2:</strong> Complete any 2FA or security checks
            </div>

            <div class="step">
                <strong>Step 3:</strong> When fully logged in, <span class="warning">close THIS tab</span>
            </div>

            <p>
                ℹ️ Closing this tab signals that you're done logging in.
                All cookies (including HttpOnly) will be automatically extracted and saved.
            </p>

            <p style="color: #666; font-size: 14px;">
                ⏱️ Timeout: {timeout} seconds
            </p>
        </div>
    </body>
    </html>
    """

    instructions_html = instructions or default_instructions

    logger.info(f"Starting interactive session creation for '{session_id}'")

    async with async_playwright() as p:
        # Launch headed browser
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]  # Reduce detection
        )

        try:
            # Create browser context
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )

            # Set page timeout to match our timeout parameter
            context.set_default_timeout(timeout * 1000)  # Convert to milliseconds

            # Open instructions page
            instructions_page = await context.new_page()
            await instructions_page.set_content(instructions_html)

            # Open target site in new tab
            site_page = await context.new_page()
            await site_page.goto(start_url, wait_until="domcontentloaded")

            # Bring site page to front
            await site_page.bring_to_front()

            logger.info(
                f"Browser opened. Navigate to login page and complete authentication. "
                f"Close the instructions tab when done."
            )

            # Wait for instructions page to be closed (signals completion)
            try:
                await asyncio.wait_for(
                    instructions_page.wait_for_event("close"),
                    timeout=timeout
                )
                logger.info("Instructions tab closed - extracting cookies")
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Interactive session creation timed out after {timeout} seconds"
                )

            # Extract all cookies from context (includes HttpOnly)
            cookies = await context.cookies()

            # Convert to session format
            session_cookies = []
            for cookie in cookies:
                session_cookie = {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie["domain"],
                    "path": cookie["path"],
                }
                # Add optional fields if present
                if "expires" in cookie and cookie["expires"] != -1:
                    session_cookie["expires"] = cookie["expires"]
                if cookie.get("httpOnly"):
                    session_cookie["httpOnly"] = True
                if cookie.get("secure"):
                    session_cookie["secure"] = True
                if cookie.get("sameSite"):
                    session_cookie["sameSite"] = cookie["sameSite"]

                session_cookies.append(session_cookie)

            # Save session using SessionManager
            session_manager = SessionManager()
            result = await session_manager.create_session(
                session_id=session_id,
                cookies=session_cookies,
            )

            logger.info(
                f"Session '{session_id}' created with {len(session_cookies)} cookies "
                f"(including HttpOnly)"
            )

            # Close browser
            await context.close()
            await browser.close()

            return {
                "session_id": session_id,
                "cookies_extracted": len(session_cookies),
                "http_only_cookies": sum(
                    1 for c in session_cookies if c.get("httpOnly", False)
                ),
                "storage_path": result["file_path"],
                "domains": list(set(c["domain"] for c in session_cookies)),
            }

        except Exception as e:
            logger.error(f"Failed to create interactive session '{session_id}': {e}")
            # Clean up browser on error
            try:
                await browser.close()
            except Exception:
                pass
            raise
