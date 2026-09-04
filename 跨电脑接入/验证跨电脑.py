"""Verify relocation and isolated user installation without changing the real host."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def run(repo,args,env=None):
    p=subprocess.run([sys.executable,str(repo/'安装工作流.py'),*args],capture_output=True,text=True,encoding='utf-8',env=env,timeout=45)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return json.loads(p.stdout)

def main():
    local=ROOT/'.xcflow-local';local.mkdir(exist_ok=True)
    observations=[]
    with tempfile.TemporaryDirectory(prefix='portable-',dir=local,ignore_cleanup_errors=True) as temporary:
        temp=Path(temporary).resolve();assert temp.is_relative_to(local.resolve())
        repo_a=temp/'工作电脑 A'/'影视 工作流'
        repo_b=temp/'工作电脑 B'/'另一个目录'
        ignore=shutil.ignore_patterns('.git','.xcflow-local','__pycache__','*.pyc')
        shutil.copytree(ROOT,repo_a,ignore=ignore)
        destination=temp/'独立用户'/'codex-home'/'skills'
        env=dict(os.environ);env['CODEX_HOME']=str(destination.parent)
        checked=run(repo_a,['check'])
        observations.append({'case':'复制到含中文和空格的新路径','passed':checked['skills']==22 and not checked['errors'],'observed':checked})
        first=run(repo_a,['install'],env)
        observations.append({'case':'通过 CODEX_HOME 安装到隔离用户目录','passed':Path(first['installed_to'])==destination and first['skills']==22})
        repeated=run(repo_a,['install'],env)
        observations.append({'case':'同一位置重复安装不重写','passed':repeated['written_files']==0})
        installed=run(repo_a,['check-installed'],env)
        observations.append({'case':'已安装文件和本机路径实际回读','passed':installed['matches_this_repository'],'observed':installed})
        script=destination/'xcflow-library/scripts/library.py'
        p=subprocess.run([sys.executable,str(script),'query'],cwd=temp,capture_output=True,text=True,encoding='utf-8',env=env,timeout=15)
        data=json.loads(p.stdout)
        observations.append({'case':'从任意当前目录读取本机绑定的共享库','passed':p.returncode==0 and len(data.get('candidates',[]))==36 and len(data.get('reserves',[]))==1})
        # Source skills can also locate the adjacent repository before a global install.
        p=subprocess.run([sys.executable,str(repo_a/'小虫的影视生产流-Skills/skills/xcflow-library/scripts/library.py'),'query','--model','MiniMax H3'],cwd=temp,capture_output=True,text=True,encoding='utf-8',timeout=15)
        data=json.loads(p.stdout)
        observations.append({'case':'仓库原始入口相对定位及 H3 储备隔离','passed':p.returncode==0 and len(data['candidates'])==0 and len(data['reserves'])==1})
        # Rebind the same isolated installation to a second checkout.
        shutil.copytree(ROOT,repo_b,ignore=ignore)
        moved=run(repo_b,['install'],env)
        bindings=json.loads((destination/'xcflow-control/references/bindings.json').read_text(encoding='utf-8'))
        observations.append({'case':'更换仓库目录后重绑并备份旧安装','passed':Path(bindings['workspace'])==repo_b and moved['backup'] is not None and Path(moved['backup']).is_dir()})
        observations.append({'case':'更换位置后所有文件仍一致','passed':run(repo_b,['check-installed'],env)['matches_this_repository']})
        entry=destination/'xcflow-control/SKILL.md';changed=entry.read_bytes()+b'\nLocal test edit\n';entry.write_bytes(changed)
        update=run(repo_b,['install'],env)
        observations.append({'case':'本机入口改动先保留备份','passed':(Path(update['backup'])/'xcflow-control/SKILL.md').read_bytes()==changed})
        frozen=repo_b/'影视生产系统规范/规范整合稿_2026-09-05/总控/岗位职责.md';original=frozen.read_bytes();frozen.write_bytes(original+b'\ncorrupted test\n')
        blocked=subprocess.run([sys.executable,str(repo_b/'安装工作流.py'),'check'],capture_output=True,text=True,encoding='utf-8',timeout=15)
        observations.append({'case':'冻结正文校验不符时停止安装准备','passed':blocked.returncode!=0})
        frozen.write_bytes(original)
        discover=repo_b/'小虫的影视生产流-Skills/制作与检查/discover.py'
        p=subprocess.run([sys.executable,str(discover)],capture_output=True,text=True,encoding='utf-8',env=env,timeout=55)
        if p.returncode:
            observations.append({'case':'Codex 宿主发现隔离安装','passed':False,'observed':p.stdout+p.stderr})
        else:
            metadata=json.loads((repo_b/'.xcflow-local/宿主发现检查.json').read_text(encoding='utf-8'))
            observations.append({'case':'Codex 宿主发现隔离安装','passed':metadata['all_enabled'] and metadata['new_skill_count']==22,'observed':{'skills':metadata['new_skill_count'],'all_enabled':metadata['all_enabled'],'agent_turns_created':metadata['agent_turns_created']}})
    result={'version':'1.0.1','scope':'当前电脑的隔离目录和隔离用户环境；不是对真实工作电脑的远程验证','cases':observations,'passed':sum(x['passed'] for x in observations),'failed':sum(not x['passed'] for x in observations)}
    out=ROOT/'跨电脑接入/跨目录安装验证.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['failed']:raise SystemExit(1)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
