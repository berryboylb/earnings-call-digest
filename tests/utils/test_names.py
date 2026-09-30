from utils.names import (
    contains_words,
    looks_like_name,
    looks_like_title,
    name_key,
    split_name_title,
)


def test_name_key_ignores_case_punctuation_and_initials():
    assert name_key("Priya S. Raman") == ("priya", "raman")
    assert name_key("PRIYA RAMAN") == name_key("Priya S. Raman")
    assert name_key("Siobhan O’Neil") == ("siobhan", "o'neil")


def test_looks_like_name_accepts_initials_and_particles():
    assert looks_like_name("Priya S. Raman")
    assert looks_like_name("Ana de la Cruz")
    assert looks_like_name("Jean-Luc van Damme")


def test_looks_like_name_rejects_headings_and_non_names():
    assert not looks_like_name("Business Highlights")
    assert not looks_like_name("Question-and-Answer Session")
    assert not looks_like_name("Madonna")  # a single word is not enough
    assert not looks_like_name("Q3 Results")


def test_title_versus_rest_of_sentence():
    assert looks_like_title("Chief Financial Officer")
    assert looks_like_title("Acme Holdings Inc.")
    assert not looks_like_title("our Chief Financial Officer, will now walk through the numbers in more detail.")


def test_split_name_title_handles_separators():
    assert split_name_title("Jane Doe – Chief Financial Officer") == ("Jane Doe", "Chief Financial Officer")
    assert split_name_title("Alex Chen, Citi") == ("Alex Chen", "Citi")
    assert split_name_title("Revenue was up - a lot") is None


def test_contains_matches_consecutive_words():
    text = name_key("Our next question comes from Alex Chen with Citi.")
    assert contains_words(text, ("alex", "chen"))
    assert not contains_words(text, ("chen", "alex"))
    assert not contains_words(text, ())
