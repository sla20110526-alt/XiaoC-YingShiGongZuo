"""Compatibility entry for the cross-computer installer. Old implementation is archived."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
if __name__=="__main__":
    step=sys.argv[1] if len(sys.argv)>1 else "validate"
    action={"prepare":"check","validate":"check","install":"install","connect":"check-installed"}.get(step)
    if action is None:raise SystemExit("Use prepare, validate, install, or connect")
    raise SystemExit(subprocess.call([sys.executable,str(ROOT/"安装工作流.py"),action,*sys.argv[2:]]))
