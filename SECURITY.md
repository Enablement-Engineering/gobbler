# Security Policy

## Supported Versions

Gobbler is currently in active beta. Security fixes target the latest commit on `main` and the latest published release.

| Version | Supported |
| --- | --- |
| 0.2.x | Yes |
| 0.1.x | Best effort |

## Reporting a Vulnerability

Please report suspected security issues privately instead of opening a public issue.

- Email: dylan@enablement.engineering
- Include: affected version/commit, reproduction steps, impact, and any relevant logs.
- Please avoid including secrets, tokens, private documents, or private URLs in reports.

I will acknowledge credible reports as quickly as practical and coordinate a fix or mitigation before public disclosure.

## Security Model

Gobbler is primarily a local CLI tool. Important boundaries:

- Browser command guards check whether a tab's group ID matches the extension's stored `gobblerGroupId`. A different group with the same visible title does not match, but manually moving a tab into the existing extension-managed group does make it eligible for commands.
- Site-origin permissions gate scripting-based extraction and page-API injection, but they do **not** gate `gobbler browser exec`. That command uses Chrome's debugger permission and can execute JavaScript with page-side effects in any group-eligible tab; the attachment may persist until tab close or relay disconnect.
- Document and web conversion may call local Docker services such as Docling and Crawl4AI.
- Output markdown can contain content from untrusted sources; review generated files before publishing them.
- Do not pass secrets, cookies, private URLs, or confidential documents to third-party services unless you intentionally configured that provider.

## Dependency and CI Hygiene

The repository uses GitHub Actions, Dependabot, Ruff, Bandit, and unit tests to catch common quality/security issues. Dependency updates are reviewed through pull requests rather than merged automatically.
