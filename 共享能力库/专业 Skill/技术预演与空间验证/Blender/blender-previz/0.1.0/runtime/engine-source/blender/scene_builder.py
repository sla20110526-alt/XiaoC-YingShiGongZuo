import bpy
import math
import json
import os
from pathlib import Path
from mathutils import Vector

# =========================================================
# AI PREVIZ TEST 01
# 9:16 房间 + 两个人物Proxy + 桌子 + 摄影机 + 简单Blocking
# =========================================================

# ---------- 导演数据入口：先读取并校验，再进行任何场景修改 ----------
def resolve_scene_json_path():
    """支持外部脚本、Blender文本编辑器和已保存的TEST01工程。"""
    explicit_path = os.environ.get("BLENDER_PREVIZ_CONFIG")
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if not candidate.is_file():
            raise RuntimeError(f"指定的预演配置不存在: {candidate}")
        return candidate

    script_paths = [globals().get("__file__")]
    space = getattr(bpy.context, "space_data", None)
    active_text = getattr(space, "text", None)
    if active_text is not None and active_text.filepath:
        script_paths.append(bpy.path.abspath(active_text.filepath))
    for script_path in script_paths:
        if script_path:
            candidate = Path(script_path).resolve()
            if candidate.suffix.lower() == ".py" and candidate.is_file():
                return candidate.parent.parent / "projects" / "TEST01" / "scene.json"
    if bpy.data.filepath:
        return Path(bpy.data.filepath).resolve().parent / "scene.json"
    return Path.cwd() / "projects" / "TEST01" / "scene.json"


def validate_scene_config(data):
    """校验必要字段、单位值域、角色引用和时间范围；错误包含字段路径。"""
    def require(condition, field, message):
        if not condition:
            raise ValueError(f"{field}: {message}")

    def obj(value, field, keys):
        require(isinstance(value, dict), field, "必须是JSON对象")
        for key in keys:
            require(key in value, f"{field}.{key}", "缺少必填字段")
        return value

    def number(value, field, positive=False):
        require(type(value) in (int, float) and math.isfinite(value), field, "必须是有限数值")
        if positive:
            require(value > 0, field, "必须大于0")

    def integer(value, field, minimum=1, maximum=None):
        require(type(value) is int and value >= minimum, field, f"必须是大于等于{minimum}的整数")
        if maximum is not None:
            require(value <= maximum, field, f"不能大于{maximum}")

    def vector(value, field, positive=False, color=False):
        require(isinstance(value, list) and len(value) == 3, field, "必须包含3个数值，坐标顺序为X/Y/Z")
        for i, component in enumerate(value):
            number(component, f"{field}[{i}]", positive)
            if color:
                require(0 <= component <= 1, f"{field}[{i}]", "RGB颜色必须在0至1之间")

    def name(value, field):
        require(isinstance(value, str) and bool(value.strip()), field, "必须是非空字符串")

    obj(data, "scene", ("schema_version", "project", "room", "table", "actors", "blocking", "facing", "reference_camera", "cameras"))
    require(type(data["schema_version"]) is int and data["schema_version"] == 1, "schema_version", "仅支持版本1")
    project = obj(data["project"], "project", ("name", "resolution", "resolution_percentage", "fps", "frame_start", "frame_count"))
    name(project["name"], "project.name")
    resolution = project["resolution"]
    require(isinstance(resolution, list) and len(resolution) == 2, "project.resolution", "必须是[宽, 高]")
    for i, value in enumerate(resolution):
        integer(value, f"project.resolution[{i}]", 4, 65536)
    integer(project["resolution_percentage"], "project.resolution_percentage", 1, 100)
    integer(project["fps"], "project.fps", 1, 32767)
    integer(project["frame_start"], "project.frame_start", 1, 1048574)
    integer(project["frame_count"], "project.frame_count")
    first = project["frame_start"]
    last = first + project["frame_count"] - 1
    integer(last, "project计算结束帧", first, 1048574)

    room = obj(data["room"], "room", ("dimensions", "floor_thickness", "wall_thickness", "colors"))
    vector(room["dimensions"], "room.dimensions", positive=True)
    for key in ("floor_thickness", "wall_thickness"):
        number(room[key], f"room.{key}", positive=True)
    colors = obj(room["colors"], "room.colors", ("floor", "back_wall", "side_walls"))
    for key in ("floor", "back_wall", "side_walls"):
        vector(colors[key], f"room.colors.{key}", color=True)
    table = obj(data["table"], "table", ("name", "dimensions", "position", "color"))
    name(table["name"], "table.name")
    vector(table["dimensions"], "table.dimensions", positive=True)
    vector(table["position"], "table.position")
    vector(table["color"], "table.color", color=True)

    require(isinstance(data["actors"], list) and bool(data["actors"]), "actors", "必须是非空数组")
    actors_by_id = {}
    object_names = {"ENV_FLOOR", "ENV_BACK_WALL", "ENV_LEFT_WALL", "ENV_RIGHT_WALL", "LIGHT_KEY", "LIGHT_FILL"}
    def unique_name(value, field):
        name(value, field)
        require(value not in object_names, field, "物体名称重复")
        object_names.add(value)
    unique_name(table["name"], "table.name")
    for i, actor in enumerate(data["actors"]):
        field = f"actors[{i}]"
        obj(actor, field, ("id", "name", "height", "color", "start_position", "end_position"))
        name(actor["id"], field + ".id")
        require(actor["id"] not in actors_by_id, field + ".id", "角色ID重复")
        actors_by_id[actor["id"]] = actor
        unique_name(actor["name"], field + ".name")
        for suffix in ("_BODY", "_HEAD", "_SHOULDER_L", "_ARM_L", "_LEG_L", "_SHOULDER_R", "_ARM_R", "_LEG_R", "_FRONT_MARKER"):
            unique_name(actor["name"] + suffix, field + ".name派生部件")
        number(actor["height"], field + ".height", positive=True)
        vector(actor["color"], field + ".color", color=True)
        for key in ("start_position", "end_position"):
            vector(actor[key], field + "." + key)

    def actor_ref(value, field):
        name(value, field)
        require(value in actors_by_id, field, f"未知角色ID: {value}")

    require(isinstance(data["blocking"], list), "blocking", "必须是数组")
    moving_ids = set()
    for i, motion in enumerate(data["blocking"]):
        field = f"blocking[{i}]"
        obj(motion, field, ("actor", "start_frame", "end_frame"))
        actor_ref(motion["actor"], field + ".actor")
        require(motion["actor"] not in moving_ids, field + ".actor", "版本1每人只支持一段起终点移动")
        moving_ids.add(motion["actor"])
        integer(motion["start_frame"], field + ".start_frame", first, last)
        integer(motion["end_frame"], field + ".end_frame", motion["start_frame"] + 1, last)
    for actor_id, actor in actors_by_id.items():
        if actor_id not in moving_ids:
            require(actor["start_position"] == actor["end_position"], f"actors.{actor_id}.end_position", "起终点不同的角色必须配置blocking")

    require(isinstance(data["facing"], list), "facing", "必须是数组")
    facing_keys = set()
    for i, facing in enumerate(data["facing"]):
        field = f"facing[{i}]"
        obj(facing, field, ("actor", "target", "frame"))
        actor_ref(facing["actor"], field + ".actor")
        actor_ref(facing["target"], field + ".target")
        require(facing["actor"] != facing["target"], field + ".target", "不能朝向自身")
        integer(facing["frame"], field + ".frame", first, last)
        key = (facing["actor"], facing["frame"])
        require(key not in facing_keys, field, "同一角色同一帧的Facing重复")
        facing_keys.add(key)

    def camera_config(camera, field, is_shot):
        obj(camera, field, ("name", "lens_mm", "position", "target"))
        unique_name(camera["name"], field + ".name")
        number(camera["lens_mm"], field + ".lens_mm", positive=True)
        require(1 <= camera["lens_mm"] <= 5000, field + ".lens_mm", "焦段范围为1至5000mm")
        vector(camera["position"], field + ".position")
        vector(camera["target"], field + ".target")
        require(camera["position"] != camera["target"], field + ".target", "目标不能与摄影机位置重合")
        if is_shot:
            obj(camera, field, ("start_frame",))
            integer(camera["start_frame"], field + ".start_frame", first, last)

    camera_config(data["reference_camera"], "reference_camera", False)
    require(isinstance(data["cameras"], list) and bool(data["cameras"]), "cameras", "必须是非空数组")
    previous_frame = first - 1
    for i, camera in enumerate(data["cameras"]):
        camera_config(camera, f"cameras[{i}]", True)
        require(camera["start_frame"] > previous_frame, f"cameras[{i}].start_frame", "必须按开始帧严格递增，不能重复")
        previous_frame = camera["start_frame"]
    require(data["cameras"][0]["start_frame"] == first, "cameras[0].start_frame", "第一镜必须从项目开始帧开始")


def load_scene_config(config_path):
    """UTF-8 JSON读取入口；失败时报告文件路径和具体原因。"""
    try:
        with Path(config_path).open("r", encoding="utf-8-sig") as config_file:
            data = json.load(config_file)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"导演配置JSON语法错误: {config_path}，第{exc.lineno}行第{exc.colno}列: {exc.msg}") from exc
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"无法读取导演配置: {config_path}。请确认文件存在、可读且为UTF-8编码。原因: {exc}") from exc
    try:
        validate_scene_config(data)
    except ValueError as exc:
        raise RuntimeError(f"导演配置字段错误: {config_path}，{exc}") from exc
    return data


SCENE_JSON_PATH = resolve_scene_json_path()
scene_config = load_scene_config(SCENE_JSON_PATH)


# ---------- 清空当前场景 ----------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

for datablocks in (
    bpy.data.meshes,
    bpy.data.curves,
    bpy.data.cameras,
    bpy.data.lights
):
    pass


scene = bpy.context.scene

# ---------- 项目设置 ----------
project = scene_config["project"]
scene.render.resolution_x, scene.render.resolution_y = project["resolution"]
scene.render.resolution_percentage = project["resolution_percentage"]
scene.render.fps = project["fps"]
scene.frame_start = project["frame_start"]
scene.frame_end = scene.frame_start + project["frame_count"] - 1


# =========================================================
# 工具函数
# =========================================================

def create_box(name, location, scale, color):
    bpy.ops.mesh.primitive_cube_add(location=location)

    obj = bpy.context.active_object
    obj.name = name

    obj.scale = scale

    obj.color = (
        color[0],
        color[1],
        color[2],
        1
    )

    return obj


def create_actor(name, height, location, color):

    # 人物控制根节点：脚底为局部 Z=0，身体正面为局部 +Y。
    bpy.ops.object.empty_add(
        type='PLAIN_AXES',
        location=location
    )

    root = bpy.context.active_object
    root.name = name

    # 所有部件直接挂到 Root，位置和尺寸按人物身高定义。
    def add_box_part(suffix, local_location, half_size):
        part = create_box(name + suffix, (0, 0, 0), half_size, color)
        part.parent = root
        part.location = local_location
        return part

    def add_sphere_part(suffix, local_location, radius):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=24,
            ring_count=12,
            radius=radius
        )
        part = bpy.context.active_object
        part.name = name + suffix
        part.parent = root
        part.location = local_location
        part.color = (color[0], color[1], color[2], 1)
        return part

    # 双腿从地面延伸到 0.46 * height；躯干延伸到 0.82 * height。
    add_box_part(
        "_BODY",
        (0, 0, height * 0.64),
        (height * 0.10, height * 0.065, height * 0.18)
    )

    # 头顶恰好位于 height，保持凤昭 1.75m、云笙 1.80m。
    head_radius = height * 0.09
    add_sphere_part(
        "_HEAD",
        (0, 0, height - head_radius),
        head_radius
    )

    # 身体朝 +Y 时，人物自身左侧为 -X，右侧为 +X。
    for side, sign in (("L", -1), ("R", 1)):
        add_sphere_part(
            "_SHOULDER_" + side,
            (sign * height * 0.13, 0, height * 0.765),
            height * 0.045
        )
        add_box_part(
            "_ARM_" + side,
            (sign * height * 0.13, 0, height * 0.60),
            (height * 0.035, height * 0.045, height * 0.165)
        )
        add_box_part(
            "_LEG_" + side,
            (sign * height * 0.06, 0, height * 0.23),
            (height * 0.045, height * 0.055, height * 0.23)
        )

    # 高亮胸前锥体：默认锥尖沿 +Z，绕 X 转 -90 度后指向局部 +Y。
    bpy.ops.mesh.primitive_cone_add(
        vertices=16,
        radius1=height * 0.045,
        radius2=0,
        depth=height * 0.14
    )
    front_marker = bpy.context.active_object
    front_marker.name = name + "_FRONT_MARKER"
    front_marker.parent = root
    front_marker.location = (0, height * 0.12, height * 0.70)
    front_marker.rotation_euler = (-math.pi / 2, 0, 0)
    front_marker.color = (1.0, 0.85, 0.05, 1)

    return root


def face_actor_toward(actor, target):
    """让当前无父级的角色 Root 以局部 +Y 朝向目标，只改变 Z 轴旋转。"""
    direction = target.location - actor.location
    if direction.x * direction.x + direction.y * direction.y < 1e-12:
        return

    actor.rotation_euler.z = math.atan2(-direction.x, direction.y)


def look_at(obj, target):

    direction = Vector(target) - obj.location

    obj.rotation_euler = direction.to_track_quat(
        '-Z',
        'Y'
    ).to_euler()


# =========================================================
# 创建房间
# =========================================================

# dimensions 为完整尺寸（米），create_box 接收半尺寸。
room = scene_config["room"]
room_width, room_depth, room_height = room["dimensions"]
floor_half = room["floor_thickness"] / 2
wall_half = room["wall_thickness"] / 2
create_box("ENV_FLOOR", (0, 0, -floor_half),
           (room_width / 2, room_depth / 2, floor_half), room["colors"]["floor"])
create_box("ENV_BACK_WALL", (0, room_depth / 2, room_height / 2),
           (room_width / 2, wall_half, room_height / 2), room["colors"]["back_wall"])
create_box("ENV_LEFT_WALL", (-room_width / 2, 0, room_height / 2),
           (wall_half, room_depth / 2, room_height / 2), room["colors"]["side_walls"])
create_box("ENV_RIGHT_WALL", (room_width / 2, 0, room_height / 2),
           (wall_half, room_depth / 2, room_height / 2), room["colors"]["side_walls"])


# =========================================================
# 桌案、人物：Proxy函数保持V01原样。
# =========================================================
table = scene_config["table"]
create_box(table["name"], table["position"],
           tuple(size / 2 for size in table["dimensions"]), table["color"])

actor_specs = {spec["id"]: spec for spec in scene_config["actors"]}
actors = {}
for actor_id, spec in actor_specs.items():
    actors[actor_id] = create_actor(spec["name"], spec["height"],
                                    spec["start_position"], spec["color"])


# =========================================================
# Blocking：只插入原有起终点位置关键帧，不改插值。
# =========================================================
for motion in scene_config["blocking"]:
    actor = actors[motion["actor"]]
    spec = actor_specs[motion["actor"]]
    scene.frame_set(motion["start_frame"])
    actor.location = spec["start_position"]
    actor.keyframe_insert(data_path="location")
    scene.frame_set(motion["end_frame"])
    actor.location = spec["end_position"]
    actor.keyframe_insert(data_path="location")

for facing in scene_config["facing"]:
    scene.frame_set(facing["frame"])
    actor = actors[facing["actor"]]
    face_actor_toward(actor, actors[facing["target"]])
    actor.keyframe_insert(data_path="rotation_euler", index=2, frame=facing["frame"])


# =========================================================
# 摄影机
# =========================================================

reference_camera = scene_config["reference_camera"]
bpy.ops.object.camera_add(location=reference_camera["position"])
camera = bpy.context.active_object
camera.name = reference_camera["name"]
camera.data.lens = reference_camera["lens_mm"]
look_at(camera, reference_camera["target"])

scene.camera = camera


# =========================================================
# 多机位自动切镜：保留 CAM_MASTER_50MM，新增五个剪辑机位。
# 坐标单位为米；共用场景的1080x1920、24fps及1-120帧设置。
# =========================================================

def create_shot_camera(name, lens, location, target):
    """复制参考机位的相机数据，建立独立的竖幅固定机位。"""
    shot_data = camera.data.copy()
    shot_data.name = name + "_DATA"
    shot_data.lens = lens
    shot_data.sensor_fit = 'VERTICAL'
    shot_data.sensor_height = 36.0

    shot_camera = bpy.data.objects.new(name, shot_data)
    bpy.context.collection.objects.link(shot_camera)
    shot_camera.location = location
    look_at(shot_camera, target)
    return shot_camera


# 镜头结束帧由下一镜开始帧减1得到；末镜使用项目结束帧。
# TEST01的机位、目标、切镜帧和Marker命名与V01完全相同。
shot_specs = []
for index, shot in enumerate(scene_config["cameras"]):
    end_frame = (scene_config["cameras"][index + 1]["start_frame"] - 1
                 if index + 1 < len(scene_config["cameras"]) else scene.frame_end)
    shot_specs.append((shot["name"], shot["lens_mm"], shot["position"],
                       shot["target"], shot["start_frame"], end_frame))

# 重复运行时只清理本切镜系统的旧 Marker，保留其他备注 Marker。
cut_marker_prefix = "PREVIZ_CUT_"
for marker in list(scene.timeline_markers):
    if marker.name.startswith(cut_marker_prefix):
        scene.timeline_markers.remove(marker)

shot_cameras = []
for name, lens, location, target, start_frame, end_frame in shot_specs:
    shot_camera = create_shot_camera(name, lens, location, target)
    shot_cameras.append(shot_camera)
    marker = scene.timeline_markers.new(
        f"{cut_marker_prefix}{name}_{start_frame:03d}_{end_frame:03d}",
        frame=start_frame
    )
    marker.camera = shot_camera

# 下一枚 Camera Marker 接管切镜；第五镜持续至原有结束帧120。
# 脚本末尾原有的 frame_set(1) 会回到第一镜。
scene.camera = shot_cameras[0]


# =========================================================
# 灯光
# =========================================================

bpy.ops.object.light_add(
    type='AREA',
    location=(0, -1.0, 4.0)
)

key_light = bpy.context.active_object
key_light.name = "LIGHT_KEY"

key_light.data.energy = 1200
key_light.data.shape = 'DISK'
key_light.data.size = 5


bpy.ops.object.light_add(
    type='AREA',
    location=(-3.0, 1.0, 2.5)
)

fill_light = bpy.context.active_object
fill_light.name = "LIGHT_FILL"

fill_light.data.energy = 500
fill_light.data.size = 4

look_at(
    fill_light,
    (0, 0.5, 1.0)
)


# =========================================================
# Viewport显示物体颜色
# =========================================================

# =========================================================
# 所有工作区的Viewport统一显示物体颜色
# =========================================================

for screen in bpy.data.screens:

    for area in screen.areas:

        if area.type == 'VIEW_3D':

            space = area.spaces.active

            space.shading.type = 'SOLID'
            space.shading.color_type = 'OBJECT'


# 回到项目开始帧
scene.frame_set(scene.frame_start)

print("AI PREVIZ TEST 01 创建完成")
