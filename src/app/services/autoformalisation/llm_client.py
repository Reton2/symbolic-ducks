from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.services.autoformalisation.err import LLMExtractionError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _build_augmented_messages(
    messages: list[dict[str, Any]], response_model: type[T]
) -> list[dict[str, Any]]:
    """Augments messages with system instruction containing response model JSON schema."""
    json_schema = response_model.model_json_schema()
    system_instruction = (
        "Respond with a valid JSON object strictly complying with the following JSON Schema.\n"
        "Think deeply about the task given and make sure you complete it fully.\n"
        f"{json.dumps(json_schema, indent=2)}"
    )
    return [
        {"role": "system", "content": system_instruction},
        *messages,
    ]


def _clean_json_text(raw_text: str) -> str:
    """Strips markdown code fence wrappers from raw JSON output."""
    clean = raw_text.strip()
    if "```" in clean:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
        if match:
            clean = match.group(1).strip()
    return clean


def _parse_json_payload(clean_text: str) -> dict[str, Any]:
    """Parses JSON text into dictionary with resilient boundary slice fallback."""
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        first_brace = clean_text.find("{")
        last_brace = clean_text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return json.loads(clean_text[first_brace : last_brace + 1])
        raise


async def _execute_completion(
    client: AsyncOpenAI, create_kwargs: dict[str, Any]
) -> str:
    """Executes chat completion with JSON object response format fallback."""
    try:
        try:
            resp = await client.chat.completions.create(
                response_format={"type": "json_object"},
                **create_kwargs,
            )
        except Exception:
            resp = await client.chat.completions.create(**create_kwargs)
        return resp.choices[0].message.content or "{}"
    except Exception as exc:
        logger.error("LLM API invocation failed: %s", exc)
        raise LLMExtractionError(f"LLM API request error: {exc}") from exc


async def chat_completion_parse(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict[str, Any]],
    response_model: type[T],
    temperature: float = 0.0,
    **kwargs: Any,
) -> T:
    augmented = _build_augmented_messages(messages, response_model)
    create_kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": augmented,
        "extra_body": {
            "reasoning": {"enabled": True},
            "provider": {"only": ["alibaba"], "allow_fallbacks": False},
        },
        **kwargs,
    }

    raw_content = await _execute_completion(client, create_kwargs)
    clean_text = _clean_json_text(raw_content)

    try:
        parsed_dict = _parse_json_payload(clean_text)
        return response_model.model_validate(parsed_dict)
    except Exception as exc:
        logger.error(
            "Failed to parse structured model %s: %s", response_model.__name__, exc
        )
        raise LLMExtractionError(
            f"Failed to parse {response_model.__name__} from LLM response: {exc}"
        ) from exc
