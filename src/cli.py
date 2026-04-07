"""CLI entry point for RetroSprite headless operations."""
from __future__ import annotations
import argparse
import glob
import os
import sys


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for CLI subcommands."""
    from src import __version__
    parser = argparse.ArgumentParser(
        prog="retrosprite",
        description="RetroSprite CLI — export, batch process, and script"
    )
    parser.add_argument("--version", action="version",
                        version=f"RetroSprite {__version__}")
    sub = parser.add_subparsers(dest="command")

    # export
    exp = sub.add_parser("export", help="Export a single project")
    exp.add_argument("input", help="Input .retro file")
    exp.add_argument("output", help="Output file path")
    exp.add_argument("--format", choices=["png", "gif", "sheet", "frames", "webp", "apng"],
                     default=None, help="Output format (auto-detect if omitted)")
    exp.add_argument("--scale", type=int, default=1, help="Scale factor (1-8)")
    exp.add_argument("--frame", type=int, default=0, help="Frame index (for png)")
    exp.add_argument("--columns", type=int, default=0,
                     help="Sheet columns (0=auto)")
    exp.add_argument("--layer", default=None, help="Layer name or index")

    # batch
    bat = sub.add_parser("batch", help="Batch process a directory")
    bat.add_argument("input_dir", help="Input directory")
    bat.add_argument("output_dir", help="Output directory")
    bat.add_argument("--pattern", default="*.retro", help="Glob pattern")
    bat.add_argument("--format", choices=["png", "gif", "sheet", "webp", "apng"],
                     required=True, help="Output format")
    bat.add_argument("--scale", type=int, default=1, help="Scale factor")

    # run
    run = sub.add_parser("run", help="Execute a script")
    run.add_argument("script", help="Script file path")
    run.add_argument("script_args", nargs="*", help="Script arguments")

    # info
    inf = sub.add_parser("info", help="Print project metadata")
    inf.add_argument("input", help="Input .retro file")

    return parser


def _detect_format(output_path: str) -> str:
    """Auto-detect format from file extension."""
    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".gif":
        return "gif"
    elif ext == ".json":
        return "sheet"
    elif ext == ".webp":
        return "webp"
    elif ext == ".apng":
        return "apng"
    elif ext == ".png":
        return "png"
    return "png"


def _parse_layer(layer_arg: str | None) -> int | str | None:
    """Parse --layer argument as int index or string name."""
    if layer_arg is None:
        return None
    try:
        return int(layer_arg)
    except ValueError:
        return layer_arg


def cmd_export(input_path: str, output_path: str, format: str | None,
               scale: int, frame: int, columns: int,
               layer: str | None) -> int:
    """Export a single project. Returns 0 on success, 1 on error."""
    from src.scripting import RetroSpriteAPI
    from src.animation import AnimationTimeline
    from src.palette import Palette
    from src.project import load_project

    try:
        ext = os.path.splitext(input_path)[1].lower()
        if ext in ('.ase', '.aseprite'):
            from src.aseprite_import import load_aseprite
            timeline, palette = load_aseprite(input_path)
        elif ext == '.psd':
            from src.psd_import import load_psd
            timeline, palette = load_psd(input_path)
        else:
            timeline, palette, _, _, _ = load_project(input_path)
    except Exception as e:
        print(f"Error loading {input_path}: {e}", file=sys.stderr)
        return 1

    api = RetroSpriteAPI(timeline=timeline, palette=palette, app=None)
    fmt = format or _detect_format(output_path)
    parsed_layer = _parse_layer(layer)

    try:
        if fmt == "png":
            api.export_png(output_path, frame=frame, scale=scale,
                           layer=parsed_layer)
        elif fmt == "gif":
            api.export_gif(output_path, scale=scale)
        elif fmt == "sheet":
            # save_sprite_sheet expects a .png path, derives .json sidecar
            sheet_path = output_path
            if sheet_path.lower().endswith(".json"):
                sheet_path = sheet_path[:-5] + ".png"
            api.export_sheet(sheet_path, scale=scale, columns=columns)
        elif fmt == "frames":
            from src.export import export_png_sequence
            export_png_sequence(api.timeline, output_path, scale=scale,
                                layer=_parse_layer(layer))
        elif fmt == "webp":
            from src.animated_export import export_webp
            export_webp(timeline, output_path, scale=scale)
        elif fmt == "apng":
            from src.animated_export import export_apng
            export_apng(timeline, output_path, scale=scale)
        print(f"Exported: {output_path}")
        return 0
    except Exception as e:
        print(f"Export error: {e}", file=sys.stderr)
        return 1


def cmd_batch(input_dir: str, output_dir: str, pattern: str,
              format: str, scale: int) -> int:
    """Batch export all matching files. Returns 0 on success."""
    files = sorted(glob.glob(os.path.join(input_dir, pattern)))
    if not files:
        print(f"No files matching '{pattern}' in {input_dir}")
        return 1

    os.makedirs(output_dir, exist_ok=True)
    total = len(files)
    errors = 0

    for idx, filepath in enumerate(files, 1):
        basename = os.path.splitext(os.path.basename(filepath))[0]
        ext = {"png": ".png", "gif": ".gif", "sheet": ".png", "webp": ".webp", "apng": ".apng"}[format]
        output_path = os.path.join(output_dir, basename + ext)
        print(f"[{idx}/{total}] Exporting {os.path.basename(filepath)} -> "
              f"{os.path.basename(output_path)}")
        result = cmd_export(filepath, output_path, format=format,
                           scale=scale, frame=0, columns=0, layer=None)
        if result != 0:
            errors += 1

    if errors:
        print(f"\n{errors}/{total} exports failed")
        return 1
    print(f"\nAll {total} exports succeeded")
    return 0


def _run_script_code(code: str, script_globals: dict) -> None:
    """Execute script code in the given global namespace.

    This is intentionally running user-provided script code -- it is the
    core feature of the 'run' CLI subcommand, analogous to 'python script.py'.
    """
    # Using exec() here is intentional: the CLI 'run' command exists
    # specifically to execute user-authored RetroSprite scripts.
    exec(code, script_globals)  # noqa: S102


def cmd_run(script_path: str, script_args: list[str]) -> int:
    """Execute a script with headless API. Returns 0 on success."""
    from src.scripting import RetroSpriteAPI
    from src.animation import AnimationTimeline
    from src.palette import Palette

    timeline = AnimationTimeline(32, 32)
    palette = Palette("Pico-8")
    api = RetroSpriteAPI(timeline=timeline, palette=palette, app=None)

    # Set up sys.argv for the script
    old_argv = sys.argv
    sys.argv = [script_path] + script_args

    try:
        with open(script_path) as f:
            code = f.read()
        _run_script_code(code, {"api": api, "__name__": "__main__",
                                "__file__": script_path})
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    except Exception as e:
        print(f"Script error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        sys.argv = old_argv


def cmd_info(input_path: str) -> int:
    """Print project metadata. Returns 0 on success."""
    from src.project import load_project

    try:
        ext = os.path.splitext(input_path)[1].lower()
        if ext in ('.ase', '.aseprite'):
            from src.aseprite_import import load_aseprite
            timeline, palette = load_aseprite(input_path)
            version = "N/A"
            color_mode = "rgba"
        elif ext == '.psd':
            from src.psd_import import load_psd
            timeline, palette = load_psd(input_path)
            version = "N/A"
            color_mode = "rgba"
        else:
            import json
            with open(input_path, "rb") as f:
                project_data = json.loads(f.read())
            version = project_data.get("version", 1)
            color_mode = project_data.get("color_mode", "rgba")
            timeline, palette, _, _, _ = load_project(input_path)
    except Exception as e:
        print(f"Error loading {input_path}: {e}", file=sys.stderr)
        return 1

    basename = os.path.basename(input_path)
    frame_obj = timeline.get_frame_obj(0)
    layer_names = [l.name for l in frame_obj.layers]

    # Check for effects
    effects_info = []
    for layer in frame_obj.layers:
        if hasattr(layer, 'effects') and layer.effects:
            fx_names = [e.effect_type for e in layer.effects]
            effects_info.append(f"{layer.name} has {', '.join(fx_names)}")

    # Check for tilesets
    ts_names = list(getattr(timeline, 'tilesets', {}).keys())

    print(f"Project: {basename} (v{version})")
    print(f"Size: {timeline.width}x{timeline.height}, {timeline.fps} fps")
    print(f"Frames: {timeline.frame_count}")
    print(f"Layers: {len(layer_names)} ({', '.join(layer_names)})")
    if effects_info:
        print(f"Effects: {'; '.join(effects_info)}")
    else:
        print("Effects: none")
    if ts_names:
        print(f"Tilesets: {', '.join(ts_names)}")
    else:
        print("Tilesets: none")
    if color_mode == "indexed":
        print(f"Color mode: indexed")
    print(f"Palette: \"{palette.name}\" ({len(palette.colors)} colors)")
    return 0


def main() -> int:
    """CLI main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "export":
        return cmd_export(args.input, args.output, args.format, args.scale,
                         args.frame, args.columns, args.layer)
    elif args.command == "batch":
        return cmd_batch(args.input_dir, args.output_dir, args.pattern,
                        args.format, args.scale)
    elif args.command == "run":
        return cmd_run(args.script, args.script_args)
    elif args.command == "info":
        return cmd_info(args.input)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
