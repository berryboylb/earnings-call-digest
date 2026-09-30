"""Settings for talking to the LLM, and patterns for cleaning up its answers."""

import re

# Rate limits, server errors and dropped connections are retried this many times, pausing
# RETRY_PAUSE_SECONDS longer before each try. Timeouts are not retried: a model that is too
# slow or stuck in a queue hands over to the next model instead.
TRANSIENT_RETRIES = 2
RETRY_PAUSE_SECONDS = 5

# Ways of asking for structured output, most to least strict. Not every NVIDIA-hosted
# model supports json_schema, so the provider steps down if the server rejects one.
STRUCTURED_OUTPUT_MODES = ("json_schema", "json_object", "prompt_only")

# HTTP status codes a server uses to reject a request it can't handle.
REJECTED_REQUEST_STATUS_CODES = (400, 422)
# Words in that error that show the server rejected response_format specifically.
RESPONSE_FORMAT_ERROR_WORDS = ("response_format", "json_schema", "json_object", "guided", "schema")

# At most this many extra quotes may back up one figure or guidance item.
MAX_CONTEXT_QUOTES = 2

# Some models write their reasoning inside <think>...</think> before the answer.
THINK_OPEN_TAG = "<think>"
THINK_CLOSE_TAG = "</think>"
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S | re.I)

# ```json ... ``` (or plain ```) fences around the whole answer.
JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S | re.I)
