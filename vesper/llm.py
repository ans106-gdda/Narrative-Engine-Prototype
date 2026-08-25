import hashlib
import json
import os
import time
from pathlib import Path

import anthropic
import dotenv

from vesper import world

dotenv.load_dotenv()

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "llm_calls.jsonl"


class LLMError(RuntimeError):
    ...


def _log(fn: str, system: str, user: str, output, usage, stop_reason) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.time(),
        "fn": fn,
        "system_hash": hashlib.sha256(system.encode("utf-8")).hexdigest(),
        "user": user,
        "output": output,
        "usage": usage,
        "stop_reason": stop_reason,
    }
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def complete(system: str, user: str, max_tokens: int = 4096, effort: str = "medium") -> str:
    response = _client.messages.create(
        model=world.MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort},
    )

    text = "".join(b.text for b in response.content if b.type == "text").strip()

    usage = response.usage.model_dump() if response.usage else None
    _log("complete", system, user, text, usage, response.stop_reason)

    if response.stop_reason != "end_turn":
        raise LLMError(f"truncated or refused: {response.stop_reason}")
    if not text:
        raise LLMError("empty text extracted from response")

    return text


def parse(system: str, user: str, model_cls, max_tokens: int = 4096):
    response = _client.messages.parse(
        model=world.MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=model_cls,
    )

    parsed = response.parsed_output
    usage = response.usage.model_dump() if response.usage else None
    _log(
        "parse",
        system,
        user,
        parsed.model_dump() if parsed is not None else None,
        usage,
        getattr(response, "stop_reason", None),
    )

    if parsed is None:
        raise LLMError("parsed_output was None")

    return parsed
