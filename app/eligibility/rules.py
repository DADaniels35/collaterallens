from __future__ import annotations

RATING_ORDER = {
    "AAA": 22,
    "AA+": 21,
    "AA": 20,
    "AA-": 19,
    "A+": 18,
    "A": 17,
    "A-": 16,
    "BBB+": 15,
    "BBB": 14,
    "BBB-": 13,
    "BB+": 12,
    "BB": 11,
    "BB-": 10,
    "B+": 9,
    "B": 8,
    "B-": 7,
    "CCC": 6,
    "CC": 5,
    "C": 4,
    "D": 0,
}


def rating_notch(rating: str) -> int:
    return RATING_ORDER.get(rating.upper(), -1)


def rating_bucket(rating: str) -> str:
    rating = rating.upper()
    if rating.startswith("AAA"):
        return "AAA"
    if rating.startswith("AA"):
        return "AA"
    if rating.startswith("A"):
        return "A"
    if rating.startswith("BBB"):
        return "BBB"
    if rating.startswith("BB"):
        return "BB"
    if rating.startswith("B"):
        return "B"
    return "CCC"
