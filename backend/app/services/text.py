"""Small wording helpers shared by the insights and the PDF export."""


def ordinal(n) -> str:
    """92 -> '92nd', 95 -> '95th', 11 -> '11th'. Non-integers (92.5) keep a plain 'th'."""
    v = float(n)
    if v != int(v):
        return f"{v:g}th"
    i = int(v)
    if 11 <= i % 100 <= 13:
        return f"{i}th"
    return f"{i}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(i % 10, 'th') }"