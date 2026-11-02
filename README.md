# TI-89 drill bit finder

`bits.tibasic` contains the complete TI-89 BASIC program, including its lookup data. Run it as `bits()`. It accepts **0–1 inch or 0–25.4 mm**, including endpoints. One inch is 25.4 mm; the request's 2.54 mm upper limit appears to be a decimal-place typo.

Enter the hole diameter in the first field, choose `in` or `mm` in the second field (Units), and confirm the dialog. Units default to `mm` on startup, and the Hole field starts in numeric mode with alpha-lock off. Numeric expressions such as `27/64` are accepted. Invalid, complex, or symbolic inputs return to the input dialog with a short message. ESC in the input dialog exits.

The results show six rows. Each new lookup starts with the best match in row 3, marked `*`. Two nearby bits at or below the input appear above it, and three above the input appear below it. All four bit types participate in every lookup, regardless of input units.

Press **↓** to scroll one row toward larger bits or **↑** to scroll one row toward smaller bits. The `*` stays with the original best match as it moves through the display; all differences remain relative to the entered hole size. If the best match is off screen, `↑` beside the first row points back toward it from larger bits, or `↓` beside the last row points toward it from smaller bits. The arrow uses the same column as `*` and becomes `*` again when the best match returns to view. Scrolling stops with the smallest or largest catalog entry in row 3, with unavailable rows shown as `--`.

Press **F2** (`center`) to reset scrolling and return the original best match to row 3. The entered hole size and current display units stay the same.

For `.419 in`, the screen looks like this (spacing illustrated):

```text
0.419in ~27/64in
 Bit     D in    d in
 Z       0.4130  -0.0060
 10.5mm  0.4134  -0.0056
*10.6mm  0.4173  -0.0017
 10.7mm  0.4213  +0.0023
 27/64in 0.4219  +0.0029
 10.8mm  0.4252  +0.0062
F1:new F2:center F3:mm ESC
```

`D` is the bit diameter. `d` is **bit diameter minus hole diameter**: `+` means a larger bit and `-` means a smaller bit. `in` on a fraction means inches; `#` identifies a number/gauge bit, and a single letter identifies a letter bit.

| Key | Action |
| --- | --- |
| ↑ / ↓ | Scroll one row toward smaller / larger bits |
| F1 | Enter a new hole size and choose input units; put the new best match in row 3 |
| F2 | Reset scrolling to put the original best match in row 3 |
| F3 | Toggle both the diameter and difference columns between inches and mm; the label shows the unit pressing F3 will switch to |
| ESC | Exit |

<details>
<summary>Implementation details</summary>

Both result columns initially use the input units and always switch units together. Changing result units preserves the original input and scroll position. The top line shows the hole diameter to three decimal places in its original units, decimal inches when the input is in mm, and the nearest 1/64 inch reduced to lowest terms. For example, `10.6426 mm` displays `10.643mm 0.419in ~27/64in`. The `~` marks the rounded fraction; halfway values round up, and the endpoints display as `0in` and `1in`. The fraction is calculated from the full hole diameter before display rounding. Result columns show four decimal places in inches or three in mm. The program computes matches and differences before rounding them for display.

Bit diameters include a leading zero below one, such as `0.4130`. Exact matches show `=0.0000` in inches or `=0.000` in mm. Ordinary nonzero differences include a leading zero below one, such as `-0.124` or `+0.100`, so their decimal points align with exact matches. A nonzero difference that would round to zero shows, for example, `+<.0001` or `-<.001`, preserving its direction. A numerical tolerance of 0.000001 internal tick (about 0.000000000000197 inch) absorbs calculator arithmetic noise; this is much smaller than the display resolution. Equal-distance ties favor the smaller diameter. Equal-diameter aliases follow catalog order; for example, `1/4in` wins the tie with `E`, and both can appear.

The display uses the Program I/O screen and pixel-positioned `Output`, with nine lines from row 0 through row 64. The six result rows start at pixels 16 through 56, and the key legend starts at pixel 64. The bit, diameter, and difference columns begin at pixels 6, 56, and 104. Text fits within 160 pixels using a conservative six pixels per character. ↑, ↓, F1, F2, F3, and ESC are read with `getKey()`. Only the up/down arrow keys scroll: their TI-89 key codes are 338 and 344, respectively. Those commands, key codes, and display arrow characters follow the [official TI-89 guidebook](https://education.ti.com/html/eguides/graphing/89-Titanium/PDFs/TI-89-Guidebook_EN.pdf) (printed pages 924 and 926). The program temporarily selects full screen, decimal base, and AUTO arithmetic; it restores saved modes on normal exit and handled errors. Its working variables are local.

The included catalog contains **304 entries**: all 80 gauge sizes from #80 through #1, all 26 letters A–Z, all 64 fractional sizes from 1/64" through 1" in 1/64" increments, and 134 metric sizes. The metric selection is **0.5–11 mm by 0.1 mm, then 11.5–25 mm by 0.5 mm**: 10.1, 10.2, …, 10.9, 11.0, 11.5, 12.0, and so on. There are no gaps in the specified gauge, letter, or fractional ranges.

Diameters use each designation's nominal size: exact fractions, exact metric sizes, and the listed decimal inch values for gauge and letter bits. This avoids unit-dependent matches caused by separately rounded inch/mm values. For example, `4.7 mm` and `#13` are distinct even though both round to `0.1850` inch at four decimal places. For `.419 in`, the best match is `10.6mm`, with a difference displayed as `-0.0017 in` or `-0.043 mm`. The nearby `27/64in` difference is `+0.002875 in = +0.073025 mm`, displayed as `+0.0029` or `+0.073`.

To save space, the program stores two numeric lists and generates bit labels only for visible rows. Diameters are integers in units of 1/5,080,000 inch, equivalent to 1/200,000 mm; all catalog sizes are exact whole numbers in these units. The second list encodes designations. The generated UTF-8 source is about 6.6 KB; this is a source-file measurement, not a measured calculator memory requirement. Each list loads in one literal assignment, avoiding repeated `augment()` calls at startup. These two source lines are intentionally long; desktop tokenization is recommended. The lists load once per run, and new inputs reuse them.

The lookup uses binary search on the sorted diameters, taking at most nine search steps for the current catalog instead of two full scans totaling 607 iterations. It compares the two bracketing diameters and retains the first equal-diameter alias. The six visible rows are calculated directly from the scroll position, preserving the initial smaller/best/larger arrangement and both equal-diameter aliases. Each arrow press redraws those six rows using the existing catalog and best match. The original tolerance, smaller-diameter tie preference, and endpoint placeholders are preserved. Actual elapsed-time improvements still need measurement on a calculator.

</details>

## Tokenization, loading on calculator
**Command-line tools:** ensure that [Tokens89](https://github.com/jonkeane/tokens89) and [tilibs](https://github.com/debrouxl/tilibs/) are on your path.

**Tokenize and verify:** run these commands from this repository's root. The included `bits.tibasic` is ready to encode; rebuilding the catalog first is only necessary after source/data changes.

```sh
tokens89 encode bits.tibasic --output bits.89p --name bits --folder main --type program --force
tokens89 verify bits.89p
```

**Transfer and run:** connect and turn on a TI-89 Titanium, then send the generated file over a DirectLink cable:

```sh
tilp --calc=ti89t --cable=DirectLink --port=1 --no-gui bits.89p
```

Adjust the calculator, cable, and port options for your hardware. For example, for an original TI-89 using a SilverLink cable on port 2:

```sh
tilp --calc=ti89 --cable=SilverLink --port=2 --no-gui bits.89p
```

Run `tilp --help` for the installed version's options. If the calculator is not found, check the cable connection, calculator power, model, cable type, and port. From Home, run `bits()`, or `main\bits()` if your current calculator folder differs.

## Development
* Running host checks:** run from this repository's root using the included `bits.tibasic` and `catalog.csv`:

```sh
python3 verify.py
```

The verifier compares the generated lists with `catalog.csv` and executes the actual lookup, visible-row, marker, and navigation blocks using a small TI-BASIC subset runner. It compares results with an independent exact-fraction calculation at every catalog diameter, neighboring midpoint, and 1,001 evenly spaced inputs, and enforces a lookup loop budget. Inputs within and around the numerical tolerance of every diameter and midpoint are also compared with the original linear search. Navigation checks traverse the full catalog in both directions, including equal-diameter aliases, endpoint limits, one-row shifts, off-screen direction arrows, transitions back to `*`, F3 preserving the scroll position and marker, F2 restoring the initial view while preserving the hole size and display units, and new inputs resetting the view. They also verify that left/right keys do not scroll. Other checks cover template/source consistency, single-assignment catalog loading, complete catalog coverage, the 11 mm transition, the screen example, exact aliases, unit conversion, endpoints, label decoding, and text bounds.

**Rebuilding the program:** `bits.template` is the editable program template. After template or generator changes, rebuild `bits.tibasic` from the included `catalog.csv`:

```sh
python3 build.py --from-catalog
```

This leaves `catalog.csv` unchanged. Re-tokenize the source afterward using the commands above.

**Rebuilding the data:** without `--from-catalog`, `build.py` regenerates both `bits.tibasic` and the reviewable `catalog.csv`. It imports gauge/letter diameters and alias ordering from the HTML source file configured by `SOURCE` in `build.py`, then generates the complete fractional and metric grids. The source file is expected at `../Drill Bit Size Finder | Find the Closest Drill Bit Size.html` and is not included in this repository; without it, a data rebuild fails with `FileNotFoundError`. With the source file in place, run:

```sh
python3 build.py
```

**Validation limit:** the source passes the host checks, has been tokenized with Tokens89, and the resulting `main\bits` program passes `tokens89 verify`, but this version has not been run on a physical TI-89 or ROM emulator. Startup speed, lookup speed, calculator-side syntax, input dialogs, key handling, mode restoration, and actual screen rendering still need a device smoke test. Useful checks are `.419 in`, `10.6426 mm` (the same hole), `6.35 mm` (the `1/4in`/`E` tie), `0`, `1 in`, `25.4 mm`, an out-of-range value, a fraction expression, ↑/↓ to scroll and return, the arrow indicator after three presses of ↓ or four presses of ↑ from the initial view, scrolling to each catalog end, F3 while scrolled, F2 to recenter from either direction, F1 to enter a new calculation, and ESC.
