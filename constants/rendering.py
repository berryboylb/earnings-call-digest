"""Fixed text and settings for the one-page digest."""

DIGEST_FILES = {"html": "digest.html", "pdf": "digest.pdf", "docx": "digest.docx"}

BANNER = "INCOMPLETE: extraction failed for {sections}. Missing items may exist."
TRUST_LINE = (
    "{verified} of {total} extracted items verified against the transcript · "
    "{needs_review} need review · {missed} numbers possibly missed"
)
LIMITS_LINE = (
    "Verified = quote, number and speaker match the transcript. "
    "It does not prove the claim is complete or correctly interpreted."
)

NOT_AVAILABLE = "Not available: extraction failed for this section."
NONE_IDENTIFIED = "None identified."

QA_NOTE = "Response is the model's judgment, not a verified fact."
NEEDS_REVIEW_NOTE = "Extracted by the model but not backed by the transcript. Not shown above."
POSSIBLY_MISSED_NOTE = "Numbers management stated that no item covers. Review candidates only."

PDF_UNAVAILABLE = (
    "PDF not written: WeasyPrint could not load its system libraries ({error}). "
    "On macOS, run `brew install pango`. The HTML and DOCX files were still written."
)
