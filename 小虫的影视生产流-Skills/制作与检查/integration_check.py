"""Exercise installed file operations with isolated fixtures, not a model evaluation."""
from pathlib import Path
import copy
import os
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode=True
PACKAGE=Path(__file__).resolve().parents[1]
WORKSPACE=PACKAGE.parent
FIXTURE=PACKAGE/'实际情境联调'
INSTALL=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')/'skills'

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
    lib=load_module('xcflow_library',INSTALL/'xcflow-library/scripts/library.py')
    snap=load_module('xcflow_snapshot',INSTALL/'xcflow-scene-design/scripts/snapshot.py')
    root=WORKSPACE/'共享能力库'
    before={str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file()}
    results=[]
    def check(name,fn):
        try:
            detail=fn();results.append({'case':name,'result':'通过','observed':detail})
        except Exception as e:
            results.append({'case':name,'result':'失败','error':repr(e)})
    def require(condition,detail):
        if not condition:raise AssertionError(detail)
        return detail
    def rejected(fn):
        try:fn()
        except (ValueError,KeyError,OSError) as e:return str(e)
        raise AssertionError('本应拒绝的交付却成功')
    selection=read(FIXTURE/'选择记录.json')
    all_items=lib.query(root)
    check('目录分类与储备隔离',lambda:require(len(all_items['candidates'])==36 and len(all_items['reserves'])==1,'36 个既有可选项；1 个待适配源文件单列'))
    check('综合能力按一个条目返回',lambda:require(sum(x['id']=='train-to-busan-film-profile' for x in lib.query(root,domain='导演')['candidates'])==1,'导演查询中《釜山行》只有 1 项'))
    check('声音范围排除',lambda:require(all(x['id']!='train-to-busan-film-profile' for x in lib.query(root,domain='声音')['candidates']),'声音查询没有《釜山行》'))
    check('H3 无可加载适配项',lambda:require(len(lib.query(root,model='MiniMax H3')['candidates'])==0,'返回空候选和 1 个储备，允许原执行单元判断基础装配能否继续'))
    check('Seedance 不追加通用能力查询',lambda:require(len(lib.query(root,model='Seedance 2.0')['candidates'])==0,'Seedance 专项入口不返回大师候选'))
    delivery=lib.deliver(root,selection)
    check('按准确版本提供实际正文',lambda:require(delivery['capabilities'][0]['version']=='1.0' and len(delivery['capabilities'][0]['documents'])==5,'1.0 正文与 4 份必要配套均实际回读，未混入独立 Profile'))
    wrong=copy.deepcopy(selection);wrong['capabilities'][0]['version']='9.9'
    check('指定版本不存在不替换',lambda:rejected(lambda:lib.deliver(root,wrong)))
    raw=copy.deepcopy(selection);raw['capabilities']=[{'id':'minimax-h3-prompt-writing','version':all_items['reserves'][0]['version']}]
    check('待适配源文件不能加载',lambda:rejected(lambda:lib.deliver(root,raw)))
    sound=copy.deepcopy(selection);sound['domain']='声音'
    check('已选能力仍检查专业排除',lambda:rejected(lambda:lib.deliver(root,sound)))
    incomplete=copy.deepcopy(selection);incomplete.pop('original_unit')
    check('缺少回接执行单元明确报错',lambda:rejected(lambda:lib.deliver(root,incomplete)))
    external=copy.deepcopy(selection);external['capabilities'][0]['resources']=['../SKillXC/skills/film-profile-library/SKILL.md']
    check('不能夹带库外旧 Skill',lambda:rejected(lambda:lib.deliver(root,external)))
    dune=copy.deepcopy(selection);dune['capabilities']=[{'id':'dune2-directing-style','version':'v001'}]
    d=lib.deliver(root,dune)
    check('独立 Skill 的内附 Profile 配套',lambda:require(len(d['capabilities'])==1 and len(d['capabilities'][0]['documents'])==2,'《沙丘2》导演 v001 提供正文和内附 Profile，不自动选择其他独立能力'))
    with tempfile.TemporaryDirectory(prefix='xcflow-io-',dir=FIXTURE) as temporary:
        temp=Path(temporary).resolve();assert temp.is_relative_to(FIXTURE.resolve())
        clone=temp/'library';clone.mkdir()
        shutil.copy2(root/'catalog.json',clone/'catalog.json');shutil.copy2(root/'接入索引.json',clone/'接入索引.json')
        index=read(clone/'接入索引.json');entry=next(e for e in index['entries'] if e['id']=='train-to-busan-film-profile')
        for rel in entry['resources']:
            target=clone/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/rel,target)
        main_path=clone/next(e for e in read(clone/'catalog.json')['entries'] if e['id']==entry['id'])['path']
        original=main_path.read_bytes();main_path.write_bytes(original+b'\nfixture corruption')
        check('指定版本内容损坏',lambda:rejected(lambda:lib.deliver(clone,selection)))
        main_path.write_bytes(original)
        missing=clone/entry['minimum_resources'][0];moved=missing.with_suffix('.unavailable');missing.rename(moved)
        check('缺少配套不能列作可用候选',lambda:require(not lib.query(clone,capability_id=entry['id'])['candidates'],'返回 SOURCE.md 缺口'))
        check('缺少配套不能报告加载完成',lambda:rejected(lambda:lib.deliver(clone,selection)))
        moved.rename(missing)
        entry['independent_dependencies']=[{'id':'dune2-directing-style','version':'v001'}];dump(clone/'接入索引.json',index)
        check('未选独立依赖不能暗中加载',lambda:rejected(lambda:lib.deliver(clone,selection)))
        entry['independent_dependencies']=[];dump(clone/'接入索引.json',index)
        catalog=read(clone/'catalog.json');catalog['status']='fixture changed';dump(clone/'catalog.json',catalog)
        check('目录改变后不沿用旧可选状态',lambda:rejected(lambda:lib.query(clone)))
        target=temp/'锚点-V03.md';saved=snap.save(FIXTURE/'场戏锚点-V03.md',target)
        check('快照实际保存并完整恢复',lambda:require(saved['snapshot']==(FIXTURE/'场戏锚点-V03.md').read_text(encoding='utf-8') and digest(target)==saved['sha256'],'回读全文与来源、SHA-256 一致，恢复位置为模块六完成'))
        check('同版同内容快照沿用',lambda:require(snap.save(FIXTURE/'场戏锚点-V03.md',target)['operation']=='同内容沿用','未新增版本或覆盖内容'))
        changed=temp/'different.md';changed.write_text('不同的完整快照测试内容',encoding='utf-8')
        h=digest(target)
        check('同版不同内容快照不覆盖',lambda:rejected(lambda:snap.save(changed,target)))
        check('拒绝后快照仍保持原值',lambda:require(digest(target)==h,'原快照 SHA-256 未改变'))
        blocker=temp/'not-a-directory';blocker.write_text('fixture',encoding='utf-8')
        check('不可写路径不报告保存成功',lambda:rejected(lambda:snap.save(changed,blocker/'snapshot.md')))
    # Check exact template invariants against the frozen source, not a duplicated rule list.
    template=(WORKSPACE/'影视生产系统规范/规范整合稿_2026-09-05/模板/正式镜头Prompt模板_v1.0.md').read_text(encoding='utf-8-sig')
    product=(FIXTURE/'Seedance2.0-装配结果.md').read_text(encoding='utf-8')
    blocks=re.findall(r'```text\n(.*?)```',product,re.S)
    fixed=[next(line for line in template.splitlines() if line.startswith(prefix)) for prefix in ['光线规则：','字幕限制：','音乐限制：']]
    check('单镜与镜头组的固定限制保持原文',lambda:require(len(blocks)==2 and all(all(line in b.splitlines() for line in fixed) for b in blocks),'两种完整 Prompt 的三个限制段均与冻结模板原文一致'))
    durations=[float(x) for x in re.findall(r'镜头[12]，([\d.]+)秒。',blocks[0])]
    total=float(re.search(r'镜头组，([\d.]+)秒',blocks[0]).group(1))
    check('逐镜时长与生成单元求和',lambda:require(durations==[4.5,3.5] and sum(durations)==total==8 and all(x*2==int(x*2) for x in durations) and total<=15,'4.5 + 3.5 = 8，符合 0.5 秒单位和冻结的 15 秒基线'))
    after={str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file()}
    check('查询与选版不写正式共享库',lambda:require(before==after,'正式库全部文件在查询与交付测试前后保持一致'))
    out={'test_type':'已安装辅助程序的实际文件操作与隔离反例；不包含另一个模型评估或真实出片','cases':results,'passed':sum(x['result']=='通过' for x in results),'failed':sum(x['result']=='失败' for x in results)}
    dump(WORKSPACE/'.xcflow-local/文件行为联调.json',out)
    print(json.dumps({'passed':out['passed'],'failed':out['failed'],'failures':[x for x in results if x['result']=='失败']},ensure_ascii=False))
    if out['failed']:raise SystemExit(1)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
