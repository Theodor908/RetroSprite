# Publish-Readiness Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix LICENSE, README, .gitignore, and CI workflow so the repo is ready to publish.

**Architecture:** Four independent file edits — no code logic changes, only config/metadata. Each task is one file.

**Tech Stack:** GitHub Actions, GPL-3.0-or-later, PyInstaller spec

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `LICENSE` | Modify | Prepend copyright header with "or later" language |
| `README.md` | Modify (lines 61, 142-148) | Update Python version + license wording |
| `.gitignore` | Modify (lines 17, 48) | Remove `*.spec` exclusions |
| `.github/workflows/ci.yml` | Modify | Add push trigger + Python matrix |

---

### Task 1: Update LICENSE with copyright header

**Files:**
- Modify: `LICENSE:1` (prepend before existing line 1)

- [ ] **Step 1: Prepend copyright header to LICENSE**

Add this block before the existing `GNU GENERAL PUBLIC LICENSE` line. There must be a blank line separating the header from the GPL body text.

```
RetroSprite — A pixel art editor and animation tool
Copyright (C) 2026 Vasile Theodor Gabriel

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.

```

The existing full GPL-3.0 text (starting with `GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007`) remains unchanged below.

- [ ] **Step 2: Verify the file**

Run: `head -20 LICENSE`
Expected: The copyright header followed by the start of the GPL text.

---

### Task 2: Update README license section and Python version

**Files:**
- Modify: `README.md:61` (Python version)
- Modify: `README.md:142-148` (license section)

- [ ] **Step 1: Update Python minimum version**

Change line 61 from:
```
- Python 3.8+
```
To:
```
- Python 3.10+
```

- [ ] **Step 2: Update license section**

Replace lines 142-148 from:
```markdown
## License

Copyright (c) 2026 Vasile Theodor Gabriel

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

This means you are free to use, modify, and distribute this software, but any derivative work must also be released under the GPL-3.0 license.
```

To:
```markdown
## License

Copyright (c) 2026 Vasile Theodor Gabriel

This project is licensed under the **GNU General Public License v3.0 or later** — see the [LICENSE](LICENSE) file for details.

This means you are free to use, modify, and distribute this software, but any derivative work must also be released under the GPL-3.0 (or a later version).
```

- [ ] **Step 3: Verify changes**

Run: `grep -n "3.10" README.md && grep -n "or later" README.md`
Expected: Line 61 shows `Python 3.10+`, license section shows `or later`.

---

### Task 3: Remove *.spec from .gitignore

**Files:**
- Modify: `.gitignore:17,48` (remove two lines)

- [ ] **Step 1: Remove both `*.spec` lines**

The file has `*.spec` on line 17 (under `# PyInstaller`) and line 48 (at the end). Remove both lines.

After the edit, the `# PyInstaller` comment block should be empty — remove the comment too since it has no entries under it.

Before (lines 15-18):
```
# PyInstaller
*.spec
```

After:
```
```
(Both the comment and the `*.spec` line are removed.)

Also remove the standalone `*.spec` on line 48.

- [ ] **Step 2: Verify RetroSprite.spec is no longer ignored**

Run: `git check-ignore RetroSprite.spec; echo "exit: $?"`
Expected: exit code 1 (not ignored). If exit code 0, the file is still ignored.

---

### Task 4: Improve CI workflow

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Replace the full CI workflow**

Replace the entire contents of `.github/workflows/ci.yml` with:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run tests
        run: python -m pytest tests/ -x -q
```

- [ ] **Step 2: Verify YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: No error (exits cleanly). If `yaml` module is unavailable, visual inspection is sufficient.

---

### Task 5: Final verification

- [ ] **Step 1: Run the test suite to confirm nothing broke**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass (these are metadata-only changes, so no test regressions expected).

- [ ] **Step 2: Verify git status shows all 4 files modified**

Run: `git diff --name-only`
Expected output:
```
.github/workflows/ci.yml
.gitignore
LICENSE
README.md
```
