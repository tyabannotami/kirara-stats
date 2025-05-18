# kirara_get_urls.py  （Python 3.9 以降推奨）

import re
import csv
from pathlib import Path
from urllib.parse import urljoin

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

def harvest_year(slug: str, year: int, sess: requests.Session) -> list[tuple]:
    """年別ページから号 URL を抜いて (year, month, id, full_url) を返す"""
    url = f"{BASE}/magazine/{slug}/{year}/"
    try:
        res = sess.get(url, timeout=15)
        if res.status_code != 200:
            return []                           # 年ページが存在しない
        html = res.text
    except requests.RequestException as e:
        print(f"[WARN] {url} → {e}")
        return []

    rows = []
    for y, m, pk in PATTERNS[slug].findall(html):
        full = urljoin(BASE, f"/magazine/{slug}/{y}/{m}/{pk}/")
        rows.append((slug, int(y), int(m), int(pk), full))
    return rows

def main(out_csv="kirara_issue_urls.csv"):
    sess = requests.Session()
    sess.headers.update(HEADERS)

    all_rows = []
    for slug in MAGAZINES:
        for yr in range(YEAR_START, YEAR_END + 1):
            all_rows.extend(harvest_year(slug, yr, sess))

    # 重複排除 & ソート
    uniq = {r[4]: r for r in all_rows}.values()
    all_sorted = sorted(uniq, key=lambda t: (t[0], t[1], t[2]))

    with Path(out_csv).open("w", newline="", encoding="utf-8_sig") as f:
        writer = csv.writer(f)
        writer.writerow(["種別", "年", "月", "ID", "URL"])
        writer.writerows(all_sorted)

    print(f"{len(all_sorted)} 件を {out_csv} に保存しました。")

if __name__ == "__main__":
    main()
