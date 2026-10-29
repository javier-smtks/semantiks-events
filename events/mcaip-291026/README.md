# Semantiks CUA

Chat with an AI agent that controls your laptop. Cross-OS. Five files, ~400 lines.

Built for the **[MEXICO CITY: Agents In Production | LangChain Meetup](https://luma.com/mxtw-e354f23b)** at Mexico Tech Week.
More Semantiks events: **https://www.semantiks.com/events**.

## What's inside

- **LangChain `deepagents` planner** — `gpt-6.1-sol` routes between two tools:
  - **`fetch_url(url)`** — plain HTTP GET for factual questions with a known URL.
  - **`drive_computer(task)`** — takes over the whole desktop (see below).
- **`openai`** → `gpt-6.1-sol` with the GA `computer` tool emits the low-level actions inside `drive_computer`.
- **[`trycua/cua`](https://github.com/trycua/cua) Driver** executes those actions on your real desktop. Works on macOS, Windows, Linux.
- **LangSmith** traces every step and screenshot.
- **PostHog** (optional) captures `turn_start`, `cua_action`, `turn_end` events.
- **`rich`** draws the terminal UI.

## Setup (one time)

```bash
./setup.sh
# edit .env — paste OPENAI_API_KEY
# optional: LANGSMITH_API_KEY + LANGSMITH_TRACING=true
# optional: POSTHOG_API_KEY
```

`setup.sh` installs:
1. The trycua/cua Driver (native binary, cross-OS)
2. A `uv` virtualenv at `.venv`
3. Python deps + the `semantiks-cua` command

## Use it

```bash
source .venv/bin/activate
semantiks-cua
```

Opens a terminal chat. Type what you want the computer to do:

```
› open Spotify and play my daily mix
› in the current VS Code window, find all TODO comments
› open Finder, show my Downloads folder sorted by date
```

For each turn you'll see each `→ click (x, y)` / `→ type: '…'` streamed as the agent works, then its one-line summary when it's done. Ctrl+C interrupts the current task; Ctrl+D or `exit` quits.

## Where the session goes

- `traces/session-<ts>/step-NNN.png` — every screenshot the model saw, in order. `open traces/session-<ts>/` to flip through them in Finder.
- **LangSmith** (if enabled): full step-by-step trace with model inputs, outputs, timing, and inline screenshots.
- **PostHog** (if enabled): `session_start`, `turn_start`, `cua_action`, `turn_end`, `session_end` events — build funnels, measure success rates. **Not** DOM session replay — PostHog is the wrong tool for that; use the local PNG trail instead.

## Files

| File | What it does |
|------|-------------|
| `setup.sh` | Installs the cua Driver, uv venv, Python deps |
| `pyproject.toml` | Deps + the `semantiks-cua` script registration |
| `.env.example` | Required/optional env vars |
| `README.md` | This |
| `src/semantiks_cua/__init__.py` | Package entry — loads `.env` and re-exports `main` |
| `src/semantiks_cua/__main__.py` | `python -m semantiks_cua` entry point |
| `src/semantiks_cua/cli.py` | Rich terminal UI; streams planner + per-action events |
| `src/semantiks_cua/planner.py` | **The LangChain layer**: deepagents graph + `fetch_url` and `drive_computer` tools |
| `src/semantiks_cua/agent.py` | The computer-use loop — `gpt-6.1-sol` + the GA `computer` tool |
| `src/semantiks_cua/driver.py` | Thin wrapper around trycua/cua + action translation |
| `src/semantiks_cua/events.py` | LangSmith `@traceable` + PostHog `emit` (both soft deps) |

## Honest caveats

- **Permissions on first run.** macOS will prompt for Accessibility + Screen Recording. Linux may ask for AT-SPI/X11 access. Grant them to your terminal (or whichever process launched `semantiks-cua`). The Driver prints a clear error if a permission is missing.
- **Raw-coord clicks.** OpenAI's `computer` tool emits raw `(x, y)` pixel coords. We pass those to the Driver via `ClickPosition.COORDINATES(x, y)` with `ActionTarget.DESKTOP("primary")` and `InputDeliveryMode.FOREGROUND` — the three values the Driver insists on. If a specific OS/version misses a click, those three constants in `driver.py` are where to look first.
- **Action blocklist.** We do NOT currently refuse destructive actions at the Driver level. For personal daily use, add a blocklist in `src/semantiks_cua/driver.py:DesktopDriver.execute` for `Cmd+Q`, deletions, etc. For a controlled demo on your own laptop, you'll see every action in the terminal as it fires.
- **Model availability.** `gpt-6.1-sol` is gated; make sure your OpenAI org has access. Both the planner and the CUA loop default to it (override planner via `AGENT_MODEL`, CUA via `CUA_MODEL`).
- **Multi-turn history.** Cross-turn, we persist only user prompts + final text replies, dropping intermediate tool messages. Side-effect: the planner doesn't "remember" what tools it used last turn.

## Credits

- **[trycua/cua](https://github.com/trycua/cua)** — MIT © trycua. The cross-OS Driver that actually clicks, types, and screenshots on your real desktop. We depend on it as a library (`pip install cua-driver`) and don't vendor or modify its code. See `NOTICE.md` for the full license acknowledgment.
- **LangSmith** — © LangChain, Inc. Trace observability.
- **PostHog** — © PostHog, Inc. Lightweight event capture.
- **OpenAI** — `gpt-6.1-sol` + the GA `computer` tool.
- Event hosts: Semantiks and Mexico Tech Week — see [semantiks.com/events](https://www.semantiks.com/events).

Repository license: [MIT](../../LICENSE) © 2026 Semantiks Inc.
