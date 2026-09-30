"""Produce a masked layout dump of a statement.

This is the privacy gate for the whole project: Claude reads only what this
tool writes, never a real statement. Every token becomes its SHAPE - letters
to X/x, digits to 9, punctuation kept - unless it is on the allowlist of
non-personal banking vocabulary. That preserves exactly what a parser author
needs (column order, separators, date and amount formats, Dr/Cr tokens) and
nothing that identifies a person or an account.

stdout carries only a path and counts, so running this in a shared terminal
or pasting its output reveals nothing.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import io
import re
import string
import sys
from collections import Counter
from pathlib import Path

from fbr import paths
from fbr.ingest import sha256_of, sniff_container

_ALLOWLIST_FILE = Path(__file__).with_name("dump_allowlist.txt")

# A token is a run that starts with a letter or digit IN ANY SCRIPT and runs
# on until ASCII whitespace or ASCII punctuation ends it. The four ASCII
# punctuation marks that legitimately sit inside one word (. _ / -) do not
# end it, and a comma continues it only when it groups digits (e.g.
# "1,234.56"), never between two words: "Date,Description" (a header row
# joined with no space, as CSV commonly is) must split into "Date" and
# "Description" so each is checked against the allowlist on its own, rather
# than merging into one blob that matches no single allowlist entry and gets
# shape-mangled whole.
#
# This is deliberately "everything except the ASCII separators" rather than
# an [A-Za-z0-9] allowlist of characters. An ASCII-only tokenizer never
# CAPTURES non-Latin text, and what is never captured is never shaped:
# "محمد فیضان حسنات" passed through a dump completely unchanged, and
# "José Müller" came out as "Xxxé Xüxxxx" - the tokenizer stopped dead at
# the first accented letter and left it, plus the rest of that word,
# verbatim. A foreign remitter's name or any Urdu text in a real statement
# would have reached a dump readable. Non-ASCII combining marks (Arabic
# harakat, Devanagari matras, a decomposed acute accent) are inside the run
# for the same reason: they must not split a word into fragments that are
# then allowlist-checked one character at a time.
#
# The cost is that a non-ASCII character glued between two letters - an em
# dash in "A—B" - joins the token and is shaped rather than kept as a
# separator. Standing alone, as every separator in a real statement does, it
# is not a token start and survives verbatim, so separator style is intact.
_BREAKERS = "".join(c for c in string.punctuation if c not in "._/-")
_TOKEN = re.compile(rf"[^\W_](?:[^\s{re.escape(_BREAKERS)}]|,(?=\d))*")
# Also Unicode, and for the same reason: this is what folds a token before it
# is looked up in the allowlist. Left as [^A-Za-z0-9] it would reduce "José"
# to "JOS", so an allowlist entry "JOS" would release the whole token - name
# and all - verbatim. Folding to "JOSÉ" keeps a foreign-script token from
# being allowlisted by its ASCII skeleton. Pure-ASCII tokens fold exactly as
# before.
_STRIP = re.compile(r"[\W_]")
_NUMERIC = re.compile(r"^[0-9][0-9,]*(\.[0-9]+)?$")
# Built from chr(96) rather than written literally, so this source can live
# inside a Markdown fence without closing it.
FENCE = chr(96) * 3


def load_allowlist(extra: Path | None = None) -> set[str]:
    """Shipped vocabulary, plus the owner's own additions if present."""
    words: set[str] = set()
    for source in (_ALLOWLIST_FILE, extra if extra is not None else paths.dump_allowlist_path()):
        if source and source.is_file():
            for line in source.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    words.add(_STRIP.sub("", line).upper())
    words.discard("")
    return words


def shape(token: str, *, allowlist: set[str], hide_magnitude: bool = False) -> str:
    """Replace a token with its shape, unless it is allowlisted.

    Punctuation is kept because separator style (1,234.56 vs 1234.56) and
    suffixes (Dr/Cr) are exactly what a profile author must know.
    """
    if _STRIP.sub("", token).upper() in allowlist:
        return token

    out: list[str] = []
    for ch in token:
        if ch.isdigit():
            out.append("9")
        elif ch.isupper():
            out.append("X")
        elif ch.islower():
            out.append("x")
        elif ch.isascii():
            # ASCII punctuation and separators are the layout signal a
            # profile author needs (1,234.56 vs 1234.56, a glued "Dr"), so
            # they survive. This is the ONLY thing that survives unshaped.
            out.append(ch)
        else:
            # Anything else non-ASCII: a caseless letter (Urdu, Arabic, CJK,
            # Devanagari - `isupper()` and `islower()` are both False for
            # every one of them, so the branches above never fire and the
            # character used to be copied through verbatim), a combining
            # accent, or an unfamiliar symbol. A name in the owner's own
            # script is exactly what this tool exists to hide, so the rule
            # is fail-closed: mask it. Caseless scripts have no upper form,
            # so the lowercase placeholder is the case-appropriate one.
            out.append("x")
    shaped = "".join(out)

    if hide_magnitude and any(c.isdigit() for c in token):
        # Collapse the integer part to a fixed width so the number of digits
        # does not leak the size of a balance.
        shaped = re.sub(r"9[9,]*(?=(\.99)?(?!9))", "9,999", shaped, count=1)
    return shaped


def mask_text(text: str, *, allowlist: set[str], hide_magnitude: bool = False,
              counts: Counter | None = None) -> str:
    """Mask every token in a block of text, preserving its layout."""

    def replace(m: re.Match) -> str:
        token = m.group(0)
        masked = shape(token, allowlist=allowlist, hide_magnitude=hide_magnitude)
        if counts is not None and masked != token and not _NUMERIC.match(token):
            counts[_STRIP.sub("", token).upper()] += 1
        return masked

    return _TOKEN.sub(replace, text)


def _read_rows(data: bytes, container: str) -> list[list[str]]:
    from fbr.engines.tabular import read_rows

    return read_rows(data, container)


def dump_tabular(
    data: bytes,
    container: str,
    *,
    allowlist: set[str],
    rows: int,
    hide_magnitude: bool,
) -> tuple[str, Counter]:
    """Render a masked dump of a CSV/XLSX statement."""
    counts: Counter = Counter()
    parsed = _read_rows(data, container)
    total = len(parsed)

    def mask_row(row: list[str]) -> str:
        return ",".join(
            mask_text(cell, allowlist=allowlist, hide_magnitude=hide_magnitude, counts=counts)
            for cell in row
        )

    head = parsed[: min(rows, total)]
    tail = parsed[max(len(head), total - rows):]

    lines = [
        "# Masked layout dump",
        "",
        f"- container: `{container}`",
        f"- rows: {total}",
        f"- columns (first row): {len(parsed[0]) if parsed else 0}",
        f"- magnitude hidden: {hide_magnitude}",
        "",
        "Every token below is a SHAPE (letters -> X/x, digits -> 9) unless it is",
        "non-personal banking vocabulary. Separators, suffixes and column order",
        "are preserved exactly.",
        "",
        f"## First {len(head)} row(s)",
        "",
        FENCE,
        *[mask_row(r) for r in head],
        FENCE,
        "",
    ]

    if total > len(head):
        lines += [f"## Last {len(tail)} row(s)", "",
                  FENCE, *[mask_row(r) for r in tail], FENCE, ""]

    # A per-column shape histogram shows which columns are dates, amounts or text.
    width = max((len(r) for r in parsed), default=0)
    lines += ["## Per-column shape histogram", ""]
    for col in range(width):
        column_counts: Counter = Counter()
        for row in parsed[1:]:
            cell = row[col].strip() if col < len(row) else ""
            column_counts[
                mask_text(cell, allowlist=allowlist, hide_magnitude=hide_magnitude) or "(blank)"
            ] += 1
        top = ", ".join(f"`{s}` x{n}" for s, n in column_counts.most_common(4))
        lines.append(f"- col {col}: {top}")
    lines.append("")

    return "\n".join(lines), counts


def dump_pdf(
    data: bytes,
    *,
    allowlist: set[str],
    pages: int,
    hide_magnitude: bool,
    password: str | None = None,
) -> tuple[str, Counter]:
    """Render a masked dump of a PDF: word shapes with their coordinates.

    A profile author needs geometry - which column an amount sits under, how
    columns are ordered, what the date and amount formats look like. Coordinates
    are geometry, not content, so they are printed as-is; every word is masked.
    """
    import pdfplumber

    counts: Counter = Counter()
    lines_out: list[str] = []
    with pdfplumber.open(io.BytesIO(data), password=password or "") as pdf:
        total = len(pdf.pages)
        chosen = list(range(min(pages, total)))
        if total > pages:
            chosen.append(total - 1)
        lines_out += [
            "# Masked layout dump (PDF)",
            "",
            f"- pages: {total}",
            f"- pages shown: {[i + 1 for i in chosen]}",
            f"- encrypted: {bool(password)}",
            f"- magnitude hidden: {hide_magnitude}",
            "",
            "Every token is a SHAPE (letters -> X/x, digits -> 9) unless it is",
            "non-personal banking vocabulary. Coordinates are rounded to 1pt and",
            "are geometry, not content: they are what a profile's column bands",
            "are built from.",
            "",
        ]
        for i in chosen:
            page = pdf.pages[i]
            words = page.extract_words()
            if any("(cid:" in w["text"] for w in words):
                lines_out.append(f"## Page {i + 1}: UNMAPPED FONTS ((cid:) glyphs)")
                continue
            lines_out += [f"## Page {i + 1} ({len(words)} words)", "", FENCE]
            rows: dict[int, list[str]] = {}
            for w in words:
                shaped = mask_text(w["text"], allowlist=allowlist,
                                   hide_magnitude=hide_magnitude, counts=counts)
                rows.setdefault(round(w["top"]), []).append(
                    f"{shaped}@{round(w['x0'])}-{round(w['x1'])}"
                )
            for top in sorted(rows):
                lines_out.append(f"y={top}: " + "  ".join(rows[top]))
            lines_out += [FENCE, ""]
    return "\n".join(lines_out), counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fbr-dump",
        description="Write a masked layout dump of a statement into the private folder.",
    )
    parser.add_argument("path", help="statement file to dump")
    parser.add_argument("--rows", type=int, default=15,
                        help="rows to show from the start and end (default 15)")
    parser.add_argument("--hide-magnitude", action="store_true",
                        help="also hide how many digits each amount has")
    parser.add_argument("--password", action="store_true",
                        help="accepted for compatibility; PDFs always prompt (never on the command line)")
    args = parser.parse_args(argv)

    source = Path(args.path).expanduser()
    if not source.is_file():
        print(f"fbr-dump: file not found: {source}", file=sys.stderr)
        return 2

    data = source.read_bytes()
    container = sniff_container(data)

    allowlist = load_allowlist()
    if container == "pdf":
        password = getpass.getpass("PDF password (blank if none): ") or None
        try:
            text, counts = dump_pdf(
                data, allowlist=allowlist, pages=2,
                hide_magnitude=args.hide_magnitude, password=password,
            )
        except Exception as exc:                    # noqa: BLE001
            # Never echo str(exc): it could carry file content or the password.
            print(f"fbr-dump: could not read this PDF ({type(exc).__name__}); "
                  "check the password", file=sys.stderr)
            return 2
    else:
        text, counts = dump_tabular(
            data, container, allowlist=allowlist,
            rows=args.rows, hide_magnitude=args.hide_magnitude,
        )

    paths.ensure_private_layout()
    digest = sha256_of(data)
    # Named by hash: the source filename may itself contain an account number.
    out = paths.dumps_dir() / f"{digest[:12]}.dump.md"
    out.write_text(text, encoding="utf-8")

    candidates = paths.dump_candidates_dir() / f"{digest[:12]}.txt"
    candidates.write_text(
        "# Masked words, most frequent first. Copy any that are safe, non-personal\n"
        "# vocabulary into ~/fbr-private/dump-allowlist.txt and re-run fbr-dump.\n"
        "# Claude never reads this file.\n"
        + "\n".join(f"{word}\t{n}" for word, n in counts.most_common(200)),
        encoding="utf-8",
    )

    print(f"wrote {out}: {len(text.splitlines())} lines, {sum(counts.values())} tokens masked")
    print(f"candidates: {candidates}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
