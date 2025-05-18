# tools/make_todo.py
"""
validate 結果 → overrides/issues_fix.csv に未対応 TODO を追記
"""
from pathlib import Path
import pandas as pd
from validate import validate_df

BASE      = Path(__file__).resolve().parents[1]
OV_FILE   = BASE / "overrides" / "issues_fix.csv"
MASTER    = BASE / "data" / "master.csv"

def main() -> None:
    df_master = pd.read_csv(MASTER)
    todo = validate_df(df_master)

    if todo.empty:
        print("ALL PASS ✅")
        return

    # 既に記載済みの行を除外
    if OV_FILE.exists():
        done = pd.read_csv(OV_FILE)[["issue_id", "type"]]
        todo = todo.merge(done.assign(done=1),
                          on=["issue_id", "type"], how="left")
        todo = todo[todo["done"].isna()].drop(columns="done")

    if todo.empty:
        print("👋 未対応 TODO はありません")
        return

    # 表示用並び替え（雑誌 → issue_id）
    todo = todo.sort_values(["magazine", "issue_id"]).reset_index(drop=True)

    # 空欄の fixed 列を追加して追記
    todo["fixed"] = ""
    todo["work"]  = ""
    todo["field"] = ""
    todo["value"] = ""
    OV_FILE.parent.mkdir(exist_ok=True, parents=True)
    todo.to_csv(OV_FILE, mode="a",
                header=not OV_FILE.exists(), index=False, encoding="utf-8-sig")

    print(f"⚠️ {len(todo)} 件を {OV_FILE} に追記しました。")
    print("→ 'fixed' 列を埋めてから etl.py を再実行してください。")

if __name__ == "__main__":
    main()