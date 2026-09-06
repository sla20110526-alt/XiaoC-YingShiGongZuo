"""Blender-side driver for one immutable previz build/render run."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    user_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-script", required=True)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(user_args)


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as source:
        return json.load(source)


def vector3(value) -> list[float]:
    return [round(float(component), 6) for component in value[:3]]


def camera_intervals(config: dict, frame_end: int) -> list[dict]:
    cameras = config["cameras"]
    intervals = []
    for index, camera in enumerate(cameras):
        start = camera["start_frame"]
        end = cameras[index + 1]["start_frame"] - 1 if index + 1 < len(cameras) else frame_end
        intervals.append({"config": camera, "start_frame": start, "end_frame": end})
    return intervals


def configure_render(scene, config: dict, output_dir: Path) -> None:
    render_config = config.get("render", {})
    scene.render.engine = render_config.get("engine", "BLENDER_WORKBENCH")
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 15
    render_frames = output_dir / "render_frames"
    render_frames.mkdir(exist_ok=True)
    scene.render.filepath = str(render_frames / "frame_")
    scene.render.use_file_extension = True
    scene.render.film_transparent = False
    if scene.render.engine == "BLENDER_WORKBENCH":
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "OBJECT"
        scene.display.shading.show_shadows = True
        scene.display.shading.show_cavity = True
        scene.display.shading.cavity_type = "WORLD"


def render_keyframes(scene, config: dict, output_dir: Path) -> list[dict]:
    frame_dir = output_dir / "frames"
    frame_dir.mkdir(exist_ok=True)
    cameras_by_name = {obj.name: obj for obj in bpy.data.objects if obj.type == "CAMERA"}
    output_path = scene.render.filepath
    output_format = scene.render.image_settings.file_format
    rendered = []
    for interval in camera_intervals(config, scene.frame_end):
        camera_config = interval["config"]
        frame = (interval["start_frame"] + interval["end_frame"]) // 2
        camera = cameras_by_name[camera_config["name"]]
        scene.frame_set(frame)
        scene.camera = camera
        stem = f"{camera.name}_{frame:04d}"
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(frame_dir / stem)
        bpy.ops.render.render(write_still=True)
        rendered.append({"camera": camera.name, "frame": frame, "path": f"frames/{stem}.png"})
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = output_format
    scene.frame_set(scene.frame_start)
    return rendered


def collect_report(scene, config: dict, keyframes: list[dict]) -> dict:
    actor_samples = []
    sample_frames = {scene.frame_start, scene.frame_end}
    for movement in config["blocking"]:
        sample_frames.update((movement["start_frame"], movement["end_frame"]))
    for camera in config["cameras"]:
        sample_frames.add(camera["start_frame"])
    actor_objects = {actor["id"]: bpy.data.objects.get(actor["name"]) for actor in config["actors"]}
    for frame in sorted(sample_frames):
        scene.frame_set(frame)
        for actor_id, obj in actor_objects.items():
            if obj is not None:
                actor_samples.append({
                    "actor": actor_id,
                    "frame": frame,
                    "world_position": vector3(obj.matrix_world.translation),
                    "rotation_euler": vector3(obj.rotation_euler),
                })

    cameras = []
    for interval in camera_intervals(config, scene.frame_end):
        camera_config = interval["config"]
        camera = bpy.data.objects.get(camera_config["name"])
        cameras.append({
            "name": camera_config["name"],
            "start_frame": interval["start_frame"],
            "end_frame": interval["end_frame"],
            "lens_mm": float(camera.data.lens),
            "world_position": vector3(camera.matrix_world.translation),
            "rotation_euler": vector3(camera.rotation_euler),
            "target": camera_config["target"],
        })

    counts: dict[str, int] = {}
    for obj in bpy.data.objects:
        counts[obj.type] = counts.get(obj.type, 0) + 1
    selection = config.get("selection", {})
    return {
        "status": "success",
        "blender_version": bpy.app.version_string,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "fps": scene.render.fps,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage],
        "object_counts": counts,
        "source_mapping": selection.get("source_shots", []),
        "actor_samples": actor_samples,
        "cameras": cameras,
        "keyframes": keyframes,
    }


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).resolve()
    output_dir = Path(args.output_dir).resolve()
    source_script = Path(args.source_script).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    os.environ["BLENDER_PREVIZ_CONFIG"] = str(config_path)
    config = read_json(config_path)
    runpy.run_path(str(source_script), run_name="__main__")

    scene = bpy.context.scene
    scene["blender_previz_config"] = str(config_path)
    scene["blender_previz_engine_version"] = "0.1.0"
    configure_render(scene, config, output_dir)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_dir / "previz.blend"))

    keyframes = []
    if args.render:
        keyframes = render_keyframes(scene, config, output_dir)
        scene.render.filepath = str(output_dir / "render_frames" / "frame_")
        scene.render.image_settings.file_format = "PNG"
        scene.frame_set(scene.frame_start)
        bpy.ops.render.render(animation=True)

    report = collect_report(scene, config, keyframes)
    (output_dir / "scene-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "success", "scene_report": report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
