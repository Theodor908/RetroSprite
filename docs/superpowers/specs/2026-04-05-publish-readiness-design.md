# Publish-Readiness Fixes — Design Spec

**Date:** 2026-04-05
**Scope:** 4 files, no logic changes — config/metadata only

## Context

RetroSprite needs these fixes before the repo is ready to publish:
- LICENSE file lacks copyright header and GPL version ambiguity
- README says "GPL-3.0" without specifying "only" vs "or later"
- `.gitignore` excludes `*.spec`, preventing cloners from building
- CI only tests one Python version and doesn't run on push to main

## Fix 1 — LICENSE File

Prepend a project-specific copyright header before the standard GPL-3.0 body text, per FSF guidance:

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

The existing full GPL-3.0 text below remains unchanged. The "or (at your option) any later version" language makes this explicitly GPL-3.0-or-later.

## Fix 2 — README License Section

Replace the license section to say **GNU General Public License v3.0 or later** explicitly, matching the LICENSE header. Also update "Python 3.8+" to "Python 3.10+" in the requirements section.

## Fix 3 — .gitignore

Remove `*.spec` lines so `RetroSprite.spec` is tracked. This file is required for `pyinstaller` builds and must be available to anyone who clones the repo.

## Fix 4 — CI Workflow

- Add `push:` trigger on `main` alongside existing `pull_request:`
- Add a strategy matrix for Python `["3.10", "3.12"]`
- Keep everything else the same (ubuntu-latest, pytest)

## Files Changed

| File | Change |
|------|--------|
| `LICENSE` | Prepend copyright + "or later" header |
| `README.md` | Update license wording + Python version |
| `.gitignore` | Remove `*.spec` lines |
| `.github/workflows/ci.yml` | Add push trigger + Python matrix |

## Decisions Made

- **GPL-3.0-or-later** (not "only") — user choice
- **Python 3.10+ minimum** — drops EOL 3.8/3.9, matches current CI
- **No linting or caching in CI** — YAGNI, can add later
- **Remove `*.spec` entirely from .gitignore** — only one spec file exists
