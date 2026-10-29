"""Terminal UI — the user-facing `semantiks-cua` command.

Owns the Rich `Console`. Builds the deepagents planner and streams its
events: tool calls appear as `tool: drive_computer` / `tool: fetch_url`
badges, and inside a `drive_computer` run each CUA action streams as
`→ click (x, y)` lines via the shared `Agent` singleton.
"""

from __future__ import annotations

import asyncio
import os

from rich.console import Console
from rich.panel import Panel

from .driver import describe, is_permissions_pending
from .events import flush, langsmith_enabled, posthog_enabled
from .planner import build_graph, run_turn, session_dir, set_hooks, shutdown_agent, _get_agent

console = Console()


def main() -> None:
    """Entry point registered as the `semantiks-cua` script."""
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


async def _run() -> None:
    _render_banner()

    if not os.environ.get("OPENAI_API_KEY"):
        console.print(
            "[red]✗ OPENAI_API_KEY not set — edit .env and try again.[/red]"
        )
        return

    # Wire terminal output into the Agent that drive_computer wraps so
    # per-action lines stream back to the user in real time.
    set_hooks(
        on_action=lambda a: console.print(f"  [magenta]→ {describe(a)}[/magenta]"),
        on_action_error=lambda _a, e: console.print(
            f"  [red]action failed: {type(e).__name__}: {e}[/red]"
        ),
    )

    graph = build_graph()

    try:
        # Boot the shared Agent eagerly so first-run OS-permission errors
        # land as a readable banner instead of a traceback deep in a tool.
        with console.status("[cyan]starting cua-driver…[/cyan]", spinner="dots"):
            agent = await _get_agent()
            try:
                await agent.smoke_test()
            except Exception as exc:
                if is_permissions_pending(exc):
                    _render_permissions_help()
                    return
                raise

        _render_session_header()
        history: list[dict] = []

        while True:
            try:
                prompt = console.input("[bold cyan]› [/bold cyan]")
            except (EOFError, KeyboardInterrupt):
                console.print()
                return
            if not prompt.strip() or prompt.strip().lower() in {"exit", "quit"}:
                return
            try:
                with console.status("[blue]thinking…[/blue]", spinner="dots"):
                    reply = await run_turn(
                        graph,
                        history,
                        prompt,
                        on_tool_start=lambda name, inp: console.print(
                            f"  [yellow]tool: {name}[/yellow]  [dim]{inp}[/dim]"
                        ),
                    )
                console.print(f"[green]{reply}[/green]\n")
            except KeyboardInterrupt:
                console.print("[red]  [interrupted][/red]\n")
    finally:
        await shutdown_agent()
        flush()
        sd = session_dir()
        if sd:
            console.print(f"[dim]session saved → {sd}/[/dim]")


# ----- UI chrome -----------------------------------------------------------


def _render_banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]semantiks-cua[/bold cyan]\n"
            "[dim]deepagents planner · computer-use via trycua/cua · "
            "ctrl-d or 'exit' to quit[/dim]",
            border_style="cyan",
        )
    )


def _render_session_header() -> None:
    sd = session_dir()
    if sd:
        console.print(f"[dim]session → {sd}/[/dim]")
    if posthog_enabled():
        console.print("[dim]PostHog event capture: on[/dim]")
    if langsmith_enabled():
        console.print("[dim]LangSmith tracing: on[/dim]")
    console.print()


def _render_permissions_help() -> None:
    console.print(
        "[red]✗ cua-driver is blocked on OS permissions.[/red]\n"
        "   Grant Accessibility AND Screen Recording to your terminal:\n"
        "   [dim]System Settings → Privacy & Security → Accessibility\n"
        "                                      → Screen Recording[/dim]\n"
        "   Or run:  [bold]cua-driver permissions grant[/bold]\n"
        "   Then rerun [bold]semantiks-cua[/bold]."
    )
