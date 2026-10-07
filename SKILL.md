---
name: blender-scene-from-reference
description: Recreate a reference photo (interior room, product scene) as a realistic 3D scene in Blender using a headless script workflow. Use when the user gives a reference image and asks to build, copy or recreate it realistically in Blender, or wants a photoreal Cycles render matched to a photo.
---

# Blender: recreate a scene from a reference photo

Proven on 2026-10-07 (sunlit Altbau room, Desktop\Realistic Room). Full notes: `C:\Lourea\Wissen\Blender - Szene aus Referenzfoto nachbauen.md`.

## Rules
- Never build in the user's live Blender session if it holds other work. Write one script and run headless:
  `"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b -P build_room.py -- out=<abs png> blend=<abs blend> res=500 samples=64 sun=16 sky=3.4 view=Standard`
- Always use absolute output paths. Expose tunables as `key=value` args so re-renders need no edits.
- Preview first: 500 px / 64 samples (~7 s). Only render big (2000 px / 640 samples, ~2.5 min; 3000 px on request) after the preview looks right.
- Do not stop until it reads as photographic; compare against the reference each round.

## Workflow
1. Probe the reference: `scripts/probe.py` + `scripts/cmp.sh <render-name>` print sRGB values at fixed points for the reference and the render. Tune lighting and albedo until within a few percent.
2. Estimate geometry from the image (ceiling height, window size, camera height and yaw from corner position and skirting slope). Corner at origin, floor z=0, camera zero pitch near 1.2 m.
3. Build in order: shell, cornice/skirting profiles, window, floor, furniture, outside (shadow-casting leaves, far foliage, backdrop), lights/world/camera. Preview after each stage.
4. Finish with `scripts/post.py in.png out.png` (bloom, vignette, grain).
5. Save to Desktop: .blend, script, final PNGs, post script, short daily report in `C:\Lourea\Daily Notes`.

`scripts/build_room.py` is the full working example (herringbone parquet, mitered cornice, deep-reveal window, sun patch with leaf shadows). Copy and adapt it instead of starting from zero. `scripts/run.sh` shows the run wrapper (edit its scratchpad path).

## Lighting and material rules that mattered
- Sun lamp (angle 0.5-0.9 deg), warm color ~(1.0, 0.9, 0.76); warm-tinted sky for ambient; Standard view transform for the high-key look.
- Set far backdrop objects `visible_shadow = False` or they block the sun.
- Glass: Glass BSDF mixed with Transparent via Light Path (Is Shadow Ray, Is Diffuse Ray). Add a portal area light in the window.
- Azimuth sets shadow-patch width, elevation sets height and slope. They trade off, so pick a compromise and tell the user.
- Plaster: very mild color variation. Skirting wood: noise stretched in Z only. Fabric: tiny bump, almost no blotches. Foliage: dark olive, low translucency.

## Pitfalls
- Relative `//` output path fails in unsaved files.
- `sky.dust_density` missing in Blender 5.2: wrap sky settings in try/except.
- Coplanar faces on blocks z-fight: stagger by 1 cm.
- Reject far leaves spawned inside the room (`y > -2`).
- Report honestly any remaining differences from the reference.
