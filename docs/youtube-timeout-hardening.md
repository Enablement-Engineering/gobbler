# YouTube timeout behavior

`gobbler youtube` and `gobbler batch youtube-playlist` bound transcript conversion work so automation does not wait indefinitely on YouTube, proxy, provider, or metadata operations.

## Single-video command

```bash
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --timeout 120
```

- `--timeout/-t` is the full conversion timeout in seconds.
- Default: `120` seconds.
- The bound includes synchronous metadata and transcript-provider work run through the converter's executor path.
- Timeout failures use the normal CLI error contract: human-readable stderr/console output in Markdown mode and a JSON error object in `--format json` mode.

This option is implemented in the current CLI; wrapper scripts no longer need to provide the only process-level timeout for normal single-video conversion.

## Playlist command

Playlist conversion applies a per-video timeout while processing concurrent items. The playlist CLI does not currently expose a timeout flag; its implementation uses the internal playlist timeout constant.

```bash
gobbler batch youtube-playlist \
  "https://youtube.com/playlist?list=PLAYLIST_ID" \
  -o ./transcripts --concurrency 3
```

A timed-out item is reported as a failed batch item while other eligible items continue. In `--json` mode, parse the JSON Lines events and final `batch_complete` summary.

## What timeout does not change

- It does not change provider selection or fallback policy.
- It does not bypass YouTube rate limits or IP blocks.
- It does not make a non-thread-cancellable synchronous library call stop instantaneously inside its worker thread; it bounds how long the async command waits before reporting failure.
- It does not replace an outer orchestration timeout when a caller needs a hard process-kill guarantee.

## Troubleshooting

If a normal video times out:

1. Retry with a larger bound:

   ```bash
   gobbler youtube "URL" --timeout 240
   ```

2. Run `gobbler status --json` to inspect YouTube fallback and proxy readiness.
3. Try another caption language or video.
4. Wait after an IP block, configure a documented proxy, or configure `TRANSCRIPTAPI_KEY` fallback.

Do not include credential-bearing URLs in logs or issue reports. Gobbler sanitizes known diagnostic URL surfaces, but callers should still treat submitted URLs as potentially sensitive.
