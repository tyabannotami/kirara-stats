"""
raw/*.csv → master.csv へ統合・正規化・手動フィックス適用
$ python tools/etl.py
"""
import pandas as pd, unicodedata, re, glob
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
RAW_DIR = BASE / "data" / "raw"
OV_DIR  = BASE / "overrides"
DST     = BASE / "data" / "master.csv"

# ---------- 標準化 ----------
def std(s:str):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[ｰ—–‑]", "-", s)
    return s.strip()

# ---------- エイリアス ----------
def apply_alias(df):
    alias_path = OV_DIR / "aliases.csv"
    if not alias_path.exists(): return df
    alias = pd.read_csv(alias_path)
    mapping = dict(zip(alias["alias"].map(std), alias["canonical"].map(std)))
    df["work"] = df["work"].map(lambda x: mapping.get(std(x), std(x)))
    return df

# ---------- 手動号修正 ----------
def apply_issue_fixes(df):
    fix = pd.read_csv("overrides/issues_fix.csv")
    for _, r in fix.iterrows():
        if str(r.get("fixed")).upper() != "OK":
            continue

        mask = (df["issue_id"] == r["issue_id"])
        if pd.notna(r.get("work")):
            mask &= (df["work"] == r["work"])

        # ----------------- 削除 -----------------
        if r["field"] == "delete":
            if pd.notna(r.get("value")):           # rank 指定があればさらに絞る
                mask &= (df["rank"] == int(r["value"]))
            df = df[~mask]
            continue
        # -------------- フラグ修正 --------------
        if r["field"] in ("is_cover","is_top","is_center"):
            df.loc[mask, r["field"]] = str(r["value"]).upper() == "TRUE"
        elif r["field"] == "rank":
            df.loc[mask, "rank"] = int(r["value"])
    return df
# ---------- カラー重複の整理 ----------  ★ 追加
def dedupe_two_episode_color(df: pd.DataFrame) -> pd.DataFrame:
    for (iss, work), g in df.groupby(["issue_id", "work"]):
        if len(g) <= 1:
            continue
        # is_top と is_center を個別に整理
        for flag in ["is_top", "is_center"]:
            flag_rows = g[g[flag]].sort_values("rank").index
            if len(flag_rows) > 1:
                df.loc[flag_rows[1:], flag] = False
    return df

# ---------- main ----------
def main():
    files = glob.glob(str(RAW_DIR / "*.csv"))
    frames=[]
    for f in files:
        df=pd.read_csv(f)
        # raw に magazine 列が無い旧ファイルはファイル名から補完
        if "magazine" not in df.columns:
            df["magazine"]=Path(f).stem           # kirara / kirara-max …
        frames.append(df)

    df=pd.concat(frames,ignore_index=True)

    # 雑誌ごとにユニークな issue_id を作成
    df["issue_id"]=(
        df["magazine"]+"-"+
        df["year"].astype(str)+"-"+
        df["month"].astype(str).str.zfill(2)
    ).astype(str).str.zfill(2)
    df = apply_alias(df)
    df = apply_issue_fixes(df)
    df = dedupe_two_episode_color(df)
    df.to_csv(DST, index=False, encoding="utf-8-sig")
    print(f"✅ master.csv updated: {len(df)} rows")

if __name__ == "__main__":
    main()
