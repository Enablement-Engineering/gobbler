---
icon: material/download
---

# Installation

## Requirements

- Python 3.11 or newer.
- [uv](https://docs.astral.sh/uv/) for Python environments and tools.
- ffmpeg for audio/video transcription.
- Docker Desktop, Colima, or Docker Engine for document and webpage conversion.
- A Chromium-family browser for the optional extension.

YouTube transcript conversion does not require Docker or ffmpeg.

## Install prerequisites

=== "macOS"

    ```bash
    brew install uv ffmpeg
    ```

    Choose one Docker runtime:

    ```bash
    # Docker Desktop
    brew install --cask docker

    # Or Colima plus Docker CLI
    brew install colima docker docker-compose
    colima start --cpu 5 --memory 10
    ```

=== "Ubuntu/Debian"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    sudo apt update
    sudo apt install -y ffmpeg
    curl -fsSL https://get.docker.com | sh
    ```

=== "Windows"

    Use WSL2 for the CLI and Docker Desktop with WSL integration. Install uv and ffmpeg inside the WSL distribution. Native Windows has not been the primary tested development path.

## Source checkout

```bash
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler
uv sync
uv run gobbler --version
```

`uv sync` resolves the project dependencies and creates a repository-local `.venv`. This repository does not currently track `uv.lock`, so a clean clone resolves from `pyproject.toml` rather than reproducing a committed lockfile. Use `uv run gobbler ...` to execute that environment.

## Isolated global CLI

From the cloned repository:

```bash
uv tool install .
gobbler --version
```

After pulling updates, reinstall the tool:

```bash
uv tool install . --force
```

The global tool contains the Python CLI. Keep the repository checkout if you also need the unpacked browser extension or repository Skills.

## Development environment

```bash
uv sync --extra dev
uv run pre-commit install
uv run pytest tests/unit/ -q
```

Documentation dependencies are separate:

```bash
uv sync --extra docs
uv run --extra docs mkdocs build --strict
```

## Start document and webpage services

The Compose file starts two containers:

- Docling on port `5001` for `gobbler document`.
- Crawl4AI on port `11235` for `gobbler webpage`.

```bash
make start-docker
# Equivalent: docker compose up -d

uv run gobbler doctor --json
```

Useful service commands:

```bash
make status
make logs
make stop
```

The Compose stack does **not** contain Redis or a background worker. Gobbler's optional job queue is SQLite-backed; start its worker separately with `gobbler jobs worker start`.

### Compose environment variables

- `CRAWL4AI_API_TOKEN`: token consumed by the Crawl4AI container. The Compose default is `gobbler-local-token`. If you override it, set the same value at `services.crawl4ai.api_token` in `~/.config/gobbler/config.yml`; the Python client does not read this environment variable directly.
- `GOBBLER_MODELS_PATH`: host path mounted as the Docling model cache; defaults to `~/.gobbler/models`.

## Verify the installation

```bash
# Broad runtime and dependency report
uv run gobbler doctor --json

# Conversion-provider readiness
uv run gobbler status --json

# Runtime provider registry
uv run gobbler providers list --format json

# No-Docker smoke test
uv run gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o /tmp/gobbler-test.md
```

`status --json` writes a diagnostic object even when it exits nonzero because a provider is degraded. Parse stdout before interpreting the exit status.

## Browser extension

1. Open `chrome://extensions/` in Chrome, Brave, Edge, or another Chromium browser.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose this repository's `browser-extension/` directory.
4. Open a harmless page such as `https://example.com`, open the extension popup, and click **Allow & Add** or **Add Tab**. The extension creates and stores its own group identity.
5. Verify:

```bash
uv run gobbler relay start
uv run gobbler browser status
uv run gobbler browser list
```

Most browser operations auto-start the local relay on `127.0.0.1:4625`; the read-only `browser status` command does not. See [Browser Extension](browser-extension.md) for the security model and commands.

## Install AI-agent Skills

```bash
npx skills@latest add Enablement-Engineering/gobbler --list
npx skills@latest add Enablement-Engineering/gobbler
```

This installs only Markdown Skill files. Install the CLI separately using one of the methods above.

## Uninstall

```bash
# Remove isolated global tool
uv tool uninstall gobbler

# Stop local containers
docker compose down
```

A source checkout's `.venv` can be removed by deleting that directory. User configuration remains under `~/.config/gobbler/` until removed manually.
