"""Runs every app check (both Streamlit apps, driven through a lightweight Streamlit stand-in) and fails on any FAIL.

Usage: python tests/app/run_all.py
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
failed, total_pass, total = [], 0, 0
for script in sorted(HERE.glob("check_*.py")):
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, cwd=HERE.parents[1], timeout=600)
    out = r.stdout + r.stderr
    counts = re.findall(r"(\d+)/(\d+) [\w ()-]*checks passed", out)
    fails = [l for l in out.splitlines() if l.startswith("FAIL")]
    ok = r.returncode == 0 and counts and not fails and all(a == b for a, b in counts)
    p, t = (int(counts[-1][0]), int(counts[-1][1])) if counts else (0, 0)
    total_pass, total = total_pass + p, total + t
    print(f"{'PASS' if ok else 'FAIL'}  {script.name:28s} {p}/{t}")
    if not ok:
        failed.append(script.name)
        print("\n".join(fails) or out[-3000:])
print(f"\n{total_pass}/{total} app checks passed across {len(list(HERE.glob('check_*.py')))} scripts")
sys.exit(1 if failed else 0)
