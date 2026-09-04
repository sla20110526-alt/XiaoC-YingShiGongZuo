"""Read skills/list from the installed Codex app-server. Does not start an agent turn."""
from pathlib import Path
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time

PACKAGE=Path(__file__).resolve().parents[1]
def locate_codex():
    found=shutil.which('codex')
    if found:return Path(found)
    root=Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData/Local')/'OpenAI/Codex/bin'
    choices=list(root.glob('*/codex.exe')) if root.exists() else []
    if choices:return max(choices,key=lambda p:p.stat().st_mtime)
    raise RuntimeError('未找到本机 Codex 程序；安装文件检查可先完成，宿主发现尚未验证。')

def main():
    exe=locate_codex()
    version=subprocess.run([str(exe),'--version'],capture_output=True,text=True,encoding='utf-8',timeout=10).stdout.strip()
    proc=subprocess.Popen([str(exe),'app-server','--stdio'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                          text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),cwd=PACKAGE.parent)
    messages=queue.Queue()
    def reader():
        for line in proc.stdout:
            try:messages.put(json.loads(line))
            except ValueError:pass
    threading.Thread(target=reader,daemon=True).start()
    def send(item):proc.stdin.write(json.dumps(item)+'\n');proc.stdin.flush()
    def receive(request_id):
        end=time.monotonic()+40
        while time.monotonic()<end:
            try:item=messages.get(timeout=min(1,end-time.monotonic()))
            except queue.Empty:continue
            if item.get('id')==request_id:
                if 'error' in item:raise RuntimeError(str(item['error']))
                return item['result']
        raise TimeoutError('Codex skills/list 超时')
    try:
        send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'xcflow-install-check','version':'1.0.0'}}})
        receive(1);send({'method':'initialized'})
        send({'id':2,'method':'skills/list','params':{'cwds':[str(PACKAGE.parent)],'forceReload':True}})
        data=receive(2)
        expected=json.loads((PACKAGE/'制作与检查/岗位清单.json').read_text(encoding='utf-8'))
        names={r['name'] for r in expected}
        skills=[s for d in data['data'] for s in d['skills'] if s['name'] in names]
        old=[{'name':s['name'],'path':s['path'],'enabled':s['enabled']} for d in data['data'] for s in d['skills'] if '/SKillXC/' in s['path'].replace('\\','/')]
        errors=[e for d in data['data'] for e in d['errors'] if 'xcflow-' in e['path']]
        result={'method':'skills/list','forceReload':True,'cli_version':version,'skills':skills,'new_skill_count':len(skills),
                'all_enabled':len(skills)==22 and all(s['enabled'] for s in skills),'new_skill_errors':errors,
                'archived_source_entries':old,'all_archived_source_entries_disabled':all(not s['enabled'] for s in old),
                'agent_turns_created':0,'scope':'当前宿主技能发现，不代表当前已打开对话的技能提示已刷新或每个真实创作项目已验证'}
        out=PACKAGE.parent/'.xcflow-local/宿主发现检查.json'
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:result[k] for k in ['new_skill_count','all_enabled','new_skill_errors','all_archived_source_entries_disabled','agent_turns_created']},ensure_ascii=False))
        if not result['all_enabled'] or errors:raise RuntimeError('新 Skill 发现检查未通过')
    finally:
        # Stop only this diagnostic process tree, including its file-watching helpers.
        if os.name=='nt' and proc.poll() is None:
            subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW,timeout=10)
        try:proc.stdin.close()
        except OSError:pass
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=3)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
