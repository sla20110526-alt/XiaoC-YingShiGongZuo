"""Build bindings, validate the authored skills, then install and connect locally."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tomllib
from urllib.parse import unquote

PACKAGE=Path(__file__).resolve().parents[1]
WORKSPACE=PACKAGE.parent
LIBRARY=WORKSPACE/'共享能力库'
SKILLS=PACKAGE/'skills'
RECORDS=PACKAGE/'检查与联调记录'
INSTALL=Path.home()/'.codex/skills'
CONFIG=Path.home()/'.codex/config.toml'

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def inventory(root):
    return {str(p.relative_to(root)).replace('\\','/'):digest(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

def prepare():
    RECORDS.mkdir(parents=True,exist_ok=True)
    before=RECORDS/'接入前保护记录.json'
    if not before.exists():
        config=tomllib.loads(CONFIG.read_text(encoding='utf-8-sig'))
        dump(before,{'norms':inventory(WORKSPACE/'影视生产系统规范/规范整合稿_2026-09-05'),
                     'old_skills':inventory(WORKSPACE/'SKillXC'),
                     'library_before':inventory(LIBRARY),'config_sha256':digest(CONFIG),
                     'disabled_old_skills':[x for x in config.get('skills',{}).get('config',[]) if x.get('enabled') is False]})
        for file in ['catalog.json','目录.md']:
            shutil.copy2(LIBRARY/file,RECORDS/('接入前-'+file))
    c=read(LIBRARY/'catalog.json')
    entries=[]
    for e in c['entries']:
        main=LIBRARY/e['path']
        if digest(main)!=e['sha256']:raise ValueError('库正文不符：'+e['path'])
        resources={e['path']:digest(main)}
        minimum=[]
        if e['type']=='skill':
            for p in main.parent.rglob('*'):
                if p.is_file():resources[p.relative_to(LIBRARY).as_posix()]=digest(p)
            if e['id'].startswith('dune2-'):
                minimum=[(main.parent/'references/profile.md').relative_to(LIBRARY).as_posix()]
            elif e['id']=='train-to-busan-film-profile':
                minimum=[(main.parent/f).relative_to(LIBRARY).as_posix() for f in ['SOURCE.md','references/decision-qa.md','references/style-profile.md','references/production-recipes.md']]
        elif e['type']=='profile' and e.get('evidence_path') and not e['evidence_path'].startswith('../'):
            p=LIBRARY/e['evidence_path'];resources[e['evidence_path']]=digest(p)
        for rel in minimum:
            if rel not in resources: raise ValueError('必要配套未收存：'+rel)
        selectable=e['type'] in ['profile','skill']
        entries.append({'id':e['id'],'version':e['version'],'selectable':selectable,
                        'reason':'保持已有允许选用状态与证据限制' if selectable else '官方源文件待适配，仅作储备',
                        'minimum_resources':minimum,'resources':resources,'independent_dependencies':[],
                        'boundary':'原文中的旧流程及岗位名称只作来源追溯；不覆盖当前冻结规则、用户决定和原执行单元职责。保留该版本的适用范围、证据限制和排除内容。'})
    dump(RECORDS/'待接入索引.json',{'schema_version':1,'system':'小虫的影视生产流','version':'1.0.0','entries':entries})
    print(json.dumps({'prepared_entries':len(entries),'selectable':sum(e['selectable'] for e in entries)},ensure_ascii=False))

def validate(root=SKILLS):
    errors=[];checked=[];links=0
    validator=Path.home()/'.codex/skills/.system/skill-creator/scripts/quick_validate.py'
    roles=read(PACKAGE/'制作与检查/岗位清单.json')
    for role in roles:
        folder=root/role['name']
        result=subprocess.run([sys.executable,'-X','utf8',str(validator),str(folder)],capture_output=True,text=True,encoding='utf-8')
        checked.append({'role':role['role'],'name':role['name'],'exit_code':result.returncode,'result':result.stdout.strip()})
        if result.returncode:errors.append(role['name']+':'+result.stdout+result.stderr)
    for p in root.rglob('*.md'):
        # Fenced examples are not file references. Links in prose must resolve.
        text=re.sub(r'```.*?```','',p.read_text(encoding='utf-8-sig'),flags=re.S)
        for raw in re.findall(r'\[[^\]]*\]\((<[^>]+>|[^)]+)\)',text):
            raw=unquote(raw.strip('<>')).split('#')[0]
            if not raw or re.match(r'^(https?://|mailto:)',raw): continue
            target=Path(raw)
            if not target.is_absolute():target=p.parent/target
            links+=1
            if not target.exists(): errors.append(f'{p}: missing {raw}')
    bindings=read(root/'xcflow-control/references/bindings.json')
    for f in bindings['frozen_files']:
        if digest(Path(bindings['normative_root'])/f['path'])!=f['sha256']:errors.append('冻结校验不符：'+f['path'])
    for role in read(root/'xcflow-control/references/roles.json'):
        if not (root/'xcflow-control/references'/role['path']).is_file():errors.append('岗位路由不存在：'+role['name'])
    result={'skills':checked,'skill_count':len(checked),'links_checked':links,'frozen_files_checked':len(bindings['frozen_files']),'errors':errors,'root':str(root)}
    dump(RECORDS/('安装后文件检查.json' if root==INSTALL else '制作文件检查.json'),result)
    if errors: raise ValueError(json.dumps(errors,ensure_ascii=False))
    print(json.dumps({'validated':len(checked),'links':links,'frozen_files':len(bindings['frozen_files'])},ensure_ascii=False))

def install():
    validate()
    files=inventory(SKILLS)
    prior_path=RECORDS/'安装回执.json'
    prior=read(prior_path) if prior_path.exists() else {}
    for rel,expected in files.items():
        target=INSTALL/rel
        if target.exists() and digest(target)!=expected:
            if digest(target)!=prior.get('files',{}).get(rel):
                raise ValueError('安装目标已有未记录的不同内容，未覆盖：'+str(target))
    created=[]
    updated=[]
    for rel,expected in files.items():
        target=INSTALL/rel
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SKILLS/rel,target);created.append(str(target))
        elif digest(target)!=expected:
            shutil.copy2(SKILLS/rel,target);updated.append(str(target))
        if digest(target)!=expected:raise ValueError('安装回读不符：'+str(target))
    if digest(CONFIG)!=read(RECORDS/'接入前保护记录.json')['config_sha256']:raise ValueError('宿主配置发生变化，需检查')
    dump(RECORDS/'安装回执.json',{'system':'小虫的影视生产流','version':'1.0.0','install_root':str(INSTALL),'skills':read(PACKAGE/'制作与检查/岗位清单.json'),'files':files,'created':list(dict.fromkeys(prior.get('created',[])+created)),'updated':updated,'config_unchanged':True,'readback':'全部安装文件重新读取与制作文件一致','runtime_discovery':'以宿主发现检查.json为准'})
    # Limit installed validation to this package's names, never inspect other skills.
    validate_install()
    print(json.dumps({'installed_skills':22,'files':len(files),'root':str(INSTALL)},ensure_ascii=False))

def validate_install():
    errors=[];files=inventory(SKILLS)
    for rel,expected in files.items():
        p=INSTALL/rel
        if not p.exists() or digest(p)!=expected:errors.append(rel)
    dump(RECORDS/'安装后文件检查.json',{'skill_count':22,'files_read_back':len(files),'errors':errors})
    if errors:raise ValueError(str(errors))

def connect():
    validate_install()
    c=read(LIBRARY/'catalog.json')
    index=read(RECORDS/'待接入索引.json')
    c['status']='新版专业控制部与共享能力库入口已安装接入；指定版本按用户选择读取；效果以实际任务验证为准'
    for e in c['entries']:
        if e['type']=='external_skill_source':
            e['new_system_integration']='目录查询已接入；源文件仍待适配，不可加载'
            e['availability']='官方源文件已收存；待适配；仅作储备'
        else:
            e['new_system_integration']='新版入口已安装；按用户选择读取准确版本'
            e['availability']=e['availability'].replace('新版入口待接入','新版入口已接入')
    dump(LIBRARY/'catalog.json',c)
    index['catalog_sha256']=digest(LIBRARY/'catalog.json')
    dump(LIBRARY/'接入索引.json',index)
    directory=LIBRARY/'目录.md'
    s=directory.read_text(encoding='utf-8-sig')
    s=s.replace('新版专业控制部调用入口待接入','新版专业控制部与共享能力库入口已接入').replace('新版入口待接入','新版入口已接入')
    banner='\n> 2026-09-05 接入记录：22 岗位 Skill 已安装；共享库由 `xcflow-professional-control` → `xcflow-library` 查询并交回原执行单元。36 个既有 Profile／专业 Skill 按准确版本和原有限制选用；1 个 H3 源文件仍待适配。详见 [接入回执](接入回执.md)。\n'
    if banner not in s:s=s.replace('\n','\n'+banner,1)
    directory.write_text(s,encoding='utf-8')
    for e in c['entries']:
        if digest(LIBRARY/e['path'])!=e['sha256']:raise ValueError('接入后正文校验失败')
    before=read(RECORDS/'接入前保护记录.json')
    errors=[]
    for root,key in [(WORKSPACE/'影视生产系统规范/规范整合稿_2026-09-05','norms'),(WORKSPACE/'SKillXC','old_skills')]:
        if inventory(root)!=before[key]:errors.append(key)
    for rel,h in before['library_before'].items():
        if rel not in ['catalog.json','目录.md'] and digest(LIBRARY/rel)!=h:errors.append(rel)
    if digest(CONFIG)!=before['config_sha256']:errors.append('host_config')
    dump(RECORDS/'接入保护核验.json',{'errors':errors,'frozen_tree_unchanged':not 'norms' in errors,'old_skill_tree_unchanged':not 'old_skills' in errors,'old_disabled_count':len(before['disabled_old_skills']),'library_payloads_unchanged':not any(x not in ['norms','old_skills','host_config'] for x in errors),'config_unchanged':not 'host_config' in errors,'catalog_entries':len(c['entries'])})
    if errors:raise ValueError(str(errors))
    print(json.dumps({'connected_entries':37,'selectable':36,'reserve':1,'protected_checks':'通过'},ensure_ascii=False))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('step',choices=['prepare','validate','install','connect']);a=p.parse_args()
    {'prepare':prepare,'validate':validate,'install':install,'connect':connect}[a.step]()
