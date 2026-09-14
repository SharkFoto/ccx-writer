# ccx-writer

Write **CorelDRAW CMX / CCX** files from SVG, in pure Python 3.

`ccx-writer` is a Python 3 port of the CMX writer from
[UniConvertor 2.0](https://github.com/sk1project/uniconvertor) (sK1 Project,
revision `973d5b6`), which only ever ran on Python 2 and is no longer maintained.
On top of a byte-exact port it fixes the precision and robustness defects that made
the original output unusable for real artwork, and adds the 32-bit CMX format the
original never wrote.

No native dependencies: the original needed pycairo, lcms, ImageMagick and pango;
this package needs nothing outside the standard library.

> Source comments are written in Chinese. Each fix is annotated at the exact place
> where the original went wrong, with the reason for the change.

## Install

```bash
pip install https://github.com/SharkFoto/ccx-writer/archive/refs/tags/v0.2.0.tar.gz
```

Python 3.6 or newer.

## Use

```bash
# Uncompressed CMX v1 (recommended, see below)
python -m ccx_writer drawing.svg drawing.cmx

# Same bytes, named .cdr
python -m ccx_writer drawing.svg drawing.cdr --no-pack

# zlib-packed CCX (RIFF "CDRX")
python -m ccx_writer drawing.svg drawing.cdr --pack

# 16-bit CMX instead of the default 32-bit
python -m ccx_writer drawing.svg drawing.cmx --cmx16
```

Exit codes: `0` success, `1` conversion error, `2` input outside CMX limits
(or bad usage), `3` unsupported content (`<image>`, `<text>`).

Real-world SVG (PDF exports from `pdftocairo -svg`, tracer output, editor exports)
should be normalised first:

```bash
python -m ccx_writer.svgprep input.svg prepared.svg
python -m ccx_writer prepared.svg output.cmx
```

`svgprep` expands `<use>`/`<symbol>`, moves `style="…"` declarations to attributes,
converts `rgb(…%)` colours to hex, and drops empty sub-paths, `<clipPath>` and `<mask>`.

From Python:

```python
from ccx_writer.convert import convert
convert("drawing.svg", "drawing.cmx")             # pack=False for .cmx
convert("drawing.svg", "drawing.cdr", pack=False) # .cdr defaults to pack=True
convert("drawing.svg", "drawing.cmx", bits=16)    # default bits=32
```

### Which container to write

| Output | CorelDRAW | libcdr (Inkscape, LibreOffice) |
|---|---|---|
| Uncompressed CMX v1 (`--no-pack`) | opens; objects are editable curves | reads it |
| Packed CCX (`--pack`) | opens; same result | **cannot read it** |

CorelDRAW detects the format from the content, not the extension, so uncompressed
CMX saved as `.cdr` opens as a drawing. Use `--no-pack` unless you know the reader
handles CDRX.

### 32-bit or 16-bit

Output is 32-bit CMX by default, laid out like CorelDRAW's own "CMX - Corel Presentation
Exchange Legacy" export: every instruction and resource record is a tagged list, and
coordinates are in 1/254000 inch (0.0001 mm) over a ±8454 inch range. When CorelDRAW
imports 32-bit CMX, dashed outlines stay editable dashed outlines. When it imports 16-bit
CMX, it turns them into grouped filled shapes.

`--cmx16` writes 16-bit CMX. It allows longer single paths (65535 points against 7281),
which matters only for one filled compound path whose outline and holes cannot be split
(see Limits). Both formats are read by libcdr.

## What the fixes change

The original writer only wrote 16-bit CMX, with a 72× resolution loss: every coordinate
was scaled into ±451 units out of a ±32767 range. On an A3 page that is a 0.46 mm grid,
enough to break 7 pt type into visible steps.

The default 32-bit output has a fixed 0.0001 mm unit. Fixed 16-bit output (`--cmx16`)
uses 1/1000 inch per unit (0.0254 mm), the native unit of 16-bit CMX.
libcdr reads every 16-bit coordinate in that unit and ignores the file's scale field,
so this is what keeps sizes correct in Inkscape and LibreOffice as well as CorelDRAW.
Only artwork reaching more than 32.5 inches from the page centre gets a larger unit,
chosen so the furthest point fills the 16-bit range.

Other defects fixed include hairlines truncated to zero width, dashes never written,
line caps looked up in the join table, a 16-bit instruction length that aborted the
whole file on long paths, bounding boxes smaller than their contents, and crashes on
empty documents. [`BUGS.md`](BUGS.md) lists all of them: what the original did, the
fix, and how it was checked.

The original behaviour is still available with `uc2_compat=True`. That mode exists
only to prove the port is faithful.

## How it was verified

- **Byte-identical port.** Twenty reference outputs from the original running in a
  Python 2.7 / Ubuntu 18.04 container were compared with the port in compatibility
  mode. `.cmx` files match by whole-file SHA-256 and `.cdr` files by decompressed
  stream. Fixtures that crash the original must also crash the port, and a run that
  compares nothing counts as a failure.
- **Pure-Python cairo.** The part of cairo the writer relies on (fixed-point
  conversion, incremental extents, spline bounds, path copying) was reimplemented
  and matched against libcairo 1.15.10 with zero differences.
- **Gates on fixed output, both widths.** An independent decoder, which imports nothing
  from the writer, compares every written point, node type, pen, colour, dash and
  bounding box against the source geometry. It also checks the unit, index tables,
  instruction nesting, instruction size (≤ 32767 bytes, the limit libcdr actually
  enforces) and determinism across processes. For 32-bit output it also checks every
  tag list, the end offsets and instruction counts of pages and groups, and the
  32-bit table layouts. 71 16-bit and 64 32-bit self-test cases, mostly deliberately
  corrupted files, prove each check fires. Adversarial inputs cover empty documents, degenerate strokes, dash
  edge cases, gradients, huge artwork and compound fills with hundreds of holes.
- **Mutation testing.** Reverting any single fix, or breaking any part of the 32-bit
  layout, must make the gates fail: 73 of 74 mutations are caught. The remaining one is
  unreachable by construction.
- **Real readers.** Fixed 16-bit output was opened in CorelDRAW and its objects inspected:
  sizes (80×30 mm → 79.98×30.00 mm), outline widths (1–20 mm within 0.01 mm), colours,
  positions, Chinese text converted to curves, and 7 pt type on an A3 page. 32-bit output
  imports with editable dashed outlines and exact sizes. Both were read back through
  libcdr (LibreOffice) to SVG and PNG with correct page size.

The verification tooling (decoder, gates, fixtures, the Python 2 reference container)
lives in SharkFoto's internal repository and is not part of this package.

## Limits

- `<text>`: convert text to paths first (for example
  `inkscape --export-text-to-path --export-plain-svg`).
- `<image>`: raster images are rejected.
- Gradients are written as the gradient's mean colour. Opacity is ignored.
- Dash lengths are rounded to whole multiples of the line width. In 16-bit output
  (`--cmx16`), CorelDRAW imports dashed outlines as grouped filled shapes.
- Clipping paths and masks are removed by `svgprep`, so clipped content shows in full.
- Stroke-only paths and independent shapes are split into instructions of at most
  32767 bytes. An outline together with its holes cannot be split without filling the
  holes, so when it is longer it is written as one instruction with an extended length
  field. A single curve is limited by the format to 7281 points in 32-bit CMX and 65535
  points in 16-bit CMX; a filled compound path beyond that is rejected with exit code 2.
- Page size is not written. Only little-endian output is supported.
- Stroke widths with explicit units (mm, cm, in) follow UniConvertor's 90 dpi
  convention, which is 6.25% off browsers' 96 dpi. Unitless widths are exact.

## License

GNU Affero General Public License v3 or later. See [`LICENSE`](LICENSE).
[`NOTICE`](NOTICE) records provenance: the upstream revision, what was removed, and
what was changed.

If you run a modified version as a network service, AGPL section 13 requires you to
offer its source to the service's users.
