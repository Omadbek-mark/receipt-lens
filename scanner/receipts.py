"""Conservative receipt-field proposals. OCR is AI; this extraction uses rules.

No value is authoritative until the user confirms the review form. Missing or
ambiguous evidence remains blank rather than being inferred from language/date.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

CURRENCIES = {"USD": 2, "UZS": 2, "KRW": 0}
CATEGORIES = ("Food", "Transport", "Shopping", "Education", "Health", "Utilities", "Other")
TOTAL = re.compile(
    r"\b(?:grand\s+total|total(?:\s+amount)?|amount\s+due|jami(?:\s+summa)?|to['‘’ʻ]?lov\s+summasi)\b|(?:총\s*결제\s*금액|결제\s*금액|합계\s*금액|합\s*계|총액)",
    re.I,
)
EXCLUDE = re.compile(
    r"\b(?:subtotal|sub\s+total|tax|vat|discount|change|tendered|cash\s+received)\b|소계|거스름|받은|할인",
    re.I,
)
NUMBER = re.compile(r"(?<![\dA-Za-z])\d+(?:[ ,.]\d+)*(?!\d)")


@dataclass(frozen=True)
class ReceiptProposal:
    merchant: str | None
    purchased_on: str | None
    amount: str | None
    currency: str | None
    category: str
    evidence: dict[str, str]
    warnings: tuple[str, ...]


def parse_amount(value: str, currency: str) -> int:
    """Return integer minor units; never use float for stored money."""
    if currency not in CURRENCIES:
        raise ValueError("Choose USD, UZS or KRW.")
    value = value.strip().replace("\u00a0", " ")
    if not re.fullmatch(r"\d+(?:[ ,.][0-9]+)*", value):
        raise ValueError("Enter a positive amount using digits and decimal/group separators.")
    if " " in value and not re.fullmatch(r"\d{1,3}(?: \d{3})+(?:[.,]\d{1,2})?", value):
        raise ValueError("Check the amount grouping spaces.")
    value = value.replace(" ", "")
    if "," in value and "." in value:
        decimal = "," if value.rfind(",") > value.rfind(".") else "."
        group = "." if decimal == "," else ","
        whole, fraction = value.rsplit(decimal, 1)
        if not re.fullmatch(rf"\d{{1,3}}(?:\{group}\d{{3}})+", whole):
            raise ValueError("Check the amount separators.")
        value = whole.replace(group, "") + "." + fraction
    elif "," in value or "." in value:
        separator = "," if "," in value else "."
        pieces = value.split(separator)
        if len(pieces) > 2 or len(pieces[-1]) == 3:
            if not (1 <= len(pieces[0]) <= 3 and all(len(piece) == 3 for piece in pieces[1:])):
                raise ValueError("Check the amount separators.")
            value = "".join(pieces)
        else:
            value = value.replace(separator, ".")
    try:
        amount = Decimal(value)
        factor = Decimal(10) ** CURRENCIES[currency]
        minor = amount * factor
        if amount <= 0 or minor != minor.to_integral_value() or minor > 10**14:
            raise ValueError("Check the amount and currency decimal places.")
        return int(minor)
    except InvalidOperation as error:
        raise ValueError("Check the amount.") from error


def format_amount(minor: int, currency: str) -> str:
    return f"{Decimal(minor) / (10 ** CURRENCIES[currency]):.{CURRENCIES[currency]}f}"


def currency_in(text: str) -> str | None:
    matches = set()
    if re.search(r"\bUSD\b|US\$", text, re.I):
        matches.add("USD")
    if re.search(r"\bUZS\b|\bso['‘’ʻ]?m\b|сум", text, re.I):
        matches.add("UZS")
    if re.search(r"\bKRW\b|₩|\d\s*원", text, re.I):
        matches.add("KRW")
    return next(iter(matches)) if len(matches) == 1 else None


def extract_receipt(text: str) -> ReceiptProposal:
    text = unicodedata.normalize("NFC", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    evidence: dict[str, str] = {}
    warnings = []
    merchant = None
    for line in lines[:3]:
        if (
            3 <= len(line) <= 160
            and re.search(r"[A-Za-z가-힣]", line)
            and not re.search(r"receipt|invoice|영수증|chek|sana|date|tel|사업자|주소", line, re.I)
            and not TOTAL.search(line)
            and not re.search(r"\d{4}", line)
        ):
            merchant = line
            evidence["merchant"] = line
            break
    dates = {}
    for line in lines:
        patterns = [
            (r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", False),
            (r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", False),
            (r"\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b", True),
        ]
        for pattern, reverse in patterns:
            for match in re.finditer(pattern, line):
                values = list(map(int, match.groups()))
                if reverse:
                    values.reverse()
                try:
                    dates[date(*values).isoformat()] = line
                except ValueError:
                    pass
    purchased_on = next(iter(dates)) if len(dates) == 1 else None
    if purchased_on:
        evidence["purchased_on"] = dates[purchased_on]
    totals = []
    for index, line in enumerate(lines):
        label = TOTAL.search(line)
        if not label or EXCLUDE.search(line):
            continue
        tail = line[label.end() :].strip(" :：=")
        source = line
        if not tail and index + 1 < len(lines):
            tail, source = lines[index + 1], line + " / " + lines[index + 1]
        if re.search(r"-\s*\d", tail):
            continue
        numbers = NUMBER.findall(tail)
        currency = currency_in(tail) or currency_in(text)
        if len(numbers) == 1 and currency:
            try:
                minor = parse_amount(numbers[0], currency)
                totals.append((format_amount(minor, currency), currency, source))
            except ValueError:
                pass
    distinct = {(amount, currency) for amount, currency, _ in totals}
    amount = currency = None
    if len(distinct) == 1:
        amount, currency = next(iter(distinct))
        evidence["amount"] = next(source for a, c, source in totals if (a, c) == (amount, currency))
        evidence["currency"] = evidence["amount"]
    if not currency:
        currency = currency_in(text)
        if currency:
            evidence["currency"] = "Explicit currency marker in receipt text."
    for name, value in (
        ("merchant", merchant),
        ("date", purchased_on),
        ("total", amount),
        ("currency", currency),
    ):
        if value is None:
            warnings.append(f"Check {name}: missing or ambiguous evidence.")
    categories = set()
    for category, keywords in {
        "Food": r"cafe|coffee|restaurant|bakery|kafe|oshxona|식당|카페|커피",
        "Transport": r"taxi|metro|bus ticket|taksi|교통|택시|버스",
        "Education": r"bookstore|tuition|kitob|o['‘’ʻ]?quv|서점|학원|도서",
        "Health": r"pharmacy|dorixona|약국",
        "Utilities": r"electricity|internet bill|elektr|전기요금",
    }.items():
        if re.search(keywords, text, re.I):
            categories.add(category)
    category = next(iter(categories)) if len(categories) == 1 else "Other"
    return ReceiptProposal(
        merchant, purchased_on, amount, currency, category, evidence, tuple(warnings)
    )
