"""Currency-separated summaries and spreadsheet-safe UTF-8 CSV exports."""

import csv
from io import StringIO

from scanner.receipts import format_amount


def safe_csv_cell(value: str) -> str:
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def summaries(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    totals, months = {}, {}
    for row in rows:
        currency = row["currency"]
        totals[currency] = totals.get(currency, 0) + row["amount_minor"]
        key = row["purchased_on"][:7], currency
        months[key] = months.get(key, 0) + row["amount_minor"]
    return (
        [
            {"Currency": currency, "Total": format_amount(value, currency)}
            for currency, value in sorted(totals.items())
        ],
        [
            {"Month": month, "Currency": currency, "Total": format_amount(value, currency)}
            for (month, currency), value in sorted(months.items())
        ],
    )


def expense_csv(rows: list[dict]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["Date", "Merchant", "Amount", "Currency", "Category", "Note"])
    for row in rows:
        writer.writerow(
            [
                row["purchased_on"],
                safe_csv_cell(row["merchant"]),
                format_amount(row["amount_minor"], row["currency"]),
                row["currency"],
                row["category"],
                safe_csv_cell(row["note"]),
            ]
        )
    return stream.getvalue().encode("utf-8-sig")
