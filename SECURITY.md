# Security and privacy

## Intended boundary

This repository contains reusable code and synthetic fixtures. Real activities,
credentials, race plans, check-ins, reports, and history belong in private runtime
storage. Strava Coach is a single-user command-line tool, not a hosted service or
credential vault.

## Data flow

| Action | Destination | Data sent |
| --- | --- | --- |
| Normal report | Strava | OAuth refresh request and authenticated activity reads |
| `--send` | Gmail and recipient mail provider | Full HTML and text report |
| `--ai` | Anthropic | Documented coaching payload below |
| Offline example | None | Reads synthetic local files only |

The AI payload contains the goal, selected profile measurements, weekly summary,
matched-HR trend, up to four saved weekly summaries, coming plan, and each completed
run's date, name, distance, pace, average/max HR, temperature, power, and athlete
note. It excludes activity IDs, routes, GPS, laps, check-ins, and credentials.
Activity names, notes, and plan context can still contain private free text.

## Implemented controls

- Email, AI, and history each require an explicit command option. Simulation and
  offline reports cannot enable them.
- The OAuth helper uses a random state value, a loopback callback, a one-time code,
  and least-privilege activity scope by default. `--read-private` is explicit.
- Tokens and reports use atomic replacement and owner-only file modes. Authenticated
  provider requests verify TLS, use bounded timeouts, and reject redirects.
- Tokens are sent in headers or request bodies, never query strings. Provider
  responses and private inputs are omitted from normal error output.
- HTML output escapes activity names, notes, configuration, and AI text.
- Public CI has read-only permissions, pinned Actions, synthetic fixtures, and no
  schedule, secrets, report artifacts, or write-capable job.
- A repository test checks common private filenames and credential patterns.
  Dependabot checks Python and GitHub Actions dependencies weekly.

## Residual risks

File permissions are not encryption and cannot protect a compromised computer or
user account. Anyone with access to the report or its recipient mailbox can read
the included health and training information. Opt-in AI sends the payload above to
Anthropic. Model output is interpretation rather than verified medical or coaching
advice.

Activity and configuration text is untrusted. The model receives no tools and
cannot access tokens or send mail independently, but a prompt filter cannot provide
an absolute guarantee about generated content. Review AI output before acting on it.

Strava may rotate refresh tokens, so unattended use needs durable private state.
Public CI caches, artifacts, logs, issues, and pull requests are unsuitable for
that state. The tracked-file test detects only known patterns and cannot prove that
a commit contains no personal data or vulnerability.

## Reporting a vulnerability

Use GitHub's **Report a vulnerability** option if it is enabled. Otherwise, open a
non-sensitive issue asking the maintainer for a private contact channel. Do not put
credentials, personal activities, or exploit details in a public issue.

If a credential was exposed, revoke or rotate it first. Removing the current file
or adding it to `.gitignore` does not erase earlier commits, branch refs, pull-request
refs, forks, or clones. Historical cleanup can require a coordinated history rewrite
and GitHub Support. Follow [GitHub's removal guide](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
