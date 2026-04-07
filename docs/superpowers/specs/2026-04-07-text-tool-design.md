# Text Tool — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Problem

RetroSprite has no way to add text to the canvas. Both Aseprite and Pixelorama offer text tools. This is a standalone feature gap.

## Goals

- Render text onto the pixel canvas using built-in bitmap pixel fonts or user-loaded TTF fonts
- Floating text overlay with live preview, repositioning, and inline editing
- Integration with existing selection transform system for rotate/scale/skew
- Options bar with font, size, spacing, line height, and alignment controls

## User Decisions

| Decision | Choice |
|----------|--------|
| Font rendering | Built-in bitmap fonts + optional TTF loading |
| Built-in fonts | Tiny (3x5) and Standard (5x7) |
| TTF loading | "Load Font..." file picker, session-scoped |
| Entry workflow | Floating overlay with inline typing on canvas |
| Multiline | Enter = newline, Ctrl+Enter or Apply = commit |
| Transform | Ctrl+T enters SelectionTransform mode on the text image |
| Options | Font, Size (TTF only), Spacing, Line Height, Align (L/C/R) |

---

## Workflow

### Text Entry

1. User selects Text tool from toolbar
2. Clicks on canvas → blinking cursor appears at click position
3. Types text → each keystroke re-renders the floating text overlay
4. Can drag the floating text to reposition
5. Options bar shows font/size/spacing/line-height/align controls
6. Enter inserts a newline; Ctrl+Enter or Apply button commits
7. Esc cancels and discards the text
8. Switching tools auto-commits the text

### Transform Integration

1. While text is floating, user presses Ctrl+T
2. Current rendered text image becomes a `SelectionTransform` with `source="paste"`
3. Full rotate/scale/skew handles appear (reuses existing transform system)
4. Text editing ends — cannot modify text string after entering transform
5. Enter commits transformed text to layer, Esc cancels

### Commit & Cancel

- **Commit** (Ctrl+Enter, Apply button, tool switch): stamp text pixels onto active layer at current position, push undo, clear text state. Clicking on canvas while in text mode commits current text and starts a new text at the clicked position.
- **Cancel** (Esc): discard text entirely, clear text state. If text string is empty, exit text mode silently.

---

## Built-in Bitmap Fonts

### Storage Format

Fonts stored as Python dicts in `src/bitmap_fonts.py`. Each font is a dict mapping characters to pixel patterns:

```python
FONT_TINY = {
    "name": "Tiny 3x5",
    "char_width": 3,
    "char_height": 5,
    "glyphs": {
        "A": [0b010, 0b101, 0b111, 0b101, 0b101],
        "B": [0b110, 0b101, 0b110, 0b101, 0b110],
        # ... ASCII 32-126
    }
}
```

Each glyph is a list of row integers where set bits represent opaque pixels. Row 0 is the top. Bit order: MSB = leftmost pixel.

### Included Fonts

| Font | Dimensions | Use Case |
|------|-----------|----------|
| Tiny 3x5 | 3px wide, 5px tall | HUD labels, tiny annotations |
| Standard 5x7 | 5px wide, 7px tall | General-purpose readable text |

Both cover ASCII printable range (characters 32-126): letters, digits, punctuation, symbols.

---

## TTF Font Support

- Font dropdown lists: "Tiny (3x5)", "Standard (5x7)", then a separator, then "Load Font..."
- "Load Font..." opens a file picker filtered to `.ttf` and `.otf`
- Loaded font is added to the dropdown for the current session
- TTF rendering uses `PIL.ImageFont.truetype(path, size)` and `PIL.ImageDraw.text()`
- Rendered in current palette color onto an RGBA image
- Size spinner only enabled when a TTF font is selected

---

## Rendering Pipeline

### `src/bitmap_fonts.py`

```python
def render_text(text: str, font: dict, color: tuple,
                spacing: int = 1, line_height: int = 2,
                align: str = "left") -> Image.Image
```

Renders a text string using a bitmap font dict. Returns an RGBA `PIL.Image`.

- For each character, looks up glyph in font dict
- Stamps pixels in `color` where bits are set
- `spacing`: extra pixels between characters (default 1)
- `line_height`: extra pixels between lines for multiline (default 2)
- `align`: "left", "center", or "right" for multiline text
- Unknown characters render as a filled rectangle (missing glyph indicator)

```python
def render_text_ttf(text: str, font_path: str, size: int, color: tuple,
                    spacing: int = 0, line_height: int = 0,
                    align: str = "left") -> Image.Image
```

Renders text using a TTF font via Pillow. Returns an RGBA `PIL.Image`.

---

## Options Bar

When the Text tool is active, the options bar shows:

```
Text | Font: [Standard 5x7 ▼] | Size: [12] | Spacing: [1] | Line H: [2] | Align: [L|C|R] | [Apply] [Cancel]
```

| Control | Type | Default | Notes |
|---------|------|---------|-------|
| Font | Dropdown | "Standard 5x7" | Built-in fonts + "Load Font..." |
| Size | Spinbox (4-128) | 12 | Only enabled for TTF fonts |
| Spacing | Spinbox (0-10) | 1 | Extra pixels between characters |
| Line H | Spinbox (0-20) | 2 | Extra pixels between lines |
| Align | 3-button toggle (L/C/R) | Left | For multiline text |
| Apply | Button | — | Commits text to layer |
| Cancel | Button | — | Discards text |

---

## Data Model

### App State (in `src/app.py`)

```python
self._text_mode = False           # True when text tool is active and typing
self._text_string = ""            # Current text being typed
self._text_pos = (0, 0)           # Canvas position of text origin
self._text_cursor_pos = 0         # Character index of cursor in text string
self._text_cursor_visible = True  # Blink state
self._text_cursor_after_id = None # Tkinter after() ID for blink timer
self._text_loaded_fonts = {}      # {display_name: font_path} for loaded TTFs
```

---

## Cursor Blinking

While in text mode:
- A 1-pixel-wide vertical line drawn at the cursor position in the floating overlay
- Toggles visibility every 500ms using `root.after()`
- Cursor position tracks with typed characters
- Cleared when text mode exits

---

## Key Handling

When `_text_mode` is True, keyboard input is intercepted:

| Key | Action |
|-----|--------|
| Printable characters | Insert at cursor position, re-render |
| Backspace | Delete character before cursor, re-render |
| Delete | Delete character after cursor, re-render |
| Left/Right arrows | Move cursor position |
| Home/End | Move cursor to start/end of line |
| Enter | Insert newline character |
| Ctrl+Enter | Commit text to layer |
| Ctrl+T | Enter selection transform mode with text image |
| Esc | Cancel text, discard |
| Ctrl+A | Select all text (for future use) |

---

## Functions

### `src/bitmap_fonts.py`

```python
def render_text(text: str, font: dict, color: tuple,
                spacing: int = 1, line_height: int = 2,
                align: str = "left") -> Image.Image
```
Render text string using built-in bitmap font. Returns RGBA PIL Image.

```python
def render_text_ttf(text: str, font_path: str, size: int, color: tuple,
                    spacing: int = 0, line_height: int = 0,
                    align: str = "left") -> Image.Image
```
Render text string using TTF font via Pillow. Returns RGBA PIL Image.

```python
def get_cursor_x(text: str, cursor_pos: int, font: dict, spacing: int) -> int
```
Calculate the pixel X offset of the cursor at a given character index.

### `src/tools.py`

```python
class TextTool:
    def apply(self, grid: PixelGrid, image: Image.Image, x: int, y: int) -> None
```
Stamp a rendered text image onto the grid at position (x, y). Uses `PixelGrid.paste_rgba_array()`.

---

## Files Changed/Created

| File | Action | Purpose |
|------|--------|---------|
| `src/bitmap_fonts.py` | **New** | Font data dicts (Tiny 3x5, Standard 5x7), `render_text()`, `render_text_ttf()`, `get_cursor_x()` |
| `src/tools.py` | **Modify** | Add `TextTool` class |
| `src/input_handler.py` | **Modify** | Text mode: click entry, keystroke handling, drag to reposition, commit/cancel, Ctrl+T handoff |
| `src/canvas.py` | **Modify** | Cursor blink overlay drawing |
| `src/app.py` | **Modify** | Text state vars, tool registration, key event routing, cursor blink timer |
| `src/ui/options_bar.py` | **Modify** | Text tool options (font dropdown, size, spacing, line height, align) |
| `src/ui/icons.py` | **Modify** | Add "text" icon mapping |
| `src/tool_settings.py` | **Modify** | Text tool defaults |
| `tests/test_bitmap_fonts.py` | **New** | Bitmap font rendering, TTF rendering, cursor position, multiline, alignment |

## Dependencies

No new dependencies. Uses:
- Pillow `ImageFont.truetype()` for TTF rendering (already a dependency)
- Pillow `ImageDraw` for TTF text drawing (already used)
- Existing `SelectionTransform` system for Ctrl+T integration
- Existing `PixelGrid.paste_rgba_array()` for committing text

## Testing

### `tests/test_bitmap_fonts.py`

- `test_render_single_char` — renders "A" with bitmap font, verify dimensions match font size
- `test_render_string` — renders "Hello", verify width = 5 chars * (char_width + spacing) - spacing
- `test_render_multiline` — renders "Hi\nLo", verify height = 2 * char_height + line_height
- `test_render_empty_string` — returns 1x1 transparent image
- `test_unknown_char_fallback` — unknown char renders as filled rect
- `test_spacing_affects_width` — spacing=0 vs spacing=2 changes output width
- `test_alignment_center` — multiline centered text has correct offsets
- `test_alignment_right` — multiline right-aligned text has correct offsets
- `test_cursor_x_at_start` — cursor pos 0 returns x=0
- `test_cursor_x_at_end` — cursor at len(text) returns correct x
- `test_render_ttf_basic` — renders text with a TTF font, produces non-empty RGBA image
- `test_color_applied` — rendered pixels use the specified color
- `test_text_tool_apply` — TextTool.apply() stamps image onto grid correctly
