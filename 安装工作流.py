"""Check the complete repository and bind its 22 skills to this computer."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parent
PACKAGE=ROOT/'小虫的影视生产流-Skills'
SKILLS=PACKAGE/'skills'
NORMS=ROOT/'影视生产系统规范/规范整合稿_2026-09-05'
LIBRARY=ROOT/'共享能力库'
VERSION='1.0.1'
LINK=re.compile(r'\[([^\]]*)\]\((<[^>]+>|[^)]+)\)')

def sha(data):return hashlib.sha256(data).hexdigest()
def read_json(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def json_bytes(obj):return (json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def local_path(base,raw):
    p=Path(raw)
    return (p if p.is_absolute() else base/p).resolve()
def repo_file(relative):
    p=(ROOT/relative).resolve()
    if not p.is_relative_to(ROOT):raise ValueError('目录记录越出本仓库：'+str(relative))
    if not p.is_file():raise ValueError('必需文件缺失：'+str(relative))
    return p
def skills_dir(override=None):
    if override:return Path(override).expanduser().resolve()
    codex_home=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex').expanduser()
    return (codex_home/'skills').resolve()

def source_files():
    return [p for p in SKILLS.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']

def check_package():
    errors=[]
    frozen=read_json(NORMS/'修订依据/正式冻结记录.json')
    for f in frozen['files']:
        p=NORMS/f['path']
        if not p.is_file() or sha(p.read_bytes())!=f['sha256']:errors.append('冻结文件校验失败：'+f['path'])
    catalog=read_json(LIBRARY/'catalog.json')
    index=read_json(LIBRARY/'接入索引.json')
    if sha((LIBRARY/'catalog.json').read_bytes())!=index.get('catalog_sha256'):errors.append('共享目录与接入索引不同步')
    resources={}
    for e in index['entries']:resources.update(e['resources'])
    for e in catalog['entries']:resources[e['path']]=e['sha256']
    for relative,expected in resources.items():
        p=repo_file('共享能力库/'+relative)
        if sha(p.read_bytes())!=expected:errors.append('共享能力校验失败：'+relative)
    roles=read_json(PACKAGE/'制作与检查/岗位清单.json')
    if len(roles)!=22 or len({e['name'] for e in roles})!=22:errors.append('岗位数量或唯一性不符')
    links=0
    for role in roles:
        p=repo_file('小虫的影视生产流-Skills/skills/'+role['name']+'/SKILL.md')
        text=p.read_text(encoding='utf-8-sig')
        if not text.startswith('---\n') or not re.search(r'^name: '+re.escape(role['name'])+r'$',text,re.M):errors.append('Skill 名称或文件头不符：'+role['name'])
        if not re.search(r'^description: .+',text,re.M):errors.append('缺少用途描述：'+role['name'])
    for p in source_files():
        if p.suffix!='.md':continue
        text=re.sub(r'```.*?```','',p.read_text(encoding='utf-8-sig'),flags=re.S)
        for match in LINK.finditer(text):
            raw=unquote(match.group(2).strip('<>')).split('#',1)[0]
            if not raw or re.match(r'^(https?://|mailto:)',raw):continue
            target=local_path(p.parent,raw);links+=1
            if not target.is_relative_to(ROOT) or not target.exists():errors.append('运行引用不可用：'+str(p.relative_to(ROOT))+' → '+raw)
    bindings_file=SKILLS/'xcflow-control/references/bindings.json'
    bindings=read_json(bindings_file)
    for key,wanted in [('workspace',ROOT),('normative_root',NORMS),('library_root',LIBRARY)]:
        if local_path(bindings_file.parent,bindings[key])!=wanted:errors.append('可移植绑定错误：'+key)
    result={'version':VERSION,'skills':len(roles),'frozen_files':len(frozen['files']),'shared_entries':len(catalog['entries']),
            'selectable_entries':sum(e['selectable'] for e in index['entries']),'runtime_links':links,'verified_resources':len(resources),'errors':errors}
    if errors:raise ValueError(json.dumps(result,ensure_ascii=False,indent=2))
    return result

def render(src,destination):
    rel=src.relative_to(SKILLS)
    if rel.as_posix()=='xcflow-control/references/bindings.json':
        value=read_json(src)
        value.update({'workspace':str(ROOT),'normative_root':str(NORMS),'library_root':str(LIBRARY),'version':VERSION})
        return json_bytes(value)
    data=src.read_bytes()
    if src.suffix!='.md':return data
    text=data.decode('utf-8-sig')
    def replace(match):
        raw=unquote(match.group(2).strip('<>'))
        path,separator,fragment=raw.partition('#')
        if not path or re.match(r'^(https?://|mailto:)',path):return match.group(0)
        target=local_path(src.parent,path)
        if target.is_relative_to(SKILLS):
            installed=destination/target.relative_to(SKILLS)
            address=Path(os.path.relpath(installed,(destination/rel).parent)).as_posix()
        elif target.is_relative_to(ROOT):address=target.as_posix()
        else:raise ValueError('不安装库外文件引用：'+path)
        if separator:address+='#'+fragment
        return f'[{match.group(1)}](<{address}>)'
    return LINK.sub(replace,text).encode('utf-8')

def check_install(destination):
    errors=[];checked=0
    for src in source_files():
        target=destination/src.relative_to(SKILLS);checked+=1
        if not target.is_file() or target.read_bytes()!=render(src,destination):errors.append(str(target))
    return {'installed_files':checked,'errors':errors,'matches_this_repository':not errors}

def install(destination):
    checked=check_package()
    files={p.relative_to(SKILLS).as_posix():render(p,destination) for p in source_files()}
    roles=read_json(PACKAGE/'制作与检查/岗位清单.json')
    # A same-name unrelated skill is never overwritten. Existing xcflow edits are backed up.
    for r in roles:
        target=destination/r['name']
        if target.exists():
            entry=target/'SKILL.md'
            if not entry.is_file():raise ValueError('同名文件夹没有本系统入口，未覆盖：'+str(target))
            text=entry.read_text(encoding='utf-8-sig')
            if '小虫的影视生产流' not in text or not re.search(r'^name: '+re.escape(r['name'])+r'$',text,re.M):
                raise ValueError('同名 Skill 不属于本系统，未覆盖：'+str(target))
    changed=[rel for rel,data in files.items() if (destination/rel).exists() and (destination/rel).read_bytes()!=data]
    backup=None
    if changed:
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup=destination.parent/'xcflow-backups'/stamp
        for rel in changed:
            target=backup/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(destination/rel,target)
    written=0
    for rel,data in files.items():
        target=destination/rel
        if not target.exists() or target.read_bytes()!=data:
            target.parent.mkdir(parents=True,exist_ok=True)
            temp=target.with_name(target.name+'.xcflow-writing')
            with temp.open('xb') as f:f.write(data)
            os.replace(temp,target);written+=1
        if target.read_bytes()!=data:raise ValueError('安装回读不一致：'+str(target))
    check=check_install(destination)
    if check['errors']:raise ValueError(str(check['errors']))
    receipt={'system':'小虫的影视生产流','version':VERSION,'repository':str(ROOT),'installed_to':str(destination),
             'time_utc':datetime.now(timezone.utc).isoformat(),'skills':22,'files':{rel:sha(data) for rel,data in files.items()},
             'written_files':written,'backup':str(backup) if backup else None,'package_check':checked,'readback':check,
             'host_config_changed':False,'runtime_discovery':'文件已安装并回读；宿主技能发现需由当前 Codex 确认，不据此声明工作电脑已运行生产任务'}
    destination.mkdir(parents=True,exist_ok=True)
    receipt_path=destination/'.xcflow-install-receipt.json';receipt_path.write_bytes(json_bytes(receipt))
    return {'status':'安装与路径绑定完成','version':VERSION,'skills':22,'installed_to':str(destination),'written_files':written,
            'backup':receipt['backup'],'receipt':str(receipt_path),'next':'在 Codex 中读取 xcflow-control 的 SKILL.md，启动总控；如技能列表未刷新，重新打开任务。'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['check','install','check-installed'])
    parser.add_argument('--skills-dir',help='Optional destination; defaults to CODEX_HOME/skills or ~/.codex/skills')
    args=parser.parse_args();destination=skills_dir(args.skills_dir)
    if args.action=='check':result=check_package()
    elif args.action=='install':result=install(destination)
    else:
        check_package();result=check_install(destination)
        if result['errors']:print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(1)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    try:main()
    except (OSError,ValueError,KeyError) as e:
        print('未完成：'+str(e));raise SystemExit(1)
