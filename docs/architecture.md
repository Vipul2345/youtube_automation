# Architecture decision record — Phase 1

Status: configuration and packaging implemented; service, rendering, orchestration,
and automation contracts below are design decisions for Phases 2–5, not claims of
an already working uploader.

## Runtime and layout

Use Python 3.12 (supported range 3.12–3.13), with a real installable package at
`src/shorts_pipeline`. This avoids importing a generic package named `src` and works
regardless of the invoking working directory. Python provides the native `edge-tts`
stream, Pydantic JSON Schema/validation, Google's official OAuth/upload libraries,
and safe `subprocess` argument lists without Node-to-Python bridges. No MoviePy,
browser automation, GitHub Pages, paid voice API, or shell-generated FFmpeg commands.

`pyproject.toml` pins direct dependencies; `requirements.lock` pins and hashes the
resolved runtime and development dependencies. The initial lock is generated with
Python 3.12 on Windows; Linux installation must also be verified when the workflow
is built. The `.venv` is local-only. FFmpeg/ffprobe are system dependencies and must
include libass, libx264, AAC, loudnorm, and alimiter support.

| Dependency | Purpose |
| --- | --- |
| edge-tts | Audio plus explicitly requested WordBoundary events |
| httpx | Official Gemini REST endpoint, Pexels, streaming downloads, GitHub state |
| pydantic / pydantic-settings | Strict generated-content schemas and environment configuration |
| google-api-python-client | Official YouTube resumable upload client |
| google-auth / google-auth-oauthlib | Refresh-token authentication and local loopback consent |
| pytest / ruff | Offline tests, lint, and format verification |

Dependency names and current versions were checked against PyPI on 2026-09-06.
Gemini uses the official REST API, not the deprecated `google-generativeai` SDK.
Default: `gemini-3.1-flash-lite`, a stable Flash-class model supporting structured
outputs with free text input/output listed by Google. It is deliberately configurable,
not an obsolete fixed model or an auto-changing `latest` alias.

Sources checked:
- https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite
- https://ai.google.dev/gemini-api/docs/pricing
- https://pypi.org/project/edge-tts/

## Stage contracts for subsequent phases

1. Read persistent recent history before the single normal Gemini request. Request
   hook, three sections with visual keywords, CTA, topic/category and YouTube metadata
   as one JSON document. Validate strictly; only safe syntax repairs and a finite
   retry budget are allowed. Apply content-hash and topic-similarity checks locally.
   A similarity heuristic cannot mathematically guarantee semantic uniqueness; fail
   closed on detected overlap and include recent topics in the generation prompt.
2. TTS is behind a provider protocol. Edge must request `boundary="WordBoundary"`
   explicitly (the current package can default to sentence boundaries). Persist
   original offset/duration ticks and normalized seconds from actual events; reject
   missing/invalid word metadata. Never synthesize caption times from text length
   or a words-per-second assumption. Validate actual audio duration before rendering.
3. Resolve section keyword visuals with bounded search/download budgets: portrait,
   crop-able landscape, alternate keyword, alternate relevant result, curated local
   asset, then a programmatically animated background. Store source/license attribution
   in the run manifest. No stock result is a supported condition, not a fatal error.
   No curated media is bundled in Phase 1; do not imply absent assets are licensed.
4. Generate ASS from actual word metadata; render 1080x1920, 30 FPS H.264/AAC with
   FFmpeg using argument arrays. Stage files use controlled names and paths, not LLM
   text. Validate probe results and subtitle-burn execution evidence before upload.
5. Dry run renders and validates but cannot upload. Live upload uses an OAuth refresh
   token and resumable upload; persist a private upload journal before remote effects.
   Commit published topic history only after confirmed upload success and validation.
   Persist explicit dry-run history only if opted in, clearly labeled as not published.
6. Twice-daily Actions execution will serialize the entire generation/upload/state
   operation with `cancel-in-progress: false`, upload only allowlisted safe artifacts,
   and clean only per-run temporary directories. Stage CLIs arrive with orchestration.

## Persistence trade-off and decision

| Option | Benefit | Reliability / operational cost |
| --- | --- | --- |
| Commit history into default source branch | Simple, durable | Pollutes source history, branch protections conflict, can retrigger workflows |
| Actions artifacts | Built in, no source writes | Expire or can be deleted; latest-success lookup and crash recovery are fragile |
| Actions cache | Fast | Evictable and immutable per key; not a transactional database |
| GitHub issue body | Durable without content writes | Public chatter, issue permission, no simple SHA compare-and-swap update |
| External free database | Transactions and durability | Extra account/secrets, free-tier lifecycle/quotas, more setup and dependency risk |
| Dedicated repository state branch | Durable, same account, SHA-guarded updates | Requires contents write; branch/rules configuration; journal privacy needs care |

Choose a **dedicated `shorts-state` branch**, not commits to the source branch, after
weighing the alternatives. It holds only bounded non-secret topic history and
non-secret operation markers. Local development uses an ignored JSON ledger in
`state/`. Future GitHub state updates must use the Contents API blob SHA for
compare-and-swap, re-read/merge on bounded conflicts, and fail closed if state cannot
be read. First-time initialization must be explicit and distinguish missing state
from a corrupt or inaccessible ledger. One workflow concurrency group per channel
must include manual and scheduled runs. Run only one repository writer per channel.

The execution job will require `contents: write` (GitHub's minimum permission for
this API); do not request issues, pull-requests, packages, or administration writes.
Use the ephemeral `GITHUB_TOKEN`, not a broad PAT. State must never contain OAuth
tokens, API keys, resumable session URLs, full request/response bodies, or dotenv.
Public repositories expose state-branch metadata; use a private repo if that matters
and accept its Actions free-minute/storage limits. Durable pending-operation markers
must distinguish uncertain uploads from published topics. YouTube and GitHub cannot
participate in an atomic transaction: after an ambiguous upload completion or a
failed post-upload history write, do not blindly start a second upload. Reconcile
when possible; otherwise stop safely and report the unresolved operation. Routine
scheduled runs are unattended, but exceptional failures can require operator repair.

## Configuration, security, and cost boundaries

- Importing settings has no I/O. `load_settings()` explicitly reads root `.env`;
  process environment wins. Empty variables use defaults. Unknown dotenv keys fail
  validation to catch typos. Stage credential preflight permits offline render tests
  and stock fallback without keys. Dry run still needs Gemini for real generation.
- Secret fields use `SecretStr`, are hidden from repr, and validation text hides
  input values. Never log a settings dump, raw exception payload, or
  `ValidationError.errors()`; those can bypass presentation redaction.
- Generated directory paths resolve against the project root, must remain inside
  it, and cannot overlap source, fallback, or each other. These checks complement,
  not replace, later safe per-run creation and cleanup.
- Zero direct cost is conditional, not an unlimited-service promise. Use Gemini
  free-tier access with billing disabled, and do not automatically switch to a paid
  model. Free-tier availability and quotas vary by model, project, and region.
- `edge-tts` is open source but uses Microsoft's online Edge endpoint: it is not an
  official hosted API with an SLA. The library license does not grant blanket rights
  to Microsoft's service or voices. Verify applicable service terms before unattended
  publishing; blocks or protocol changes must stop safely, never trigger paid fallback.
- Pexels free API access has rate limits, licensing and attribution rules. GitHub
  Actions hosted-runner minutes/storage are limited for private repositories; public
  repository standard-runner use is subject to GitHub terms and usage policy. Keep
  billing disabled/at zero, short artifact retention, and bounded render/search budgets.
- YouTube has API quotas and spam/quality policies. OAuth alone does not allow public
  uploads from projects subject to the unverified-project private-only restriction;
  the applicable audit/compliance process must be completed. Testing-mode consent
  refresh tokens can expire, and account revocation always remains possible.
- There is no guarantee of perpetual free availability, exact cron start times,
  factual perfection from an LLM, monetization eligibility, or maintenance-free use.
  The design stops rather than spending money or publishing invalid/uncertain work.

## Phase 1 validation commands (PowerShell, workspace root)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
ffmpeg -version
ffprobe -version
```

The full runbook, OAuth helper, workflow and stage commands belong to Phase 5.