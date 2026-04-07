# Contributing to RetroSprite

## Quick Start

```bash
git clone https://github.com/Theodor908/RetroSprite.git
cd RetroSprite
pip install -r requirements.txt
python -m pytest tests/
python main.py
```

**Requirements:** Python 3.10+, NumPy, Pillow, imageio, pytest.

## Project Structure

```text
RetroSprite/
|- main.py                  # Desktop entry point
|- src/                     # Application logic, tools, effects, import/export, UI
|- tests/                   # pytest suite
|- docs/                    # Architecture, standards, planning documents
|- requirements.txt         # Runtime and test dependencies
`- RetroSprite.spec         # Build configuration for PyInstaller
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full module map and data flow.

## Code Style

- Follow PEP 8 with a 100-character line limit.
- Add type hints on function signatures.
- Add docstrings for public classes and non-obvious methods.
- Use `snake_case` for functions and variables, `PascalCase` for classes, and `UPPER_CASE` for module-level constants.
- Keep imports grouped as stdlib, third-party, then local.
- Tool dictionary keys stay capitalized: `"Pen"`, `"Eraser"`, `"Wand"`, `"Lasso"`.

See [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md) for the detailed conventions.

## Where Code Goes

| What you're adding | Where it goes |
|--------------------|---------------|
| New drawing tool | `src/tools.py`, `src/input_handler.py`, `src/app.py` |
| New layer effect | `src/effects.py`, `src/ui/effects_dialog.py` |
| New export format | `src/export.py` or `src/animated_export.py` |
| New UI widget | `src/ui/` |
| New image filter | `src/image_processing.py` |
| New palette format | `src/palette_io.py` |

## Rules

- Never add methods directly to `src/app.py` when a dedicated module or mixin fits the change.
- Never access `grid._pixels` directly in new code; use `get_pixel()`, `set_pixel()`, `copy()`, or `to_pil_image()`.
- Keep tools stateless; they should operate on `PixelGrid`, not on `Layer` or `Frame`.
- Use shared theme colors from `src/ui/theme.py`.
- Use NumPy for pixel operations instead of Python loops over pixels.

## Testing

```bash
python -m pytest tests/
python -m pytest tests/test_tools.py
python -m pytest -x
```

- All new features require tests.
- Test files should mirror source ownership where practical.
- Prefer testing tool logic independently from the UI.
- Use `PixelGrid` directly in tests unless UI behavior is the thing being validated.

## Branching and Pull Requests

1. Branch from `main`.
2. Use a descriptive branch name such as `feature/spray-tool` or `fix/fill-tolerance`.
3. Keep each pull request focused on one feature or one fix.
4. Run the full test suite before opening the pull request.
5. Include tests for new behavior and note any known gaps clearly in the PR description.

## Reporting Issues

- Include clear reproduction steps.
- Note the canvas size, active tool, and active mode.
- Attach screenshots or short recordings for visual defects when possible.
