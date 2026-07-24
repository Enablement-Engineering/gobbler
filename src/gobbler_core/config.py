"""Configuration management for Gobbler."""

from __future__ import annotations

import logging
import threading
from collections import ChainMap
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode

logger = logging.getLogger(__name__)


class _BackrefRewriter:
    """Analyze repair payload graphs once while applying scoped replacements."""

    def __init__(self, roots: list[Any], target_ids: set[int]) -> None:
        self._parents: dict[int, set[int]] = {}
        self._node_ids: set[int] = set()
        self._marked: dict[int, set[int]] = {}
        self._targets_by_ancestor: dict[int, set[int]] = {}
        self._projection_memos: dict[frozenset[tuple[int, int]], dict[int, Any]] = {}
        stack = list(roots)
        while stack:
            current = stack.pop()
            current_id = id(current)
            if current_id in self._node_ids:
                continue
            self._node_ids.add(current_id)
            if current_id in target_ids:
                continue
            for child in self._children(current):
                child_id = id(child)
                self._parents.setdefault(child_id, set()).add(current_id)
                stack.append(child)
        for target_id in target_ids:
            for ancestor_id in self._ancestor_closure(target_id):
                self._targets_by_ancestor.setdefault(ancestor_id, set()).add(target_id)

    @staticmethod
    def _children(value: Any) -> list[Any]:
        if isinstance(value, dict):
            return [child for item in value.items() for child in item]
        if isinstance(value, (list, tuple)):
            return list(value)
        return []

    def _ancestor_closure(self, value_id: int) -> set[int]:
        cached = self._marked.get(value_id)
        if cached is not None:
            return cached
        marked = {value_id} if value_id in self._node_ids else set()
        queue = list(marked)
        while queue:
            child_id = queue.pop()
            for parent_id in self._parents.get(child_id, set()):
                if parent_id not in marked:
                    marked.add(parent_id)
                    queue.append(parent_id)
        self._marked[value_id] = marked
        return marked

    def rewrite(self, value: Any, replacements: Mapping[int, Any]) -> Any:
        """Rewrite a value using cached ancestor closures and shared clone state."""
        marked: set[int] = set()
        relevant_targets = {
            target_id
            for target_id in self._targets_by_ancestor.get(id(value), set())
            if target_id in replacements
        }
        projection = frozenset(
            (target_id, id(replacements[target_id])) for target_id in relevant_targets
        )
        memo = self._projection_memos.setdefault(projection, {})
        for target_id in relevant_targets:
            marked.update(self._ancestor_closure(target_id))
            memo[target_id] = replacements[target_id]
        return _ConfigLoader._clone_marked_containers(value, marked, memo)


class _ConfigLoader(yaml.SafeLoader):
    """Safe YAML loader that preserves the documented fallback ``on`` key."""

    _BOOL_TAG = "tag:yaml.org,2002:bool"
    _STRING_TAG = "tag:yaml.org,2002:str"

    def __init__(self, stream: str) -> None:
        """Initialize the loader with source retained for stable lexical offsets."""
        self._source = stream
        super().__init__(stream)

    @classmethod
    def _mapping_value(cls, node: MappingNode, key: str) -> Node | None:
        """Return the last effective string-keyed value from a flattened mapping."""
        value: Node | None = None
        for key_node, value_node in node.value:
            if (
                isinstance(key_node, ScalarNode)
                and key_node.tag == cls._STRING_TAG
                and key_node.value == key
            ):
                value = value_node
        return value

    @classmethod
    def _string_mapping_values(cls, node: MappingNode) -> dict[str, Node]:
        """Return effective string-keyed values from a flattened mapping."""
        values: dict[str, Node] = {}
        for key_node, value_node in node.value:
            if isinstance(key_node, ScalarNode) and key_node.tag == cls._STRING_TAG:
                values[key_node.value] = value_node
        return values

    def _is_implicit_plain_on(self, node: ScalarNode) -> bool:
        """Return whether a key is the exact implicit plain scalar ``on``."""
        source_parts = self._source[node.start_mark.index : node.end_mark.index].split()
        return (
            node.tag == self._BOOL_TAG
            and node.style is None
            and bool(source_parts)
            and source_parts[-1] == "on"
            and not any(part.startswith("!") for part in source_parts[:-1])
        )

    def _desired_fallback(self, node: MappingNode) -> dict[Any, Any] | None:
        """Construct fallback contents as if every implicit plain ``on`` key were a string."""
        if self._mapping_value(node, "provider") is None:
            return None

        found_plain_on = False
        desired: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.constructed_objects[key_node]
            if isinstance(key_node, ScalarNode) and self._is_implicit_plain_on(key_node):
                key = "on"
                found_plain_on = True
            desired[key] = self.constructed_objects[value_node]
        return desired if found_plain_on else None

    @staticmethod
    def _container_children(value: Any) -> list[Any]:
        """Return graph children for YAML mapping and sequence containers."""
        if isinstance(value, dict):
            return [child for item in value.items() for child in item]
        if isinstance(value, (list, tuple)):
            return list(value)
        return []

    @classmethod
    def _replacement_closure(cls, value: Any, replacements: Mapping[int, Any]) -> set[int]:
        """Return container identities lying on paths to replacement targets."""
        objects: dict[int, Any] = {}
        parents: dict[int, set[int]] = {}
        found_replacements: set[int] = set()
        stack = [value]
        while stack:
            current = stack.pop()
            current_id = id(current)
            if current_id in replacements:
                found_replacements.add(current_id)
            children = cls._container_children(current)
            if current_id in objects or not children:
                continue
            objects[current_id] = current
            for child in children:
                child_id = id(child)
                parents.setdefault(child_id, set()).add(current_id)
                stack.append(child)

        marked = found_replacements
        queue = list(marked)
        while queue:
            child_id = queue.pop()
            for parent_id in parents.get(child_id, set()):
                if parent_id not in marked:
                    marked.add(parent_id)
                    queue.append(parent_id)
        return marked

    @classmethod
    def _collect_marked_objects(
        cls,
        value: Any,
        marked: set[int],
        memo: Mapping[int, Any],
    ) -> dict[int, Any]:
        """Collect reachable marked containers without recursive Python calls."""
        objects: dict[int, Any] = {}
        stack = [value]
        while stack:
            current = stack.pop()
            current_id = id(current)
            if current_id in objects or current_id not in marked or current_id in memo:
                continue
            objects[current_id] = current
            stack.extend(cls._container_children(current))
        return objects

    @staticmethod
    def _initialize_clone_memo(objects: Mapping[int, Any], memo: dict[int, Any]) -> set[int]:
        """Allocate mutable placeholders and return marked tuple identities."""
        tuple_ids: set[int] = set()
        for object_id, current in objects.items():
            if isinstance(current, dict):
                memo[object_id] = {}
            elif isinstance(current, list):
                memo[object_id] = []
            elif isinstance(current, tuple):
                tuple_ids.add(object_id)
        return tuple_ids

    @staticmethod
    def _clone_marked_tuples(
        objects: Mapping[int, Any],
        tuple_ids: set[int],
        memo: dict[int, Any],
    ) -> None:
        """Materialize tuples after their directly nested tuple dependencies."""
        pending = set(tuple_ids)
        while pending:
            progressed = False
            for object_id in list(pending):
                current = objects[object_id]
                dependencies = {
                    id(item) for item in current if id(item) in tuple_ids and id(item) not in memo
                }
                if dependencies:
                    continue
                memo[object_id] = tuple(memo.get(id(item), item) for item in current)
                pending.remove(object_id)
                progressed = True
            if not progressed:
                return

    @staticmethod
    def _populate_marked_clones(objects: Mapping[int, Any], memo: dict[int, Any]) -> None:
        """Populate preallocated mutable clones from resolved graph references."""
        for object_id, current in objects.items():
            clone = memo.get(object_id)
            if isinstance(current, dict) and isinstance(clone, dict):
                clone.update(
                    (memo.get(id(key), key), memo.get(id(item), item))
                    for key, item in current.items()
                )
            elif isinstance(current, list) and isinstance(clone, list):
                clone.extend(memo.get(id(item), item) for item in current)

    @classmethod
    def _clone_marked_containers(
        cls,
        value: Any,
        marked: set[int],
        memo: dict[int, Any],
    ) -> Any:
        """Clone marked YAML containers iteratively, preserving graph identity."""
        value_id = id(value)
        if value_id in memo:
            return memo[value_id]
        if value_id not in marked:
            return value

        objects = cls._collect_marked_objects(value, marked, memo)
        tuple_ids = cls._initialize_clone_memo(objects, memo)
        cls._clone_marked_tuples(objects, tuple_ids, memo)
        cls._populate_marked_clones(objects, memo)
        return memo.get(value_id, value)

    @classmethod
    def _rewrite_backrefs(cls, value: Any, replacements: Mapping[int, Any]) -> Any:
        """Copy only containers that lead to a replaced path ancestor."""
        marked = cls._replacement_closure(value, replacements)
        memo = {value_id: replacements[value_id] for value_id in marked if value_id in replacements}
        return cls._clone_marked_containers(value, marked, memo)

    @classmethod
    def _rewrite_mapping_backrefs(
        cls,
        mapping: dict[Any, Any],
        replacements: Mapping[int, Any],
        excluded_keys: set[str],
    ) -> None:
        """Rewrite ancestor references outside structural path keys."""
        for key, value in list(mapping.items()):
            if key not in excluded_keys:
                mapping[key] = cls._rewrite_backrefs(value, replacements)

    def _fallback_repair_plans(
        self,
        providers_node: MappingNode,
    ) -> list[
        tuple[
            str,
            str,
            dict[Any, Any],
            dict[Any, Any],
            dict[Any, Any],
            dict[Any, Any],
        ]
    ]:
        """Collect effective provider paths that need the documented-key repair."""
        plans = []
        for category_name, category_node in self._string_mapping_values(providers_node).items():
            if not isinstance(category_node, MappingNode):
                continue
            category = self.constructed_objects[category_node]
            if not isinstance(category, dict):
                continue
            for provider_name, provider_node in self._string_mapping_values(category_node).items():
                if not isinstance(provider_node, MappingNode):
                    continue
                fallback_node = self._mapping_value(provider_node, "fallback")
                if not isinstance(fallback_node, MappingNode):
                    continue
                desired = self._desired_fallback(fallback_node)
                provider = self.constructed_objects[provider_node]
                fallback = self.constructed_objects[fallback_node]
                if (
                    desired is not None
                    and isinstance(provider, dict)
                    and isinstance(fallback, dict)
                ):
                    plans.append(
                        (category_name, provider_name, category, provider, fallback, desired)
                    )
        return plans

    @staticmethod
    def _rewrite_mapping_tasks(
        tasks: list[tuple[dict[Any, Any], Mapping[int, Any], set[str]]],
        target_ids: set[int],
    ) -> None:
        """Rewrite mapping values from one shared graph index and scoped clone memos."""
        roots = [
            value
            for mapping, _replacements, excluded_keys in tasks
            for key, value in mapping.items()
            if key not in excluded_keys
        ]
        rewriter = _BackrefRewriter(roots, target_ids)
        for mapping, replacements, excluded_keys in tasks:
            for key, value in list(mapping.items()):
                if key not in excluded_keys:
                    mapping[key] = rewriter.rewrite(value, replacements)

    def _repair_provider_fallbacks(self, root_node: Node, data: Any) -> Any:
        """Copy and repair only effective provider paths containing an implicit plain ``on``."""
        if not isinstance(root_node, MappingNode) or not isinstance(data, dict):
            return data
        providers_node = self._mapping_value(root_node, "providers")
        if not isinstance(providers_node, MappingNode):
            return data
        providers = self.constructed_objects[providers_node]
        if not isinstance(providers, dict):
            return data

        plans = self._fallback_repair_plans(providers_node)
        if not plans:
            return data

        repaired = data.copy()
        repaired_providers = providers.copy()
        repaired["providers"] = repaired_providers
        replacements: dict[int, Any] = {id(data): repaired, id(providers): repaired_providers}
        category_clones: dict[int, dict[Any, Any]] = {}
        category_provider_names: dict[int, set[str]] = {}
        provider_clones: dict[int, dict[Any, Any]] = {}
        fallback_clones: dict[int, dict[Any, Any]] = {}
        provider_fallbacks: dict[int, tuple[int, dict[Any, Any]]] = {}

        for category_name, provider_name, category, provider, fallback, desired in plans:
            repaired_category = category_clones.setdefault(id(category), category.copy())
            category_provider_names.setdefault(id(category), set()).add(provider_name)
            repaired_provider = provider_clones.setdefault(id(provider), provider.copy())
            repaired_fallback = fallback_clones.setdefault(id(fallback), desired.copy())
            provider_fallbacks[id(provider)] = (id(fallback), repaired_fallback)
            replacements[id(category)] = repaired_category
            replacements[id(provider)] = repaired_provider
            replacements[id(fallback)] = repaired_fallback
            repaired_providers[category_name] = repaired_category
            repaired_category[provider_name] = repaired_provider
            repaired_provider["fallback"] = repaired_fallback

        fallback_ids = set(fallback_clones)
        ancestor_replacements = {
            value_id: replacement
            for value_id, replacement in replacements.items()
            if value_id not in fallback_ids
        }
        tasks: list[tuple[dict[Any, Any], Mapping[int, Any], set[str]]] = []
        for fallback_id, fallback in fallback_clones.items():
            scope = ChainMap({fallback_id: fallback}, ancestor_replacements)
            tasks.append((fallback, scope, set()))
        for provider_id, provider in provider_clones.items():
            fallback_id, fallback = provider_fallbacks[provider_id]
            scope = ChainMap({fallback_id: fallback}, ancestor_replacements)
            tasks.append((provider, scope, {"fallback"}))
        tasks.extend(
            (category, ancestor_replacements, category_provider_names[category_id])
            for category_id, category in category_clones.items()
        )
        tasks.append(
            (
                repaired_providers,
                ancestor_replacements,
                {category_name for category_name, *_rest in plans},
            )
        )
        tasks.append((repaired, {id(data): repaired}, {"providers"}))
        self._rewrite_mapping_tasks(tasks, set(replacements))
        return repaired

    def construct_document(self, node: Node) -> Any:
        """Construct and narrowly repair the document before PyYAML clears node identities."""
        data = self.construct_object(node)
        while self.state_generators:
            state_generators = self.state_generators
            self.state_generators = []
            for state_generator in state_generators:
                for _dummy in state_generator:
                    pass
        data = self._repair_provider_fallbacks(node, data)
        self.constructed_objects = {}
        self.recursive_objects = {}
        self.deep_construct = False
        return data


class Config:
    """Configuration loader and manager."""

    DEFAULTS: ClassVar[dict[str, Any]] = {
        "proxy_services": {},
        "providers": {
            "transcription": {
                "default": "whisper-local",
                "whisper-local": {
                    "model": "small",
                },
            },
            "document": {
                "default": "docling",
                "docling": {
                    "ocr": True,
                },
            },
            "webpage": {
                "default": "crawl4ai",
                "crawl4ai": {
                    "timeout": 30,
                },
            },
            "youtube": {
                "default": "youtube-transcript-api",
                "youtube-transcript-api": {},
                "transcriptapi": {},
            },
        },
        "whisper": {
            "model": "small",
            "language": "auto",
        },
        "docling": {
            "ocr": True,
            "vlm": False,
        },
        "crawl4ai": {
            "timeout": 30,
            "max_timeout": 120,
        },
        "output": {
            "default_format": "frontmatter",
            "timestamp_format": "iso8601",
            "default_directory": None,
        },
        "services": {
            "crawl4ai": {
                "host": "localhost",
                "port": 11235,
                "api_token": "gobbler-local-token",  # nosec B105
            },
            "docling": {
                "host": "localhost",
                "port": 5001,
            },
        },
        "redis": {
            "host": "localhost",
            "port": 6380,
            "db": 0,
        },
        "queue": {
            "auto_queue_threshold": 105,
            "default_queue": "default",
        },
        "models_path": "~/.gobbler/models",
        "monitoring": {
            "metrics_enabled": False,
            "metrics_port": 9090,
            "metrics_host": "0.0.0.0",  # noqa: S104  # nosec B104
            "log_format": "text",
            "log_level": "INFO",
            "health_check_interval": 60,
        },
    }

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize configuration.

        Args:
            config_path: Path to config file. If None, uses default location.
        """
        self.config_path = config_path or self._default_config_path()
        self._lock = threading.RLock()
        self.data = self._load_config()

    @staticmethod
    def _default_config_path() -> Path:
        """Get default configuration file path."""
        return Path.home() / ".config" / "gobbler" / "config.yml"

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from file, falling back to defaults.

        Returns:
            Configuration dictionary.
        """
        config = self.DEFAULTS.copy()

        if self.config_path.exists():
            try:
                with self.config_path.open() as config_file:
                    loader = _ConfigLoader(config_file.read())
                    try:
                        user_config = loader.get_single_data()
                    finally:
                        loader.dispose()  # type: ignore[no-untyped-call]
                    if user_config:
                        config = self._deep_merge(config, user_config)
                        logger.info("Loaded configuration from %s", self.config_path)
            except Exception:
                logger.warning("Failed to load config from %s", self.config_path, exc_info=True)
                logger.info("Using default configuration")
        else:
            logger.info("No config file found at %s, using defaults", self.config_path)

        return config

    @staticmethod
    def _clone_override_value(
        value: Any,
        active: dict[int, dict[str, Any]],
        cloned: dict[int, Any],
    ) -> Any:
        """Clone an unmerged override graph iteratively and redirect active back-references."""
        value_id = id(value)
        if value_id in active:
            return active[value_id]
        if value_id in cloned:
            return cloned[value_id]

        marked: set[int] = set()
        stack = [value]
        while stack:
            current = stack.pop()
            current_id = id(current)
            if current_id in active or current_id in cloned or current_id in marked:
                continue
            if not isinstance(current, (dict, list, tuple)):
                continue
            marked.add(current_id)
            stack.extend(_ConfigLoader._container_children(current))

        memo = {**cloned, **active}
        result = _ConfigLoader._clone_marked_containers(value, marked, memo)
        cloned.update(
            (object_id, memo[object_id])
            for object_id in marked
            if object_id not in active and object_id in memo
        )
        return result

    @staticmethod
    def _clone_projected_override(
        value: Any,
        active: dict[int, dict[str, Any]],
        shared: dict[int, Any],
        projection: dict[int, Any],
        replacement_cache: dict[int, set[int]],
    ) -> Any:
        """Clone a value, isolating only paths that reference an active merge projection."""
        value_id = id(value)
        marked = replacement_cache.get(value_id)
        if marked is None:
            marked = _ConfigLoader._replacement_closure(value, active)
            replacement_cache[value_id] = marked
        if id(value) not in marked:
            return Config._clone_override_value(value, active, shared)

        for target_id in marked:
            if target_id in active:
                projection[target_id] = active[target_id]
        objects = _ConfigLoader._collect_marked_objects(value, marked, projection)
        for current in objects.values():
            for child in _ConfigLoader._container_children(current):
                child_id = id(child)
                if child_id not in marked and child_id not in projection:
                    projection[child_id] = Config._clone_override_value(child, active, shared)
        return _ConfigLoader._clone_marked_containers(value, marked, projection)

    @staticmethod
    def _has_container_cycle(value: Any, cache: dict[int, bool]) -> bool:
        """Return whether a container graph is cyclic without recursive Python calls."""
        value_id = id(value)
        if value_id in cache:
            return cache[value_id]
        visiting: set[int] = set()
        visited: set[int] = set()
        stack: list[tuple[Any, bool]] = [(value, False)]
        while stack:
            current, exiting = stack.pop()
            current_id = id(current)
            if exiting:
                visiting.discard(current_id)
                visited.add(current_id)
                continue
            if current_id in visited:
                continue
            cached = cache.get(current_id)
            if cached is not None:
                if cached:
                    cache.update((object_id, True) for object_id in visiting)
                    cache[value_id] = True
                    return True
                visited.add(current_id)
                continue
            if current_id in visiting:
                cache.update((object_id, True) for object_id in visiting)
                cache[value_id] = True
                return True
            children = _ConfigLoader._container_children(current)
            if not children:
                visited.add(current_id)
                continue
            visiting.add(current_id)
            stack.append((current, True))
            for child in children:
                child_id = id(child)
                if child_id in visiting:
                    cache.update((object_id, True) for object_id in visiting)
                    cache[value_id] = True
                    return True
                if child_id not in visited:
                    stack.append((child, False))
        cache.update((object_id, False) for object_id in visited)
        cache[value_id] = False
        return False

    @staticmethod
    def _deep_merge(
        base: dict[str, Any],
        override: dict[str, Any],
        _active: dict[int, dict[str, Any]] | None = None,
        _cloned: dict[int, Any] | None = None,
    ) -> dict[str, Any]:
        """Deep merge dictionaries while preserving cycles and path-specific defaults.

        Args:
            base: Base dictionary.
            override: Dictionary to merge over base.
            _active: Internal mappings currently being merged, for ancestor aliases.
            _cloned: Internal memo for containers copied outside a matching base path.

        Returns:
            Merged dictionary.
        """
        active = {} if _active is None else _active
        cloned = {} if _cloned is None else _cloned
        existing = active.get(id(override))
        if existing is not None:
            return existing

        result = base.copy()
        override_id = id(override)
        active[override_id] = result
        completed: dict[tuple[int, int], dict[str, Any]] = {}
        cycle_cache: dict[int, bool] = {}
        stack: list[
            tuple[
                Any,
                int,
                dict[str, Any],
                dict[int, Any],
                dict[int, set[int]],
                tuple[int, int] | None,
            ]
        ] = [(iter(override.items()), override_id, result, {}, {}, None)]
        while stack:
            (
                iterator,
                current_override_id,
                target,
                projection,
                replacement_cache,
                completed_key,
            ) = stack[-1]
            try:
                key, value = next(iterator)
            except StopIteration:
                if completed_key is not None:
                    completed[completed_key] = target
                del active[current_override_id]
                stack.pop()
                continue

            current = target.get(key)
            if isinstance(current, dict) and isinstance(value, dict):
                value_id = id(value)
                active_value = active.get(value_id)
                if active_value is not None:
                    target[key] = active_value
                    continue
                pair = (id(current), value_id)
                cacheable = not Config._has_container_cycle(
                    current, cycle_cache
                ) and not Config._has_container_cycle(value, cycle_cache)
                cached = completed.get(pair) if cacheable else None
                if cached is not None:
                    target[key] = cached
                    continue
                child = current.copy()
                target[key] = child
                active[value_id] = child
                stack.append(
                    (
                        iter(value.items()),
                        value_id,
                        child,
                        {},
                        {},
                        pair if cacheable else None,
                    )
                )
                continue

            target[key] = Config._clone_projected_override(
                value,
                active,
                cloned,
                projection,
                replacement_cache,
            )
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Args:
            key: Configuration key, such as ``whisper.model``.
            default: Default value if key is not found.

        Returns:
            Configuration value.
        """
        with self._lock:
            keys = key.split(".")
            value = self.data
            for key_part in keys:
                if isinstance(value, dict) and key_part in value:
                    value = value[key_part]
                else:
                    return default
            return value

    def get_service_url(self, service: str) -> str:
        """Get full service URL.

        Args:
            service: Service name, such as ``crawl4ai`` or ``docling``.

        Returns:
            Full HTTP URL for the service.
        """
        host = self.get(f"services.{service}.host", "localhost")
        port = self.get(f"services.{service}.port")
        return f"http://{host}:{port}"

    def get_provider_name(self, category: str) -> str:
        """Get the default provider name for a category.

        Args:
            category: Provider category.

        Returns:
            Provider name.
        """
        return self.get(f"providers.{category}.default", self._default_provider(category))

    def get_provider_config(self, category: str, provider_name: str | None = None) -> dict:
        """Get configuration for a specific provider.

        Args:
            category: Provider category.
            provider_name: Provider name, or None to use default.

        Returns:
            Provider configuration dictionary.
        """
        if provider_name is None:
            provider_name = self.get_provider_name(category)

        return self.get(f"providers.{category}.{provider_name}", {})

    @staticmethod
    def _default_provider(category: str) -> str:
        """Get the default provider name for a category.

        Args:
            category: Provider category.

        Returns:
            Default provider name.
        """
        defaults = {
            "transcription": "whisper-local",
            "document": "docling",
            "webpage": "crawl4ai",
            "youtube": "youtube-transcript-api",
        }
        return defaults.get(category, "")

    def get_proxy_service(self, service_name: str) -> dict | None:
        """Get proxy service configuration by name.

        Args:
            service_name: Name of the proxy service.

        Returns:
            Proxy service configuration dictionary, or None if not found.
        """
        return self.get(f"proxy_services.{service_name}")

    def get_provider_proxy(self, category: str, provider_name: str | None = None) -> dict | None:
        """Get proxy configuration for a provider.

        Args:
            category: Provider category.
            provider_name: Provider name, or None to use default.

        Returns:
            Proxy service configuration dictionary, or None if no proxy configured.
        """
        if provider_name is None:
            provider_name = self.get_provider_name(category)

        proxy_service_name = self.get(f"providers.{category}.{provider_name}.proxy")
        if proxy_service_name is None:
            return None

        return self.get_proxy_service(proxy_service_name)

    def get_provider_fallback(self, category: str, provider_name: str | None = None) -> dict | None:
        """Get fallback configuration for a provider.

        Args:
            category: Provider category.
            provider_name: Provider name, or None to use default.

        Returns:
            Fallback config dict with provider and condition keys, or None.
        """
        if provider_name is None:
            provider_name = self.get_provider_name(category)

        fallback = self.get(f"providers.{category}.{provider_name}.fallback")
        if fallback is None:
            return None

        if (
            isinstance(fallback, dict)
            and "provider" in fallback
            and "on" not in fallback
            and any(type(key) is bool and key is True for key in fallback)
        ):
            fallback = {**fallback, "on": fallback[True]}

        if not isinstance(fallback, dict) or "provider" not in fallback or "on" not in fallback:
            return None

        return fallback

    def reload(self) -> None:
        """Reload configuration from file."""
        with self._lock:
            self.data = self._load_config()


_config: Config | None = None


def get_config() -> Config:
    """Get global configuration instance.

    Returns:
        Config instance.
    """
    global _config  # noqa: PLW0603
    if _config is None:
        _config = Config()
    return _config
