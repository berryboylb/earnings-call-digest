# Earnings Call Digest

This project reads a plain-text earnings call transcript and produces structured
figures, guidance, risks, and Q&A topics with quotes. It has two working stages:

1. **Parse** turns the transcript into speaker segments. It labels each speaker's
   role and separates prepared remarks from Q&A. Ambiguous input produces warnings
   or a parse error.
2. **Extract** sends those segments to an LLM and validates the shape of its JSON
   response. It records which model answered each section and whether the answer
   came from the cache.

**The extracted claims are not yet checked against the transcript.** Quote and
speaker verification is planned for a later stage; treat the current JSON as
model output, not verified research.

## Run it

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). Copy `.env.example`
to `.env` and set `NVIDIA_API_KEY` and the exact `LLM_MODEL` ID.

```sh
uv sync
uv run main.py
```

It runs every transcript in `data/`: it prints the parsed segments and warnings,
then the extracted items, and writes `out/<name>.extraction.json`. To run one
transcript, put only that file in `data/`.

LLM responses are cached in `.cache/`, so a rerun replays them instead of calling
the API again. Delete `.cache/` to force fresh calls.

Optional fallback models and endpoint settings are described in `.env.example`.
Run tests with `uv run pytest -q`.

## Project layout

```
main.py              entry point: every transcript in data/ -> parse -> extract -> out/
config.py            paths and LLM settings from .env
report.py            console output

schema/
  transcript.py      Participant, Paragraph, Segment, ParsedTranscript
  extraction.py      Figure, Guidance, Risk, QaTopic, Extraction, run results
constants/
  parsing.py         transcript format patterns, word lists, thresholds
  prompts.py         system prompt, section headers, repair text, PROMPT_VERSION
  llm.py             structured-output modes, retries, <think> and JSON-fence patterns
  report.py          console output settings
utils/
  text.py            text normalising, sentence splitting
  names.py           name matching
  llm.py             reading LLM answers: strip <think>, parse JSON, spot rejected requests
  cache.py           disk cache of LLM answers
providers/
  base.py            Provider interface and LlmError
  llm_client.py      LlmClient: sends one request to one model, checks the answer
  nvidia.py          NvidiaProvider: cache, one repair attempt, fallback models
  fixture.py         replays saved answers instead of calling the API (tests)

parsing/             stage 1: transcript -> speaker segments
  parser.py          parse_transcript: the parsing steps in order
  roster.py          participant list
  speakers.py        speaker turns and roles
  sections.py        where Q&A starts
  paragraphs.py      paragraphs and safe-harbor boilerplate
  validation.py      parse errors and warnings
extraction/          stage 2: segments -> structured items
  extractor.py       run_extraction: one LLM call per section
  messages.py        builds the user message from segments

tests/               mirrors the folders above
```

The data flow is `parse_file` → `run_extraction` → `NvidiaProvider.complete`
→ `ExtractionRun`. `FixtureProvider` replaces the API provider for local examples
and tests. Each section can be `ok`, `empty_input`, or `failed`; a failed section
is never presented as an empty extraction.
