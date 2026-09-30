# src/fbr/engines/_bands.py
"""Column-band geometry for the PDF engine.

A bank's money columns are right-aligned, so an amount's RIGHT edge lines up
with its header's right edge. That is the signal used here. A token that is
outside every band, or equally close to two, returns None and becomes an
unresolved row - never a guess, because a guess on Meezan's unsigned
Credit/Debit pair is a silent sign inversion.

No pdfplumber import: this is arithmetic, and it is tested as arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass


class BandError(RuntimeError):
    """The header does not contain a label the profile requires."""


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float

    @classmethod
    def from_dict(cls, d: dict) -> "Word":
        return cls(d["text"], float(d["x0"]), float(d["x1"]),
                   float(d["top"]), float(d["bottom"]))


@dataclass(frozen=True, slots=True)
class Band:
    role: str
    x0: float
    x1: float
    align: str


def _find_label(header: list[Word], label: str) -> tuple[float, float]:
    """Locate a possibly multi-word header label, returning its x span."""
    wanted = label.split()
    lowered = [w.text.strip().lower() for w in header]
    target = [t.lower() for t in wanted]
    for i in range(len(lowered) - len(target) + 1):
        if lowered[i:i + len(target)] == target:
            return header[i].x0, header[i + len(target) - 1].x1
    raise BandError(f"header has no label {label!r}; header reads "
                    f"{' '.join(w.text for w in header)!r}")


def build_bands(
    header: list[Word], roles: dict[str, str], aligns: dict[str, str]
) -> tuple[Band, ...]:
    """Build one band per role from the header row's word boxes.

    A numeric column keeps its header label's own narrow box, because an
    amount is matched on its right edge. A text column instead spans from its
    own left edge to wherever the next column begins: a description is many
    words wide, and matching it on an edge would orphan every word but the
    first.
    """
    raw = sorted(
        (
            (role, *_find_label(header, label), aligns.get(role, "right"))
            for role, label in roles.items()
        ),
        key=lambda r: r[1],
    )
    bands: list[Band] = []
    for i, (role, x0, x1, align) in enumerate(raw):
        if align == "left":
            next_x0 = raw[i + 1][1] if i + 1 < len(raw) else float("inf")
            bands.append(Band(role, x0, next_x0, align))
        else:
            bands.append(Band(role, x0, x1, align))
    return tuple(bands)


def _edge(word: Word, align: str) -> float:
    if align == "left":
        return word.x0
    if align == "center":
        return (word.x0 + word.x1) / 2
    return word.x1


def _band_edge(band: Band) -> float:
    if band.align == "center":
        return (band.x0 + band.x1) / 2
    return band.x1


def assign(
    word: Word, bands: tuple[Band, ...], *, tolerance: float = 6.0
) -> str | None:
    """Return the role this word belongs to, or None when it is not clear.

    Two stages, and the order matters:

    1. A numeric column claims the word by edge proximity. This is the test
       that separates Meezan's unsigned Credit from its Debit, and it runs
       first because a money column's band sits inside the description
       column's span - reversed, every amount would be read as description
       text.
    2. Otherwise a text column claims it by containment, since a description
       is many words wide.

    None is a deliberate outcome: the caller turns it into an unresolved row,
    which fails the statement. That is far better than assigning an amount to
    the wrong side of the ledger, which reconciles against itself and reports
    a confidently wrong figure.
    """
    scored: list[tuple[float, str]] = []
    for band in bands:
        if band.align == "left":
            continue
        distance = abs(_edge(word, band.align) - _band_edge(band))
        if distance <= tolerance:
            scored.append((distance, band.role))
    if scored:
        scored.sort()
        if len(scored) > 1 and abs(scored[0][0] - scored[1][0]) < 1e-9:
            return None          # equally close to two money columns
        return scored[0][1]

    for band in bands:
        if band.align == "left" and band.x0 - tolerance <= word.x0 < band.x1:
            return band.role
    return None


def group_lines(
    words: list[Word], *, y_tolerance: float = 3.0
) -> list[list[Word]]:
    """Group words into visual lines, in printed order, each sorted left to right.

    Printed order, not sorted-by-date order: a bank may list same-day rows by
    posting sequence, and the running-balance check walks the printed sequence.
    """
    lines: list[list[Word]] = []
    for word in sorted(words, key=lambda w: (round(w.top, 1), w.x0)):
        for line in lines:
            if abs(line[0].top - word.top) <= y_tolerance:
                line.append(word)
                break
        else:
            lines.append([word])
    for line in lines:
        line.sort(key=lambda w: w.x0)
    return lines
