# Gobbler Roadmap

Gobbler is an active beta project: the core CLI works today, and the next work focuses on reliability, agent ergonomics, and public packaging polish.

## Current Direction

- **CLI-first:** `gobbler` is the stable automation contract for humans, scripts, and agents.
- **Skills-ready:** markdown Skills teach AI agents the same commands humans use.
- **Browser-aware:** optional browser extension support unlocks authenticated sessions without broad browser access.
- **Maintainable over broad:** integrations that duplicate the CLI are avoided unless they prove durable and easy to test.

## Recently Completed

- Reframed docs around CLI-first usage and Skills.
- Kept unit tests, Ruff, Bandit, Dependency Review, and CodeQL green for the active CLI-first surface.

## Next Milestones

### v0.2.x: Public polish and release hygiene

- Publish the first GitHub release with clear migration notes.
- Keep README badges, docs, changelog, and GitHub topics current.
- Keep Dependabot PRs grouped and low-noise.
- Add small example workflows for common agent tasks.

### v0.3: Reliability hardening

- Make background queue job claiming more robust.
- Store queued commands as structured argv instead of shell-like strings.
- Improve worker cancellation, retries, and stale-job recovery.
- Add more browser-extension validation tests.

### v0.4: Agent experience

- Add more focused Skill examples for Hermes, OpenClaw, and other agent workflows.
- Improve JSON/status output for scripts and agents.
- Add recipe docs for research ingestion, meeting/audio workflows, and document batches.

## Non-Goals

- Adding hosted SaaS behavior to the core project.
- Supporting browser automation outside explicitly selected Gobbler tabs.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for local development and PR guidance. Small, focused PRs with tests and docs are preferred.
