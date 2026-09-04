from pathlib import Path
from urllib.parse import unquote
import json, re, hashlib, sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[1]
evidence=root/'修订依据'
if (evidence/'正式冻结记录.json').exists():
    raise SystemExit('本套规范已正式冻结；本脚本仅用于冻结前核验，冻结后结果见正式冻结记录。')
audit=root.parent/'横向拉通检查_2026-09-04'
def readjson(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(b):return hashlib.sha256(b).hexdigest()
manifest=readjson(evidence/'规范文件索引.json')
changes=readjson(evidence/'逐条修改记录.json')
sources=readjson(audit/'审查资料/冻结稿索引.json')
protected=readjson(evidence/'原始资料校验.json')
errors=[]

# Check full-document coverage and every actual written byte hash.
keys={(m['unit'],m['type']) for m in manifest}
if len(manifest)!=66 or len(keys)!=66:errors.append('66份规范覆盖不完整或存在重复。')
source_bodies={(s['unit'],s['type']):s['body'].replace('\r\n','\n').strip()+'\n' for s in sources}
replayed=source_bodies.copy()
for c in changes:
    if c['unit']=='模板':continue
    k=c['unit'],c['type']
    if replayed[k].count(c['before'])!=c['count']:
        errors.append('修改记录无法复原：'+str(k)+' '+c['reference']);continue
    replayed[k]=replayed[k].replace(c['before'],c['after'])
def normalized(body):
    body=body.split('\n',1)[1].lstrip('\n')
    body=re.sub(r'^> (?:所属系统：|状态：正式冻结|修订及重新冻结日期：|本稿为规范稿件).+\n?', '',body,flags=re.M)
    return body.replace('当前冻结候选稿确定的固定生产范围','本规范确定的固定生产范围').strip()+'\n'
for m in manifest:
    p=root/m['relative_path'];body=p.read_text(encoding='utf-8');k=m['unit'],m['type']
    if digest(p.read_bytes())!=m['output_sha256']:errors.append('保存文件校验不符：'+m['relative_path'])
    actual=body.split('\n\n',3)[3] if False else body[body.index('\n\n',body.index('> 正文及冻结来源'))+2:]
    if actual!=normalized(replayed[k]):errors.append('存在未列入修改记录的正文差异：'+m['relative_path'])
    pending=any(r.startswith('R') for r in m['references'])
    if pending and '待用户重新冻结' not in body.split('\n',4)[2]:errors.append('修订状态错误：'+m['relative_path'])
    if '当前冻结候选稿' in body or '本轮修订条款已由用户确认重新冻结' in body:errors.append('历史状态残留：'+m['relative_path'])

# Protected history, shared capability payloads and sealed old sources stay byte-identical.
for name,old_hash in protected.items():
    p=Path(name)
    if not p.exists() or digest(p.read_bytes())!=old_hash:errors.append('原始材料发生变化：'+name)

# Fixed generation limits remain verbatim in both template shapes.
template=(root/'模板/正式镜头Prompt模板_v1.0.md').read_text(encoding='utf-8')
old_path=next(Path(p) for p in protected if p.endswith('阶段3B_正式镜头Prompt交付模板.md'))
old_template=old_path.read_text(encoding='utf-8')
for label in ['光线规则：','字幕限制：','音乐限制：']:
    expected=next(l for l in old_template.splitlines() if l.startswith(label))
    if template.count(expected)!=2:errors.append('固定限制未完整保留：'+label)
for obsolete in ['阶段 2','阶段 3 参考资产负载闸门','未通过时先在代码块外拆分生成单元','必须先询问并取得用户对目标模型']:
    if obsolete in template:errors.append('旧模板行为残留：'+obsolete)

report='''# 小虫的影视生产流｜横向复查结果

复查日期：2026-09-05。范围：本轮9项建议对应的66份整合正文、3份通用约定和1份正式Prompt模板。

**9项建议已按对应条款位置落入完整稿件，关联接口已完成静态复查。本轮修订等待用户重新冻结。**

## 情境复查

以下是对规范路径的逐项核对，不是已运行部门Skill、创建真实生产任务或调用视频模型的结果。

| 情境 | 修订后路径与边界 | 主要依据 |
|---|---|---|
| 要求判断资产优先级，同时提到生产依赖 | 优先级单元只判断资产优先级；依赖按跨分支、资产分派和资产内部职责处理，不建立同级排序或固定批次 | [前期分控流程](前期准备分控/执行流程.md)、[优先级职责](资产生产优先级编排/岗位职责.md) |
| 已有资料，直接说“启动某执行单元” | 默认当前任务读取目标规范并承接，不强制创建新任务或用户手工复制 | [启动约定](通用约定/任务启动与交接.md) |
| 明确说“创建某单元任务” | 工具支持时创建并写入必要内容，按实际结果反馈；失败时交付已备妥文本，不虚报成功 | [资产分控流程](资产生产分控/执行流程.md)、[影视镜头分控流程](影视镜头生产分控/执行流程.md) |
| 在原执行入口拒绝额外能力 | 必要依据齐备且基础职责可完成时，继续原工作；同一有效授权范围不反复询问 | [共享调用约定](通用约定/共享能力调用.md) |
| 指定某共享能力版本及依赖 | 专业控制部经共享库返回候选，用户选定后实际读取准确版本，返回范围、位置和应用要点，原执行单元继续整合 | [专业控制部流程](专业控制部/执行流程.md)、[共享库输出](共享能力库/输出约定.md) |
| H3没有适配且可读的候选 | 源文件不混入可加载清单；说明缺口，必要装配依据齐备时继续现有方式，不以空清单阻塞用户 | [视频流程](视频生成综合执行/执行流程.md) |
| 首次生物或VFX制作尚无系统调用名 | 有唯一真实参考即可继续；生物基础首发可记无来源，变体保留实际来源；正式调用名留到明确登记任务建立 | [资产引用约定](通用约定/资产身份与引用.md)、[生物输出](生物、怪物与形态变体资产制作执行单元/输出约定.md)、[VFX流程](VFX资产制作执行单元/执行流程.md) |
| 含对白、音效与暗部的镜头组交给视频装配 | 分镜交付焦段、原台词与说话者、同期声位置、实际光源及受光、参考依据；待补项不冒充不需要，视频不补设计 | [分镜输出](分镜与镜头设计综合执行/输出约定.md)、[正式模板](模板/正式镜头Prompt模板_v1.0.md) |
| 能力入库时发现同版本内容不一致 | 共享库拒绝覆盖并返回冲突；建设单元不能先写目录或提前报完成；核验回执后才报实际入库情况 | [建设流程](专业能力建设单元/执行流程.md)、[共享库流程](共享能力库/执行流程.md) |
| 模块结束、任务中断或没有可写位置 | 正常保存完整快照后重新读取；不能保存则在当前任务交付完整快照，恢复时从实际文件或快照继续 | [分镜流程](分镜与镜头设计综合执行/执行流程.md)、[分镜输出](分镜与镜头设计综合执行/输出约定.md) |
| 装配模板仍有旧项目阶段与负载拆分要求 | 视频入口统一指向新系统v1.0模板；继承已确认模型，超限只报告受影响单元并交用户决定，固定限制保持原文 | [正式模板](模板/正式镜头Prompt模板_v1.0.md) |

## 文件与来源核验

__COUNTS__

完整逐处修改与来源见[变更清单](变更清单.md)、[修订依据索引](修订依据索引.md)；文件核验明细见[交付核验记录](修订依据/交付核验结果.json)。

## 当前状态

63份规范含本轮业务修订；专业顾问单元三份规范没有业务修改。三份通用约定与模板属于新增修订范围。所有未改条款继续沿用此前冻结结论，本轮修改尚未重新冻结。

本次实际完成的是文稿整合、文件写入及静态接口核验。没有安装部门Skill，没有运行自动跨任务调用链，也没有执行生成模型效果验证。共享库已有能力版本、待适配状态和SKillXC旧30项的封存状态保持原样。
'''
report_path=root/'横向复查结果.md'
report_path.write_text(report,encoding='utf-8')
# Make the evidence target available before validating all links; overwritten with final results below.
result_path=evidence/'交付核验结果.json'
result_path.write_text('{}\n',encoding='utf-8')
link_count=0
for p in list(root.rglob('*.md'))+[root.parent/'README.md',root.parent.parent/'README.md']:
    for m in re.finditer(r'(?<!!)\[[^\]\n]+\]\((<[^>]+>|[^)\n]+)\)',p.read_text(encoding='utf-8')):
        target=unquote(m.group(1).strip('<>')).split('#')[0]
        if not target or re.match(r'^[a-z]+://',target):continue
        target=re.sub(r':\d+$','',target);q=Path(target)
        if not q.is_absolute():q=p.parent/q
        link_count+=1
        if not q.exists():errors.append('失效链接：'+str(p)+' -> '+target)
result=dict(documents=len(manifest),unique_documents=len(keys),pending_business_revision_documents=sum(m['status']=='本轮修订待重新冻结' for m in manifest),common_contracts=3,templates=1,logged_changes=len(changes),checked_links=link_count,protected_files=len(protected),protected_files_unchanged=not any('原始材料发生变化' in x for x in errors),body_replay_and_hashes_verified=not any(any(s in e for s in ['正文差异','校验不符','修改记录无法复原']) for e in errors),errors=errors,validation_kind='实际文件核验与规范静态情境复查；未运行生产Skill或生成模型')
result_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
counts=f'''- 22个规范对象、66份岗位职责／执行流程／输出约定：全部存在并已重新读取；文件校验值与索引一致。
- {len(changes)}条逐处修改记录（含历史补充、重复出现位置和模板修订）：可据来源逐步复原完整正文；除已列明修改及系统标识、状态整理外，没有未记录的正文差异。
- 3份通用约定及1份模板已保存，{link_count}处本地链接均可定位。
- {len(protected)}个受保护原始文件的内容校验保持一致，覆盖原审查资料、此前12份修订稿及其总览、共享能力库、封存SKillXC资料和旧项目来源模板。
- 新模板的连续单镜头与镜头组均逐字保留原有光线、字幕、音乐固定限制；旧阶段指称、重复询问模型和自动拆分规则已清除。
- 核验结果：{'通过。' if not errors else '存在待处理问题：'+'；'.join(errors)}'''
report_path.write_text(report.replace('__COUNTS__',counts),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
if errors:raise SystemExit(1)
