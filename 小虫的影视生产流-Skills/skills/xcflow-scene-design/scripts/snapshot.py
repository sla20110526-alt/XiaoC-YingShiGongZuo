"""Persist a complete task snapshot and return the actual re-read content."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

def save(source,target):
    source,target=Path(source).resolve(),Path(target).resolve()
    data=source.read_bytes()
    if not data.strip(): raise ValueError('完整锚点为空')
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if target.read_bytes()!=data: raise ValueError('同版本已有不同快照；使用下一锚点版本，不覆盖')
        operation='同内容沿用'
    else:
        with target.open('xb') as f: f.write(data)
        operation='已保存'
    reread=target.read_bytes()
    if reread!=data: raise ValueError('保存后重新读取不一致')
    return {'operation':operation,'path':str(target),'sha256':hashlib.sha256(reread).hexdigest(),
            'status':'文件已保存并回读；内容完整性须按本单元输出约定检查','snapshot':reread.decode('utf-8-sig')}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True);p.add_argument('--target',required=True)
    a=p.parse_args();print(json.dumps(save(a.source,a.target),ensure_ascii=False,indent=2))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try: main()
    except (OSError,ValueError) as e:
        print(json.dumps({'error':str(e),'status':'保存未完成；按规范在当前任务交付完整快照'},ensure_ascii=False));sys.exit(1)
