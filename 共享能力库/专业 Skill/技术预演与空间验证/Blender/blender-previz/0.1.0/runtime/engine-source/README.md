# Blender AI Previz Engine v0.1.0

本目录是“小虫的影视生产流”中 `blender-previz` 专业 Skill 候选的本机执行引擎。它把助手根据局部分镜生成的 JSON 和 Blender Python 转为可复核的场景、关键帧和预演视频；用户不需要编写 JSON、建模或手改 Blender。

## 使用边界

- 只处理用户点名的疑难镜头或局部人物动线，不自动预演整场。
- 人物站位与动线优先，其次检查遮挡、构图、景别、机位、焦段、轴线和运镜。
- 每次运行使用新的 `run-id`，已有结果目录会拒绝覆盖。
- 预演代理模型用于空间验证，不代表最终人物外观、材质、灯光或美术风格。
- 创作性镜头修改回到分镜设计确认；本引擎只执行已确认设计和技术修正。

## 目录

```text
AI_PREVIZ_SYSTEM/
├── blender/scene_builder.py        # Blender 场景构建源
├── engine/blender_driver.py        # 后台构建、保存、抽帧和渲染驱动
├── schemas/previz-scene-v0.1.schema.json
├── examples/selected-shot.json     # 单个疑难镜头及原镜头编号映射示例
├── projects/TEST01/scene.json      # 初始测试输入，保留原成果
├── run_previz.py                   # 每次运行入口
└── runs/                           # 独立运行结果，不纳入版本库
```

## 运行

```powershell
python .\run_previz.py --config .\projects\TEST01\scene.json --run-id TEST01-v001 --render
```

成功后生成：

- `previz.blend`
- `render_frames/*.png` 与 `previz.mp4`（使用 `--render` 时）
- `frames/*.png`（各镜头代表帧）
- `scene-report.json`
- `previz-manifest.json`
- `blender.log`
- `previz-report.md`

默认绑定 `D:\002-工具\blender.exe`，也可用 `--blender` 或环境变量 `BLENDER_EXE` 重绑。后台启动会使用工厂设置并关闭工程内嵌脚本的自动执行；实际执行的是本仓库显式指定的驱动与构建脚本。动画先渲染为可恢复的 PNG 帧序列，再由 ffmpeg 编码为 MP4；单帧失败时不必重渲全部内容。
