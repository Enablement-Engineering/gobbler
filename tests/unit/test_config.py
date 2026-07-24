"""Unit tests for configuration management."""

import threading
from collections.abc import Iterator, Mapping
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from gobbler_core.config import Config, _ConfigLoader, get_config


def create_test_config(data: dict) -> Config:
    """Create a Config instance for testing without loading from file."""
    config = Config.__new__(Config)
    config._lock = threading.RLock()
    config.data = data
    return config


class TestConfigLoading:
    """Test configuration loading and defaults."""

    def test_config_defaults_exist(self):
        """Test that default configuration values are defined."""
        assert "whisper" in Config.DEFAULTS
        assert "services" in Config.DEFAULTS
        assert "redis" in Config.DEFAULTS
        assert Config.DEFAULTS["whisper"]["model"] == "small"

    @patch("gobbler_core.config.Path")
    def test_config_loads_defaults_when_no_file(self, mock_path_class):
        """Test that defaults are used when config file doesn't exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path_class.home.return_value = Path("/home/user")

        config = Config(config_path=mock_path)

        assert config.data["whisper"]["model"] == "small"
        assert config.data["services"]["crawl4ai"]["port"] == 11235

    @patch("gobbler_core.config.Path")
    def test_config_merges_user_config(self, mock_path_class):
        """Test that user config is merged over defaults."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.home.return_value = Path("/home/user")

        # Mock Path.open() to return a file-like object with YAML content
        mock_path.open = mock_open(read_data="whisper:\n  model: large\n")

        config = Config(config_path=mock_path)

        # User override should be applied
        assert config.data["whisper"]["model"] == "large"
        # Other defaults should remain
        assert config.data["whisper"]["language"] == "auto"

    def test_config_canonicalizes_documented_fallback_on_key(self, tmp_path: Path) -> None:
        """Test that PyYAML's fallback ``on`` coercion is repaired during loading."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers:\n"
            "  youtube:\n"
            "    youtube-transcript-api:\n"
            "      fallback:\n"
            "        provider: transcriptapi\n"
            "        on: [ip_blocked, rate_limited]\n"
            "  document:\n"
            "    docling:\n"
            "      ocr: true\n"
        )

        config = Config(config_path=config_path)
        fallback = config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"]

        assert fallback == {
            "provider": "transcriptapi",
            "on": ["ip_blocked", "rate_limited"],
        }
        assert True not in fallback
        assert config.data["providers"]["document"]["docling"]["ocr"] is True
        assert config.get_provider_fallback("youtube", "youtube-transcript-api") == fallback

    def test_config_canonicalizes_fallback_on_after_large_prefix(self, tmp_path: Path) -> None:
        """Test lexical key detection uses stable source offsets beyond PyYAML's read buffer."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            f"padding: {'x' * 6000}\n"
            "providers:\n"
            "  youtube:\n"
            "    youtube-transcript-api:\n"
            "      fallback: {provider: transcriptapi, on: [rate_limited]}\n"
        )

        config = Config(config_path=config_path)
        fallback = config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"]

        assert fallback == {"provider": "transcriptapi", "on": ["rate_limited"]}

    def test_config_does_not_rewrite_non_on_fallback_keys(self, tmp_path: Path) -> None:
        """Test that numeric, explicit boolean, and unrelated mappings remain unchanged."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "numeric:\n"
            "  fallback: {provider: numeric-provider, 1: keep-numeric}\n"
            "boolean:\n"
            "  fallback: {provider: boolean-provider, true: keep-boolean}\n"
            "unrelated:\n"
            "  fallback: {on: keep-coerced-without-provider}\n"
            "metadata:\n"
            "  fallback: {provider: metadata-provider, on: keep-unrelated}\n"
            "provider_metadata: {provider: metadata-provider, on: keep-unrelated}\n"
        )

        config = Config(config_path=config_path)

        assert config.data["numeric"]["fallback"] == {
            "provider": "numeric-provider",
            1: "keep-numeric",
        }
        assert config.data["boolean"]["fallback"] == {
            "provider": "boolean-provider",
            True: "keep-boolean",
        }
        assert config.data["unrelated"]["fallback"] == {True: "keep-coerced-without-provider"}
        assert config.data["metadata"]["fallback"] == {
            "provider": "metadata-provider",
            True: "keep-unrelated",
        }
        assert config.data["provider_metadata"] == {
            "provider": "metadata-provider",
            True: "keep-unrelated",
        }

        config.reload()

        assert config.data["numeric"]["fallback"][1] == "keep-numeric"
        assert config.data["boolean"]["fallback"][True] == "keep-boolean"
        assert config.data["unrelated"]["fallback"][True] == "keep-coerced-without-provider"
        assert config.data["metadata"]["fallback"][True] == "keep-unrelated"
        assert config.data["provider_metadata"][True] == "keep-unrelated"

    def test_config_preserves_explicit_tags_and_duplicate_on_keys(self, tmp_path: Path) -> None:
        """Test canonicalization does not override explicit tags or collapse distinct keys."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers:\n"
            "  youtube:\n"
            "    explicit-bool:\n"
            "      fallback: {provider: transcriptapi, !!bool on: [ip_blocked]}\n"
            "    duplicate:\n"
            "      fallback:\n"
            "        provider: transcriptapi\n"
            "        on: [ip_blocked]\n"
            '        "on": [rate_limited]\n'
        )

        config = Config(config_path=config_path)

        assert config.data["providers"]["youtube"]["explicit-bool"]["fallback"] == {
            "provider": "transcriptapi",
            True: ["ip_blocked"],
        }
        assert config.data["providers"]["youtube"]["duplicate"]["fallback"] == {
            "provider": "transcriptapi",
            "on": ["rate_limited"],
        }

    def test_config_collapses_duplicate_plain_on_keys_with_last_value(self, tmp_path: Path) -> None:
        """Test duplicate documented keys retain normal last-key precedence."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers:\n"
            "  youtube:\n"
            "    youtube-transcript-api:\n"
            "      fallback:\n"
            "        provider: transcriptapi\n"
            "        on: [ip_blocked]\n"
            "        on: [rate_limited]\n"
        )

        config = Config(config_path=config_path)

        assert config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"] == {
            "provider": "transcriptapi",
            "on": ["rate_limited"],
        }

    def test_config_preserves_invalid_explicit_tag_failure(self, tmp_path: Path) -> None:
        """Test an invalid explicit tag still rejects the user config like SafeLoader."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "output:\n"
            "  default_format: json\n"
            "providers:\n"
            "  youtube:\n"
            "    youtube-transcript-api:\n"
            "      fallback: {provider: transcriptapi, !!int on: [rate_limited]}\n"
        )

        config = Config(config_path=config_path)

        assert config.data["output"]["default_format"] == "frontmatter"

    def test_config_loader_preserves_unrelated_alias_identity(self) -> None:
        """Test documents without a target fallback retain SafeLoader alias identity."""
        loader = _ConfigLoader(
            "shared: &shared {value: 1}\n"
            "metadata: *shared\n"
            "providers: {custom: {provider: *shared}}\n"
        )
        try:
            data = loader.get_single_data()
        finally:
            loader.dispose()

        assert data["shared"] is data["metadata"]
        assert data["shared"] is data["providers"]["custom"]["provider"]

    def test_config_loader_preserves_root_back_references(self) -> None:
        """Test compatibility repair does not clone an unrelated recursive document root."""
        loader = _ConfigLoader("&root\nself: *root\nnested: [*root]\n")
        try:
            data = loader.get_single_data()
        finally:
            loader.dispose()

        assert data["self"] is data
        assert data["nested"][0] is data

    def test_config_loader_preserves_root_back_references_during_repair(self) -> None:
        """Test a repaired provider path retains direct and nested document-root aliases."""
        loader = _ConfigLoader(
            "&root\n"
            "self: *root\n"
            "nested: [*root]\n"
            "providers:\n"
            "  youtube:\n"
            "    youtube-transcript-api:\n"
            "      fallback: {provider: transcriptapi, on: [rate_limited]}\n"
        )
        try:
            data = loader.get_single_data()
        finally:
            loader.dispose()

        assert data["self"] is data
        assert data["nested"][0] is data

    def test_config_loader_preserves_all_provider_path_back_references(self) -> None:
        """Test repair keeps self aliases at each cloned provider path level."""
        loader = _ConfigLoader(
            "providers: &providers\n"
            "  self: *providers\n"
            "  youtube: &category\n"
            "    self: *category\n"
            "    youtube-transcript-api: &provider\n"
            "      self: *provider\n"
            "      fallback: {provider: transcriptapi, on: [rate_limited]}\n"
        )
        try:
            data = loader.get_single_data()
        finally:
            loader.dispose()

        providers = data["providers"]
        category = providers["youtube"]
        provider = category["youtube-transcript-api"]
        assert providers["self"] is providers
        assert category["self"] is category
        assert provider["self"] is provider

    def test_config_loader_preserves_pairs_ancestor_back_references(self) -> None:
        """Test YAML pairs containing provider ancestors follow repaired path identity."""
        loader = _ConfigLoader(
            "providers:\n"
            "  youtube:\n"
            "    p: &provider\n"
            "      fallback:\n"
            "        provider: transcriptapi\n"
            "        on: [rate_limited]\n"
            "        refs: !!pairs [owner: *provider]\n"
        )
        try:
            loaded = loader.get_single_data()
        finally:
            loader.dispose()

        provider = loaded["providers"]["youtube"]["p"]
        assert provider["fallback"]["refs"][0][1] is provider
        assert provider["fallback"]["on"] == ["rate_limited"]

        merged = Config._deep_merge(Config.DEFAULTS, loaded)
        merged_provider = merged["providers"]["youtube"]["p"]
        assert merged_provider["fallback"]["refs"][0][1] is merged_provider
        assert merged_provider["fallback"]["on"] == ["rate_limited"]

    def test_config_loader_rewrites_provider_sibling_aliases_once(self) -> None:
        """Test sibling aliases to repaired paths retain canonical identity."""
        loader = _ConfigLoader(
            "providers:\n"
            "  youtube:\n"
            "    p: &provider\n"
            "      fallback: &fallback {provider: transcriptapi, on: [rate_limited]}\n"
            "      fallback_copy: *fallback\n"
            "      first: &wrapper [*provider]\n"
            "      second: *wrapper\n"
        )
        try:
            data = loader.get_single_data()
        finally:
            loader.dispose()

        provider = data["providers"]["youtube"]["p"]
        assert provider["fallback_copy"] is provider["fallback"]
        assert provider["fallback"]["on"] == ["rate_limited"]
        assert provider["first"] is provider["second"]
        assert provider["first"][0] is provider

    def test_config_loader_handles_deep_alias_chains_iteratively(self) -> None:
        """Test valid deep alias chains do not exceed Python recursion depth during repair."""
        aliases = ["      link0: &link0 [*provider]"]
        aliases.extend(
            f"      link{index}: &link{index} [*link{index - 1}]" for index in range(1, 1100)
        )
        source = (
            "providers:\n"
            "  youtube:\n"
            "    p: &provider\n" + "\n".join(aliases) + "\n"
            "      fallback:\n"
            "        provider: transcriptapi\n"
            "        on: [rate_limited]\n"
            "        refs: *link1099\n"
        )
        loader = _ConfigLoader(source)
        try:
            data = loader.get_single_data()
        finally:
            loader.dispose()

        provider = data["providers"]["youtube"]["p"]
        current = provider["fallback"]["refs"]
        for _index in range(1100):
            current = current[0]
        assert current is provider

    def test_config_loader_preserves_shared_repaired_payload_projection(self) -> None:
        """Test equivalent ancestor rewrites reuse one shared payload clone."""
        loader = _ConfigLoader(
            "&root\n"
            "payload: &payload [*root]\n"
            "providers:\n"
            "  youtube:\n"
            "    first:\n"
            "      fallback: {provider: x, on: [a], payload: *payload}\n"
            "    second:\n"
            "      fallback: {provider: y, on: [b], payload: *payload}\n"
        )
        try:
            data = loader.get_single_data()
        finally:
            loader.dispose()

        first = data["providers"]["youtube"]["first"]["fallback"]["payload"]
        second = data["providers"]["youtube"]["second"]["fallback"]["payload"]
        assert first is second
        assert first is data["payload"]
        assert first[0] is data

    def test_config_loader_preserves_shared_target_fallback_identity(self) -> None:
        """Test one aliased fallback repaired at multiple target paths stays shared."""
        loader = _ConfigLoader(
            "shared: &fallback {provider: transcriptapi, on: [rate_limited]}\n"
            "providers:\n"
            "  youtube:\n"
            "    first: {fallback: *fallback}\n"
            "    second: {fallback: *fallback}\n"
        )
        try:
            data = loader.get_single_data()
        finally:
            loader.dispose()

        first = data["providers"]["youtube"]["first"]["fallback"]
        second = data["providers"]["youtube"]["second"]["fallback"]
        assert first is second
        assert first == {"provider": "transcriptapi", "on": ["rate_limited"]}
        assert data["shared"] == {"provider": "transcriptapi", True: ["rate_limited"]}

    def test_config_rewrites_backrefs_without_enumerating_all_replacements(self) -> None:
        """Test each fallback repair performs only graph-reachable replacement lookups."""

        class LookupOnlyReplacements(Mapping[int, object]):
            """Mapping that rejects whole-map iteration and sizing."""

            _ITERATION_ERROR = "replacement mappings must not be enumerated per fallback"
            _LENGTH_ERROR = "replacement mappings must not be sized per fallback"

            def __init__(self, values: dict[int, object]) -> None:
                self._values = values

            def __getitem__(self, key: int) -> object:
                return self._values[key]

            def __iter__(self) -> Iterator[int]:
                raise AssertionError(self._ITERATION_ERROR)

            def __len__(self) -> int:
                raise AssertionError(self._LENGTH_ERROR)

        original: dict[str, object] = {}
        repaired: dict[str, object] = {}
        value = [original]

        result = _ConfigLoader._rewrite_backrefs(
            value,
            LookupOnlyReplacements({id(original): repaired}),
        )

        assert result is not value
        assert result[0] is repaired

    def test_config_preserves_alias_heavy_fallback_graph(self, tmp_path: Path) -> None:
        """Test compact fallback alias graphs remain shared without custom merge expansion."""
        config_path = tmp_path / "config.yml"
        lines = ["alias_0: &alias_0 [leaf]"]
        lines.extend(
            f"alias_{index}: &alias_{index} [*alias_{index - 1}, *alias_{index - 1}]"
            for index in range(1, 30)
        )
        lines.extend(
            [
                "providers:",
                "  youtube:",
                "    youtube-transcript-api:",
                "      fallback:",
                "        provider: transcriptapi",
                "        on: [rate_limited]",
                "        payload: *alias_29",
            ]
        )
        config_path.write_text("\n".join(lines) + "\n")

        config = Config(config_path=config_path)
        payload = config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"][
            "payload"
        ]

        assert payload is config.data["alias_29"]
        for _index in range(29):
            assert payload[0] is payload[1]
            payload = payload[0]

    def test_config_canonicalizes_fallback_on_with_merged_provider(self, tmp_path: Path) -> None:
        """Test fallback schema detection when ``provider`` comes from a YAML merge."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "fallback_defaults: &fallback_defaults\n"
            "  provider: transcriptapi\n"
            "shared_fallback: &shared_fallback\n"
            "  provider: transcriptapi\n"
            "  on: [ip_blocked]\n"
            "providers:\n"
            "  youtube:\n"
            "    youtube-transcript-api:\n"
            "      fallback:\n"
            "        <<: *fallback_defaults\n"
            "        on: [rate_limited]\n"
            "    transcriptapi:\n"
            "      fallback: *shared_fallback\n"
        )

        config = Config(config_path=config_path)

        fallback = config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"]
        assert fallback == {"provider": "transcriptapi", "on": ["rate_limited"]}
        assert config.data["providers"]["youtube"]["transcriptapi"]["fallback"] == {
            "provider": "transcriptapi",
            "on": ["ip_blocked"],
        }
        assert config.data["fallback_defaults"] == {"provider": "transcriptapi"}
        assert config.data["shared_fallback"] == {
            "provider": "transcriptapi",
            True: ["ip_blocked"],
        }

    def test_config_preserves_recursive_merge_semantics_on_provider_path(
        self, tmp_path: Path
    ) -> None:
        """Test recursive YAML merges behave like SafeLoader while fallback is repaired."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers: &providers\n"
            "  <<: *providers\n"
            "  youtube:\n"
            "    youtube-transcript-api:\n"
            "      fallback: {provider: transcriptapi, on: [rate_limited]}\n"
        )

        config = Config(config_path=config_path)
        fallback = config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"]

        assert fallback == {"provider": "transcriptapi", "on": ["rate_limited"]}

    def test_config_canonicalizes_fallbacks_inherited_at_each_provider_path_level(
        self, tmp_path: Path
    ) -> None:
        """Test root, category, and provider merge inheritance share the canonical schema."""
        cases = {
            "root": (
                "base: &base\n"
                "  providers:\n"
                "    youtube:\n"
                "      default: youtube-transcript-api\n"
                "      youtube-transcript-api:\n"
                "        fallback: {provider: transcriptapi, on: [rate_limited]}\n"
                "<<: *base\n"
            ),
            "category": (
                "youtube_defaults: &youtube_defaults\n"
                "  youtube:\n"
                "    default: youtube-transcript-api\n"
                "    youtube-transcript-api:\n"
                "      fallback: {provider: transcriptapi, on: [rate_limited]}\n"
                "providers:\n"
                "  <<: *youtube_defaults\n"
            ),
            "provider": (
                "provider_defaults: &provider_defaults\n"
                "  fallback: {provider: transcriptapi, on: [rate_limited]}\n"
                "providers:\n"
                "  youtube:\n"
                "    default: youtube-transcript-api\n"
                "    youtube-transcript-api:\n"
                "      <<: *provider_defaults\n"
            ),
        }

        for name, source in cases.items():
            config_path = tmp_path / f"{name}.yml"
            config_path.write_text(source)
            config = Config(config_path=config_path)
            fallback = config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"]

            assert fallback == {"provider": "transcriptapi", "on": ["rate_limited"]}

    def test_config_isolates_aliased_provider_mapping_from_unrelated_consumers(
        self, tmp_path: Path
    ) -> None:
        """Test provider-path canonicalization does not retag external alias consumers."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "shared_provider: &shared_provider\n"
            "  fallback: {provider: transcriptapi, on: [rate_limited]}\n"
            "metadata: *shared_provider\n"
            "providers:\n"
            "  youtube:\n"
            "    default: youtube-transcript-api\n"
            "    youtube-transcript-api: *shared_provider\n"
        )

        config = Config(config_path=config_path)

        assert config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"] == {
            "provider": "transcriptapi",
            "on": ["rate_limited"],
        }
        assert config.data["shared_provider"]["fallback"] == {
            "provider": "transcriptapi",
            True: ["rate_limited"],
        }
        assert config.data["metadata"]["fallback"] == {
            "provider": "transcriptapi",
            True: ["rate_limited"],
        }

    def test_config_canonicalizes_last_effective_duplicate_provider_path(
        self, tmp_path: Path
    ) -> None:
        """Test an explicit providers mapping wins over a merged duplicate mapping."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "base: &base\n"
            "  providers:\n"
            "    youtube:\n"
            "      default: shadowed\n"
            "      shadowed:\n"
            "        fallback: {provider: transcriptapi, on: [ip_blocked]}\n"
            "<<: *base\n"
            "providers:\n"
            "  youtube:\n"
            "    default: youtube-transcript-api\n"
            "    youtube-transcript-api:\n"
            "      fallback: {provider: transcriptapi, on: [rate_limited]}\n"
        )

        config = Config(config_path=config_path)

        assert config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"] == {
            "provider": "transcriptapi",
            "on": ["rate_limited"],
        }

    def test_config_does_not_retag_shadowed_fallback_reachable_from_effective_value(
        self, tmp_path: Path
    ) -> None:
        """Test duplicate fallback precedence cannot mutate an aliased shadowed mapping."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers:\n"
            "  youtube:\n"
            "    youtube-transcript-api:\n"
            "      fallback: &shadowed\n"
            "        provider: old\n"
            "        on: [ip_blocked]\n"
            "      fallback:\n"
            "        provider: transcriptapi\n"
            "        on: [rate_limited]\n"
            "        payload: *shadowed\n"
        )

        config = Config(config_path=config_path)
        fallback = config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"]

        assert fallback["on"] == ["rate_limited"]
        assert fallback["payload"] == {"provider": "old", True: ["ip_blocked"]}

    def test_config_does_not_retag_shared_fallback_nested_in_another_target(
        self, tmp_path: Path
    ) -> None:
        """Test each target fallback gets a path-local alias replacement boundary."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "shared: &shared {provider: nested, on: [ip_blocked]}\n"
            "providers:\n"
            "  youtube:\n"
            "    first: {fallback: *shared}\n"
            "    second:\n"
            "      fallback:\n"
            "        provider: direct\n"
            "        on: [rate_limited]\n"
            "        payload: *shared\n"
        )

        config = Config(config_path=config_path)
        providers = config.data["providers"]["youtube"]

        assert providers["first"]["fallback"]["on"] == ["ip_blocked"]
        assert providers["second"]["fallback"]["payload"] == {
            "provider": "nested",
            True: ["ip_blocked"],
        }

    def test_config_ignores_shadowed_duplicate_provider_mapping(self, tmp_path: Path) -> None:
        """Test only the last effective provider mapping is canonicalized."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers:\n"
            "  youtube:\n"
            "    duplicate: &shadowed\n"
            "      fallback: {provider: old, on: [ip_blocked]}\n"
            "    duplicate:\n"
            "      fallback:\n"
            "        provider: new\n"
            "        on: [rate_limited]\n"
            "        payload: *shadowed\n"
        )

        config = Config(config_path=config_path)
        fallback = config.data["providers"]["youtube"]["duplicate"]["fallback"]

        assert fallback["on"] == ["rate_limited"]
        assert fallback["payload"]["fallback"] == {
            "provider": "old",
            True: ["ip_blocked"],
        }

    def test_config_canonicalizes_only_aliased_fallback_on_key(self, tmp_path: Path) -> None:
        """Test an aliased ``on`` scalar is not retagged in unrelated value positions."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "token: &token on\n"
            "providers:\n"
            "  youtube:\n"
            "    youtube-transcript-api:\n"
            "      fallback:\n"
            "        provider: transcriptapi\n"
            "        *token: [rate_limited]\n"
            "        marker: *token\n"
        )

        config = Config(config_path=config_path)
        fallback = config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"]

        assert fallback == {
            "provider": "transcriptapi",
            "on": ["rate_limited"],
            "marker": True,
        }
        assert config.data["token"] is True

    def test_config_loader_preserves_recursive_yaml_aliases(self, tmp_path: Path) -> None:
        """Test compatibility traversal terminates for recursive YAML node graphs."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "output:\n"
            "  default_format: json\n"
            "recursive_sequence: &recursive_sequence [*recursive_sequence]\n"
            "recursive_mapping: &recursive_mapping\n"
            "  self: *recursive_mapping\n"
        )

        config = Config(config_path=config_path)

        assert config.data["output"]["default_format"] == "json"
        assert config.data["recursive_sequence"][0] is config.data["recursive_sequence"]
        assert config.data["recursive_mapping"]["self"] is config.data["recursive_mapping"]

    def test_config_loader_preserves_recursive_fallback_alias(self, tmp_path: Path) -> None:
        """Test a recursive fallback alias cannot make the whole config fall back to defaults."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "output:\n"
            "  default_format: json\n"
            "metadata: &metadata\n"
            "  provider: metadata-provider\n"
            "  on: keep-unrelated\n"
            "  fallback: *metadata\n"
        )

        config = Config(config_path=config_path)

        assert config.data["output"]["default_format"] == "json"
        assert config.data["metadata"]["fallback"] is config.data["metadata"]

    def test_config_canonicalizes_recursive_provider_fallback(self, tmp_path: Path) -> None:
        """Test a targeted recursive fallback stays recursive after key canonicalization."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers:\n"
            "  youtube:\n"
            "    youtube-transcript-api:\n"
            "      fallback: &fallback\n"
            "        provider: transcriptapi\n"
            "        on: [rate_limited]\n"
            "        self: *fallback\n"
        )

        config = Config(config_path=config_path)
        fallback = config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"]

        assert fallback["on"] == ["rate_limited"]
        assert fallback["self"] is fallback

    def test_config_preserves_fallback_alias_to_enclosing_provider(self, tmp_path: Path) -> None:
        """Test fallback graph cloning redirects a back-reference to its provider copy."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers:\n"
            "  youtube:\n"
            "    youtube-transcript-api: &provider\n"
            "      fallback:\n"
            "        provider: transcriptapi\n"
            "        on: [rate_limited]\n"
            "        enclosing: *provider\n"
            "        nested: [*provider]\n"
        )

        config = Config(config_path=config_path)
        provider = config.data["providers"]["youtube"]["youtube-transcript-api"]

        assert provider["fallback"]["on"] == ["rate_limited"]
        assert provider["fallback"]["enclosing"] is provider
        assert provider["fallback"]["nested"][0] is provider

    def test_config_preserves_provider_precloned_through_sibling_fallback(
        self, tmp_path: Path
    ) -> None:
        """Test a provider reached through an earlier fallback is canonicalized only once."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "shared_second: &second\n"
            "  fallback:\n"
            "    provider: transcriptapi\n"
            "    on: [ip_blocked]\n"
            "    enclosing: *second\n"
            "providers:\n"
            "  youtube:\n"
            "    first:\n"
            "      fallback:\n"
            "        provider: transcriptapi\n"
            "        on: [rate_limited]\n"
            "        sibling: *second\n"
            "    second: *second\n"
        )

        config = Config(config_path=config_path)
        providers = config.data["providers"]["youtube"]
        second = providers["second"]

        assert providers["first"]["fallback"]["sibling"] is second
        assert second["fallback"]["on"] == ["ip_blocked"]
        assert second["fallback"]["enclosing"] is second
        assert config.data["shared_second"]["fallback"][True] == ["ip_blocked"]

    def test_config_uses_plain_on_after_merged_quoted_on(self, tmp_path: Path) -> None:
        """Test a later plain ``on`` overrides an inherited quoted spelling."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "fallback_defaults: &fallback_defaults\n"
            '  "on": [ip_blocked]\n'
            "providers:\n"
            "  youtube:\n"
            "    youtube-transcript-api:\n"
            "      fallback:\n"
            "        <<: *fallback_defaults\n"
            "        provider: transcriptapi\n"
            "        on: [rate_limited]\n"
        )

        config = Config(config_path=config_path)
        fallback = config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"]

        assert fallback == {"provider": "transcriptapi", "on": ["rate_limited"]}
        assert config.data["fallback_defaults"] == {"on": ["ip_blocked"]}

    def test_config_uses_quoted_on_after_merged_plain_on(self, tmp_path: Path) -> None:
        """Test a later quoted ``on`` overrides an inherited plain spelling."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "fallback_defaults: &fallback_defaults\n"
            "  on: [ip_blocked]\n"
            "providers:\n"
            "  youtube:\n"
            "    youtube-transcript-api:\n"
            "      fallback:\n"
            "        <<: *fallback_defaults\n"
            "        provider: transcriptapi\n"
            '        "on": [rate_limited]\n'
        )

        config = Config(config_path=config_path)
        fallback = config.data["providers"]["youtube"]["youtube-transcript-api"]["fallback"]

        assert fallback == {
            "provider": "transcriptapi",
            "on": ["rate_limited"],
        }
        assert config.data["fallback_defaults"] == {True: ["ip_blocked"]}


class TestConfigGet:
    """Test configuration value retrieval."""

    def test_get_simple_key(self):
        """Test getting simple top-level key."""
        config = create_test_config({"test_key": "test_value"})

        assert config.get("test_key") == "test_value"

    def test_get_nested_key(self):
        """Test getting nested key with dot notation."""
        config = create_test_config({"level1": {"level2": {"level3": "value"}}})

        assert config.get("level1.level2.level3") == "value"

    def test_get_missing_key_returns_default(self):
        """Test that missing keys return default value."""
        config = create_test_config({})

        assert config.get("missing.key", "default") == "default"

    def test_get_partial_path_returns_default(self):
        """Test that partial paths return default."""
        config = create_test_config({"level1": "value"})

        assert config.get("level1.level2.level3", "default") == "default"

    def test_get_provider_fallback_accepts_legacy_boolean_on_key(self) -> None:
        """Test compatibility with mappings constructed before load canonicalization."""
        config = create_test_config(
            {
                "providers": {
                    "youtube": {
                        "default": "youtube-transcript-api",
                        "youtube-transcript-api": {
                            "fallback": {
                                "provider": "transcriptapi",
                                True: ["ip_blocked", "rate_limited"],
                            }
                        },
                    }
                }
            }
        )

        assert config.get_provider_fallback("youtube") == {
            "provider": "transcriptapi",
            True: ["ip_blocked", "rate_limited"],
            "on": ["ip_blocked", "rate_limited"],
        }

    def test_get_provider_fallback_does_not_treat_integer_one_as_true(self) -> None:
        """Test that integer key ``1`` is not mistaken for legacy boolean ``True``."""
        config = create_test_config(
            {
                "providers": {
                    "youtube": {
                        "default": "youtube-transcript-api",
                        "youtube-transcript-api": {
                            "fallback": {"provider": "transcriptapi", 1: ["rate_limited"]}
                        },
                    }
                }
            }
        )

        assert config.get_provider_fallback("youtube") is None


class TestServiceUrl:
    """Test service URL generation."""

    def test_get_service_url(self):
        """Test generating service URLs."""
        config = create_test_config(
            {"services": {"crawl4ai": {"host": "localhost", "port": 11235}}}
        )

        url = config.get_service_url("crawl4ai")
        assert url == "http://localhost:11235"

    def test_get_service_url_custom_host(self):
        """Test service URL with custom host."""
        config = create_test_config(
            {"services": {"crawl4ai": {"host": "example.com", "port": 8080}}}
        )

        url = config.get_service_url("crawl4ai")
        assert url == "http://example.com:8080"


class TestDeepMerge:
    """Test deep merging of configuration dictionaries."""

    def test_deep_merge_simple(self):
        """Test simple deep merge."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = Config._deep_merge(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested(self):
        """Test deep merge with nested dictionaries."""
        base = {"level1": {"a": 1, "b": 2}}
        override = {"level1": {"b": 3, "c": 4}}

        result = Config._deep_merge(base, override)

        assert result == {"level1": {"a": 1, "b": 3, "c": 4}}

    def test_deep_merge_preserves_base(self):
        """Test that deep merge doesn't mutate base dict."""
        base = {"level1": {"a": 1}}
        override = {"level1": {"b": 2}}

        result = Config._deep_merge(base, override)

        # Base should not be modified
        assert base == {"level1": {"a": 1}}
        # Result should have both
        assert result == {"level1": {"a": 1, "b": 2}}

    def test_deep_merge_keeps_path_specific_defaults_for_shared_override(self) -> None:
        """Test one override alias cannot make distinct default branches share state."""
        shared: dict[str, object] = {}
        base = {"first": {"first_default": 1}, "second": {"second_default": 2}}
        override = {"first": shared, "second": shared}

        result = Config._deep_merge(base, override)

        assert result["first"] == {"first_default": 1}
        assert result["second"] == {"second_default": 2}
        assert result["first"] is not result["second"]

    def test_deep_merge_projects_recursive_aliases_per_default_path(self) -> None:
        """Test recursive shared overrides point into each path-specific projection."""
        shared: dict[str, object] = {}
        wrapper = [shared]
        shared["back"] = wrapper
        base = {"first": {"first_default": 1}, "second": {"second_default": 2}}

        for override in (
            {"anchor": shared, "first": shared, "second": shared},
            {"first": shared, "second": shared, "anchor": shared},
        ):
            result = Config._deep_merge(base, override)

            assert result["first"]["back"][0] is result["first"]
            assert result["second"]["back"][0] is result["second"]
            assert result["anchor"]["back"][0] is result["anchor"]
            assert result["first"]["back"] is not result["second"]["back"]
            assert result["first"] is not result["anchor"]

    def test_deep_merge_handles_deep_sequence_graphs_iteratively(self) -> None:
        """Test compact valid override graphs do not amplify Python recursion depth."""
        root: list[object] = []
        current = root
        for _index in range(1500):
            child: list[object] = []
            current.append(child)
            current = child

        merged = Config._deep_merge({}, {"deep": root})
        current = merged["deep"]
        for _index in range(1500):
            current = current[0]
        assert current == []

    def test_deep_merge_handles_deep_matching_mappings_iteratively(self) -> None:
        """Test matching dictionary chains do not consume Python recursion depth."""
        base: dict[str, object] = {}
        override: dict[str, object] = {}
        for _index in range(1500):
            base = {"nested": base}
            override = {"nested": override}

        merged = Config._deep_merge(base, override)
        current = merged
        for _index in range(1500):
            current = current["nested"]
        assert current == {}

    def test_deep_merge_preserves_compact_shared_mapping_dags(self) -> None:
        """Test shared acyclic merge graphs stay compact instead of expanding by path."""
        base: dict[str, object] = {}
        override: dict[str, object] = {}
        for _index in range(120):
            base = {"left": base, "right": base}
            override = {"left": override, "right": override}

        merged = Config._deep_merge(base, override)
        current = merged
        for _index in range(120):
            assert current["left"] is current["right"]
            current = current["left"]
        assert current == {}

    def test_cycle_detection_memoizes_matching_cycle_members(self) -> None:
        """Test one cycle scan classifies every active member for later merge frames."""
        nodes = [{} for _index in range(500)]
        for index, node in enumerate(nodes):
            node["next"] = nodes[(index + 1) % len(nodes)]
        cache: dict[int, bool] = {}

        assert Config._has_container_cycle(nodes[0], cache)
        assert all(cache[id(node)] for node in nodes)

    def test_deep_merge_clones_shared_acyclic_payload_once(self) -> None:
        """Test repeated aliases do not retraverse an already cloned payload."""

        class CountingList(list[object]):
            yielded = 0

            def __iter__(self):
                for item in super().__iter__():
                    type(self).yielded += 1
                    yield item

        alias_count = 80
        payload = CountingList([[] for _index in range(alias_count)])

        merged = Config._deep_merge(
            {},
            {str(index): payload for index in range(alias_count)},
        )

        assert all(merged[str(index)] is merged["0"] for index in range(alias_count))
        assert merged["0"] is not payload
        assert CountingList.yielded <= alias_count * 5

    def test_deep_merge_reuses_alias_scan_after_sibling_mapping_merges(self) -> None:
        """Test sibling merge frames do not evict an outer frame's alias scan."""

        class CountingList(list[object]):
            yielded = 0

            def __iter__(self):
                for item in super().__iter__():
                    type(self).yielded += 1
                    yield item

        alias_count = 80
        payload = CountingList([[] for _index in range(alias_count)])
        base: dict[str, object] = {}
        override: dict[str, object] = {}
        for index in range(alias_count):
            override[f"alias_{index}"] = payload
            base[f"merge_{index}"] = {"base": index}
            override[f"merge_{index}"] = {"override": index}

        merged = Config._deep_merge(base, override)

        assert all(merged[f"alias_{index}"] is merged["alias_0"] for index in range(alias_count))
        assert merged["alias_0"] is not payload
        assert CountingList.yielded <= alias_count * 5

    def test_deep_merge_clones_shared_empty_mutable_overrides(self) -> None:
        """Test empty mutable override containers are cloned once without mutating input."""
        shared_list: list[object] = []
        shared_mapping: dict[str, object] = {}
        override = {
            "first_list": shared_list,
            "second_list": shared_list,
            "first_mapping": shared_mapping,
            "second_mapping": shared_mapping,
        }

        merged = Config._deep_merge({}, override)
        merged["first_list"].append("changed")
        merged["first_mapping"]["changed"] = True

        assert merged["first_list"] is merged["second_list"]
        assert merged["first_mapping"] is merged["second_mapping"]
        assert merged["first_list"] is not shared_list
        assert merged["first_mapping"] is not shared_mapping
        assert override == {
            "first_list": [],
            "second_list": [],
            "first_mapping": {},
            "second_mapping": {},
        }

    def test_deep_merge_preserves_tuple_list_cycles(self) -> None:
        """Test immutable tuple nodes retain cycles routed through mutable lists."""
        link: list[object] = []
        cycle = (link,)
        link.append(cycle)

        merged = Config._deep_merge({}, {"cycle": cycle})

        assert merged["cycle"][0][0] is merged["cycle"]


class TestGlobalConfig:
    """Test global configuration instance."""

    @patch("gobbler_core.config.Config")
    def test_get_config_singleton(self, mock_config_class):
        """Test that get_config returns singleton instance."""
        # Reset global config
        import gobbler_core.config as config_module

        config_module._config = None

        mock_instance = MagicMock()
        mock_config_class.return_value = mock_instance

        # First call should create instance
        result1 = get_config()
        # Second call should return same instance
        result2 = get_config()

        assert result1 == result2
        assert mock_config_class.call_count == 1  # Only initialized once
