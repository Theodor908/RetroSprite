# Build Pipeline & Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up single-source versioning, CI tests on PRs, and automated build+release on tag push via GitHub Actions.

**Architecture:** `src/__init__.py` holds `__version__`. Two GitHub Actions workflows: `ci.yml` (test on PR) and `release.yml` (build+release on tag). PyInstaller spec reads version from source. Inno Setup receives version via `/D` flag.

**Tech Stack:** Python 3.10, GitHub Actions, PyInstaller, Inno Setup 6

---

### Task 1: Add `__version__` to `src/__init__.py`

**Files:**
- Modify: `src/__init__.py`

- [ ] **Step 1: Add version string**

`src/__init__.py` is currently empty. Add:

```python
"""RetroSprite — Pixel Art Creator & Animator."""

__version__ = "1.0.0"
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from src import __version__; print(__version__)"`
Expected: `1.0.0`

- [ ] **Step 3: Add `--version` flag to CLI**

In `src/cli.py`, in the `build_parser` function, add the version argument after the parser is created (after line 14, before the subparsers):

```python
    from src import __version__
    parser.add_argument("--version", action="version",
                        version=f"RetroSprite {__version__}")
```

- [ ] **Step 4: Verify CLI version**

Run: `python -m src.cli --version`
Expected: `RetroSprite 1.0.0`

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

---

### Task 2: Update PyInstaller spec to read version

**Files:**
- Modify: `RetroSprite.spec`

- [ ] **Step 1: Add version reading to spec**

At the top of `RetroSprite.spec`, before the `Analysis` call, add version extraction:

```python
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for RetroSprite."""
import re

# Read version from source
with open('src/__init__.py', 'r') as f:
    _version_match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", f.read())
    VERSION = _version_match.group(1) if _version_match else '0.0.0'
```

- [ ] **Step 2: Add version_info to EXE**

Replace the existing `exe = EXE(...)` block with one that includes version metadata. The full EXE block should be:

```python
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RetroSprite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='assets/icon.ico',
)
```

Note: PyInstaller's `version` parameter requires a separate version resource file which adds complexity. The version is better embedded via the Inno Setup installer and the `--version` CLI flag. Keep the spec simple — just read the version for potential future use but don't add a version resource file.

- [ ] **Step 3: Verify build still works**

Run: `python -m PyInstaller RetroSprite.spec --noconfirm 2>&1 | tail -5`
Expected: `Building COLLECT COLLECT-00.toc completed successfully.`

---

### Task 3: Update installer.iss for dynamic version

**Files:**
- Modify: `installer.iss`

- [ ] **Step 1: Update version define**

The `installer.iss` currently has a hardcoded version on line 6. Change:

```ini
#define MyAppVersion "1.0"
```

to:

```ini
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
```

This allows the GitHub Action to pass `/DMyAppVersion=1.2.0` to override the default, while keeping a working default for local builds.

- [ ] **Step 2: Update publisher URL**

Line 9 currently has a placeholder URL. Change:

```ini
#define MyAppURL "https://github.com/retrosprite"
```

to:

```ini
#define MyAppURL "https://github.com/Theodor908/RetroSprite"
```

---

### Task 4: Clean up requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Remove tkinterweb**

`tkinterweb` was only used for the intro video embed which was removed. Remove line 6:

```
tkinterweb>=3.24
```

The file should become:

```
Pillow>=9.0
numpy>=1.24
imageio>=2.20
pytest>=7.0
psd-tools>=1.9
```

- [ ] **Step 2: Verify install still works**

Run: `pip install -r requirements.txt`
Expected: All requirements satisfied

---

### Task 5: Create CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create directory**

Run: `mkdir -p .github/workflows`

- [ ] **Step 2: Create ci.yml**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run tests
        run: python -m pytest tests/ -x -q
```

---

### Task 6: Create release workflow

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Create release.yml**

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  release:
    runs-on: windows-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Extract version from tag
        id: version
        shell: bash
        run: |
          TAG="${GITHUB_REF#refs/tags/v}"
          echo "version=$TAG" >> "$GITHUB_OUTPUT"

      - name: Verify version matches source
        shell: bash
        run: |
          SOURCE_VER=$(python -c "import re; print(re.search(r\"__version__\s*=\s*['\\\"]([^'\\\"]+)['\\\"]\", open('src/__init__.py').read()).group(1))")
          TAG_VER="${{ steps.version.outputs.version }}"
          if [ "$SOURCE_VER" != "$TAG_VER" ]; then
            echo "ERROR: Tag version ($TAG_VER) does not match src/__init__.py ($SOURCE_VER)"
            exit 1
          fi
          echo "Version verified: $SOURCE_VER"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Run tests
        run: python -m pytest tests/ -x -q

      - name: Build with PyInstaller
        run: python -m PyInstaller RetroSprite.spec --noconfirm

      - name: Create portable zip
        shell: pwsh
        run: Compress-Archive -Path dist\RetroSprite\* -DestinationPath RetroSprite_Portable.zip

      - name: Install Inno Setup
        shell: pwsh
        run: |
          choco install innosetup --yes --no-progress
          echo "C:\Program Files (x86)\Inno Setup 6" | Out-File -Append -Encoding utf8 $env:GITHUB_PATH

      - name: Build installer
        run: iscc /DMyAppVersion=${{ steps.version.outputs.version }} installer.iss

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          name: RetroSprite v${{ steps.version.outputs.version }}
          generate_release_notes: true
          files: |
            RetroSprite_Portable.zip
            installer_output/RetroSprite_Setup.exe
```

---

### Task 7: Final verification

**Files:**
- Verify: all changed files

- [ ] **Step 1: Verify version source works**

Run: `python -c "from src import __version__; print(__version__)"`
Expected: `1.0.0`

- [ ] **Step 2: Verify CLI version**

Run: `python -m src.cli --version`
Expected: `RetroSprite 1.0.0`

- [ ] **Step 3: Verify build works**

Run: `python -m PyInstaller RetroSprite.spec --noconfirm 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 5: Verify workflow YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); yaml.safe_load(open('.github/workflows/release.yml')); print('YAML valid')"`
Expected: `YAML valid` (requires PyYAML — if not available, skip)

- [ ] **Step 6: Review file checklist**

Confirm all files exist and are correct:
- `src/__init__.py` has `__version__ = "1.0.0"`
- `src/cli.py` has `--version` argument
- `RetroSprite.spec` reads version from source
- `installer.iss` uses `#ifndef` for dynamic version
- `requirements.txt` no longer has `tkinterweb`
- `.github/workflows/ci.yml` exists
- `.github/workflows/release.yml` exists
