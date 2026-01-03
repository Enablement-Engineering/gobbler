"""Unit tests for the provider registry."""

import pytest

from gobbler_core.providers.base import ContentProvider, ProviderResult
from gobbler_core.providers.registry import ProviderNotFoundError, ProviderRegistry


class MockProvider(ContentProvider):
    """Mock provider for testing."""

    def __init__(self, value: str = "default") -> None:
        """Initialize mock provider."""
        self.value = value

    @property
    def name(self) -> str:
        """Return provider name."""
        return "mock-provider"

    async def fetch(self, source: str, **options) -> ProviderResult:
        """Fetch content."""
        return ProviderResult(
            success=True,
            content=f"mocked: {source}",
            metadata={"value": self.value},
        )

    def supports(self, source: str) -> bool:
        """Check if source is supported."""
        return source.startswith("mock://")


class AnotherMockProvider(ContentProvider):
    """Another mock provider for testing."""

    @property
    def name(self) -> str:
        """Return provider name."""
        return "another-mock"

    async def fetch(self, source: str, **options) -> ProviderResult:
        """Fetch content."""
        return ProviderResult(
            success=True,
            content="another mock",
            metadata={},
        )

    def supports(self, source: str) -> bool:
        """Check if source is supported."""
        return True


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def setup_method(self) -> None:
        """Clear registry before each test."""
        ProviderRegistry.clear()

    def teardown_method(self) -> None:
        """Clear registry after each test."""
        ProviderRegistry.clear()

    def test_register_provider(self) -> None:
        """Test registering a provider."""
        ProviderRegistry.register("test", "mock-provider", MockProvider)

        assert "test" in ProviderRegistry.list_categories()
        assert "mock-provider" in ProviderRegistry.list_providers("test")

    def test_register_multiple_providers(self) -> None:
        """Test registering multiple providers in same category."""
        ProviderRegistry.register("test", "mock-one", MockProvider)
        ProviderRegistry.register("test", "mock-two", AnotherMockProvider)

        providers = ProviderRegistry.list_providers("test")
        assert len(providers) == 2
        assert "mock-one" in providers
        assert "mock-two" in providers

    def test_register_overwrites_existing(self) -> None:
        """Test that registering same name overwrites."""
        ProviderRegistry.register("test", "mock", MockProvider)
        ProviderRegistry.register("test", "mock", AnotherMockProvider)

        provider_class = ProviderRegistry.get("test", "mock")
        assert provider_class == AnotherMockProvider

    def test_get_provider_class(self) -> None:
        """Test getting a registered provider class."""
        ProviderRegistry.register("test", "mock", MockProvider)

        provider_class = ProviderRegistry.get("test", "mock")
        assert provider_class == MockProvider

    def test_get_nonexistent_provider_raises(self) -> None:
        """Test that getting nonexistent provider raises error."""
        with pytest.raises(ProviderNotFoundError) as exc_info:
            ProviderRegistry.get("test", "nonexistent")

        assert exc_info.value.category == "test"
        assert exc_info.value.name == "nonexistent"

    def test_create_provider_instance(self) -> None:
        """Test creating a provider instance."""
        ProviderRegistry.register("test", "mock", MockProvider)

        provider = ProviderRegistry.create("test", "mock", value="custom")
        assert isinstance(provider, MockProvider)
        assert provider.value == "custom"

    def test_create_with_default_args(self) -> None:
        """Test creating provider with default arguments."""
        ProviderRegistry.register("test", "mock", MockProvider)

        provider = ProviderRegistry.create("test", "mock")
        assert isinstance(provider, MockProvider)
        assert provider.value == "default"

    def test_unregister_provider(self) -> None:
        """Test unregistering a provider."""
        ProviderRegistry.register("test", "mock", MockProvider)
        assert ProviderRegistry.unregister("test", "mock")
        assert "mock" not in ProviderRegistry.list_providers("test")

    def test_unregister_nonexistent_returns_false(self) -> None:
        """Test unregistering nonexistent provider returns False."""
        assert not ProviderRegistry.unregister("test", "nonexistent")

    def test_list_categories(self) -> None:
        """Test listing all categories."""
        ProviderRegistry.register("cat1", "provider1", MockProvider)
        ProviderRegistry.register("cat2", "provider2", AnotherMockProvider)

        categories = ProviderRegistry.list_categories()
        assert "cat1" in categories
        assert "cat2" in categories

    def test_list_providers_empty_category(self) -> None:
        """Test listing providers in empty/nonexistent category."""
        providers = ProviderRegistry.list_providers("nonexistent")
        assert providers == []

    def test_get_provider_info(self) -> None:
        """Test getting provider information."""
        ProviderRegistry.register("test", "mock", MockProvider)

        info = ProviderRegistry.get_provider_info("test", "mock")
        assert info["category"] == "test"
        assert info["name"] == "mock"
        assert info["class"] == "MockProvider"
        assert "Mock provider for testing" in info["doc"]

    def test_clear_registry(self) -> None:
        """Test clearing the registry."""
        ProviderRegistry.register("test", "mock", MockProvider)
        ProviderRegistry.clear()

        assert ProviderRegistry.list_categories() == []


class TestProviderNotFoundError:
    """Tests for ProviderNotFoundError."""

    def test_error_message_format(self) -> None:
        """Test error message includes category and name."""
        error = ProviderNotFoundError("transcription", "invalid-provider")

        assert "invalid-provider" in str(error)
        assert "transcription" in str(error)

    def test_error_shows_available_providers(self) -> None:
        """Test error message shows available providers."""
        ProviderRegistry.register("transcription", "whisper", MockProvider)

        error = ProviderNotFoundError("transcription", "invalid")
        assert "whisper" in str(error)

        ProviderRegistry.clear()

    def test_error_attributes(self) -> None:
        """Test error has correct attributes."""
        error = ProviderNotFoundError("document", "missing")

        assert error.category == "document"
        assert error.name == "missing"
