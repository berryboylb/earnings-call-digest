Earnings Call Digest: note

What it is. A tool that turns an earnings call transcript into a one-page digest for a research analyst: headline figures, guidance, risk language, and what analysts pushed on in Q&A. An LLM finds the facts, and plain code decides what gets shown. Every item must carry a verbatim quote. A verification step checks that the quote is in the transcript, that management (not an analyst) said it, and that the numbers match the transcript's own text. Items that fail are listed under "Needs review" with the reason, never silently dropped.

Tools and model. Python. Parsing, verification, rendering and evaluation are deterministic; only extraction calls a model. I used nvidia/nemotron-3-super-120b through NVIDIA's OpenAI-compatible API, with gpt-oss-20b as a fallback, and a strict JSON schema validated with pydantic. I chose it because I had access to it and it handled structured output reliably. Because the client is OpenAI-compatible, switching models is a config change, but I'd rerun the evaluation before trusting a new one.

Where I'd trust it. "Verified" means grounded, not correct. On a test transcript I labelled by hand, 16 of 20 verified figures and guidance items were fully correct. The errors were real numbers with the wrong period and one missed "reaffirmed". Neither of the 2 conditions attached to guidance ("excludes acquisitions") was captured. When I changed the prompt to fix weak risk extraction, risks went from 5/6 to 6/6 but figure accuracy dropped, and I only knew because of the evaluation. So headline figures can be skimmed with spot checks. Guidance, periods, and anything going into a model or a client note need a human.

What broke. On a real Microsoft Q4 FY26 call, all 13 Q1 FY27 guidance lines came out labelled FY27 and still passed verification. The numbers were real, so the quote and number checks couldn't catch it, even though "outlook for our first quarter" was in the model's input. I added a deterministic check that compares each guidance item's period with the nearest outlook heading above it, and all 13 now go to review. The same call exposed a parser bug: analyst labels written as "NAME, Firm:" were merged into the operator's turn. It failed safe, since no analyst's number reached the digest as management's, and it's now fixed.

With more time.

Link Q&A qualifiers back to the guidance they modify.
Test on more real transcripts, label more answer keys, and run each several times: results vary between runs even at temperature 0, so one run's score is noisy.
Fix the recall check, which treats any number inside an extracted quote as covered even when it wasn't extracted.