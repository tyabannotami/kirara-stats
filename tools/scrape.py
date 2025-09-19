"""
スクレイパ: kirara_issue_urls.csv に列挙された全ての号を取得し
data/raw/<slug>.csv を雑誌ごとに出力する
  $ python tools/scrape.py --start 2013
"""
from __future__ import annotations
import re, time, unicodedata, argparse
from pathlib import Path
import pandas as pd, requests, bs4

# ────────────────────────────────────────────────────────────────
UA        = {"User-Agent": "Mozilla/5.0"}
DATA_DIR  = Path(__file__).resolve().parents[1] / "data" / "raw"
#TITLE_RE  = re.compile(r"[「『]([^「『」』]+)[」』]")
#新フォーマットでは２重カギカッコだけ抜けば良さそうなので修正
TITLE_RE  = re.compile(r"[『]([^『』]+)[』]")
CIRCLED_RE = re.compile(r"[①-⑳➀➁]")

def std(s: str) -> str:
    return unicodedata.normalize("NFKC", s).strip()

def clean_title(x: str) -> str:
    return std(CIRCLED_RE.sub("", re.sub(r"[「」『』]", "", x)))

# ────────────────────────────────────────────────────────────────
def extract_color_blocks(
    soup: bs4.BeautifulSoup, *, new_layout: bool, magazine: str
) -> list[str]:
    """
    表紙／巻頭／センター情報を 'ラベル:タイトル' 形式で返す
      - kirara‑forward : センター無し、1行表記や <h2> を個別解析
      - その他         : 旧◆◆ブロック式 or 新レイアウト <h2> 見出し式
    """
    color: list[str] = []

    def add(lbl: str, raw: str):
        t = clean_title(raw)
        if t:
            color.append(f"{lbl}:{t}")

    # ───── kirara‑forward 専用 ─────
    if magazine == "kirara-forward":
        if new_layout:
            for h2 in soup.find_all("h2"):
                lbl = h2.get_text(strip=True)
                if lbl not in ("表紙", "巻頭カラー", "巻頭"):
                    continue
                block = []
                for sib in h2.next_siblings:
                    if isinstance(sib, bs4.Tag) and sib.name == "h2":
                        break
                    block.append(sib.get_text(" ", strip=True)
                                 if hasattr(sib, "get_text") else str(sib))
                m = TITLE_RE.search(" ".join(block))
                if m:
                    add("表紙" if "表紙" in lbl else "巻頭", m.group(1))
        else:
            hyoushiari_flag=False
            desc = soup.select_one("div.content-desc")
            if desc:
                for tk in desc.stripped_strings:
                    if "表紙" in tk:
                        hyoushiari_flag=True
                    m = TITLE_RE.search(tk)
                    if m and hyoushiari_flag : 
                        add("表紙", m.group(1))
                        break

        return color  # ← forward 終了
    # ───── その他 (kirara / kirara-max / kirara-carat …) ─────
    if new_layout:
        for h2 in soup.find_all("h2"):
            raw = h2.get_text(strip=True)
            lbls = []
            if "表紙"   in raw: lbls.append("表紙")
            if "巻頭"   in raw: lbls.append("巻頭")
            if "センター" in raw: lbls.append("センターカラー")
            if not lbls:
                continue
            block = []
            for sib in h2.next_siblings:
                if isinstance(sib, bs4.Tag) and sib.name == "h2":
                    break
                block.append(
                    sib.get_text("\n", strip=True)
                    if hasattr(sib, "get_text") else str(sib)
                )
            for m in TITLE_RE.finditer("\n".join(block)):
                for l in lbls:
                    add(l, m.group(1))
    else:                                         # ← new_layout が False
        desc = soup.select_one("div.content-desc")
        if desc:
            lbls = []
            cover_used = False
            for tk in desc.stripped_strings:
                if "◆◆" in tk:                   # 見出し行
                    lbls = []
                    cover_used = False
                    if "表紙" in tk:            lbls.append("表紙")
                    if "巻頭" in tk:            lbls.append("巻頭")
                    if "センターカラー" in tk:  lbls.append("センターカラー")
                    continue
                if "ラインナップ" in tk: break

                m = TITLE_RE.search(tk)
                if not m or not lbls: continue
                title = m.group(1)

                # 同ブロック内で「表紙」は先頭作品だけ
                if "表紙" in lbls and cover_used:
                    eff_lbls = [l for l in lbls if l != "表紙"]
                else:
                    eff_lbls = lbls
                    if "表紙" in lbls: cover_used = True

                for l in eff_lbls:
                    add(l, title)

    # 2) 関数の末尾に必ず return を置く       ← ここが抜けていた
    return color

# ────────────────────────────────────────────────────────────────
def extract_lineup(soup: bs4.BeautifulSoup) -> list[str]:
    """
    ラインナップ（作品リスト）を返す  
    ・<ul class="lineup"><li>… 形式 (font/strong/li)  
    ・<h2> ラインナップ … 形式
    """
    works: list[str] = []

    # 1) <ul class="lineup">
    for ul in soup.find_all("ul", class_="lineup"):
        cand = ul.select("font") or ul.select("strong") or ul.select("li")
        if not cand:
            continue
        tmp = [clean_title(t.get_text(" ", strip=True)) for t in cand]
        if tmp and not any("休載" in x for x in tmp):
            works = tmp
            break

    # 2) <h2> ラインナップ … フォールバック
    if not works:
        for h2 in soup.find_all("h2"):
            if h2.get_text(strip=True) != "ラインナップ":
                continue
            block: list[str] = []
            for sib in h2.next_siblings:
                if isinstance(sib, bs4.Tag) and sib.name == "h2":
                    break
                block.append(
                    sib.get_text("\n", strip=True)
                    if hasattr(sib, "get_text") else str(sib)
                )
            for ln in "\n".join(block).splitlines():
                if "休載" in ln:
                    continue
                for m in TITLE_RE.finditer(ln):
                    works.append(clean_title(m.group(1)))
            break

    return works

# ────────────────────────────────────────────────────────────────
def parse_issue(url: str, magazine: str) -> list[dict]:
    """号ページ → 行リスト(dict)"""
    soup = bs4.BeautifulSoup(requests.get(url, headers=UA, timeout=15).text, "lxml")
    year, month = map(int, re.search(r"/(\d{4})/(\d{2})/", url).groups())
    #きららMAX2025-11月号　アドレスの月が12になっている件の対応
    if url =="https://www.dokidokivisual.com/magazine/kirara-max/2025/12/12720/" :
        month = 11
    
    new_layout  = (year > 2025) or (year == 2025 and month >= 3)

    color_lines = extract_color_blocks(soup, new_layout=new_layout, magazine=magazine)
    works       = extract_lineup(soup)

    def has_flag(w: str, key: str) -> bool:
        w = std(w)
        return any(key in c and w in c for c in color_lines)

    rows = []
    for idx, w in enumerate(works, 1):
        rows.append(dict(
            magazine=magazine,
            year=year,
            month=month,
            url=url,
            work=w,
            rank=idx,
            is_cover = has_flag(w, "表紙"),
            is_top   = has_flag(w, "巻頭"),
            is_center= has_flag(w, "センターカラー"),
        ))

    # フォールバック: 表紙0なら巻頭を表紙に昇格
    if rows and not any(r["is_cover"] for r in rows):
        for r in rows:
            if r["is_top"]:
                r["is_cover"] = True
    
    # ① ラインナップ1番目を巻頭扱い
    if rows and not any(r["is_top"] for r in rows) and rows:
        rows[0]["is_top"] = True
    return rows

# ────────────────────────────────────────────────────────────────
def cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2013)
    ap.add_argument("--end",   type=int)
    ap.add_argument("--url_csv", default="kirara_issue_urls.csv")
    args = ap.parse_args()

    df_urls = pd.read_csv(args.url_csv, encoding="utf-8-sig")
    if args.start:
        df_urls = df_urls[df_urls["年"] >= args.start]
    if args.end:
        df_urls = df_urls[df_urls["年"] <= args.end]

    rows_by_slug: dict[str, list[dict]] = {}

    for _, row in df_urls.iterrows():
        url  = row["URL"]
        slug = row["種別"]                  # kirara / kirara-max / carat / kirara-forward
        print("▶", url)
        try:
            rows = parse_issue(url, slug)
            rows_by_slug.setdefault(slug, []).extend(rows)
            time.sleep(1)                   # polite crawl
        except Exception as e:
            print("  [ERROR]", e)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for slug, rows in rows_by_slug.items():
        out = DATA_DIR / f"{slug}.csv"
        # ① 既存ファイルがあれば読み込み …
        if out.exists():
            old = pd.read_csv(out, encoding="utf-8-sig")
            new = pd.DataFrame(rows)
            merged = pd.concat([old, new], ignore_index=True)

            # ② 同じ作品・同じrankの重複行は keep="first" で残す
            merged = merged.drop_duplicates(
                subset=["magazine", "year", "month", "work", "rank"],
                keep="first"
            )
        else:
            merged = pd.DataFrame(rows)
        merged.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"  ✓ {slug}: {len(merged)} rows (after merge) → {out}")
        total += len(rows)          # ← 新たにスクレイプした行数で集計


    print(f"\n✅ all done: {total} rows collected")

# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cli()
