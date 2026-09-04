# MiniMax H3：h3-prompt-writing 入库说明

## 来源与版本

- 来源：[MiniMax-AI / MiniMax-H3 官方仓库](https://github.com/MiniMax-AI/MiniMax-H3)。
- 上游路径：`skills/h3-prompt-writing`。
- 下载分支：`main`，固定到提交 `d21241f0a4b3acbb34c97dae47fa417b7065e438`。
- 固定版本入口：[官方 SKILL.md](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/SKILL.md)。
- 入库日期：2026-09-04。
- 本地入口：[h3-prompt-writing/SKILL.md](./h3-prompt-writing/SKILL.md)。
- 状态：官方原版收存，供后续专业 Skill 调用包适配。

## 本次确定的入口安排

- 视频生成综合执行单元继承已经确认的目标模型及模式。
- 目标为 MiniMax H3 时，入口询问用户是否选择“Prompt 装配与目标模型适配”类 Skill；本资源作为对应候选。
- Seedance 2.0、Seedance 2.5 按已确定的现有方式装配。
- 本资源归入专业 Skill，而不是大师风格 Profile。

这里记录的是后续调用包的接入依据，收存本身不启用原版指令。

## 官方文件

完整保留所选上游 Skill 目录中的四个文件：

- `h3-prompt-writing/SKILL.md`
- `h3-prompt-writing/agents/openai.yaml`
- `h3-prompt-writing/references/base-en.txt`
- `h3-prompt-writing/references/ref-en.txt`

全能参考模式的主要说明位于 `references/ref-en.txt`；其中的基础镜头、运镜、对白和声音写法还引用 `references/base-en.txt`。

## 接入时需衔接的已有规则

1. 原版要求英文六段输出，并使用 `<Subject N>`、`<Picture N>`、`<Video N>`、`<Audio N>` 等标签。后续需明确与现有正式 Prompt 模板及资产引用规范的衔接方式；本次未改动任一方。
2. 原版示例使用带小数的时间格式；项目镜头时长仍以 0.5 秒为最小单位。显示格式与镜头设计精度需要区分。
3. 接入范围为已确认分镜内容的 Prompt 装配与模型表达适配，沿用用户已确定的修改权限。

## 校验记录

四个文件均与上述固定提交的官方原始文件逐字节哈希比对一致；主文件引用的两份参考说明均已随目录收存。

| 文件 | SHA-256 |
| --- | --- |
| `SKILL.md` | `A7000443588CA3F145E3B3FD8900F14E0325DC460BD811268FAC89A9DC8E56D0` |
| `agents/openai.yaml` | `7770C9D784B7251AB882EE29A738219A3F01811E57BA7FC7822FA83EB8438C1A` |
| `references/base-en.txt` | `2CFEBC096A6E08370F288D468D90B60F7F9BCB938F94BF090816E910E48E75FC` |
| `references/ref-en.txt` | `1E574F356716AD55612247FFB7BBCCBCDB484AD96599D63C7DCA1AF186B1FAB7` |

本地 skill-creator 的 `quick_validate.py` 未通过，报告原版头部的 `compatibility` 不在其允许字段中。该结果已保留，不为通过本地校验而修改官方原版；正式制作调用包时再处理运行适配。文件完整性通过不等于生成效果已验证。

所收存目录及所查看的该提交仓库根目录未发现独立 LICENSE 文件；后续再分发调用包前需核实适用许可。
