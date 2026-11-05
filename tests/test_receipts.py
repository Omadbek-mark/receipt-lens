from decimal import Decimal

import pytest

from scanner.receipts import extract_receipt, format_amount, parse_amount


@pytest.mark.parametrize(
    "text,merchant,day,amount,currency",
    [
        (
            "DEMO CAFE\nDate: 2026-11-01\nSubtotal: 10.00 USD\nTax: 1.00 USD\nTOTAL: 11.00 USD\nCash: 20.00 USD\nChange: 9.00 USD",
            "DEMO CAFE",
            "2026-11-01",
            "11.00",
            "USD",
        ),
        (
            "DEMO MARKET\nSana: 01.11.2026\nJami: 125 000 so‘m",
            "DEMO MARKET",
            "2026-11-01",
            "125000.00",
            "UZS",
        ),
        ("데모 카페\n2026년 11월 1일\n합계: 12,000원", "데모 카페", "2026-11-01", "12000", "KRW"),
        (
            "DEMO SHOP\n2026/11/01\nGrand total\n24.50 USD",
            "DEMO SHOP",
            "2026-11-01",
            "24.50",
            "USD",
        ),
    ],
)
def test_receipt_fields_use_total_not_tax_change_or_subtotal(text, merchant, day, amount, currency):
    result = extract_receipt(text)
    assert (result.merchant, result.purchased_on, result.amount, result.currency) == (
        merchant,
        day,
        amount,
        currency,
    )
    assert result.evidence["amount"]


@pytest.mark.parametrize(
    "text",
    [
        "SHOP\nSubtotal: 10.00 USD\nTax: 1.00 USD",  # no final total
        "SHOP\nTotal: -12.00 USD",  # refund unsupported
        "SHOP\nTotal: 12.00 USD\nTotal: 15.00 USD",  # conflicting totals
        "SHOP\nTotal: $12.00",  # dollar symbol alone is not an explicit USD identity
        "SHOP\nTotal: 12 USD 140000 UZS",  # currency conversion ambiguity
    ],
)
def test_unknown_or_conflicting_total_is_not_invented(text):
    assert extract_receipt(text).amount is None


def test_ambiguous_or_invalid_date_is_left_blank():
    assert extract_receipt("SHOP\nDate: 11/01/2026\nTotal: 1 USD").purchased_on is None
    assert extract_receipt("SHOP\n2026-02-30\nTotal: 1 USD").purchased_on is None
    assert extract_receipt("SHOP\n2026-11-01\n2026-11-02").purchased_on is None


@pytest.mark.parametrize(
    "value,currency,minor",
    [
        ("10.25", "USD", 1025),
        ("1,234.50", "USD", 123450),
        ("1.234,50", "USD", 123450),
        ("125 000", "UZS", 12500000),
        ("12,000", "KRW", 12000),
    ],
)
def test_amount_conversion_is_exact(value, currency, minor):
    assert parse_amount(value, currency) == minor
    assert Decimal(format_amount(minor, currency)) > 0


@pytest.mark.parametrize(
    "value,currency",
    [
        ("-10", "USD"),
        ("0", "USD"),
        ("10.50", "KRW"),
        ("1 23", "USD"),
        ("NaN", "USD"),
        ("12,34,567", "USD"),
        ("100", "EUR"),
        ("100000000000000000", "USD"),
    ],
)
def test_bad_amounts_are_rejected(value, currency):
    with pytest.raises(ValueError):
        parse_amount(value, currency)


def test_categories_are_suggestions_and_multiple_matches_use_other():
    assert extract_receipt("DEMO CAFE\nTotal: 1 USD").category == "Food"
    assert extract_receipt("DEMO CAFE BOOKSTORE\nTotal: 1 USD").category == "Other"
