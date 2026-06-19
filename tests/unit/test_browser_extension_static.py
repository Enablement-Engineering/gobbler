"""Static validation tests for the browser extension."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTENSION_DIR = REPO_ROOT / "browser-extension"
MANIFEST_PATH = EXTENSION_DIR / "manifest.json"
BACKGROUND_PATH = EXTENSION_DIR / "background.js"
POPUP_HTML_PATH = EXTENSION_DIR / "popup.html"
REGISTRY_PATH = EXTENSION_DIR / "page-apis" / "registry.js"
CLIENT_PATH = REPO_ROOT / "src" / "gobbler_relay" / "client.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _manifest() -> dict:
    return json.loads(_read(MANIFEST_PATH))


def _registry_entry_blocks() -> list[str]:
    registry = _read(REGISTRY_PATH)
    entries = registry.split("const PAGE_API_REGISTRY = [", 1)[1].split("\n];", 1)[0]
    return re.findall(r"^  \{\n(.*?)^  \},?", entries, flags=re.MULTILINE | re.DOTALL)


def _single_quoted_field(block: str, field_name: str) -> str:
    match = re.search(rf"{field_name}:\s*'([^']+)'", block)
    assert match is not None, f"Missing {field_name} in registry entry:\n{block}"
    return match.group(1)


def _command_cases(source: str) -> set[str]:
    return set(re.findall(r"case '([^']+)':", source))


def _client_commands(source: str) -> set[str]:
    return set(re.findall(r"send_command\(\s*\"([a-z_]+)\"", source))


def _section_between(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_manifest_references_existing_local_extension_files() -> None:
    """Validate extension manifest wiring without launching a browser."""
    manifest = _manifest()

    assert manifest["manifest_version"] == 3
    assert manifest["background"] == {"service_worker": "background.js"}
    assert (EXTENSION_DIR / manifest["background"]["service_worker"]).is_file()
    assert (EXTENSION_DIR / manifest["action"]["default_popup"]).is_file()

    for icon_path in manifest["icons"].values():
        assert (EXTENSION_DIR / icon_path).is_file()

    for icon_path in manifest["action"]["default_icon"].values():
        assert (EXTENSION_DIR / icon_path).is_file()

    assert set(manifest["host_permissions"]) == {
        "http://localhost/*",
        "ws://localhost/*",
    }
    assert set(manifest["optional_host_permissions"]) == {
        "https://*/*",
        "http://*/*",
    }
    assert "tabs" not in manifest["permissions"]
    assert {"activeTab", "scripting", "storage", "tabGroups"}.issubset(set(manifest["permissions"]))
    assert manifest["content_security_policy"]["extension_pages"] == (
        "script-src 'self'; object-src 'self'"
    )

    popup = _read(POPUP_HTML_PATH)
    assert 'src="page-apis/registry.js"' in popup
    assert 'src="popup.js"' in popup
    assert popup.index('src="page-apis/registry.js"') < popup.index('src="popup.js"')


def test_page_api_registry_entries_reference_existing_scripts() -> None:
    """Validate page API registry metadata and helper exports."""
    registry = _read(REGISTRY_PATH)
    blocks = _registry_entry_blocks()

    assert blocks
    assert "globalThis.PAGE_API_REGISTRY = PAGE_API_REGISTRY" in registry
    assert "globalThis.findMatchingApi = findMatchingApi" in registry
    assert "globalThis.getEnabledApis = getEnabledApis" in registry
    assert "if (!entry.enabled) continue;" in registry

    names = set()
    for block in blocks:
        name = _single_quoted_field(block, "name")
        api_file = _single_quoted_field(block, "apiFile")
        injection_marker = _single_quoted_field(block, "injectionMarker")
        domain = _single_quoted_field(block, "domain")
        global_var = _single_quoted_field(block, "globalVar")

        assert name not in names
        names.add(name)
        assert "enabled: true" in block
        assert (EXTENSION_DIR / api_file).is_file()
        assert injection_marker.startswith("__gobbler")
        assert injection_marker.endswith("Injected")
        assert domain in block
        assert global_var.startswith("window.gobbler")
        assert re.search(r"methods:\s*\[[^\]]+'[^']+'[^\]]*\]", block)


def test_background_command_contract_matches_relay_client_helpers() -> None:
    """Keep relay client command names aligned with the extension switch."""
    background = _read(BACKGROUND_PATH)
    client = _read(CLIENT_PATH)
    background_commands = _command_cases(background)
    client_commands = _client_commands(client)

    assert client_commands <= background_commands
    assert {
        "extract_page",
        "navigate",
        "execute_script",
        "get_page_info",
        "list_gobbler_tabs",
        "execute_script_in_tab",
        "get_injected_apis",
        "inject_api",
        "open_tabs",
    } <= background_commands

    assert "type: 'command_response'" in background
    assert "command_id: command_id" in background
    assert "result: result" in background
    assert "type: 'register'" in background
    assert "extension_version: '0.2.1'" in background
    assert "type: 'ping'" in background
    assert "message.type === 'pong'" in background


def test_tab_group_guards_cover_sensitive_commands() -> None:
    """Validate tab group scoping on commands that read or modify pages."""
    background = _read(BACKGROUND_PATH)

    guarded_by_active_tab = {
        "extractPage": ("async function extractPage", "async function navigateToUrl"),
        "navigateToUrl": ("async function navigateToUrl", "async function openTabs"),
        "executeScript": ("async function executeScript", "// Clean up debugger"),
        "getPageInfo": ("async function getPageInfo", "// Context menu setup"),
    }
    for function_name, (start_marker, end_marker) in guarded_by_active_tab.items():
        section = _section_between(background, start_marker, end_marker)
        assert "getActiveGobblerTab()" in section, f"{function_name} must guard active tab access"

    guarded_by_tab_id = {
        "manuallyInjectApi": (
            "async function manuallyInjectApi",
            "async function executeScriptInTab",
        ),
        "executeScriptInTab": (
            "async function executeScriptInTab",
            "async function getCurrentTabGroupStatus",
        ),
    }
    for function_name, (start_marker, end_marker) in guarded_by_tab_id.items():
        section = _section_between(background, start_marker, end_marker)
        assert "isTabInGobblerGroup(tabId)" in section, (
            f"{function_name} must guard explicit tab access"
        )

    group_tabs = _section_between(
        background,
        "async function getGobblerGroupTabs",
        "async function listGobblerTabs",
    )
    assert "chrome.storage.local.get('gobblerGroupId')" in group_tabs
    assert "chrome.tabs.query({ groupId: stored.gobblerGroupId })" in group_tabs

    list_tabs = _section_between(
        background,
        "async function listGobblerTabs",
        "async function getInjectedApis",
    )
    assert "chrome.tabs.query({ groupId: stored.gobblerGroupId })" in list_tabs
    expected_supported_hosts = [
        ".".join(("notebooklm", "google", "com")),
        ".".join(("claude", "ai")),
        ".".join(("chatgpt", "com")),
        ".".join(("gemini", "google", "com")),
    ]
    for host in expected_supported_hosts:
        assert host in list_tabs


def test_extraction_payload_serialization_matches_relay_endpoint() -> None:
    """Validate the extension serializes extracted page data for /extract."""
    background = _read(BACKGROUND_PATH)
    extract_page = _section_between(
        background,
        "async function extractPage",
        "async function navigateToUrl",
    )

    assert "url: window.location.href" in extract_page
    assert "title: document.title" in extract_page
    assert "html: (element || document.documentElement).outerHTML" in extract_page
    assert "text: (element || document.body).innerText" in extract_page
    assert "selector: selector" in extract_page
    assert "fetch('http://localhost:4625/extract'" in extract_page
    assert "method: 'POST'" in extract_page
    assert "headers: { 'Content-Type': 'application/json' }" in extract_page
    assert "body: JSON.stringify(pageData)" in extract_page
    assert "markdown: data.markdown" in extract_page
    assert "metadata: data.metadata" in extract_page
