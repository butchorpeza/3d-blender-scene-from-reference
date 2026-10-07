# 3D Blender Scene from Reference

A Claude skill (`blender-scene-from-reference`) that recreates a reference photo (an interior room or a product scene) as a photorealistic 3D scene in Blender. You give Claude a photo and ask for a realistic Blender recreation. It writes one Python script, runs Blender headless, and renders a Cycles image matched to the photo.

## When it triggers

When you give a reference image and ask Claude to build, copy or recreate it realistically in Blender, or want a photoreal Cycles render matched to a photo.

## How it works

1. **Probe the reference.** Helper scripts print color values at fixed points for both the photo and the render. Lighting and materials are tuned until they are within a few percent of the photo.
2. **Estimate geometry from the photo:** ceiling height, window size, camera height and angle.
3. **Build in stages:** shell, cornice and skirting, window, floor, furniture, outside view, then lights and camera. Preview after each stage.
4. **Preview before the big render.** Preview: 500 px / 64 samples (~7 s). Full render: 2000 px / 640 samples (~2.5 min). 3000 px only on request.
5. **Post-process** with bloom, vignette and grain.
6. **Save** the .blend, script and final PNGs.

## Files

| File | Purpose |
|---|---|
| `SKILL.md` | Rules, workflow, lighting and material tips, known pitfalls |
| `scripts/build_room.py` | Full example scene (herringbone parquet, mitered cornice, deep-reveal window, sun patch with leaf shadows) |
| `scripts/post.py` | Bloom, vignette and grain |
| `scripts/probe.py`, `scripts/cmp.sh` | Color-comparison helpers |
| `scripts/run.sh` | Headless run wrapper |

## Installation

Copy this folder to `~/.claude/skills/blender-scene-from-reference/` (on Windows: `C:\Users\<you>\.claude\skills\blender-scene-from-reference\`) and start a new Claude Code session.

## Usage notes

- Requires Blender (developed with 5.2) and runs headless: `blender -b -P build_room.py -- out=<abs png> blend=<abs blend> res=500 samples=64`
- `run.sh` and `cmp.sh` contain hardcoded working-folder paths. Edit them before reuse.
- `build_room.py` references local example `.blend` files via the `lasse_file` and `clothes_file` arguments. Override or remove them.
- Always use absolute output paths. Relative `//` paths fail in unsaved files.

## License

MIT, see [LICENSE](LICENSE).
