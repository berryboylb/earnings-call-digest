"""How the prepared remarks are split into LLM calls."""

# Each prepared-remarks speaker turn is its own call. A turn longer than this is split into
# parts at paragraph boundaries, so no single call is too big for the API's gateway.
MAX_WORDS_PER_CALL = 2500
# Every part after the first also gets this many paragraphs from before it, as read-only
# context, so the model knows which period or topic the text is about.
CONTEXT_PARAGRAPHS = 2
