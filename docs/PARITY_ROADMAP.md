# RetroSprite — Competitive Parity Roadmap

Tracked features to close gaps with Aseprite and Pixelorama.

## Completed

- [x] **Import/Export Parity** — GIF, APNG, WebP, PNG sequence, sprite sheet import (2026-04-06)
  - Spec: `docs/superpowers/specs/2026-04-06-import-parity-design.md`
  - Plan: `docs/superpowers/plans/2026-04-06-import-parity.md`

- [x] **Grid System Overhaul** — Dual grid (pixel + custom NxM), toggle, RGBA color, per-project persistence (2026-04-07)
  - Spec: `docs/superpowers/specs/2026-04-07-grid-system-design.md`
  - Plan: `docs/superpowers/plans/2026-04-07-grid-system.md`

## In Progress

- [ ] **Selection Rotation/Scale/Skew** — Full affine transform on floating selections with Photoshop-style handles
  - Spec: `docs/superpowers/specs/2026-04-07-selection-transform-design.md` (approved, ready for plan)
  - Needs: implementation plan + execution

## Planned (not yet specced)

- [ ] **Text Tool** — Both Aseprite and Pixelorama have it. Standalone feature.
- [ ] **Movable Symmetry Axis** — Current axis is locked to canvas center. Small enhancement.
- [ ] **Pressure Sensitivity** — Tablet support for brush size/opacity. Important for tablet users.
- [ ] **Isometric/Hex Tilemaps** — Pixelorama supports iso + hex tilemap layers. Extends existing tilemap system.

## Competitive Comparison Reference

| Feature | RetroSprite | Aseprite | Pixelorama |
|---------|:-----------:|:--------:|:----------:|
| Import/export parity | Yes | Yes | Yes |
| Configurable grid | Yes | Yes | Yes |
| Selection transform | **In progress** | Yes | Yes |
| Text tool | **No** | Yes | Yes |
| Movable symmetry axis | **No** | Yes | Yes |
| Pressure sensitivity | **No** | Yes | Yes |
| Isometric/hex tilemaps | **No** | No | Yes |
| Diagonal symmetry | **No** | No | Yes |
| 3D layer | **No** | No | Yes |
| Audio sync | **No** | No | Yes |
