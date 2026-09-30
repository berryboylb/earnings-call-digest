"""The hand-written Northwind extraction has one of each planted mistake. Each must be caught."""


def test_correct_items_are_verified(planted, find_item):
    for fields in [
        {"metric": "Operating income", "value": "$52.8 million"},
        {"metric": "Revenue", "range": "$1.60 billion to $1.64 billion"},
        {"metric": "Revenue", "range": "$425 million to $440 million"},
        {"metric": "Gross margin", "range": "40% to 42%"},
        {"theme": "Foreign exchange"},
        {"asked_by": "Lena Kovacs"},
    ]:
        item = find_item(planted, **fields)
        assert item.status == "verified", (fields, item.reasons)
        assert item.reasons == []


def test_hallucinated_figure(planted, find_item):
    item = find_item(planted, metric="Recurring software revenue")
    assert item.status == "unverified"
    assert item.reasons == ["quote not found in transcript"]
    assert item.source is None


def test_real_sentence_with_altered_number(planted, find_item):
    item = find_item(planted, metric="Services revenue growth")
    assert item.source.method == "fuzzy"  # the sentence is found despite the changed number...
    assert item.reasons == ["value mismatch: extracted 14%, transcript says 12%"]  # ...but the number isn't


def test_prior_year_revenue_reported_as_current(planted, find_item):
    item = find_item(planted, metric="Revenue", value="$371.2 million")
    assert item.reasons == ["$371.2 million is a prior-period comparison in the transcript, not a current result"]


def test_analyst_number_attributed_to_ceo(planted, find_item):
    item = find_item(planted, metric="Order growth")
    assert item.speaker == "Ethan Brooks" and item.speaker_claimed == "Marcus Oyelaran"
    assert "quote is from Ethan Brooks (analyst), not management" in item.reasons
    assert "speaker corrected: model said Marcus Oyelaran, transcript says Ethan Brooks" in item.notes


def test_guidance_direction_contradicted_by_the_sentence(planted, find_item):
    item = find_item(planted, metric="Non-GAAP earnings per share")
    assert item.reasons == ["direction 'raised' not supported: the sentence says 'reaffirming' (reaffirmed)"]


def test_raised_is_accepted_when_the_sentence_says_up_from_our_prior(planted, find_item):
    assert find_item(planted, range="$1.60 billion to $1.64 billion").status == "verified"


def test_duplicate_figure_is_merged_and_evidence_kept(planted):
    revenue = [item for item in planted.items if item.fields.get("value") == "$412.6 million"]
    assert len(revenue) == 1
    [kept] = revenue
    assert kept.status == "verified" and kept.speaker == "Priya Raman"
    assert [match.segment_id for match in kept.context] == ["S3"]  # Marcus's statement, kept as evidence
    assert "also stated by Marcus Oyelaran" in kept.notes


def test_paraphrased_but_close_quote_fuzzy_matches_and_passes(planted, find_item):
    item = find_item(planted, metric="Gross margin", value="41.3%")
    assert item.status == "verified"
    assert item.source.method == "fuzzy" and item.source.score >= 0.9


def test_answer_quality_is_marked_as_the_models_judgment(planted, find_item):
    item = find_item(planted, asked_by="Samuel Adeyemi")
    assert "answer quality is the model's judgment, not verified" in item.notes


def test_ids_follow_extraction_order_after_dedupe(planted):
    figure_ids = [(item.id, item.fields["metric"]) for item in planted.items if item.kind == "figure"]
    assert figure_ids[:3] == [("F1", "Revenue"), ("F2", "Recurring software revenue"), ("F3", "Services revenue growth")]
    assert [item.id for item in planted.items if item.kind == "qa"] == ["Q1", "Q2", "Q3"]
