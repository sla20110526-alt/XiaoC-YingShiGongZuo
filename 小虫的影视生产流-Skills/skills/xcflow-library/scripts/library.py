"""Read-only catalog and exact-version content delivery for the local library."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

HERE=Path(__file__).resolve()
BINDINGS=HERE.parents[2]/'xcflow-control/references/bindings.json'

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def library_root(override=None):
    if override:
        return Path(override).resolve()
    configured = Path(read_json(BINDINGS)['library_root'])
    return (configured if configured.is_absolute() else BINDINGS.parent/configured).resolve()

def inside(root,relative):
    p=(root/relative).resolve()
    if not p.is_relative_to(root):
        raise ValueError('不是库内运行资源：'+str(relative))
    return p

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def records(root):
    catalog=read_json(root/'catalog.json')
    index=read_json(root/'接入索引.json')
    if index.get('catalog_sha256')!=digest(root/'catalog.json'):
        raise ValueError('目录与接入索引不同步；请共享能力库核对维护，不使用过期可选状态')
    return catalog,{(e['id'],e['version']):e for e in index['entries']}

def query(root,domain=None,model=None,capability_id=None):
    catalog,index=records(root)
    candidates=[]
    reserves=[]
    for e in catalog['entries']:
        if capability_id and e['id']!=capability_id: continue
        if domain and (domain in e.get('excluded_domains',[]) or domain not in [e.get('domain'),*e.get('tags',[])]): continue
        if model:
            if model in ['Seedance 2.0','Seedance 2.5']: continue
            if model!='MiniMax H3': raise ValueError('未登记的模型入口')
            if e.get('subcategory')!='Prompt 装配与模型适配': continue
            if 'H3' not in json.dumps(e,ensure_ascii=False): continue
        item=dict(e)
        r=index.get((e['id'],e['version']))
        item['content_status']='目录检索；正文尚未加载'
        if not r or not r['selectable']:
            item['reason']=(r or {}).get('reason','尚无本系统接入记录')
            reserves.append(item)
            continue
        missing=[p for p in [e['path'],*r['minimum_resources']] if not inside(root,p).is_file()]
        if missing:
            item['reason']='指定版本正文或必要配套缺失：'+', '.join(missing)
            reserves.append(item)
            continue
        item['necessary_resources']=r['minimum_resources']
        item['independent_dependencies']=r['independent_dependencies']
        item['runtime_boundary']=r['boundary']
        candidates.append(item)
    return {'query':{'domain':domain,'model':model,'id':capability_id},'candidates':candidates,'reserves':reserves,
            'next':'由专业控制部结合当前任务判断匹配、影响和范围；用户选定后读取。' if candidates else '没有可加载候选；说明具体缺口，基础输入齐备时回原执行单元继续。'}

def deliver(root,selection):
    for key in ['project','task','original_unit','stage','need','scope','selection_basis','capabilities']:
        if not selection.get(key): raise ValueError('选择交接信息缺失：'+key)
    catalog,index=records(root)
    entries={(e['id'],e['version']):e for e in catalog['entries']}
    selected={(e['id'],e['version']) for e in selection['capabilities']}
    if len(selected)!=len(selection['capabilities']): raise ValueError('选择记录重复')
    prepared=[]
    for choice in selection['capabilities']:
        key=(choice['id'],choice['version'])
        e=entries.get(key)
        if not e: raise ValueError('指定版本不存在，不替换其他版本：'+str(key))
        r=index.get(key)
        if not r or not r['selectable']: raise ValueError('该版本尚不可加载：'+str(key))
        if selection.get('domain') in e.get('excluded_domains',[]): raise ValueError('当前专业范围被该版本排除')
        for dep in r['independent_dependencies']:
            if (dep['id'],dep['version']) not in selected: raise ValueError('必要独立依赖未纳入用户选择：'+str(dep))
        paths=[e['path'],*r['minimum_resources'],*choice.get('resources',[])]
        documents=[]
        for relative in dict.fromkeys(paths):
            expected=r['resources'].get(relative)
            if not expected: raise ValueError('资源不是该版本登记的配套：'+relative)
            path=inside(root,relative)
            data=path.read_bytes()
            actual=hashlib.sha256(data).hexdigest()
            if actual!=expected: raise ValueError('版本文件校验不符：'+relative)
            if relative==e['path'] and actual!=e['sha256']: raise ValueError('目录与正文校验不符')
            documents.append({'path':str(path),'sha256':actual,'text':data.decode('utf-8-sig')})
        prepared.append({'id':e['id'],'name':e['name'],'version':e['version'],'scope':selection['scope'],
                         'excluded_domains':e.get('excluded_domains',[]),'evidence_status':e.get('evidence_status'),
                         'boundary':r['boundary'],'documents':documents})
    return {'task':selection['task'],'original_unit':selection['original_unit'],'selection_basis':selection['selection_basis'],
            'status':'指定版本正文已由文件工具读取并完整提供；应用方须实际阅读必要正文后确认已加载',
            'capabilities':prepared}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',help='Explicit alternative library for a user-authorized project or isolated validation')
    commands=parser.add_subparsers(dest='command',required=True)
    q=commands.add_parser('query');q.add_argument('--domain');q.add_argument('--model');q.add_argument('--id')
    l=commands.add_parser('load');l.add_argument('--selection',required=True)
    args=parser.parse_args()
    root=library_root(args.library)
    result=query(root,args.domain,args.model,args.id) if args.command=='query' else deliver(root,read_json(args.selection))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try: main()
    except (ValueError,KeyError,OSError) as e:
        print(json.dumps({'error':str(e),'status':'未完成指定交付'},ensure_ascii=False));sys.exit(1)
