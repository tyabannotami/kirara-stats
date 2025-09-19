"""
kirara_get_urls.py
 公式サイトの年別ページを巡回して “号 URL 一覧 CSV” を更新する。

使い方:
  # 全誌をデフォルト月数で
  python tools/kirara_get_urls.py

  # きららは +1 か月先まで、MAX は +2
  python tools/kirara_get_urls.py --slug kirara --month_ahead 1
  python tools/kirara_get_urls.py --slug kirara-max --month_ahead 2
"""
import re
import csv
from pathlib import Path
from urllib.parse import urljoin
import argparse, pandas as pd
from datetime import datetime, timedelta

import requests

BASE = "https://www.dokidokivisual.com"
MAGAZINES = {                     # slug : 日本語名
    "kirara-carat":   "きららキャラット",
    "kirara":         "きらら",
    "kirara-max":     "きららMAX",
    "kirara-forward": "きららフォワード",
    "kirara-miracle": "きららミラク",      # ～2017 年
}
YEAR_START = 2007                 # 初年度
YEAR_END   = 2025                 # 必要なら更新

HEADERS = {
    # ブロック回避用に普通のブラウザ名を名乗る
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# あとで使い回すコンパイル済みパターンを magazine ごとに持っておく
PATTERNS = {
    slug: re.compile(rf"/magazine/{slug}/(\d{{4}})/(\d{{2}})/(\d+)/")
    for slug in MAGAZINES
}


OUT_CSV = Path(__file__).resolve().parents[1] / "tools" / "kirara_issue_urls.csv"
# ↑ 場所はプロジェクトに合わせて変更可
# ──────────────────────────────────────────────
def harvest_year(slug: str, year: int, sess: requests.Session) -> list[tuple]:
    """年ページをパースして (slug, year, month, url) タプルを返す"""
    url = f"{BASE}/magazine/{slug}/{year}/"
    try:
        res = sess.get(url, timeout=15)
        if res.status_code != 200:
            return []
        html = res.text
    except requests.RequestException:
        return []

    rows = []
    for y, m, pk in PATTERNS[slug].findall(html):
        full = urljoin(BASE, f"/magazine/{slug}/{y}/{m}/{pk}/")
        #きららMAX2025-11月号　アドレスの月が12になっている件の対応
        if full =="https://www.dokidokivisual.com/magazine/kirara-max/2025/12/12720/" :
            m = 11
        rows.append((slug, int(y), int(m), full))
    return rows
# ──────────────────────────────────────────────
def cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", nargs="*", choices=list(MAGAZINES), help="対象雑誌（省略で全て）")
    ap.add_argument("--month_ahead", type=int, default=2,
                    help="今日から何か月先の号まで取得するか（デフォルト 2）")
    ap.add_argument("--out_csv", default=str(OUT_CSV))
    args = ap.parse_args()

    targets = args.slug or list(MAGAZINES)
    sess = requests.Session(); sess.headers.update(HEADERS)

    today = datetime.now()
    latest = today + timedelta(days=30 * args.month_ahead)
    year_range = range(2007, latest.year + 1)   # 2007 以降がサイトに存在

    all_rows: list[tuple] = []
    for slug in targets:
        for yr in year_range:
            all_rows.extend(harvest_year(slug, yr, sess))

    # ─── 既存 CSV をマージして重複除去 ───
    out_path = Path(args.out_csv)
    if out_path.exists():
        with out_path.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                all_rows.append((r["種別"], int(r["年"]), int(r["月"]), r["URL"]))

    # dict で URL 重複排除 → ソート
    uniq = {r[3]: r for r in all_rows}.values()
    sorted_rows = sorted(uniq, key=lambda t: (t[0], t[1], t[2]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["種別", "年", "月",  "URL"])
        w.writerows(sorted_rows)

    print(f"✅ {len(sorted_rows)} 行を書き出しました → {out_path}")

# ──────────────────────────────────────────────
if __name__ == "__main__":
    cli()
