#!/usr/bin/env python3
"""Create one immutable Blender previz run from a scene JSON file."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENGINE_VERSION = "0.1.0"
DEFAULT_BLENDER = Path(r"D:\002-工具\blender.exe")
ROOT = Path(__file__).resolve().parent


def safe_name(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field} 不能为空")
    cleaned = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "-", value).strip(".-")
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError(f"{field} 不能生成安全目录名")
    return cleaned[:96]


def load_config(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 语法错误，第 {exc.lineno} 行第 {exc.colno} 列: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("配置根节点必须是 JSON 对象")
    project = data.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("name"), str):
        raise ValueError("缺少 project.name")
    return data


def find_blender(explicit: str | None) -> Path:
    candidates = [
        Path(explicit).expanduser() if explicit else None,
        Path(os.environ["BLENDER_EXE"]).expanduser() if os.environ.get("BLENDER_EXE") else None,
        DEFAULT_BLENDER,
    ]
    found_on_path = shutil.which("blender")
    if found_on_path:
        candidates.append(Path(found_on_path))
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("未找到 Blender；请用 --blender 或 BLENDER_EXE 指定 blender.exe")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path, run_dir: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(run_dir).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="运行一个不覆盖旧结果的 Blender 镜头预演")
    parser.add_argument("--config", required=True, help="场景 JSON 配置")
    parser.add_argument("--run-id", required=True, help="本次运行的唯一版本号")
    parser.add_argument("--output-root", default=str(ROOT / "runs"), help="运行结果根目录")
    parser.add_argument("--blender", help="blender.exe 路径")
    parser.add_argument("--ffmpeg", help="ffmpeg 可执行文件路径")
    parser.add_argument("--render", action="store_true", help="同时生成预演视频和关键帧")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"配置不存在: {config_path}")
    config = load_config(config_path)
    blender = find_blender(args.blender)

    project_name = safe_name(config["project"]["name"], "project.name")
    selection = config.get("selection") if isinstance(config.get("selection"), dict) else {}
    segment_name = safe_name(str(selection.get("segment_id") or config["project"].get("scene_id") or "selected-shots"), "segment_id")
    run_id = safe_name(args.run_id, "run-id")
    output_root = Path(args.output_root).expanduser().resolve()
    run_dir = output_root / project_name / segment_name / run_id
    if run_dir.exists():
        raise FileExistsError(f"运行目录已存在，为避免覆盖已停止: {run_dir}")

    run_dir.mkdir(parents=True)
    input_copy = run_dir / "scene.input.json"
    shutil.copy2(config_path, input_copy)

    driver = ROOT / "engine" / "blender_driver.py"
    builder = ROOT / "blender" / "scene_builder.py"
    command = [
        str(blender), "--factory-startup", "--background", "--disable-autoexec",
        "--python", str(driver), "--", "--config", str(input_copy),
        "--output-dir", str(run_dir), "--source-script", str(builder),
    ]
    if args.render:
        command.append("--render")

    started_at = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log_text = completed.stdout.decode("utf-8", errors="replace")
    (run_dir / "blender.log").write_text(log_text, encoding="utf-8")

    blender_ok = (
        completed.returncode == 0
        and (run_dir / "previz.blend").is_file()
        and (run_dir / "scene-report.json").is_file()
    )
    encode_returncode = 0
    if args.render and blender_ok:
        ffmpeg = args.ffmpeg or shutil.which("ffmpeg")
        frames = run_dir / "render_frames"
        first_frame = int(config["project"].get("frame_start", 1))
        if not ffmpeg or not any(frames.glob("frame_*.png")):
            encode_returncode = 1
            (run_dir / "ffmpeg.log").write_text("未找到 ffmpeg 或 Blender 未生成 PNG 帧序列。\n", encoding="utf-8")
        else:
            render_config = config.get("render", {}) if isinstance(config.get("render"), dict) else {}
            encode_command = [
                str(ffmpeg), "-y", "-framerate", str(config["project"]["fps"]),
                "-start_number", str(first_frame), "-i", str(frames / "frame_%04d.png"),
                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264",
                "-preset", str(render_config.get("video_preset", "medium")),
                "-crf", str(render_config.get("video_crf", 18)), "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(run_dir / "previz.mp4"),
            ]
            encoded = subprocess.run(encode_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
            encode_returncode = encoded.returncode
            (run_dir / "ffmpeg.log").write_text(
                encoded.stdout.decode("utf-8", errors="replace"), encoding="utf-8"
            )

    render_ok = not args.render or (encode_returncode == 0 and (run_dir / "previz.mp4").is_file())
    final_status = "success" if blender_ok and render_ok else "failed"

    manifest: dict[str, Any] = {
        "manifest_version": 1,
        "engine_version": ENGINE_VERSION,
        "status": final_status,
        "run_id": run_id,
        "project": config["project"]["name"],
        "segment_id": selection.get("segment_id") or config["project"].get("scene_id") or "selected-shots",
        "source_mapping": selection.get("source_shots", []),
        "started_at_utc": started_at,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "render_requested": bool(args.render),
        "blender_executable": str(blender),
        "source_config": str(config_path),
        "engine_sources": {
            "run_previz": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
            "blender_driver": {"path": str(driver), "sha256": sha256(driver)},
            "scene_builder": {"path": str(builder), "sha256": sha256(builder)},
            "scene_schema": {
                "path": str(ROOT / "schemas" / "previz-scene-v0.1.schema.json"),
                "sha256": sha256(ROOT / "schemas" / "previz-scene-v0.1.schema.json"),
            },
        },
        "reference_policy": config.get("reference_policy", {
            "role": "camera_blocking_reference",
            "reference_use": ["camera", "blocking", "movement_direction", "timing"],
            "must_preserve": ["approved_assets", "approved_visual_style"],
            "do_not_inherit": ["proxy_appearance", "proxy_material", "preview_lighting"],
        }),
        "files": [],
    }

    report_lines = [
        "# Blender Previz 运行报告", "",
        f"- 状态：{manifest['status']}",
        f"- 项目：{manifest['project']}",
        f"- 局部范围：{manifest['segment_id']}",
        f"- 运行版本：{run_id}",
        f"- 是否渲染：{'是' if args.render else '否'}",
        "- 说明：本报告只证明引擎执行结果；构图、景别和动线结论必须在实际查看视频或关键帧后填写。",
    ]
    if not blender_ok:
        report_lines.append(f"- Blender 返回码：{completed.returncode}，请查看 blender.log。")
    if args.render and not render_ok:
        report_lines.append(f"- 视频编码返回码：{encode_returncode}，请查看 ffmpeg.log。")
    (run_dir / "previz-report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    for path in sorted(p for p in run_dir.rglob("*") if p.is_file() and p.name != "previz-manifest.json"):
        manifest["files"].append(file_record(path, run_dir))
    write_json(run_dir / "previz-manifest.json", manifest)

    result_code = 0 if final_status == "success" else (completed.returncode or encode_returncode or 1)
    print(json.dumps({"status": manifest["status"], "run_dir": str(run_dir), "returncode": result_code}, ensure_ascii=False))
    return result_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
