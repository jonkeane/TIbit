#!/usr/bin/env python3
"""Host checks for the generated data, lookup, and result navigation.

This executes numeric source blocks with a small TI-BASIC subset runner.
It is not a TI-89 emulator or a substitute for a device smoke test.
"""

from fractions import Fraction
from pathlib import Path
import csv
import re
import unittest

from build import TICKS_PER_INCH, TICKS_PER_MM, render_program

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "bits.tibasic").read_text()
with (HERE / "catalog.csv").open(newline="") as catalog_file:
    CATALOG = [
        dict(label=row["bit"], kind=row["type"], ticks=int(row["ticks"]), code=int(row["code"]))
        for row in csv.DictReader(catalog_file)
    ]


class TIList(list):
    """TI-BASIC lists have one-based indexing."""

    def __getitem__(self, index):
        if not 1 <= index <= len(self):
            raise IndexError(index)
        return super().__getitem__(index - 1)

    def __setitem__(self, index, value):
        if not 1 <= index <= len(self):
            raise IndexError(index)
        super().__setitem__(index - 1, value)


def table(name):
    # Exactly one literal assignment per table: no incremental list rebuilding.
    values, = re.findall(r"^\{([\d,]+)\}→" + name + r"$", SOURCE, re.MULTILINE)
    return TIList(map(int, values.split(",")))


def expression(text, env):
    text = text.replace("≤", "<=").replace("≥", ">=").replace("≠", "!=")
    text = re.sub(r"(?<![<>!=])=(?!=)", "==", text)
    text = text.replace("{", "TIList([").replace("}", "])")
    return eval(text, {
        "__builtins__": {}, "abs": abs, "TIList": TIList,
        "intDiv": lambda a, b: int(a / b),
    }, env)


def parse_block(source):
    lines = [line.strip() for line in source.splitlines()]
    pos = 0

    def block(stops=()):
        nonlocal pos
        nodes = []
        while pos < len(lines) and not any(lines[pos].startswith(s) for s in stops):
            nodes.append(statement())
        return nodes

    def conditional(line):
        nonlocal pos
        condition = line.split(" ", 1)[1]
        if not condition.endswith(" Then"):
            return ("if", condition, [statement()], [])
        condition = condition[:-5]
        yes = block(("Else", "EndIf"))
        next_line = lines[pos]
        pos += 1
        if next_line.startswith("ElseIf "):
            no = [conditional(next_line)]
        elif next_line == "Else":
            no = block(("EndIf",))
            assert lines[pos] == "EndIf"
            pos += 1
        else:
            assert next_line == "EndIf"
            no = []
        return ("if", condition, yes, no)

    def statement():
        nonlocal pos
        line = lines[pos]
        pos += 1
        if line.startswith("For "):
            var, first, last, *step = line[4:].split(",")
            body = block(("EndFor",))
            assert lines[pos] == "EndFor"
            pos += 1
            return ("for", var, first, last, step[0] if step else "1", body)
        if line.startswith("While "):
            body = block(("EndWhile",))
            assert lines[pos] == "EndWhile"
            pos += 1
            return ("while", line[6:], body)
        if line == "Exit":
            return ("exit",)
        if line.startswith("If "):
            return conditional(line)
        value, target = line.split("→")
        return ("store", value, target)

    nodes = block()
    assert pos == len(lines)
    return nodes


def source_block(start, end, *, include_start=False):
    first = SOURCE.index(start)
    if not include_start:
        first += len(start)
    last = SOURCE.index(end, first)
    return parse_block(SOURCE[first:last])


DIAMETERS, CODES = table("d"), table("c")
# Official TI-89 guidebook, Table 2: Arrow Keys (printed page 926).
KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT = 338, 344, 337, 340
LOOKUP = source_block("  1→lo\n", "  u→du\n", include_start=True)
ROWS = source_block('  ht&" ~"&string(q/64)&"in"→ht\n  Loop\n', "   If du=1 Then\n")
MARKER = source_block("    8*(j+1)→y\n", "    Output y,0,t\n")
KEYS = source_block("    getKey()→k\n", "   EndLoop\n")
ACTIONS = source_block("   EndLoop\n", "  EndLoop\n")


def run_block(nodes, env, *, stats=None):
    iterations = 0

    class ExitLoop(Exception):
        pass

    def iteration(body):
        nonlocal iterations
        iterations += 1
        if iterations > 1000:
            raise RuntimeError("TI-BASIC block exceeded its loop budget; possible infinite loop")
        try:
            execute(body)
        except ExitLoop:
            return False
        return True

    def execute(nodes):
        for node in nodes:
            if node[0] == "store":
                _, value, target = node
                value = expression(value, env)
                match = re.fullmatch(r"(\w+)\[(.+)\]", target)
                if match:
                    env[match[1]][expression(match[2], env)] = value
                else:
                    env[target] = value
            elif node[0] == "if":
                execute(node[2] if expression(node[1], env) else node[3])
            elif node[0] == "exit":
                raise ExitLoop
            elif node[0] == "while":
                _, condition, body = node
                while expression(condition, env):
                    if not iteration(body):
                        break
            elif node[0] == "for":
                _, var, first, last, step, body = node
                step = expression(step, env)
                stop = expression(last, env) + (1 if step > 0 else -1)
                for value in range(expression(first, env), stop, step):
                    env[var] = value
                    if not iteration(body):
                        break
            else:
                raise ValueError(node)

    exited = False
    try:
        execute(nodes)
    except ExitLoop:
        exited = True
    if stats is not None:
        stats["iterations"] = iterations
    return exited


def lookup_state(ticks, *, stats=None):
    env = dict(d=DIAMETERS, h=float(ticks), n=len(DIAMETERS))
    run_block(LOOKUP + ROWS, env, stats=stats)
    return env


def lookup(ticks, *, stats=None):
    env = lookup_state(ticks, stats=stats)
    return env["b"], list(env["r"])


def markers(state):
    env = dict(state)
    result = []
    for j in range(1, 7):
        env["j"] = j
        run_block(MARKER, env)
        result.append(env["t"])
    return result


def decode(code):
    if code <= 80:
        return f"#{81 - code}"
    if code <= 106:
        return chr(code - 16)
    if code <= 170:
        n = code - 106
        return f"{Fraction(n, 64)}in"
    mm = (code - 166) / 10 if code <= 276 else (code - 254) / 2
    return f"{mm:.1f}mm"


def oracle(ticks):
    rows = CATALOG
    best = min(range(len(rows)), key=lambda i: abs(rows[i]["ticks"] - ticks))
    smaller = [i + 1 for i, row in enumerate(rows) if i != best and row["ticks"] <= ticks]
    larger = [i + 1 for i, row in enumerate(rows) if i != best and row["ticks"] > ticks]
    smaller = smaller[-2:]
    larger = larger[:3]
    return best + 1, [0] * (2 - len(smaller)) + smaller + [best + 1] + larger + [0] * (3 - len(larger))


def linear_reference(ticks):
    """Original full-scan behavior, including its floating-point tolerance."""
    h = float(ticks)
    best = 1
    for i in range(2, len(DIAMETERS) + 1):
        if abs(DIAMETERS[i] - h) < abs(DIAMETERS[best] - h) - 1e-6:
            best = i
    smaller = [i for i in range(1, len(DIAMETERS) + 1)
               if i != best and DIAMETERS[i] <= h + 1e-6][-2:]
    larger = [i for i in range(1, len(DIAMETERS) + 1)
              if i != best and DIAMETERS[i] > h + 1e-6][:3]
    return best, [0] * (2 - len(smaller)) + smaller + [best] + larger + [0] * (3 - len(larger))


def navigation_reference(ticks):
    """Extend the original smaller / best / larger display to the whole catalog."""
    best, _ = linear_reference(ticks)
    smaller = [i for i in range(1, len(DIAMETERS) + 1)
               if i != best and DIAMETERS[i] <= float(ticks) + 1e-6]
    larger = [i for i in range(1, len(DIAMETERS) + 1)
              if i != best and DIAMETERS[i] > float(ticks) + 1e-6]
    return smaller + [best] + larger, len(smaller) + 1


class Checks(unittest.TestCase):
    def test_generated_source_and_catalog_loading(self):
        self.assertEqual(SOURCE, render_program(CATALOG))
        self.assertNotIn("augment(", SOURCE)

    def test_catalog_and_encoding(self):
        rows = CATALOG
        self.assertEqual(len(DIAMETERS), 304)
        self.assertEqual(list(DIAMETERS), sorted(DIAMETERS))
        self.assertEqual(list(DIAMETERS), [r["ticks"] for r in rows])
        self.assertEqual(list(CODES), [r["code"] for r in rows])
        self.assertEqual(len(set(CODES)), 304)
        for i, row in enumerate(rows, 1):
            label = row["label"].replace('"', 'in').replace(" ", "")
            self.assertEqual(decode(CODES[i]), label)

    def test_catalog_coverage(self):
        rows = CATALOG
        by_kind = {
            kind: [row for row in rows if row["kind"] == kind]
            for kind in ("wire", "letter", "frac", "metric")
        }
        self.assertEqual({row["label"] for row in by_kind["wire"]}, {f"#{n}" for n in range(1, 81)})
        self.assertEqual({row["label"] for row in by_kind["letter"]}, set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        self.assertEqual(
            [row["ticks"] for row in by_kind["frac"]],
            [Fraction(n, 64) * TICKS_PER_INCH for n in range(1, 65)],
        )
        expected_mm = [Fraction(n, 10) for n in range(5, 111)]
        expected_mm += [Fraction(n, 2) for n in range(23, 51)]
        self.assertEqual(
            [row["ticks"] for row in by_kind["metric"]],
            [mm * TICKS_PER_MM for mm in expected_mm],
        )

    def test_screen_example(self):
        _, indices = lookup(Fraction("0.419") * TICKS_PER_INCH)
        self.assertEqual([decode(CODES[i]) for i in indices], ["Z", "10.5mm", "10.6mm", "10.7mm", "27/64in", "10.8mm"])
        diffs = [(DIAMETERS[i] / TICKS_PER_INCH - .419) for i in indices]
        self.assertEqual([f"{v:+.4f}" for v in diffs], ["-0.0060", "-0.0056", "-0.0017", "+0.0023", "+0.0029", "+0.0062"])

    def test_all_sizes_midpoints_and_range(self):
        targets = {Fraction(0), Fraction(TICKS_PER_INCH)}
        targets.update(map(Fraction, DIAMETERS))
        targets.update(Fraction(a + b, 2) for a, b in zip(DIAMETERS, list(DIAMETERS)[1:]))
        targets.update(Fraction(i * TICKS_PER_INCH, 1000) for i in range(1001))
        for ticks in sorted(targets):
            with self.subTest(ticks=str(ticks)):
                stats = {}
                best, rows = lookup(ticks, stats=stats)
                self.assertEqual((best, rows), oracle(ticks))
                self.assertEqual(len(rows), 6)
                self.assertEqual(rows[2], best)
                # Covers the binary search, alias handling, and neighbor selection.
                self.assertLessEqual(stats["iterations"], 20)

    def test_tolerance_matches_original_search(self):
        centers = set(map(Fraction, DIAMETERS))
        centers.update(Fraction(a + b, 2) for a, b in zip(DIAMETERS, list(DIAMETERS)[1:]))
        offsets = [Fraction(n, 2_000_000) for n in (-4, -2, -1, 0, 1, 2, 4)]
        for center in sorted(centers):
            for offset in offsets:
                ticks = center + offset
                if 0 <= ticks <= TICKS_PER_INCH:
                    with self.subTest(ticks=str(ticks)):
                        self.assertEqual(lookup(ticks), linear_reference(ticks))

    def test_exact_aliases_and_boundaries(self):
        best, rows = lookup(Fraction(".25") * TICKS_PER_INCH)
        self.assertEqual(decode(CODES[best]), "1/4in")
        self.assertIn("E", [decode(CODES[i]) for i in rows if i])
        # Above an alias group, the first designation must still win.
        self.assertEqual(lookup(Fraction(".25") * TICKS_PER_INCH + 1)[0], best)
        self.assertEqual(lookup(0)[1][:2], [0, 0])
        self.assertEqual(lookup(TICKS_PER_INCH)[1][-3:], [0, 0, 0])
        self.assertEqual(lookup(TICKS_PER_INCH)[0], 304)

    def test_added_sizes_and_metric_transition(self):
        ticks = Fraction(3, 64) * TICKS_PER_INCH
        best, _ = lookup(ticks)
        self.assertEqual(DIAMETERS[best], ticks)
        self.assertEqual(decode(CODES[best]), "3/64in")
        for mm in [Fraction(n, 10) for n in range(101, 111)] + [Fraction("11.5"), Fraction(25)]:
            ticks = mm * TICKS_PER_MM
            best, _ = lookup(ticks)
            self.assertEqual(DIAMETERS[best], ticks)
            self.assertEqual(decode(CODES[best]), f"{float(mm):.1f}mm")

    def test_input_unit_invariance(self):
        for inches in [Fraction(".419"), Fraction(1, 4), Fraction(1, 64), Fraction(".185"), Fraction(1)]:
            mm = inches * Fraction("25.4")
            self.assertEqual(lookup(inches * TICKS_PER_INCH), lookup(mm * TICKS_PER_MM))

    def test_scroll_one_row_and_back(self):
        state = lookup_state(Fraction(".419") * TICKS_PER_INCH)
        original = list(state["r"])
        state["k"] = KEY_DOWN
        self.assertTrue(run_block(KEYS, state))
        run_block(ROWS, state)
        self.assertEqual(list(state["r"])[:5], original[1:])
        self.assertEqual(decode(CODES[state["r"][6]]), "10.9mm")
        self.assertEqual(state["r"][2], state["b"])
        state["k"] = KEY_UP
        self.assertTrue(run_block(KEYS, state))
        run_block(ROWS, state)
        self.assertEqual(list(state["r"]), original)
        self.assertEqual(markers(state), ["", "", "*", "", "", ""])

    def test_scroll_whole_catalog_aliases_and_endpoints(self):
        targets = [0, TICKS_PER_INCH, Fraction(".419") * TICKS_PER_INCH]
        alias = Fraction(1, 4) * TICKS_PER_INCH
        targets += [alias, alias + Fraction(1, 2_000_000), alias + 1]
        for ticks in targets:
            with self.subTest(ticks=str(ticks)):
                state = lookup_state(ticks)
                order, initial = navigation_reference(ticks)
                fixed = {key: state[key] for key in ("h", "b", "p", "bc")}
                center = initial
                for key, destination in [(KEY_UP, 1), (KEY_DOWN, len(order)), (KEY_UP, initial)]:
                    for _ in range(abs(destination - center)):
                        state["k"] = key
                        self.assertTrue(run_block(KEYS, state))
                        center += -1 if key == KEY_UP else 1
                        run_block(ROWS, state)
                        expected = [order[i - 1] if 1 <= i <= len(order) else 0
                                    for i in range(center - 2, center + 4)]
                        self.assertEqual(state["sc"], center)
                        self.assertEqual(list(state["r"]), expected)
                        self.assertEqual({key: state[key] for key in fixed}, fixed)
                        expected_markers = ["*" if i == state["b"] else "" for i in expected]
                        if state["b"] not in expected:
                            if order.index(state["b"]) + 1 < center - 2:
                                expected_markers[0] = "↑"
                            else:
                                expected_markers[5] = "↓"
                        self.assertEqual(markers(state), expected_markers)
                        for index, marker in zip(expected, expected_markers):
                            if marker:
                                self.assertNotEqual(index, 0)
                    if destination in (1, len(order)):
                        state["k"] = KEY_UP if destination == 1 else KEY_DOWN
                        before = list(state["r"])
                        self.assertTrue(run_block(KEYS, state))
                        run_block(ROWS, state)
                        self.assertEqual(state["sc"], destination)
                        self.assertEqual(list(state["r"]), before)

    def test_navigation_keys_units_and_new_input(self):
        state = lookup_state(Fraction(".419") * TICKS_PER_INCH)
        state.update(k=KEY_DOWN, du=1, z=0)
        run_block(KEYS, state)
        run_block(ROWS, state)
        scrolled = state["sc"], list(state["r"])
        for key in (270, 270):
            state["k"] = key
            self.assertTrue(run_block(KEYS, state))
            old_units = state["du"]
            self.assertFalse(run_block(ACTIONS, state))
            self.assertEqual(state["du"], 3 - old_units)
            run_block(ROWS, state)
            self.assertEqual((state["sc"], list(state["r"])), scrolled)
        for key in (0, 13, KEY_LEFT, KEY_RIGHT):
            state["k"] = key
            self.assertFalse(run_block(KEYS, state))
            self.assertEqual(state["sc"], scrolled[0])
        for key, quit_flag in ((268, 0), (264, 1)):
            state["k"] = key
            self.assertTrue(run_block(KEYS, state))
            self.assertTrue(run_block(ACTIONS, state))
            self.assertEqual(state["z"], quit_flag)
        state["h"] = 0
        run_block(LOOKUP + ROWS, state)
        self.assertEqual(state["sc"], 1)
        self.assertEqual((state["b"], list(state["r"])), lookup(0))

    def test_offscreen_indicator_transitions_and_unit_toggle(self):
        for ticks in (Fraction(".419") * TICKS_PER_INCH, Fraction(1, 4) * TICKS_PER_INCH):
            for key, edge, steps, arrow, return_key in (
                (KEY_DOWN, 0, 2, "↑", KEY_UP), (KEY_UP, 5, 3, "↓", KEY_DOWN)
            ):
                with self.subTest(ticks=str(ticks), key=key):
                    state = lookup_state(ticks)
                    state.update(du=1, z=0)
                    for _ in range(steps):
                        state["k"] = key
                        run_block(KEYS, state)
                        run_block(ROWS, state)
                    expected = ["", "", "", "", "", ""]
                    expected[edge] = "*"
                    self.assertEqual(markers(state), expected)
                    run_block(KEYS, state)
                    run_block(ROWS, state)
                    expected[edge] = arrow
                    self.assertEqual(markers(state), expected)
                    state["k"] = 270
                    run_block(KEYS, state)
                    run_block(ACTIONS, state)
                    run_block(ROWS, state)
                    self.assertEqual(markers(state), expected)
                    state["k"] = return_key
                    run_block(KEYS, state)
                    run_block(ROWS, state)
                    expected[edge] = "*"
                    self.assertEqual(markers(state), expected)

    def test_f2_recenters_without_changing_hole_or_units(self):
        targets = (0, TICKS_PER_INCH, Fraction(".419") * TICKS_PER_INCH,
                   Fraction(1, 4) * TICKS_PER_INCH)
        for ticks in targets:
            for units in (1, 2):
                state = lookup_state(ticks)
                state.update(du=units, z=0)
                initial_rows = list(state["r"])
                fixed = {key: state[key] for key in ("h", "b", "p", "bc", "du", "z")}
                for position in (1, len(DIAMETERS), state["bc"]):
                    with self.subTest(ticks=str(ticks), units=units, position=position):
                        state["sc"] = position
                        run_block(ROWS, state)
                        state["k"] = 269
                        self.assertTrue(run_block(KEYS, state))
                        self.assertFalse(run_block(ACTIONS, state))
                        run_block(ROWS, state)
                        self.assertEqual(list(state["r"]), initial_rows)
                        self.assertEqual(markers(state), ["", "", "*", "", "", ""])
                        self.assertEqual({key: state[key] for key in fixed}, fixed)

    def test_display_bounds(self):
        # Conservative medium-font allowance: six pixels per character, eight per row.
        # Full-screen pixel rows run from 0 through 76 (TI-89 guidebook, p. 628).
        # Read the rendering loop so the sixth result cannot overlap the footer.
        display, = re.findall(r'^   For j,1,(\d+)\n    (.+)→y$', SOURCE, re.MULTILINE)
        count, position = display
        self.assertEqual(int(count), 6)
        row_positions = [expression(position, {"j": j}) for j in range(1, int(count) + 1)]
        self.assertGreaterEqual(row_positions[0], 16)
        for previous, current in zip(row_positions, row_positions[1:]):
            self.assertGreaterEqual(current - previous, 8)
        footer_row, footer = re.findall(r'^   Output (\d+),0,("F1:new .+)$', SOURCE, re.MULTILINE)[0]
        self.assertGreaterEqual(int(footer_row), row_positions[-1] + 8)
        self.assertLessEqual(int(footer_row) + 8, 77)
        for units in (1, 2):
            rendered = expression(footer.replace("&", "+"), {
                "du": units, "mid": lambda text, start, count: text[start - 1:start - 1 + count],
            })
            self.assertLessEqual(len(rendered) * 6, 160)
        self.assertLessEqual(max(len(decode(code)) for code in CODES) * 6 + 6, 56)
        for diameter in DIAMETERS:
            self.assertLessEqual(56 + len(f"{diameter / TICKS_PER_INCH:.4f}") * 6, 104)
            self.assertLessEqual(56 + len(f"{diameter / TICKS_PER_MM:.3f}") * 6, 104)
        # Scrolling can expose the full one-inch difference from a zero-sized hole.
        self.assertLessEqual(104 + len("+1.0000") * 6, 160)
        self.assertLessEqual(104 + len("+25.400") * 6, 160)
        self.assertLessEqual(104 + len("+<.0001") * 6, 160)
        self.assertLessEqual(104 + len("=0.0000") * 6, 160)


if __name__ == "__main__":
    unittest.main(verbosity=2)
