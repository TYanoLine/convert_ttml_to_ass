# Copilot instructions for `convert_ttml`

## Build, test, and lint commands

This repository is a single-file Python converter with no configured build system, test runner, or linter.

- Run the converter:
  - `python convert_ttml.py`
  - `python convert_ttml.py 0:00:00.00 sample.ttml output.ass`
- Syntax check:
  - `python -m py_compile convert_ttml.py`
- Manual end-to-end check with the sample TTML:
  - `python convert_ttml.py 0:00:00.00 sample.ttml sample_test.ass`

There is no single-test command because there is no automated test suite in this repository.

## High-level architecture

All application logic lives in `convert_ttml.py`.

The conversion pipeline is:

1. Parse TTML with `xml.etree.ElementTree` using the namespace map in `convert_ttml_to_ass()`.
2. Collect TTML style metadata:
   - `collect_ruby_styles()` finds which style IDs represent ruby containers, ruby base text, and ruby text.
   - `collect_style_definitions()` and `resolve_font_style()` resolve inherited `tts:fontStyle` values.
3. Flatten each `<p>` element into a sequence of parts with `get_all_parts()`:
   - `("text", text)`
   - `("ruby", (base, ruby))`
   - `("br", None)`
4. Split parts into visual lines with `split_lines()`.
5. Render one of three ASS output modes:
   - `render_standard_dialogue()` for plain horizontal subtitles
   - `render_positioned_ruby_dialogues()` for horizontal subtitles with ruby annotations
   - `render_positioned_vertical_dialogues()` for right-side vertical subtitles
6. Write the final ASS script with a fixed header and event list.

Text measurement is Windows-specific. `TextMeasurer` uses GDI through `ctypes.windll.gdi32` to measure base-text widths so ruby can be positioned accurately.

## Key conventions

### TTML namespace handling is mandatory

Do not query XML tags or attributes as plain names. Follow the existing namespace-aware pattern:

- Elements are queried with paths like `.//tt:p`
- Namespaced attributes use `f"{{{XML_NS}}}id"` and `f"{{{TTS_NS}}}fontStyle"`

If you add new TTML parsing logic, thread the same `ns` map through it.

### Keep style resolution data-driven

Italic handling should come from TTML `tts:fontStyle`, not hardcoded style IDs. Reuse:

- `collect_style_definitions()`
- `resolve_font_style()`
- `is_italic_element()`

When adding other style-dependent behavior, follow the same pattern and respect inherited TTML styles.

### Ruby parsing depends on style roles, not tag names alone

Ruby is detected by style IDs collected from TTML style definitions. Preserve this flow:

- detect ruby container/base/text styles first
- then walk descendants to extract `(base, ruby)` pairs

Avoid introducing ruby parsing that assumes a fixed nested shape without consulting the style-role helpers.

### Vertical text is rendered character-by-character

Vertical subtitles are not emitted as one ASS line. The converter:

- substitutes some punctuation with vertical glyph variants via `VERTICAL_CHAR_MAP`
- rotates selected characters with `\frz90`
- applies per-character offsets with `VERTICAL_CHAR_OFFSET_MAP`
- emits each visible character as its own positioned ASS dialogue event

If you adjust vertical layout, keep glyph substitution, rotation, and offsets in sync.

### Horizontal ruby layout depends on measured base text width

Ruby placement is centered over the measured width of the base text. If you change font sizes, margins, or line spacing, verify:

- base line centering
- ruby top position
- multi-line stacking

The constants near the top of `convert_ttml.py` define the layout contract for both horizontal and vertical rendering.

### ASS output must stay escaped and explicit

Use `escape_ass_text()` before writing visible text into ASS events. Preserve current escaping rules for:

- `\`
- `{`
- `}`

Line breaks must stay as `\N` in ASS output.

### This repository is validated by manual conversion

There is no automated test harness. The normal validation flow is:

1. run `python -m py_compile convert_ttml.py`
2. run the converter on `sample.ttml`
3. inspect the generated ASS output, especially horizontal text, ruby placement, and vertical lines

Do not add unrelated tooling unless the task explicitly calls for it.
