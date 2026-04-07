# Build Pipeline & Versioning — Design Spec

**Date:** 2026-04-03
**Scope:** Single version source, CI tests on PRs, automated build+release on tag push

---

## 1. Single Version Source

`src/__init__.py` becomes the single source of truth for the app version:

```python
__version__ = "1.0.0"
```

All other version references read from this:
- **PyInstaller spec** reads `__version__` at build time to embed in exe metadata
- **installer.iss** receives version via `/D` flag from the release Action
- **CLI** `python -m src.cli --version` prints it
- **App title** can optionally display it

Version follows **Semantic Versioning**: `MAJOR.MINOR.PATCH`

---

## 2. GitHub Actions Pipelines

### `ci.yml` — Test on PR

**Trigger:** Pull request to `main`

Steps:
1. Checkout code
2. Set up Python 3.10
3. Install dependencies from `requirements.txt`
4. Run `python -m pytest tests/ -x -q`

### `release.yml` — Build + Release on tag push

**Trigger:** Tag push matching `v*`

Steps:
1. Checkout code
2. Set up Python 3.10
3. Install dependencies + PyInstaller
4. Extract version from tag (strip `v` prefix)
5. Verify `src/__init__.py` version matches the tag (fail-fast if mismatch)
6. Run tests (safety check)
7. Build with PyInstaller (`RetroSprite.spec`)
8. Zip `dist/RetroSprite/` folder → `RetroSprite_Portable.zip`
9. Install Inno Setup via `jrsoftware/iscc` GitHub Action
10. Compile `installer.iss` with version injected via `/DMyAppVersion=X.Y.Z`
11. Create GitHub Release with both artifacts, using tag name as release title

**Artifacts published to GitHub Release:**
- `RetroSprite_Portable.zip` — portable distribution (no install needed)
- `RetroSprite_Setup.exe` — Inno Setup installer with Start Menu + desktop shortcut

### Developer Release Process

1. Update `__version__` in `src/__init__.py`
2. Update `CHANGELOG.md` with new section
3. Commit, push to `main`
4. `git tag v1.1.0 && git push origin v1.1.0`
5. GitHub Actions builds and publishes the release automatically

---

## 3. File Changes

| File | Change |
|------|--------|
| `src/__init__.py` | **Modify** — add `__version__ = "1.0.0"` |
| `.github/workflows/ci.yml` | **New** — test on PR to main |
| `.github/workflows/release.yml` | **New** — build + release on tag push |
| `RetroSprite.spec` | **Modify** — read version from `src/__init__.py`, embed in exe version info |
| `installer.iss` | **Modify** — use `{#MyAppVersion}` from `/D` flag instead of hardcoded `"1.0"` |
| `requirements.txt` | **Modify** — remove `tkinterweb` (unused after video removal) |

No changes to app.py, mixins, or any application logic. No new Python dependencies.
