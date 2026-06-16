# YouTube Timeout Hardening

Date: 2026-04-14

## Problem

`gobbler batch youtube-playlist` already protects itself with a per-video timeout, but single-video `gobbler youtube` does not.

That means any downstream automation using the single-video command can still hang indefinitely if:
- `youtube-transcript-api` stalls
- proxy/network behavior gets weird
- metadata extraction via `yt-dlp` drags

## Goal

Make `gobbler youtube` safe for automation by adding a first-class timeout path instead of forcing wrapper scripts to kill the process from outside.

## Proposed Change

### CLI
Add a `--timeout` option to `gobbler youtube`.
- default: `120` seconds

### Converter
Thread timeout through `convert_youtube_to_markdown(...)`.

Apply timeout to the synchronous work bundle:
- metadata fetch (`yt-dlp`)
- transcript provider fetch (`youtube-transcript-api` or fallback provider)

Implementation approach:
- run sync work in executor
- wrap with `asyncio.wait_for(...)`
- raise a clean `RuntimeError` when the timeout expires

### Metadata fetch
Add `socket_timeout` to `yt-dlp` metadata extraction as an extra guard.

## Why this belongs upstream

This is not Dylan-specific workflow logic.
It is baseline reliability for anyone automating YouTube transcript extraction.

## Non-goals

- moving playlist scheduling/cursor logic into Gobbler
- redesigning batch orchestration
- changing provider selection behavior

## Expected Outcome

- `gobbler youtube` becomes automation-safe
- wrapper scripts no longer need to invent their own process-kill logic for every video
- errors become clearer: timeout vs unavailable transcript vs rate limit
