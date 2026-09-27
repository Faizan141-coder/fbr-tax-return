# tests/test_money.py
import pytest
from fbr.money import AmountError, UnsupportedDecimals, format_paisa, parse_paisa


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


# --- formats.decimals must never silently rescale (final fix round, Finding 6)


@pytest.mark.parametrize(
    "text,decimals,what_it_used_to_return",
    [
        ("1.50", 3, 600),     # Rs 6.00 instead of Rs 1.50
        ("1.5", 1, 105),      # Rs 1.05 instead of Rs 1.50
        ("1.50", 0, 150),     # only right by accident; still unsupported
        ("1.50", 4, 15000),
    ],
)
def test_an_unsupported_decimals_is_rejected_not_miscomputed(
    text, decimals, what_it_used_to_return
):
    # PAISA_PER_RUPEE is 100 and the grammar caps the fraction at two digits,
    # so `decimals` never rescaled anything - it just corrupted the sum. A
    # profile author using the documented knob got a wrong figure with no
    # error anywhere.
    with pytest.raises(UnsupportedDecimals, match="paisa"):
        parse_paisa(text, decimals=decimals)


def test_the_unsupported_decimals_error_is_not_mistaken_for_a_bad_amount():
    # The engine turns AmountError (and ValueError) into an unresolved row,
    # which would blame the statement for what is a configuration bug.
    assert not issubclass(UnsupportedDecimals, AmountError)
    assert not issubclass(UnsupportedDecimals, ValueError)


def test_two_decimals_is_still_the_default_and_still_works():
    assert parse_paisa("1.50") == 150
    assert parse_paisa("1.50", decimals=2) == 150
