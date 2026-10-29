"""The agent loop: screenshot → gpt-6.1-sol → execute → repeat.

Owns one `DesktopDriver` session and one chain of `previous_response_id`s
(the OpenAI Responses API trick that lets us send only the latest tool
output instead of the full history — 10× cheaper over long runs).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

from openai import AsyncOpenAI

from .driver import DesktopDriver
from .events import emit, traceable

MODEL = os.environ.get("CUA_MODEL", "gpt-6.1-sol")
MAX_STEPS = 40
TRACES_DIR = Path("traces")

SYSTEM = """You control the user's computer directly. The screenshots you see
are the user's actual desktop. Be decisive and persistent.

- Launch an app with Spotlight: press Cmd+Space, type the app name, Enter.
- Interact with native UI: dock icons, menu bars, windows.
- When the task is complete, respond in one short sentence summarizing what
  you did. Do not keep taking actions after you have answered.
"""


ActionCallback = Callable[[dict], None]
ErrorCallback = Callable[[dict, BaseException], None]


class Agent:
    """Model loop that pairs OpenAI's computer tool with the trycua Driver."""

    def __init__(
        self,
        *,
        on_action: Optional[ActionCallback] = None,
        on_action_error: Optional[ErrorCallback] = None,
    ) -> None:
        self._openai = AsyncOpenAI()
        self._driver = DesktopDriver()
        self._on_action = on_action or (lambda _a: None)
        self._on_action_error = on_action_error or (lambda _a, _e: None)
        self.session_id = f"session-{int(time.time())}"
        self.session_dir = TRACES_DIR / self.session_id
        self._step = 0

    # ----- lifecycle -------------------------------------------------------

    async def start(self) -> None:
        await self._driver.start()
        TRACES_DIR.mkdir(parents=True, exist_ok=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        emit(self.session_id, "session_start", {})

    async def shutdown(self) -> None:
        emit(self.session_id, "session_end", {"steps": self._step})
        await self._driver.shutdown()

    async def smoke_test(self) -> None:
        """One screenshot early so permission errors surface immediately."""
        await self._screenshot_data_url()

    # ----- the loop --------------------------------------------------------

    @traceable
    async def run_turn(self, user_prompt: str) -> str:
        """One user prompt → model loop until a text answer or MAX_STEPS."""
        emit(self.session_id, "turn_start", {"prompt": user_prompt})

        screenshot = await self._screenshot_data_url()
        inputs: list[Any] = [
            {"role": "developer", "content": SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_prompt},
                    {"type": "input_image", "image_url": screenshot},
                ],
            },
        ]
        previous_response_id: Optional[str] = None

        for _ in range(MAX_STEPS):
            response = await self._openai.responses.create(
                model=MODEL,
                input=inputs,
                tools=[{"type": "computer"}],
                truncation="auto",
                previous_response_id=previous_response_id,
            )
            previous_response_id = response.id

            computer_calls = [o for o in response.output if o.type == "computer_call"]
            if not computer_calls:
                text = _extract_text(response.output)
                emit(self.session_id, "turn_end", {"ok": True, "chars": len(text)})
                return text or "[model produced no text]"

            call = computer_calls[-1]
            # `actions` can be None on reasoning-only computer_calls; still
            # send a fresh screenshot back so the loop advances.
            for raw_action in call.actions or []:
                action = _as_dict(raw_action)
                self._on_action(action)
                emit(self.session_id, "cua_action", {"action": action})
                try:
                    await self._driver.execute(action)
                except Exception as exc:
                    self._on_action_error(action, exc)

            screenshot = await self._screenshot_data_url()
            inputs = [
                {
                    "type": "computer_call_output",
                    "call_id": call.call_id,
                    "output": {
                        "type": "computer_screenshot",
                        "image_url": screenshot,
                    },
                }
            ]

        emit(self.session_id, "turn_end", {"ok": False, "reason": "max_steps"})
        return "[hit max steps without a text answer]"

    # ----- helpers ---------------------------------------------------------

    async def _screenshot_data_url(self) -> str:
        png, data_url = await self._driver.screenshot_png()
        self._step += 1
        (self.session_dir / f"step-{self._step:03d}.png").write_bytes(png)
        return data_url


def _as_dict(raw_action: Any) -> dict:
    if hasattr(raw_action, "model_dump"):
        return raw_action.model_dump()
    return dict(raw_action)


def _extract_text(outputs: list) -> str:
    parts: list[str] = []
    for item in outputs:
        content = getattr(item, "content", None)
        if content is None:
            continue
        for block in content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
    return "".join(parts).strip()
