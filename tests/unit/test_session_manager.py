"""Unit tests for session manager."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from gobbler_mcp.crawlers.session_manager import SessionManager


@pytest.fixture
def mock_config():
    """Mock configuration with sessions directory."""
    mock_cfg = MagicMock()
    mock_cfg.config_path = "/home/user/.config/gobbler/config.yml"
    return mock_cfg


@pytest.fixture
def session_manager(mock_config, tmp_path):
    """Create session manager with temp directory."""
    with patch("gobbler_mcp.crawlers.session_manager.get_config", return_value=mock_config):
        with patch("gobbler_mcp.crawlers.session_manager.Path") as mock_path_class:
            # Make parent return tmp_path
            mock_parent = MagicMock()
            mock_parent.__truediv__ = lambda self, x: tmp_path / x

            mock_path_instance = MagicMock()
            mock_path_instance.parent = mock_parent
            mock_path_class.return_value = mock_path_instance

            manager = SessionManager.__new__(SessionManager)
            manager.sessions_dir = tmp_path / "sessions"
            manager.sessions_dir.mkdir(parents=True, exist_ok=True)
            return manager


class TestCreateSession:
    """Tests for creating sessions."""

    @pytest.mark.asyncio
    async def test_create_session_with_cookies(self, session_manager):
        """Test creating a session with cookies."""
        cookies = [{"name": "session_token", "value": "abc123", "domain": "example.com"}]

        result = await session_manager.create_session(session_id="test-session", cookies=cookies)

        assert result["session_id"] == "test-session"
        assert result["cookie_count"] == 1
        assert result["has_user_agent"] is False
        assert "file_path" in result

        # Verify file was created
        session_file = session_manager.sessions_dir / "test-session.json"
        assert session_file.exists()

        # Verify content
        with open(session_file) as f:
            data = json.load(f)
        assert data["cookies"] == cookies

    @pytest.mark.asyncio
    async def test_create_session_with_local_storage(self, session_manager):
        """Test creating a session with localStorage."""
        local_storage = {"user_id": "12345", "theme": "dark"}

        result = await session_manager.create_session(
            session_id="storage-session", local_storage=local_storage
        )

        assert result["session_id"] == "storage-session"
        assert result["local_storage_keys"] == ["user_id", "theme"]

        # Verify file content
        session_file = session_manager.sessions_dir / "storage-session.json"
        with open(session_file) as f:
            data = json.load(f)
        assert data["local_storage"] == local_storage

    @pytest.mark.asyncio
    async def test_create_session_with_user_agent(self, session_manager):
        """Test creating a session with custom user agent."""
        result = await session_manager.create_session(
            session_id="ua-session", user_agent="CustomBot/1.0"
        )

        assert result["has_user_agent"] is True

        # Verify file content
        session_file = session_manager.sessions_dir / "ua-session.json"
        with open(session_file) as f:
            data = json.load(f)
        assert data["user_agent"] == "CustomBot/1.0"

    @pytest.mark.asyncio
    async def test_create_session_with_all_options(self, session_manager):
        """Test creating a session with all options."""
        cookies = [{"name": "auth", "value": "token123", "domain": "test.com"}]
        local_storage = {"key1": "value1"}
        user_agent = "TestAgent/2.0"

        result = await session_manager.create_session(
            session_id="full-session",
            cookies=cookies,
            local_storage=local_storage,
            user_agent=user_agent,
        )

        assert result["cookie_count"] == 1
        assert result["local_storage_keys"] == ["key1"]
        assert result["has_user_agent"] is True

    @pytest.mark.asyncio
    async def test_create_session_empty(self, session_manager):
        """Test creating a session with no data."""
        result = await session_manager.create_session(session_id="empty-session")

        assert result["cookie_count"] == 0
        assert result["local_storage_keys"] == []
        assert result["has_user_agent"] is False


class TestLoadSession:
    """Tests for loading sessions."""

    @pytest.mark.asyncio
    async def test_load_session_success(self, session_manager):
        """Test loading an existing session."""
        # Create session file
        session_data = {
            "session_id": "existing-session",
            "cookies": [{"name": "token", "value": "xyz"}],
            "local_storage": {"pref": "value"},
            "user_agent": "MyAgent",
        }
        session_file = session_manager.sessions_dir / "existing-session.json"
        with open(session_file, "w") as f:
            json.dump(session_data, f)

        result = await session_manager.load_session("existing-session")

        assert result["session_id"] == "existing-session"
        assert len(result["cookies"]) == 1
        assert result["local_storage"]["pref"] == "value"
        assert result["user_agent"] == "MyAgent"

    @pytest.mark.asyncio
    async def test_load_session_not_found(self, session_manager):
        """Test loading a non-existent session raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Session 'nonexistent' not found"):
            await session_manager.load_session("nonexistent")

    @pytest.mark.asyncio
    async def test_load_session_corrupted_json(self, session_manager):
        """Test loading a session with corrupted JSON raises RuntimeError."""
        # Create corrupted file
        session_file = session_manager.sessions_dir / "corrupted-session.json"
        with open(session_file, "w") as f:
            f.write("{not valid json")

        with pytest.raises(RuntimeError, match="Invalid session file"):
            await session_manager.load_session("corrupted-session")


class TestListSessions:
    """Tests for listing sessions."""

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, session_manager):
        """Test listing sessions when none exist."""
        result = await session_manager.list_sessions()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_sessions_multiple(self, session_manager):
        """Test listing multiple sessions."""
        # Create some session files
        for name in ["alpha", "beta", "gamma"]:
            session_file = session_manager.sessions_dir / f"{name}.json"
            with open(session_file, "w") as f:
                json.dump({"session_id": name}, f)

        result = await session_manager.list_sessions()

        assert len(result) == 3
        assert result == ["alpha", "beta", "gamma"]  # Should be sorted


class TestDeleteSession:
    """Tests for deleting sessions."""

    @pytest.mark.asyncio
    async def test_delete_session_success(self, session_manager):
        """Test deleting an existing session."""
        # Create session file
        session_file = session_manager.sessions_dir / "to-delete.json"
        with open(session_file, "w") as f:
            json.dump({"session_id": "to-delete"}, f)

        result = await session_manager.delete_session("to-delete")

        assert result is True
        assert not session_file.exists()

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, session_manager):
        """Test deleting a non-existent session returns False."""
        result = await session_manager.delete_session("nonexistent")
        assert result is False


class TestUpdateSession:
    """Tests for updating sessions."""

    @pytest.mark.asyncio
    async def test_update_session_cookies(self, session_manager):
        """Test updating session cookies."""
        # Create initial session
        await session_manager.create_session(
            session_id="update-test", cookies=[{"name": "old", "value": "cookie"}]
        )

        # Update cookies
        new_cookies = [{"name": "new", "value": "cookie"}]
        result = await session_manager.update_session(session_id="update-test", cookies=new_cookies)

        assert result["cookie_count"] == 1

        # Verify update
        session_data = await session_manager.load_session("update-test")
        assert session_data["cookies"] == new_cookies

    @pytest.mark.asyncio
    async def test_update_session_merges_local_storage(self, session_manager):
        """Test updating session merges localStorage."""
        # Create initial session
        await session_manager.create_session(
            session_id="merge-test", local_storage={"key1": "value1"}
        )

        # Update with additional localStorage
        result = await session_manager.update_session(
            session_id="merge-test", local_storage={"key2": "value2"}
        )

        # Verify merge
        session_data = await session_manager.load_session("merge-test")
        assert session_data["local_storage"] == {"key1": "value1", "key2": "value2"}

    @pytest.mark.asyncio
    async def test_update_session_not_found(self, session_manager):
        """Test updating a non-existent session raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await session_manager.update_session(session_id="nonexistent", cookies=[])
