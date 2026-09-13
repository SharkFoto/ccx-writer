# ccx-writer

Write **CorelDRAW CMX / CCX** files from SVG, in pure Python 3.

`ccx-writer` is a Python 3 port of the CMX writer from
[UniConvertor 2.0](https://github.com/sk1project/uniconvertor) (sK1 Project,
revision `973d5b6`), which only ever ran on Python 2 and is no longer maintained.
On top of a byte-exact port it fixes the precision and robustness defects that made
the original output unusable for real artwork.

No native dependencies: the original needed pycairo, lcms, ImageMagick and pango;
this package needs nothing outside the standard library.

> Source comments are written in Chinese. Each fix is annotated at the exact place
> where the original went wrong, with the reason for the change.

## Install

```bash
pip install https://github.com/SharkFoto/ccx-writer/archive/refs/tags/v0.1.0.tar.gz
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
```

### Which container to write

| Output | CorelDRAW | libcdr (Inkscape, LibreOffice) |
|---|---|---|
| Uncompressed CMX v1 (`--no-pack`) | opens; objects are editable curves | reads it |
| Packed CCX (`--pack`) | opens; same result | **cannot read it** |

CorelDRAW detects the format from the content, not the extension, so uncompressed
CMX saved as `.cdr` opens as a drawing. Use `--no-pack` unless you know the reader
handles CDRX.

## What the fixes change

The original writer had a 72× resolution loss: every coordinate was scaled into
±451 units out of a ±32767 range. On an A3 page that is a 0.46 mm grid, enough to
break 7 pt type into visible steps.

Fixed output uses 1/1000 inch per unit (0.0254 mm), the native unit of 16-bit CMX.
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
- **Gates on fixed output.** An independent decoder, which imports nothing from the
  writer, compares every written point, node type, pen, colour, dash and bounding
  box against the source geometry. It also checks the unit, index tables, instruction
  nesting, instruction size (≤ 32767 bytes, the limit libcdr actually enforces) and
  determinism across processes. 65 deliberately corrupted files prove each check
  fires. Adversarial inputs cover empty documents, degenerate strokes, dash edge
  cases, gradients, huge artwork and compound fills with hundreds of holes.
- **Mutation testing.** Reverting any single fix must make the gates fail. 23 of 24
  reverted fixes are caught; the remaining one is unreachable by construction.

The verification tooling (decoder, gates, fixtures, the Python 2 reference container)
lives in SharkFoto's internal repository and is not part of this package.
- **Real readers.** CorelDRAW opens the original writer's output (identical to
  compatibility mode) both uncompressed and packed, with the same result. The gates
  replay libcdr's own instruction-length parsing. Opening *fixed* output in CorelDRAW
  has not been checked for this release yet.

## Limits

- `<text>`: convert text to paths first (for example
  `inkscape --export-text-to-path --export-plain-svg`).
- `<image>`: raster images are rejected.
- Gradients are written as the gradient's mean colour. Opacity is ignored.
- Clipping paths and masks are removed by `svgprep`, so clipped content shows in full.
- A single filled compound path whose outline and holes exceed 6540 points cannot be
  split without filling the holes, so it is rejected with exit code 2. Stroke-only
  paths and independent shapes are split automatically.
- Page size is not written. Only little-endian output is supported.
- Stroke widths with explicit units (mm, cm, in) follow UniConvertor's 90 dpi
  convention, which is 6.25% off browsers' 96 dpi. Unitless widths are exact.

## License

GNU Affero General Public License v3 or later. See [`LICENSE`](LICENSE).
[`NOTICE`](NOTICE) records provenance: the upstream revision, what was removed, and
what was changed.

If you run a modified version as a network service, AGPL section 13 requires you to
offer its source to the service's users.
