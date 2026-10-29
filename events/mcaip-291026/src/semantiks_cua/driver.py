"""Thin wrapper around the [trycua/cua](https://github.com/trycua/cua) Driver.

The Driver is the OS-level input/output layer that actually clicks, types,
and captures screenshots on your real desktop — cross-OS. We depend on it
as a library via the `cua-driver` PyPI package (MIT; see NOTICE.md).

This module exposes two things:

- `DesktopDriver`: a tiny class with `start`, `shutdown`, `screenshot_png`,
  and `execute`. Owns the `CuaDriver` instance.
- `translate_action`: a map from the OpenAI `computer_call` action schema
  (click / type / scroll / keypress / wait / screenshot) to a Driver call.

Both API surfaces are async + `@traceable` so the whole loop shows up in
LangSmith with per-step timing.
"""

from __future__ import annotations

import asyncio
import base64
import sys
from typing import Any

try:
    from cua_driver import (
        ActionTarget,
        ClickButton,
        ClickInput,
        ClickPosition,
        CuaDriver,
        DesktopScope,
        EndSessionInput,
        GetDesktopStateInput,
        HotkeyInput,
        InputDeliveryMode,
        PressKeyInput,
        ScrollBy,
        ScrollDirection,
        ScrollInput,
        TypeTextInput,
    )
except ImportError:
    sys.stderr.write(
        "cua-driver is not installed. Run ./setup.sh to install the Driver + Python client.\n"
    )
    sys.exit(1)

from .events import traceable

# The Driver uses the magic string "primary" to identify the main display's
# "portable desktop target" — see cua_driver/_native_contract.py:1819.
# Passing anything else gets rejected with "portable desktop target must be primary".
PRIMARY_DISPLAY = "primary"


def is_permissions_pending(exc: BaseException) -> bool:
    """Detect the first-run macOS Accessibility / Screen Recording wait."""
    msg = str(exc)
    return "permissions_pending" in msg or "permission is still pending" in msg


class DesktopDriver:
    """A one-session wrapper around trycua `CuaDriver`."""

    def __init__(self) -> None:
        self._driver: CuaDriver | None = None

    async def start(self) -> None:
        # CuaDriver.create() is sync; the per-tool methods are async.
        self._driver = CuaDriver.create()

    async def shutdown(self) -> None:
        if self._driver is None:
            return
        try:
            await self._driver.end_session(EndSessionInput(session=None))
        except Exception:
            # The Driver may already be gone (SIGINT); don't shadow the
            # original error with a cleanup failure.
            pass

    @traceable
    async def screenshot_png(self) -> tuple[bytes, str]:
        """Grab a screenshot. Returns (png_bytes, data_url)."""
        assert self._driver is not None
        result = await self._driver.get_desktop_state(
            GetDesktopStateInput(session=None, screenshot_out_file=None)
        )
        if getattr(result, "is_error", False):
            raise RuntimeError(f"screenshot failed: {getattr(result, 'text', '?')}")
        img = result.images[0]
        mime = getattr(img, "mime_type", "image/png")
        b64 = getattr(img, "data_base64", None)
        if not b64:
            raise RuntimeError(
                "ToolResult.images[0] has no data_base64 — "
                "Driver API drift from cua-driver 0.38."
            )
        return base64.b64decode(b64), f"data:{mime};base64,{b64}"

    @traceable
    async def execute(self, action: dict) -> None:
        """Translate one OpenAI computer_call action into a Driver call."""
        assert self._driver is not None
        kind = action.get("type")

        if kind in ("click", "double_click"):
            await self._driver.click(
                ClickInput(
                    target=_desktop_target(),
                    position=ClickPosition.COORDINATES(
                        x=float(action["x"]), y=float(action["y"])
                    ),
                    # Desktop targets reject BACKGROUND delivery — a real
                    # display click must be FOREGROUND.
                    delivery_mode=InputDeliveryMode.FOREGROUND,
                    session=None,
                    button=ClickButton.LEFT,
                    count=2 if kind == "double_click" else 1,
                )
            )
            return

        if kind == "type":
            await self._driver.type_text(
                TypeTextInput(
                    text=action.get("text", "") or "",
                    target=None,
                    scope=DesktopScope.DESKTOP,
                    session=None,
                )
            )
            return

        if kind == "keypress":
            keys = [str(k).lower() for k in action.get("keys", [])]
            if not keys:
                return
            if len(keys) == 1:
                await self._driver.press_key(
                    PressKeyInput(
                        key=keys[0],
                        target=None,
                        scope=DesktopScope.DESKTOP,
                        session=None,
                        modifiers=[],
                    )
                )
            else:
                await self._driver.hotkey(
                    HotkeyInput(
                        keys=keys,
                        target=None,
                        scope=DesktopScope.DESKTOP,
                        session=None,
                    )
                )
            return

        if kind == "scroll":
            dy = int(action.get("scroll_y", 0))
            await self._driver.scroll(
                ScrollInput(
                    x=float(action.get("x", 0)),
                    y=float(action.get("y", 0)),
                    direction=ScrollDirection.DOWN if dy >= 0 else ScrollDirection.UP,
                    target=_desktop_target(),
                    scope=DesktopScope.DESKTOP,
                    session=None,
                    by=ScrollBy.LINE,
                    amount=max(1, abs(dy) // 20),
                )
            )
            return

        if kind == "wait":
            await asyncio.sleep(1.0)
            return

        if kind == "screenshot":
            # The loop takes a fresh screenshot after every action batch;
            # this one is a no-op.
            return

        raise ValueError(f"unknown action: {action}")


def describe(action: dict) -> str:
    """Human-readable one-liner for a `computer_call` action."""
    kind = action.get("type", "?")
    if kind == "click":
        return f"click ({action.get('x')}, {action.get('y')})"
    if kind == "double_click":
        return f"double-click ({action.get('x')}, {action.get('y')})"
    if kind == "type":
        text = (action.get("text") or "")[:60]
        return f"type: {text!r}"
    if kind == "keypress":
        return f"keys: {'+'.join(action.get('keys', []))}"
    if kind == "scroll":
        return f"scroll Δy={action.get('scroll_y', 0)}"
    if kind == "wait":
        return "wait"
    if kind == "screenshot":
        return "screenshot"
    return kind


def _desktop_target() -> Any:
    return ActionTarget.DESKTOP(display_id=PRIMARY_DISPLAY)
