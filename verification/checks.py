"""The checks run on each extracted item.

Each check adds a reason (the item fails and needs review) or a note (worth knowing,
but the item still passes). They only read the transcript; nothing here calls an LLM.
"""

import re

from constants.verification import (
    DIRECTION_CUES,
    PRIOR_PERIOD_AFTER,
    PRIOR_PERIOD_BEFORE,
    PRIOR_PERIOD_WINDOW,
)
from schema.verification import Amount, SourceMatch, VerifiedItem
from utils.names import contains_words, name_key
from utils.numbers import amounts_equal, parse_amounts
from verification.matching import (
    TranscriptIndex,
    find_quote,
    sentence_context,
    tokenise,
)


def check_quote_found(item: VerifiedItem, index: TranscriptIndex) -> bool:
    """Find the item's quote in the transcript. Returns False (and the other checks are
    skipped) if it isn't there."""
    match = find_quote(index, item.fields["quote"], speaker=item.speaker_claimed)
    if match is None:
        item.reasons.append("quote not found in transcript")
        return False
    item.source = match
    item.speaker = index.segment_of(match).speaker
    return True


def check_boilerplate(item: VerifiedItem) -> None:
    if item.source.in_boilerplate:
        item.reasons.append("quote is from the safe-harbor (legal boilerplate) text")


def check_speaker(item: VerifiedItem, index: TranscriptIndex) -> None:
    """The quote must come from management. If the model named the wrong person, say so."""
    segment = index.segment_of(item.source)
    if segment.role != "management":
        item.reasons.append(f"quote is from {segment.speaker} ({segment.role}), not management")
    if name_key(item.speaker_claimed) != name_key(segment.speaker):
        item.notes.append(f"speaker corrected: model said {item.speaker_claimed}, transcript says {segment.speaker}")


def check_context(item: VerifiedItem, index: TranscriptIndex) -> None:
    """Every supporting quote (context_quotes) must be in the transcript too."""
    for quote in item.fields.get("context_quotes", []):
        match = find_quote(index, quote)
        if match is None:
            item.reasons.append(f'context quote not found in transcript: "{quote[:60]}"')
        else:
            item.context.append(match)


def check_values(item: VerifiedItem, index: TranscriptIndex) -> None:
    """Every number the model reported must be in the transcript's own text where the quote
    was found. Numbers are read from the transcript, never from the model's quote."""
    field = "value" if item.kind == "figure" else "range"
    reported = _numbers_in(item.fields[field])
    if not reported:
        item.reasons.append(f"no number could be read from the extracted {field} '{item.fields[field]}'")
        return

    plain_numbers = all(amount.unit == "number" for amount in reported)
    in_source = parse_amounts(item.source.text, include_plain_numbers=plain_numbers)

    for amount in reported:
        if _contains_amount(in_source, amount):
            continue

        context = _context_containing(item, amount, plain_numbers)
        if context is not None:
            segment = index.segment_of(context)
            if segment.role == "management":
                item.notes.append(f"{amount.raw} is only in supporting context from {segment.speaker}")
            else:
                item.reasons.append(
                    f"number only appears in {segment.speaker}'s ({segment.role}) words; needs human confirmation"
                )
            continue

        found = ", ".join(source_amount.raw for source_amount in in_source) or "no amount"
        item.reasons.append(f"value mismatch: extracted {amount.raw}, transcript says {found}")


def check_prior_period(item: VerifiedItem, index: TranscriptIndex) -> None:
    """A currency figure the transcript introduces as a comparison ("compared to $371.2 million",
    "$0.49 in the prior-year quarter") is not a current result."""
    reported = [amount for amount in parse_amounts(item.fields["value"]) if amount.unit == "currency"]
    if not reported:
        return

    text = index.paragraph_of(item.source).paragraph.text
    for amount in parse_amounts(text):
        inside_quote = item.source.start <= amount.start and amount.end <= item.source.end
        if not inside_quote or not _contains_amount(reported, amount):
            continue
        sentence_start, _ = sentence_context(text, amount.start, amount.end)
        before = text[max(sentence_start, amount.start - PRIOR_PERIOD_WINDOW):amount.start]
        after = text[amount.end:amount.end + PRIOR_PERIOD_WINDOW]
        if PRIOR_PERIOD_BEFORE.search(before) or PRIOR_PERIOD_AFTER.search(after):
            item.reasons.append(f"{amount.raw} is a prior-period comparison in the transcript, not a current result")
            return


def check_is_comparison(item: VerifiedItem) -> None:
    if item.fields["is_comparison"]:
        item.reasons.append("the model marked this figure as a prior-period comparison")


def check_direction(item: VerifiedItem, index: TranscriptIndex) -> None:
    """Guidance marked raised/lowered/reaffirmed/initiated needs a matching word in its sentence."""
    claimed = item.fields["direction"]
    if claimed == "not stated":
        return

    text = index.paragraph_of(item.source).paragraph.text
    sentence_start, sentence_end = sentence_context(text, item.source.start, item.source.end)
    sentence = text[sentence_start:sentence_end].lower()
    if _find_cue(sentence, DIRECTION_CUES[claimed]):
        return

    for direction, cues in DIRECTION_CUES.items():
        word = _find_cue(sentence, cues)
        if word:
            item.reasons.append(f"direction '{claimed}' not supported: the sentence says '{word}' ({direction})")
            return
    item.reasons.append(f"direction '{claimed}' not supported: the sentence has no direction word")


def check_hedging_phrase(item: VerifiedItem, index: TranscriptIndex) -> None:
    """The hedging phrase must appear word for word in the paragraph the quote came from."""
    phrase = item.fields["hedging_phrase"]
    phrase_words = tuple(token.text for token in tokenise(phrase))
    paragraph_words = tuple(token.text for token in index.paragraph_of(item.source).tokens)
    if not contains_words(paragraph_words, phrase_words):
        item.reasons.append(f"hedging phrase not found in the quoted paragraph: '{phrase}'")


def check_asked_by(item: VerifiedItem, index: TranscriptIndex) -> None:
    """asked_by must be an analyst on the call. Answer quality can't be checked by code."""
    asked_by = item.fields["asked_by"]
    parsed = index.parsed
    analysts = {name_key(p.name) for p in parsed.participants if p.role == "analyst"}
    analysts |= {name_key(segment.speaker) for segment in parsed.segments if segment.role == "analyst"}
    if name_key(asked_by) not in analysts:
        item.reasons.append(f"asked_by '{asked_by}' is not an analyst on this call")
    item.notes.append("answer quality is the model's judgment, not verified")


def _numbers_in(text: str) -> list[Amount]:
    """The amounts in an extracted value. A plain count ("38") is read too, if that's all there is."""
    return parse_amounts(text) or parse_amounts(text, include_plain_numbers=True)


def _contains_amount(amounts: list[Amount], wanted: Amount) -> bool:
    return any(amounts_equal(amount, wanted) for amount in amounts)


def _context_containing(item: VerifiedItem, amount: Amount, plain_numbers: bool) -> SourceMatch | None:
    for context in item.context:
        if _contains_amount(parse_amounts(context.text, include_plain_numbers=plain_numbers), amount):
            return context
    return None


def _find_cue(sentence: str, cues: list[str]) -> str | None:
    """The word in the sentence that starts with one of the cues ("reaffirming" for "reaffirm")."""
    for cue in cues:
        match = re.search(r"\b" + re.escape(cue) + r"\w*", sentence)
        if match:
            return match.group()
    return None
