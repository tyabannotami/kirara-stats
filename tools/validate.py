"""
master.csv を検査して表紙・巻頭・センターの整合性をチェック。
issues_fix.csv に fixed=OK で登録された type は警告を無視する。
CLI:  python tools/validate.py data/master.csv
"""
from pathlib import Path
import pandas as pd

# ──────────────────────────────────────────────
EXPECT = {
    "kirara"        : dict(cover=1, top=1, center=4),
    "kirara-max"    : dict(cover=1, top=1, center=4),
    "kirara-carat"  : dict(cover=1, top=1, center=4),
    "kirara-forward": dict(cover=1, top=1, center=None),   # センターなし
    "default"       : dict(cover=1, top=1, center=4),
}

# ──────────────────────────────────────────────
def _make_issue_id(row):
    return f"{row['magazine']}-{row['year']}-{row['month']:02d}"

# ──────────────────────────────────────────────
def _load_ignore_set() -> set[tuple[str, str, str]]:
    """
    issues_fix.csv から fixed=OK 行の (magazine, issue_id, type) を収集。
    手動修正行 (type NaN) は対象外。
    """
    fix_path = Path(__file__).resolve().parents[1] / "overrides" / "issues_fix.csv"
    ignore = set()
    if fix_path.exists():
        fix = pd.read_csv(fix_path)
        ok_rows = fix[fix["fixed"].astype(str).str.upper() == "OK"]
        ok_rows = ok_rows[pd.notna(ok_rows["type"])]          # 自動警告行のみ
        for _, r in ok_rows.iterrows():
            ignore.add( (r["magazine"], r["issue_id"], r["type"]) )
    return ignore

IGNORE = _load_ignore_set()

# ──────────────────────────────────────────────
def validate_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    master DataFrame → 警告 DataFrame
    IGNORE に含まれる (mag, issue_id, type) は除外
    """
    if "issue_id" not in df.columns:
        df = df.assign(issue_id=df.apply(_make_issue_id, axis=1))

    warnings = []
    for (mag, yr, mo), g in df.groupby(["magazine", "year", "month"]):
        expect = EXPECT.get(mag, EXPECT["default"])
        issue_id = f"{mag}-{yr}-{mo:02d}"

        # ① 表紙
        cov = g["is_cover"].sum()
        if cov != expect["cover"] and (mag, issue_id, "cover_count") not in IGNORE:
            warnings.append(dict(magazine=mag, issue_id=issue_id,
                                 type="cover_count", detail=f"{cov} 作"))

        # ② 巻頭
        tops = g[g["is_top"]]
        if len(tops) != expect["top"] and (mag, issue_id, "top_count") not in IGNORE:
            warnings.append(dict(magazine=mag, issue_id=issue_id,
                                 type="top_count", detail=f"{len(tops)} 作"))
        elif len(tops) == 1 and int(tops.iloc[0]["rank"]) != 1 \
             and (mag, issue_id, "top_not_rank1") not in IGNORE:
            warnings.append(dict(magazine=mag, issue_id=issue_id,
                                 type="top_not_rank1",
                                 detail=f"rank={int(tops.iloc[0]['rank'])}"))

        # ③ センター
        if expect["center"] is not None:
            cen = g["is_center"].sum()
            if cen != expect["center"] and (mag, issue_id, "center_count") not in IGNORE:
                warnings.append(dict(magazine=mag, issue_id=issue_id,
                                     type="center_count", detail=f"{cen} 作"))

    return pd.DataFrame(warnings)

# ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    warn_df = validate_df(pd.read_csv(sys.argv[1]))
    if warn_df.empty:
        print("ALL PASS ✅")
    else:
        print(warn_df.to_string(index=False))