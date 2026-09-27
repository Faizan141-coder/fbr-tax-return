# tests/test_money.py
import pytest
from fbr.money import AmountError, format_paisa, parse_paisa


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1234.56", 123456),
        ("1,234.56", 123456),
        ("1,234", 123400),
        ("0.01", 1),
        ("0", 0),
        ("12,34,567.89", 123456789),   # lakh-style grouping
        ("PKR 1,234.56", 123456),
        ("Rs. 1,234.56", 123456),
        ("Rs1,234.56", 123456),
        ("1,234.5", 123450),           # one decimal place is valid
        ("  1,234.56  ", 123456),      # surrounding whitespace
        ("1 234.56", 123456),     # non-breaking space as separator
    ],
)
def test_parses_valid_amounts(text, expected):
    assert parse_paisa(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("-1,234.56", -123456),
        ("+1,234.56", 123456),
        ("−1,234.56", -123456),   # Unicode minus
        ("(1,234.56)", -123456),       # accounting negative
        ("1,234.56-", -123456),        # trailing minus
    ],
)
def test_parses_signed_amounts(text, expected):
    assert parse_paisa(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "abc",
        "1.2.3",
        "1,234.567",      # 3 decimals — Review Focus #4
        "1,23.456",       # misplaced separator + 3 decimals — Review Focus #4
        "1,2345.00",      # 4-digit group after a separator
        "(1,234.56",      # unbalanced parenthesis
        "1,234.56)",
        "--1234",
        "1,234.56Dr",     # Dr/Cr is the profile's job, not the grammar's
        "1 234 56",
    ],
)
def test_rejects_malformed_amounts(text):
    with pytest.raises(AmountError):
        parse_paisa(text)


def test_never_uses_float():
    # 0.1 + 0.2 in float is 0.30000000000000004; in paisa it must be exact.
    assert parse_paisa("0.10") + parse_paisa("0.20") == parse_paisa("0.30")


def test_large_amount_is_exact():
    assert parse_paisa("99,999,999.99") == 9999999999


@pytest.mark.parametrize(
    "paisa,expected",
    [(123456, "1,234.56"), (-123456, "-1,234.56"), (0, "0.00"), (1, "0.01")],
)
def test_formats_paisa(paisa, expected):
    assert format_paisa(paisa) == expected


def test_round_trips():
    for text in ("1,234.56", "0.01", "12,34,567.89"):
        assert parse_paisa(format_paisa(parse_paisa(text))) == parse_paisa(text)
