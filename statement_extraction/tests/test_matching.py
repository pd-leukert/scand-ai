import os
import unicodedata
from pathlib import Path

import pytest
from src.app.documents import Document, Line, Unit, load_corpus
from src.app.matching import find_span

CORPUS = Path(os.environ.get("CORPUS_DIR", Path(__file__).parents[2] / "corpus"))


def unit(*lines: tuple[int, str, str]) -> Unit:
    return Unit("Bo Ray", None, None, [Line(no, text, position) for no, text, position in lines])


TURN = unit(
    (17, "Good. So we will walk through forecasting first,", "1 minute 20 seconds"),
    (19, "then replenished, and the shelf-life  data", "1 minute 27 seconds"),
    (20, "was 94 percent populated, roughly 3", "1 minute 40 seconds"),
)


def test_a_quote_on_one_line_gives_that_line_and_its_position():
    match = find_span(TURN, "walk through forecasting first")
    assert (match.first_line, match.last_line, match.position) == (17, 17, "1 minute 20 seconds")
    assert match.text == "walk through forecasting first"


def test_a_quote_across_lines_gives_the_first_and_last_line():
    match = find_span(TURN, "forecasting first, then replenished")
    assert (match.first_line, match.last_line) == (17, 19)
    assert match.position == "1 minute 20 seconds"


def test_whitespace_and_line_breaks_do_not_matter_and_the_text_returned_is_the_sources():
    match = find_span(TURN, "shelf-life\ndata   was 94 percent")
    assert (match.first_line, match.last_line) == (19, 20)
    assert match.text == "shelf-life data was 94 percent"


def test_a_missing_final_full_stop_is_fine():
    assert find_span(TURN, "Good. So we will walk through forecasting first").first_line == 17


def test_composed_and_decomposed_letters_match():
    name = "Jörg Müller"
    decomposed = unicodedata.normalize("NFD", name)
    assert decomposed != name
    turn = unit((1, f"Henrik Sørensen and {name}", "line 1"))
    assert find_span(turn, decomposed).text == name


@pytest.mark.parametrize(
    "span",
    [
        "walk through forecasting second",  # a word changed
        "roughly 3.4%",  # the cut-off number completed
        "roughly 3.4",
        "Good. So we will forecasting first",  # words dropped from the middle
        "life  dat",  # ends inside a word
        "ulated, roughly",  # starts inside a word
        "",
        "   ",
    ],
)
def test_a_quote_that_is_not_there_verbatim_is_rejected(span: str):
    assert find_span(TURN, span) is None


def test_a_quote_cannot_start_or_end_inside_a_number():
    turn = unit((1, "Fresh waste was 3.4 against a 4.1 baseline.", "line 1"))
    assert find_span(turn, "waste was 3") is None
    assert find_span(turn, ".4 against") is None
    assert find_span(turn, "waste was 3.4 against a 4.1 baseline").first_line == 1


def test_the_same_text_twice_gives_the_first_occurrence():
    turn = unit((5, "Yeah.", "1 minute"), (6, "Right.", "1 minute"), (7, "Yeah.", "2 minutes"))
    assert find_span(turn, "Yeah.").first_line == 5


def test_a_quote_belongs_to_the_unit_it_is_searched_in():
    other = unit((30, "Something else entirely.", "3 minutes"))
    assert find_span(other, "walk through forecasting first") is None


@pytest.fixture(scope="module")
def corpus() -> list[Document]:
    if not CORPUS.is_dir():
        pytest.skip(f"no corpus at {CORPUS}; set CORPUS_DIR")
    return load_corpus(CORPUS)


def test_the_whole_text_of_every_unit_in_the_corpus_matches_itself(corpus: list[Document]):
    for doc in corpus:
        for u in doc.units:
            match = find_span(u, "\n".join(line.text for line in u.lines))
            assert match is not None, (doc.doc_id, u.lines[0].no)
            assert (match.first_line, match.last_line) == (u.lines[0].no, u.lines[-1].no)
            assert match.position == u.lines[0].position


def test_every_line_in_the_corpus_is_found_at_or_before_its_own_number(corpus: list[Document]):
    for doc in corpus:
        for u in doc.units:
            for line in u.lines:
                match = find_span(u, line.text)
                assert match is not None, (doc.doc_id, line.no)
                assert match.first_line <= line.no
