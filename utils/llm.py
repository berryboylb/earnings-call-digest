"""Helpers for LLM answers: removing reasoning, parsing JSON, and reading API errors."""

import json

import openai
from pydantic import BaseModel, ValidationError

from constants.llm import (
    JSON_FENCE,
    REJECTED_REQUEST_STATUS_CODES,
    RESPONSE_FORMAT_ERROR_WORDS,
    THINK_BLOCK,
    THINK_CLOSE_TAG,
    THINK_OPEN_TAG,
)
from constants.prompts import SCHEMA_INSTRUCTIONS


def strip_reasoning(content: str) -> str:
    """Remove the <think>...</think> reasoning some models write before their answer."""
    text = THINK_BLOCK.sub("", content)

    # Only a closing tag is left: the reasoning started before the output. Keep what follows it.
    close_tag_at = text.lower().rfind(THINK_CLOSE_TAG)
    if close_tag_at != -1:
        text = text[close_tag_at + len(THINK_CLOSE_TAG):]

    # Only an opening tag is left: the model never finished reasoning. Drop everything from it.
    open_tag_at = text.lower().find(THINK_OPEN_TAG)
    if open_tag_at != -1:
        text = text[:open_tag_at]

    return text.strip()


def parse_model_output(content: str, schema: type[BaseModel]) -> BaseModel:
    """Turn the model's answer into a validated schema object.

    Raises ValueError, with a readable message, if the answer isn't valid JSON
    or doesn't match the schema.
    """
    fenced = JSON_FENCE.match(content)
    if fenced:
        content = fenced.group(1)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(f"not valid JSON ({error})") from error
    try:
        return schema.model_validate(data)
    except ValidationError as error:
        raise ValueError(str(error)) from error


def schema_instructions(schema_json: dict) -> str:
    """Text that tells the model which JSON schema to follow, for the system prompt."""
    return SCHEMA_INSTRUCTIONS + json.dumps(schema_json)


def is_response_format_error(error: openai.APIStatusError) -> bool:
    """True if the server rejected the request because it doesn't support our response_format."""
    if error.status_code not in REJECTED_REQUEST_STATUS_CODES:
        return False
    error_text = f"{error.message} {json.dumps(error.body, default=str)}".lower()
    for word in RESPONSE_FORMAT_ERROR_WORDS:
        if word in error_text:
            return True
    return False
