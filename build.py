#!/usr/bin/env python3
"""Build TI-89 source from drill bit data; standard library only."""

from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import argparse
import csv
import re

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "Drill Bit Size Finder | Find the Closest Drill Bit Size.html"
TICKS_PER_INCH = 5_080_000
TICKS_PER_MM = 200_000


def catalog():
    entries = re.findall(
        r"\{s:'([^']+)',t:'([^']+)',i:([\d.]+),m:([\d.]+)\}",
        SOURCE.read_text(),
    )
    if len(entries) != 295:
        raise ValueError("Expected 295 entries in the source data")

    # Keep the source's alias order and gauge/letter diameters, but generate
    # complete fractional and metric grids independently of its omissions.
    source_order = {label: order for order, (label, _, _, _) in enumerate(entries)}
    sizes = [
        (label, kind, Fraction(inches))
        for label, kind, inches, _ in entries
        if kind in ("wire", "letter")
    ]
    sizes.extend(
        (f'{Fraction(n, 64)}"', "frac", Fraction(n, 64))
        for n in range(1, 65)
    )
    metric_sizes = [Fraction(n, 10) for n in range(5, 111)]
    metric_sizes += [Fraction(n, 2) for n in range(23, 51)]
    sizes.extend(
        (f"{Decimal(mm.numerator) / mm.denominator:.1f} mm", "metric", mm / Fraction("25.4"))
        for mm in metric_sizes
    )

    rows = []
    for label, kind, size in sizes:
        if kind == "wire":
            code = 81 - int(label[1:])
        elif kind == "letter":
            code = ord(label) + 16
        elif kind == "frac":
            code = 106 + int(size * 64)
        elif kind == "metric":
            metric = size * Fraction("25.4")
            code = int(metric * 10 + 166) if metric <= 11 else int(metric * 2 + 254)
        else:
            raise ValueError(kind)
        ticks = size * TICKS_PER_INCH
        if ticks.denominator != 1:
            raise ValueError(f"Nonintegral diameter for {label}")
        order = source_order.get(label, len(entries))
        rows.append(dict(label=label, kind=kind, ticks=int(ticks), code=code, order=order))
    return sorted(rows, key=lambda row: (row["ticks"], row["order"]))


def ti_list(name, values):
    """Load the entire list once instead of rebuilding it through augment()."""
    return "{" + ",".join(map(str, values)) + "}→" + name


def render_program(rows):
    template = (HERE / "bits.template").read_text()
    program = template.replace("@DIAMETERS@", ti_list("d", [r["ticks"] for r in rows]))
    return program.replace("@CODES@", ti_list("c", [r["code"] for r in rows]))


def build(from_catalog=False):
    if from_catalog:
        with (HERE / "catalog.csv").open(newline="") as source:
            rows = [
                dict(ticks=int(row["ticks"]), code=int(row["code"]))
                for row in csv.DictReader(source)
            ]
    else:
        rows = catalog()
    program = render_program(rows)
    (HERE / "bits.tibasic").write_text(program)
    if not from_catalog:
        with (HERE / "catalog.csv").open("w", newline="") as out:
            writer = csv.writer(out)
            writer.writerow(["bit", "type", "diameter_in", "diameter_mm", "ticks", "code"])
            for row in rows:
                ticks = Decimal(row["ticks"])
                writer.writerow([
                    row["label"], row["kind"],
                    str(ticks / TICKS_PER_INCH), str(ticks / TICKS_PER_MM),
                    row["ticks"], row["code"],
                ])
    print(f"Built bits.tibasic: {len(rows)} bits, {len(program.encode())} UTF-8 source bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-catalog", action="store_true",
        help="rebuild only bits.tibasic using the included catalog.csv",
    )
    build(from_catalog=parser.parse_args().from_catalog)
