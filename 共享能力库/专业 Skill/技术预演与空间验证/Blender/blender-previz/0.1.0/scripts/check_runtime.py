#!/usr/bin/env python3
"""Check the local Blender Previz runtime without modifying it."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


DEFAULT_ENGINE_ROOT = Path(r"D:\003-AI制作\005-blender\AI_PREVIZ_SYSTEM")
DEFAULT_BLENDER_EXE = Path(r"D:\002-工具\blender.exe")


def resolve_path(cli_value: str | None, env_name: str, fallback: Path) -> Path:
    value = cli_value or os.environ.get(env_name)
    return Path(value).expanduser().resolve() if value else fallback.resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-root")
    parser.add_argument("--blender")
    parser.add_argument("--ffmpeg")
    args = parser.parse_args()

    engine_root = resolve_path(args.engine_root, "BLENDER_PREVIZ_ROOT", DEFAULT_ENGINE_ROOT)
    blender = resolve_path(args.blender, "BLENDER_EXE", DEFAULT_BLENDER_EXE)
    required = [
        engine_root / "run_previz.py",
        engine_root / "blender" / "scene_builder.py",
        engine_root / "engine" / "blender_driver.py",
        engine_root / "schemas" / "previz-scene-v0.1.schema.json",
    ]
    errors: list[str] = []
    if not engine_root.is_dir():
        errors.append(f"预演引擎目录不存在: {engine_root}")
    if not blender.is_file():
        errors.append(f"Blender 程序不存在: {blender}")
    for path in required:
        if not path.is_file():
            errors.append(f"缺少运行文件: {path}")

    version = None
    ffmpeg = args.ffmpeg or shutil.which("ffmpeg")
    ffmpeg_version = None
    if blender.is_file():
        try:
            process = subprocess.run(
                [str(blender), "--version"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            version = process.stdout.splitlines()[0] if process.stdout else None
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"无法读取 Blender 版本: {exc}")

    if not ffmpeg:
        errors.append("未找到 ffmpeg，无法把预演帧序列装配为 MP4")
    else:
        try:
            process = subprocess.run(
                [str(ffmpeg), "-version"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            ffmpeg_version = process.stdout.splitlines()[0] if process.stdout else None
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"无法读取 ffmpeg 版本: {exc}")

    result = {
        "status": "ready" if not errors else "not_ready",
        "engine_root": str(engine_root),
        "blender_executable": str(blender),
        "blender_version": version,
        "ffmpeg_executable": str(ffmpeg) if ffmpeg else None,
        "ffmpeg_version": ffmpeg_version,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
