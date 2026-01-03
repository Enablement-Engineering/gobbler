"""Browser session management for authenticated crawling."""

import json
import logging
from pathlib import Path

from ..config import get_config

logger = logging.getLogger(__name__)


class SessionManager:
    """Manage browser sessions with cookie and localStorage persistence."""

    def __init__(self):
        """Initialize session manager with config-based storage directory."""
        config = get_config()
        config_dir = Path(config.config_path).parent
        self.sessions_dir = config_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Session storage directory: %s", self.sessions_dir)

    async def create_session(
        self,
        session_id: str,
        cookies: list[dict] | None = None,
        local_storage: dict | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """Create and persist session to disk.

        Args:
            session_id: Unique identifier for the session
            cookies: List of cookie dicts with name, value, domain, path, etc.
            local_storage: Dictionary of localStorage key-value pairs
            user_agent: Custom user agent string

        Returns:
            Dictionary with session metadata

        Example:
            cookies = [
                {
                    "name": "session_token",
                    "value": "abc123",
                    "domain": "example.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True
                }
            ]
            local_storage = {"user_id": "12345", "theme": "dark"}
            session = await session_manager.create_session(
                "my-session",
                cookies=cookies,
                local_storage=local_storage,
                user_agent="CustomBot/1.0"
            )
        """
        session_data = {
            "session_id": session_id,
            "cookies": cookies or [],
            "local_storage": local_storage or {},
            "user_agent": user_agent,
        }

        session_file = self.sessions_dir / f"{session_id}.json"

        try:
            with session_file.open("w") as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            logger.exception("Failed to create session '%s'", session_id)
            msg = f"Failed to save session: {e}"
            raise RuntimeError(msg) from e
        else:
            logger.info(
                "Created session '%s' with %d cookies",
                session_id,
                len(session_data["cookies"]),
            )

            return {
                "session_id": session_id,
                "file_path": str(session_file),
                "cookie_count": len(session_data["cookies"]),
                "local_storage_keys": list(session_data["local_storage"].keys()),
                "has_user_agent": user_agent is not None,
            }

    async def load_session(self, session_id: str) -> dict:
        """Load session from disk.

        Args:
            session_id: Unique identifier for the session

        Returns:
            Dictionary with session data (cookies, local_storage, user_agent)

        Raises:
            FileNotFoundError: If session does not exist
        """
        session_file = self.sessions_dir / f"{session_id}.json"

        if not session_file.exists():
            msg = f"Session '{session_id}' not found"
            raise FileNotFoundError(msg)

        try:
            with session_file.open() as f:
                session_data = json.load(f)
        except json.JSONDecodeError as e:
            logger.exception("Failed to parse session '%s'", session_id)
            msg = f"Invalid session file: {e}"
            raise RuntimeError(msg) from e
        else:
            logger.info(
                "Loaded session '%s' with %d cookies",
                session_id,
                len(session_data.get("cookies", [])),
            )

            return session_data

    async def list_sessions(self) -> list[str]:
        """List all saved session IDs.

        Returns:
            List of session IDs
        """
        session_files = self.sessions_dir.glob("*.json")
        session_ids = [f.stem for f in session_files]

        logger.debug("Found %d sessions", len(session_ids))
        return sorted(session_ids)

    async def delete_session(self, session_id: str) -> bool:
        """Delete saved session.

        Args:
            session_id: Unique identifier for the session

        Returns:
            True if session was deleted, False if it didn't exist
        """
        session_file = self.sessions_dir / f"{session_id}.json"

        if not session_file.exists():
            logger.warning("Session '%s' not found for deletion", session_id)
            return False

        try:
            session_file.unlink()
        except Exception as e:
            logger.exception("Failed to delete session '%s'", session_id)
            msg = f"Failed to delete session: {e}"
            raise RuntimeError(msg) from e
        else:
            logger.info("Deleted session '%s'", session_id)
            return True

    async def update_session(
        self,
        session_id: str,
        cookies: list[dict] | None = None,
        local_storage: dict | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """Update existing session with new data.

        Args:
            session_id: Unique identifier for the session
            cookies: New cookies list (replaces existing if provided)
            local_storage: New localStorage dict (merges with existing if provided)
            user_agent: New user agent string (replaces existing if provided)

        Returns:
            Dictionary with updated session metadata

        Raises:
            FileNotFoundError: If session does not exist
        """
        # Load existing session
        session_data = await self.load_session(session_id)

        # Update fields if provided
        if cookies is not None:
            session_data["cookies"] = cookies
        if local_storage is not None:
            # Merge localStorage
            existing_storage = session_data.get("local_storage", {})
            existing_storage.update(local_storage)
            session_data["local_storage"] = existing_storage
        if user_agent is not None:
            session_data["user_agent"] = user_agent

        # Save updated session
        session_file = self.sessions_dir / f"{session_id}.json"

        try:
            with session_file.open("w") as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            logger.exception("Failed to update session '%s'", session_id)
            msg = f"Failed to update session: {e}"
            raise RuntimeError(msg) from e
        else:
            logger.info("Updated session '%s'", session_id)

            return {
                "session_id": session_id,
                "file_path": str(session_file),
                "cookie_count": len(session_data["cookies"]),
                "local_storage_keys": list(session_data["local_storage"].keys()),
                "has_user_agent": session_data.get("user_agent") is not None,
            }
