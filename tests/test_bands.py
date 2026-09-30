# tests/test_bands.py
"""Column geometry, tested with numbers rather than PDFs.

An amount in the wrong column is a sign inversion, and a sign inversion on a
bank statement still reconciles against itself - which is why this is tested
harder than its size suggests.
"""
import pytest

from fbr.engines._bands import Band, BandError, Word, assign, build_bands, group_lines

# A Meezan-style header: Credit at x1=400, Debit at x1=470, Balance at x1=555.
HEADER = [
    Word("Booking", 40, 72, 100, 108), Word("Date", 74, 92, 100, 108),
    Word("Description", 130, 178, 100, 108),
    Word("Credit", 378, 400, 100, 108),
    Word("Debit", 450, 470, 100, 108),
    Word("Available", 500, 534, 100, 108), Word("Balance", 536, 555, 100, 108),
]
ROLES = {"date": "Booking Date", "description": "Description",
         "credit": "Credit", "debit": "Debit", "balance": "Available Balance"}
ALIGNS = {"date": "left", "description": "left", "credit": "right",
          "debit": "right", "balance": "right"}


def _bands():
    return build_bands(HEADER, ROLES, ALIGNS)


def test_builds_one_band_per_role():
    assert {b.role for b in _bands()} == set(ROLES)


def test_multiword_header_label_is_matched():
    # "Booking Date" and "Available Balance" each span two words.
    bands = {b.role: b for b in _bands()}
    assert bands["date"].x0 <= 40
    assert bands["balance"].x1 >= 555


def test_missing_header_label_raises_naming_it():
    with pytest.raises(BandError, match="Credit"):
        build_bands([w for w in HEADER if w.text != "Credit"], ROLES, ALIGNS)


def test_right_aligned_amount_goes_to_the_nearest_header_right_edge():
    assert assign(Word("500.00", 372, 400, 120, 128), _bands()) == "credit"
    assert assign(Word("200.00", 442, 470, 120, 128), _bands()) == "debit"


def test_every_word_of_a_multiword_description_assigns():
    # A tolerance-only assign() claims the first word and orphans the rest,
    # which turns every row into an unresolved row and fails every statement.
    # A text column must claim by containment, not by edge proximity.
    bands = _bands()
    for i, text in enumerate(["TRANSF", "CR/ICT/", "Top-up", "from", "SOMEONE"]):
        x0 = 130 + i * 36
        assert assign(Word(text, x0, x0 + 30, 120, 128), bands) == "description", text


def test_a_long_description_stops_at_the_first_money_column():
    # It must not bleed into Credit, whose band starts at 378.
    bands = _bands()
    assert assign(Word("tail", 360, 376, 120, 128), bands) == "description"
    assert assign(Word("tail", 380, 396, 120, 128), bands) != "description"


def test_a_date_assigns_across_its_own_width():
    bands = _bands()
    assert assign(Word("01", 40, 52, 120, 128), bands) == "date"
    assert assign(Word("Jul", 54, 70, 120, 128), bands) == "date"
    assert assign(Word("2025", 72, 90, 120, 128), bands) == "date"


def test_a_money_column_still_wins_over_the_text_span_containing_it():
    # Credit's band sits inside the description column's span; the numeric
    # edge test must be tried first or every amount becomes description text.
    assert assign(Word("500.00", 372, 400, 120, 128), _bands()) == "credit"


def test_an_amount_between_two_columns_is_ambiguous_not_guessed():
    # x1 = 435 sits 35pt from Credit's 400 and 35pt from Debit's 470.
    assert assign(Word("300.00", 407, 435, 120, 128), _bands()) is None


def test_an_amount_outside_every_band_is_ambiguous():
    assert assign(Word("999.00", 700, 740, 120, 128), _bands()) is None


def test_tolerance_is_respected_at_its_edge():
    bands = _bands()
    assert assign(Word("1.00", 380, 405, 120, 128), bands, tolerance=6.0) == "credit"
    assert assign(Word("1.00", 380, 412, 120, 128), bands, tolerance=6.0) is None


def test_left_aligned_text_assigns_by_left_edge():
    assert assign(Word("ATM", 130, 150, 120, 128), _bands()) == "description"
    assert assign(Word("01", 40, 52, 120, 128), _bands()) == "date"


def test_group_lines_keeps_printed_order():
    words = [
        Word("row2", 40, 60, 140, 148),
        Word("row1", 40, 60, 120, 128),
        Word("row1b", 130, 160, 121, 129),
    ]
    lines = group_lines(words)
    assert [w.text for w in lines[0]] == ["row1", "row1b"]
    assert [w.text for w in lines[1]] == ["row2"]


def test_group_lines_sorts_each_line_left_to_right():
    words = [Word("b", 200, 220, 120, 128), Word("a", 40, 60, 120, 128)]
    assert [w.text for w in group_lines(words)[0]] == ["a", "b"]


def test_y_tolerance_merges_slightly_offset_words():
    words = [Word("a", 40, 60, 120.0, 128.0), Word("b", 200, 220, 122.0, 130.0)]
    assert len(group_lines(words, y_tolerance=3.0)) == 1
    assert len(group_lines(words, y_tolerance=1.0)) == 2


def test_word_converts_from_a_pdfplumber_dict():
    w = Word.from_dict({"text": "x", "x0": 1.0, "x1": 2.0, "top": 3.0, "bottom": 4.0})
    assert (w.text, w.x0, w.x1, w.top, w.bottom) == ("x", 1.0, 2.0, 3.0, 4.0)
