"""
1. kirara_get_urls.py で号 URL を最新化
2. scrape.py           今年分だけ取得し data/raw をマージ
3. etl.py              master.csv を再生成
4. validate.py         ALL PASS でなければ exit 1
"""
from datetime import datetime
from pathlib import Path
import subprocess, sys

ROOT  = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PY    = sys.executable

def run(script, *args):
    cmd = [PY, script, *args]
    print("▶", *cmd)
    res = subprocess.run(cmd, cwd=TOOLS)
    if res.returncode:
        sys.exit(res.returncode)

MAG_OFFSET = {
    "kirara": 1,
    "kirara-max": 2,
    "kirara-carat": 2,
    "kirara-forward": 2,
    "kirara-miracle": 2
}

def run_get_urls():
    for slug, offset in MAG_OFFSET.items():
        run("kirara_get_urls.py", "--slug", slug, "--month_ahead", str(offset))                       # ← kirara_page.py を改名
run_get_urls()         
this_year = str(datetime.now().year)
run("scrape.py", "--start", this_year)
run("etl.py")

# バリデーションに引っかかったら終了 
res = subprocess.run([PY, "validate.py", "../data/master.csv"], cwd=TOOLS)
if res.returncode != 0:
    print("❌ Validation failed — aborting CI")
    sys.exit(res.returncode)
