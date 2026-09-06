# GPT-6 Astra 与 Blender 优化依据

核对日期：2026-09-07。以下只记录官方资料与由其推导出的本 Skill 架构决定，不把发布演示当作影视预演质量保证。

## 官方资料

- OpenAI 的 GPT-6 Astra 发布页把在 Blender 中建模并继续送入 Unreal Engine 5 作为端到端电脑工作的公开示例：<https://openai.com/index/gpt-6-astra/>
- GPT-6 Astra 模型页列出长上下文、电脑使用和不同推理强度：<https://developers.openai.com/api/docs/models/gpt-6-astra>
- Codex 官方说明本地任务可以直接在用户电脑的文件夹、仓库和工具中工作：<https://help.openai.com/en/articles/20001275/>
- Blender 5.2 官方建议用后台命令行运行自动化脚本，并把新的 `.blend`、渲染图和文本作为迭代结果保存：<https://docs.blender.org/api/5.2/info_tips_and_tricks.html>
- Blender 5.2 官方说明 Workbench 面向布局、建模和预览：<https://docs.blender.org/manual/en/5.2/render/introduction.html>
- Blender 5.2 官方建议动画先渲染静态图像序列，再编码为视频，以便断点恢复和更换编码：<https://docs.blender.org/manual/en/5.2/render/output/properties/output.html>

## 对本工作流的实际优化

1. 模型负责理解局部分镜、空间推理、生成配置与代码、阅读结果和提出修正；Blender 负责确定性场景计算与渲染。不要把聊天记忆或界面点击历史当作工程真源。
2. 正式依据写入版本化 JSON、外部 Python、运行清单和结构化报告。即使使用 Astra 的长上下文，新任务仍须实际读取用户带入的分镜锚点与资产路径。
3. 默认后台运行，从工厂场景开始，并关闭工程内嵌脚本自动执行；用户只需首次启动或需要人工观察时打开 Blender。
4. 每次使用独立运行编号，先保存新的 `.blend` 和 PNG 帧序列，再编码 MP4。不能仅凭进程返回码判断成功，必须同时检查场景报告与目标文件。
5. 预演默认使用 Workbench，以人物站位、动线、遮挡与相机关系的可读性优先。需要验证灯光或真实材质时另建明确的高质量测试，不污染 Blocking 预演。
6. 一般局部镜头使用中等或高推理强度即可；多人复杂调度、长路径连续性或多重遮挡问题再使用更高推理强度。模型选择不写死在 Skill 内。
7. 结果回写采用显式交接包：原镜头编号、本地帧映射、准确时长、输入版本、运行版本、视频参考用途和禁止继承项。长上下文不能替代跨任务交接。
