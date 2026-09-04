from pathlib import Path
from urllib.parse import unquote
import json, re, hashlib, sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
BASE = Path(__file__).resolve().parents[1]
EVIDENCE = BASE / '修订依据'
RECORD = EVIDENCE / '正式冻结记录.json'
DATE = '2026-09-05'
CONFIRMATION = '确认重新冻结'

def sha(b):
    return hashlib.sha256(b).hexdigest()

def readj(p):
    return json.loads(p.read_text(encoding='utf-8'))

if RECORD.exists():
    raise SystemExit('本轮重新冻结已有记录，不重复改写。')

manifest_path = EVIDENCE / '规范文件索引.json'
manifest = readj(manifest_path)
assert len(manifest) == 66
assert sum(m['status'] == '本轮修订待重新冻结' for m in manifest) == 63
for m in manifest:
    assert sha((BASE / m['relative_path']).read_bytes()) == m['output_sha256'], m['relative_path']

protected = readj(EVIDENCE / '原始资料校验.json')
for name, expected in protected.items():
    assert Path(name).is_file() and sha(Path(name).read_bytes()) == expected, name

updates = {}
backup = {}

def source(p):
    p = p.resolve()
    if p not in updates:
        b = p.read_bytes()
        backup[p.as_posix()] = {'text': b.decode('utf-8'), 'sha256': sha(b)}
        updates[p] = p.read_text(encoding='utf-8')
    return updates[p]

def edit(p, old, new, count=1):
    p = p.resolve()
    body = source(p)
    assert body.count(old) == count, (p.name, old[:100], body.count(old), count)
    updates[p] = body.replace(old, new)

norm_paths = [BASE / m['relative_path'] for m in manifest]
resource_paths = sorted((BASE / '通用约定').glob('*.md')) + sorted((BASE / '模板').glob('*.md'))
assert len(resource_paths) == 4
business_before = {p: p.read_text(encoding='utf-8').splitlines(keepends=True)[6:] for p in norm_paths}
resource_before = {p: p.read_text(encoding='utf-8').splitlines(keepends=True) for p in resource_paths}

for m in manifest:
    p = BASE / m['relative_path']
    if m['status'] == '本轮修订待重新冻结':
        edit(p, '> 状态：本轮涉及条款已局部解冻修订，待用户重新冻结；未涉及条款继续沿用既有冻结结论。',
             '> 状态：正式冻结。用户于2026-09-05确认本轮修订条款重新冻结；未涉及条款继续沿用既有冻结结论。依据见[重新冻结记录](../正式冻结记录.md)。')
        m['refrozen_date'] = DATE
        m['freeze_confirmation'] = CONFIRMATION
        m['freeze_basis'] = '本轮修订重新冻结；其余沿用既有冻结'
    else:
        m['freeze_basis'] = '沿用既有正式冻结结论，本轮没有业务变更'
    m['pre_refreeze_output_sha256'] = m['output_sha256']
    m['status'] = '正式冻结'

for p in resource_paths:
    if p.parent.name == '通用约定':
        edit(p, '版本：v1.0 修订稿。', '版本：v1.0 正式冻结版。')
        edit(p, '，待重新冻结。', '，用户于2026-09-05确认正式冻结。')
    else:
        edit(p, '状态：新系统模板修订稿，待用户重新冻结。', '状态：v1.0正式冻结版，用户于2026-09-05确认重新冻结。')

p = BASE / 'README.md'
edit(p, '# 小虫的影视生产流｜规范整合稿', '# 小虫的影视生产流｜正式冻结规范')
edit(p, '整理日期：2026-09-05。依据：用户“确认采用报告中的9项建议”。',
     '整理及重新冻结日期：2026-09-05。修订依据：用户“确认采用报告中的9项建议”；重新冻结依据：用户“确认重新冻结”。')
edit(p, '**本轮新增或修改的业务条款待用户重新冻结；没有变更的既有条款继续有效。**',
     '**本轮新增或修改的业务条款已正式重新冻结；没有变更的既有条款继续有效。**')
edit(p, '三份通用约定及一份模板同属本轮待重新冻结范围。', '63份规范的本轮修订、三份通用约定及一份模板均已重新冻结；66份规范现均具有正式冻结依据。')
edit(p, '含本轮修订，待重新冻结', '正式冻结（本轮重新冻结）', 21)
edit(p, '审阅本轮修订以本目录完整正文为准，按正文链接读取相关通用约定和模板，不再拼接历史补丁。尚未重新冻结的条款保留明确状态；重新冻结时只需覆盖本轮修订，不要求重审此前未变内容。之后制作部门Skill时，应从用户最终确认的本套规范生成，不能用审查副本或旧30项Skill替代。',
     '后续采用本目录的完整冻结正文，按正文链接读取相关通用约定和模板，不再拼接历史补丁。制作部门Skill时，从本套正式冻结规范生成，不能用审查副本或旧30项Skill替代。再次修改冻结业务条款，按用户明确授权范围局部解冻并记录。\n\n冻结范围、确认依据及文件核验见[正式冻结记录](正式冻结记录.md)。')

edit(BASE / '变更清单.md', '**修订已完成不等于重新冻结；本轮修改等待用户确认。**',
     '**用户已于2026-09-05确认本轮修订正式重新冻结，详见[冻结记录](正式冻结记录.md)。**')
edit(BASE / '修订依据索引.md', '本轮修订待重新冻结', '本轮修订已重新冻结（2026-09-05）', 63)
edit(BASE / '修订依据索引.md', '原文件未覆盖。', '原文件未覆盖。本轮修订已由用户于2026-09-05确认重新冻结，见[正式冻结记录](正式冻结记录.md)。')
edit(BASE / '横向复查结果.md', '本轮修订等待用户重新冻结。', '本轮修订已由用户于2026-09-05确认重新冻结。')
edit(BASE / '横向复查结果.md', '所有未改条款继续沿用此前冻结结论，本轮修改尚未重新冻结。',
     '所有未改条款继续沿用此前冻结结论，本轮修改已由用户于2026-09-05确认正式重新冻结。冻结时只更新状态、入口和记录，业务正文保持不变，见[正式冻结记录](正式冻结记录.md)。')
edit(BASE / '横向复查结果.md', '- 3份通用约定及1份模板已保存，559处本地链接均可定位。',
     '- 修订交付时，3份通用约定及1份模板已保存，559处本地链接均可定位；重新冻结后的当前链接核验另见冻结记录。')

p = BASE.parent / 'README.md'
edit(p, '**当前审阅入口：[规范整合稿](规范整合稿_2026-09-05/README.md)。**',
     '**当前正式入口：[冻结规范全文](规范整合稿_2026-09-05/README.md)。**')
edit(p, '其中 63 份规范包含本轮业务修订，相关条款及新增通用约定、模板待用户重新冻结；未涉及条款继续沿用既有冻结结论。专业顾问单元三份规范没有业务修改，仅统一标识。用户采用修订建议不自动等于最终稿重新冻结。',
     '用户已于2026-09-05明确“确认重新冻结”：63份规范的本轮修订条款、3份通用约定和1份模板正式重新冻结；专业顾问单元三份规范及其余未改条款沿用既有冻结结论。当前22个规范对象的66份规范均已正式冻结，记录见[正式冻结记录](规范整合稿_2026-09-05/正式冻结记录.md)。')
p = BASE.parent.parent / 'README.md'
edit(p, '2026-09-05 按用户确认的 9 项建议修订，涉及条款待重新冻结，其余沿用既有冻结结论。',
     '2026-09-05 按9项建议修订并经用户确认重新冻结；66份规范、3份通用约定及1份模板现已正式冻结。')
edit(p, '本轮审阅入口：[规范整合稿与变更清单]', '当前正式入口：[冻结规范与变更清单]')

# These historical builders write pre-freeze status. Preserve them, but prevent
# an accidental rerun from overwriting the now-frozen publication.
edit(EVIDENCE / '整理规范.py', "OUT = Path(__file__).resolve().parents[1]\n",
     "OUT = Path(__file__).resolve().parents[1]\nif (OUT / '修订依据/正式冻结记录.json').exists():\n    raise SystemExit('本套规范已正式冻结；历史整理脚本不再覆盖当前稿件。')\n")
edit(EVIDENCE / '核验交付.py', "evidence=root/'修订依据'\n",
     "evidence=root/'修订依据'\nif (evidence/'正式冻结记录.json').exists():\n    raise SystemExit('本套规范已正式冻结；本脚本仅用于冻结前核验，冻结后结果见正式冻结记录。')\n")

for p in norm_paths:
    candidate = updates.get(p.resolve(), p.read_text(encoding='utf-8'))
    assert candidate.splitlines(keepends=True)[6:] == business_before[p], p
for p in resource_paths:
    before = resource_before[p].copy()
    after = updates[p.resolve()].splitlines(keepends=True)
    before[2] = after[2] = ''
    assert before == after, p

source(manifest_path)
source(EVIDENCE / '交付核验结果.json')
backup_path = EVIDENCE / '重新冻结前状态备份.json'
assert not backup_path.exists()
backup_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
for p, body in updates.items():
    if p in [manifest_path.resolve(), (EVIDENCE/'交付核验结果.json').resolve()]: continue
    p.write_text(body, encoding='utf-8')
for m in manifest:
    m['output_sha256'] = sha((BASE / m['relative_path']).read_bytes())
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

frozen_files = []
for m in manifest:
    frozen_files.append({'path':m['relative_path'], 'status':'正式冻结', 'basis':m['freeze_basis'], 'sha256':m['output_sha256']})
for p in resource_paths:
    frozen_files.append({'path':p.relative_to(BASE).as_posix(), 'status':'正式冻结', 'basis':'用户确认本轮重新冻结', 'sha256':sha(p.read_bytes())})
freeze_record = {
    'system':'小虫的影视生产流', 'status':'正式冻结', 'date':DATE,
    'user_confirmation':CONFIRMATION, 'scope_basis':'上一轮交付的9项建议修订稿及对应通用约定和模板',
    'normative_documents':66, 'refrozen_normative_documents':63, 'inherited_frozen_documents':3,
    'common_contracts':3, 'templates':1, 'pending_freeze_count':0,
    'business_content_unchanged':True, 'files':frozen_files,
    'skills_installed_this_turn':False, 'runtime_integration_validated_this_turn':False,
    'old_30_skills_status':'继续封存'
}
RECORD.write_text(json.dumps(freeze_record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

freeze_md = '''# 小虫的影视生产流｜正式冻结记录

重新冻结日期：2026-09-05。用户确认原文：**“确认重新冻结”**。

确认对象为上一轮交付的9项建议修订稿，包括对应业务条款、通用约定和正式镜头Prompt模板。

| 范围 | 数量 | 当前状态 |
|---|---:|---|
| 包含本轮修订的岗位职责、执行流程及输出约定 | 63份 | 本轮修订正式重新冻结，其余条款沿用既有冻结 |
| 专业顾问单元三份规范 | 3份 | 沿用此前正式冻结结论，无业务变更 |
| 通用约定：任务启动与交接、共享能力调用、资产身份与引用 | 3份 | v1.0正式冻结 |
| 正式镜头Prompt模板 | 1份 | v1.0正式冻结 |

**当前22个规范对象的66份规范，以及3份通用约定和1份模板，均已正式冻结；本轮没有待冻结项。**

本次只更新冻结状态、规范入口、索引和确认记录。已审阅的业务正文、模板结构与固定限制保持不变。此前审查资料、已确认补充、共享能力文件及旧项目模板继续保留。

核验结果：__VERIFY__

后续规范采用及部门Skill制作统一以[本套冻结规范](README.md)为依据。冻结规范不等于Skill已制作、安装或联调完成；本次没有执行安装或生产模型验证。SKillXC的30项旧版生产与控制Skill继续封存。

- [逐文件冻结依据与校验记录](修订依据/正式冻结记录.json)
- [规范文件索引](修订依据/规范文件索引.json)
- [本轮变更清单](变更清单.md)
- [横向复查结果](横向复查结果.md)

原修订记录、差异和冻结前状态备份保留为历史依据，其中“待冻结”仅描述历史时点；当前状态以本记录和正文页头为准。历史整理与报告生成脚本已设冻结后停止写入，避免重新生成时覆盖当前冻结状态。
'''
(BASE/'正式冻结记录.md').write_text(freeze_md, encoding='utf-8')

# Verify only the concrete risks of a state-only publication change.
errors=[]
for p in norm_paths:
    if p.read_text(encoding='utf-8').splitlines(keepends=True)[6:] != business_before[p]:
        errors.append('规范正文发生变化：'+p.as_posix())
for p in resource_paths:
    before=resource_before[p].copy();after=p.read_text(encoding='utf-8').splitlines(keepends=True)
    before[2]=after[2]=''
    if before!=after:errors.append('资源正文发生变化：'+p.as_posix())
for f in frozen_files:
    if sha((BASE/f['path']).read_bytes())!=f['sha256']:errors.append('冻结校验值不一致：'+f['path'])
for name,expected in protected.items():
    if sha(Path(name).read_bytes())!=expected:errors.append('历史文件发生变化：'+name)

link_count=0
active_md=list(BASE.glob('*.md'))+norm_paths+resource_paths+[BASE.parent/'README.md',BASE.parent.parent/'README.md']
for p in active_md:
    body=p.read_text(encoding='utf-8')
    if re.search(r'待(?:用户)?重新冻结|本轮修订等待用户|本轮修改尚未重新冻结',body):
        errors.append('当前文件残留待冻结状态：'+p.as_posix())
    for m in re.finditer(r'(?<!!)\[[^\]\n]+\]\((<[^>]+>|[^)\n]+)\)',body):
        target=unquote(m.group(1).strip('<>')).split('#')[0]
        if not target or re.match(r'^[a-z]+://',target):continue
        q=Path(re.sub(r':\d+$','',target))
        if not q.is_absolute():q=p.parent/q
        link_count+=1
        if not q.exists():errors.append('失效链接：'+p.as_posix()+' -> '+target)

freeze_record['verification']={'frozen_files':len(frozen_files),'business_content_unchanged':not any('正文发生变化' in e for e in errors),'checked_local_links':link_count,'protected_files_unchanged':len(protected),'errors':errors}
RECORD.write_text(json.dumps(freeze_record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
prior=readj(EVIDENCE/'交付核验结果.json')
prior['pending_business_revision_documents']=0
prior['formal_frozen_documents']=66
prior['refreeze_date']=DATE
prior['refreeze_confirmation']=CONFIRMATION
prior['refreeze_verification']=freeze_record['verification']
prior['prior_revision_checked_links']=prior['checked_links']
prior['checked_links']=link_count
(EVIDENCE/'交付核验结果.json').write_text(json.dumps(prior,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
summary=(f'70份冻结文件已核对；业务正文未变化，{link_count}处本地链接可定位，{len(protected)}份受保护历史文件保持一致。' if not errors else '未通过：'+'；'.join(errors))
(BASE/'正式冻结记录.md').write_text(freeze_md.replace('__VERIFY__',summary),encoding='utf-8')
print(json.dumps({'status':'正式冻结' if not errors else '核验待修正','normative_documents':66,'refrozen_normative_documents':63,'common_contracts':3,'templates':1,'verification':freeze_record['verification']},ensure_ascii=False,indent=2))
if errors:raise SystemExit(1)
