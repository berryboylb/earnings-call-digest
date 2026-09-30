# Earnings Call Digest

This project turns a plain-text earnings call transcript into a one-page digest an
analyst can scan in under a minute: key figures, guidance, risk and hedging language,
and what analysts pushed on in Q&A.

An LLM extracts the facts; plain code checks every fact against the transcript; only
checked facts reach the main digest. It runs in four stages:

1. **Parse** turns the transcript into speaker segments. It labels each speaker's
   role and separates prepared remarks from Q&A. Ambiguous input produces warnings
   or a parse error.
2. **Extract** sends those segments to an LLM, one call per section, and validates
   the shape of its JSON answer. Every item carries a verbatim quote.
3. **Verify** finds each quote in the transcript and checks the item: the quote comes
   from management, the numbers appear in the transcript's own words, prior-period
   figures and unsupported guidance directions are flagged, and duplicates are merged.
   It also lists numbers management said that no item covers.
4. **Render** writes the digest as HTML, PDF and DOCX. Only verified items reach the
   main tables; the rest are listed under "Needs review" with the reason.

Verified means the quote, number and speaker match the transcript. It does not prove
a claim is complete or correctly interpreted.

## Run it

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). The PDF needs WeasyPrint's
system libraries (macOS: `brew install pango`); without them, HTML and DOCX are still
written. Copy `.env.example` to `.env` and set `NVIDIA_API_KEY` and the exact
`LLM_MODEL` ID.

```sh
uv sync
uv run main.py
```

It runs every transcript in `data/`, prints each stage's results, and writes a folder
`out/<name>/` with `extraction.json`, `verified.json` and `digest.html`, `digest.pdf`
and `digest.docx`. Call details for the digest's title (company, ticker, quarter, date,
source) come from `data/<name>.json`. To run one transcript, put only that file in
`data/`.

LLM answers are cached in `.cache/`, so a rerun replays them instead of calling the
API again. Delete `.cache/` to force fresh calls. Optional fallback models and endpoint
settings are described in `.env.example`. Run tests with `uv run pytest -q`.

## Project layout

```
main.py              entry point: every transcript in data/ -> parse -> extract -> verify -> render
config.py            paths and LLM settings from .env
report.py            console output

schema/
  transcript.py      Participant, Paragraph, Segment, ParsedTranscript
  extraction.py      Figure, Guidance, Risk, QaTopic, Extraction, run results
  verification.py    Amount, SourceMatch, VerifiedItem, MissedCandidate, VerificationResult
  digest.py          DigestMeta, Table, DigestView
constants/
  parsing.py         transcript format patterns, word lists, thresholds
  prompts.py         system prompt, section headers, repair text, PROMPT_VERSION
  llm.py             structured-output modes, retries, <think> and JSON-fence patterns
  numbers.py         currencies, scales, units, direction words
  verification.py    fuzzy-match thresholds, prior-period and direction keyword rules
  rendering.py       digest texts: banner, trust line, notes, limits line
  report.py          console output settings
utils/
  text.py            text normalising, sentence splitting
  names.py           name matching
  numbers.py         reading and comparing amounts ("$94.9B" = "$94,900 million")
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
verification/        stage 3: items -> checked against the transcript
  verifier.py        verify_run: runs the checks, merges duplicates, finds missed numbers
  matching.py        finds a quote in the transcript, exactly or fuzzily
  checks.py          one function per check
  dedupe.py          merges duplicates, flags conflicting values
  recall.py          numbers management said that no item covers
rendering/           stage 4: verification result -> digest
  view.py            build_view: what the digest shows; every format reads it
  meta.py            call and run details for the title and footer
  html.py            HTML, from templates/digest.html
  pdf.py             PDF, printed from the HTML
  docx.py            Word document

tests/               mirrors the folders above
```

Each extraction section can be `ok`, `empty_input` or `failed`. A failed section is
never shown as an empty result: the digest shows a banner and "Not available".
