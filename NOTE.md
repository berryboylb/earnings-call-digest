Earnings Call Digest: note

What it is. A tool that turns an earnings call transcript into a one-page digest for a research analyst: headline figures, guidance, risk language, and what analysts pushed on in Q&A. An LLM finds the facts, and plain code decides what gets shown. Every item must carry a verbatim quote. A verification step checks that the quote is in the transcript, that management (not an analyst) said it, and that the numbers match the transcript's own text. Items that fail are listed under "Needs review" with the reason, never silently dropped.

Tools and model. Python. Parsing, verification, rendering and evaluation are deterministic; only extraction calls a model. I used nvidia/nemotron-3-super-120b through NVIDIA's OpenAI-compatible API, with gpt-oss-20b as a fallback, and a strict JSON schema validated with pydantic. I chose it because I had access to it and it handled structured output reliably. Because the client is OpenAI-compatible, switching models is a config change, but I'd rerun the evaluation before trusting a new one. Each speaker's prepared remarks go to the model as a separate call, so a provider error costs one part of the digest, not the whole section. The digest says exactly which part is missing and which model answered each section.

Where I'd trust it. "Verified" means grounded, not correct. I labelled an answer key for a test transcript by hand and scored three runs. 14 to 19 of about 20 verified figures and guidance items were fully correct. No run let a wrong number through, and the stale corrected figure never appeared. The errors were period labels ("Q2" without the year, "current period"), and they varied from run to run even at temperature 0. Neither condition attached to guidance ("excludes acquisitions") was ever captured. So headline numbers can be skimmed. Periods, guidance, and anything going into a model or a client note need a human, and one run's score isn't a reliable accuracy estimate.

What broke. On a real Microsoft Q4 FY26 call, all 13 Q1 FY27 guidance lines came out labelled FY27 and still passed verification. The numbers were real, so the quote and number checks couldn't catch it, even though "outlook for our first quarter" was in the model's input. I added a deterministic check that compares each guidance item's period with the nearest outlook heading above it, and those lines now go to review. The same call exposed two more problems:

A parser bug: analyst labels written as "NAME, Firm:" were merged into the operator's turn. It failed safe, since no analyst's number reached the digest as management's, and it's now fixed.
Provider failures: NVIDIA's gateway timed out on long calls, and the smaller fallback model that answered instead credited four analyst questions to management. The speaker check held all four back, and the digest marks the part that failed as INCOMPLETE rather than showing an empty result.

With more time.

Normalize period labels in code, filling in the fiscal year from the call header, instead of trusting the model's wording.
Link Q&A qualifiers back to the guidance they modify.
Keep each model call small enough to finish reliably: split long turns further, and split the Q&A per exchange.
Test on more real transcripts, label more answer keys, and score several runs per transcript.
Fix the recall check, which treats any number inside an extracted quote as covered even when it wasn't extracted.