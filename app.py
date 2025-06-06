import streamlit as st, pandas as pd
from rapidfuzz import process, fuzz
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
st.set_page_config(page_title="きらら掲載順位検索", layout="wide")

# ① ページタイトル
st.title("まんがタイムきらら 掲載順・表紙・カラー検索（β）")
st.write("きらら系5誌（きらら・MAX・キャラット・フォワード・ミラク）の掲載順・表紙・巻頭・センターカラーを横断検索できる Web アプリです。")
st.write("作品名を入力すると、掲載された号ごとの掲載順と表紙・巻頭カラー・センターカラー状況を一覧表示します。")
st.write("現在2013年1月号からの情報を取得し、随時更新しています。")
st.write("※個人的に収集したデータのため、誤りがある可能性があります。")
# 🔸 ① 一行ヒント
st.caption("列名をクリックすると昇順 / 降順に並べ替えできます")
with st.expander("補足事項はこちら"):
    st.markdown("""
### データの出典：
- 芳文社様『まんがタイムきらら』公式サイト  
まんがタイムきららWeb  https://www.dokidokivisual.com/
### 参考にさせていただいたサイト： 
きららサーチ(β) https://search.kiraradata.xyz/  
2007年1月号以降のきらら5誌の掲載順、著者名等が確認できるようです。

### 更新タイミング：
- 毎日20:00  に GitHub Actions が自動で取得・更新
- ※個人で収集したデータのため誤りが含まれる可能性があります。
- ※下記観点で確認は行いましたが、目視確認では見切れていません。
#### 観点：  
①1号につき表紙が1作品であること、2作品以上であればコラボ表紙や記念号など妥当な理由があること。  
②1号につき巻頭カラーが1作品であり、その作品が掲載順1番であること。  
    ただし、きらら2016-5月号は巻頭カラーの『三者三葉』が掲載順2番ですが実態は未確認です。  
③本誌、MAX、ミラク、キャラットでは1号につき4作品のセンターカラーがあること   
  
プログラムでセンターカラーの抽出がしきれていない場合は下記の手順で確認を行い一覧の手入力をしています。  
(1)ホームページの本文内にカラーの記載がないか。  
(2)ホームページ前月号の予告に次号のカラーの予告がないか。  
(3)対象号のまんがタイムきらら公式ツイッターでカラーの記載がないか。  
上記手順でも確認できないものは現在調査できていません。 
  下記の号についてはセンターカラーの取得が4作未満です。  
- キャラット2013-4
- MAX2013-1.2.7.8

※2012年以前については現時点では以下の理由で調査していません。  
①ホームページのレイアウトやカラーの記載がまばらであり確認が難しい。  
②当時はきらら公式ツイッターが開設されておらず公式ツイッターでの確認ができない。 
    """)


# ② データ読み込み（master.csv は既存のまま）
df = pd.read_csv("data/master.csv")
@st.cache_data
def load():
    return pd.read_csv("data/master.csv")

df = load()

# ▼ URL をクリック可能なリンクにする JS 関数
link_renderer = JsCode("""
class UrlCellRenderer {
    init(params){
        const link = document.createElement('a');
        link.href   = params.value;
        link.target = '_blank';
        link.rel    = 'noopener noreferrer';
        link.textContent = params.value;
        this.eGui = link;
    }
    getGui(){ return this.eGui; }
}
""")

query = st.text_input("作品名を入力してENTER（部分一致可）", "")
if query:
    cand = process.extract(
        query,
        df["work"].unique(),
        scorer=fuzz.token_set_ratio,
        limit=10,
    )
    sel = st.selectbox("候補を選択", [c[0] for c in cand])
    if sel:
        sub = (
            df[df["work"] == sel]
            .sort_values(["year", "month"])
            .reset_index(drop=True)
        )

        # 英字表記から日本語表記への変換辞書
        replace_dict = {
            "kirara": "きらら",
            "kirara-carat": "キャラット",
            "kirara-forward": "フォワード",
            "kirara-max": "MAX",
            "kirara-miracle": "ミラク"
        }
        #日本語項目に修正
        sub["年"] = sub["year"]
        sub["月"] = sub["month"]
        sub["掲載順"] = sub["rank"]
        sub["URL"] = sub["url"]
        sub["雑誌名"] = sub["magazine"].map(replace_dict).fillna(sub["magazine"])
        # 見やすい表示用に絵文字カラム
        sub["表紙"] = sub["is_cover"].map({True: "●", False: ""})
        sub["巻頭カラー"] = sub["is_top"].map({True: "●", False: ""})
        sub["センターカラー"] = sub["is_center"].map({True: "●", False: ""})
        show_cols = [
            "年",
            "月",
            "雑誌名",
            "掲載順",
            "表紙",
            "巻頭カラー",
            "センターカラー",
            "URL",
        ]
        show_df = sub[show_cols]
        # ① フィルタ・メニューアイコンを消す ──────────
        st.markdown("""
        <style>
        /* ─── スマホ幅でもヘッダーを 2 文字入るように ─── */
        @media(max-width: 600px){
        .ag-icon-menu,
        .ag-icon-filter{
            display:none !important;        /* アイコン非表示 */
        }
        .ag-header-cell-label{
            white-space:normal !important;  /* 折り返し許可 */
            line-height:1.1rem;
        }
        }
        </style>
        """, unsafe_allow_html=True)

        # ④ AG Grid のオプション作成
        gb = GridOptionsBuilder.from_dataframe(show_df)      # ← show_df はフィルタ後の DataFrame
        # ── ヘッダー折り返しを有効に（全列デフォルト） ──
        gb.configure_default_column(
            filter=True, sortable=True, resizable=True,
            wrapHeaderText=True,        # ★ ← 追加
            autoHeaderHeight=True       # ★ ← 追加
        )

        # --- 日本語ロケールを設定 ----------------
        jp_locale = {
            "contains": "含む",
            "notContains": "含まない",
            "equals": "等しい",
            "notEqual": "等しくない",
            "greaterThan": "より大きい",
            "greaterThanOrEqual": "以上",
            "lessThan": "未満",
            "lessThanOrEqual": "以下",
            "inRange": "間",
            "notEquals": "等しくない",
            "startsWith": "で始まる",
            "endsWith": "で終わる",
            "blank": "空白",
            "notBlank": "空白以外",
            "andCondition": "かつ",
            "orCondition": "または",
            "filterOoo": "フィルター...",
            "applyFilter": "適用",
            "resetFilter": "リセット",
            "cancelFilter": "キャンセル",
            "clearFilter": "クリア",
            "sortAscending": "昇順で並べ替え",
            "sortDescending": "降順で並べ替え",
            "hideColumn": "列を隠す",
            "unpinColumn": "列の固定を解除",
            "autosizeThis": "自動サイズ調整",
            # 以下は必要に応じて追加（公式の localeText_JP.ts を丸ごと貼っても可）
        }
        # 🔸 ② 各列にツールチップを付ける
        for col in ["年", "月", "雑誌名", "掲載順"]:
            gb.configure_column(col, headerTooltip="クリックで並べ替え")

        gb.configure_column("掲載順",  header_name="掲\n載\n順")
        gb.configure_column("雑誌名",  header_name="雑\n誌\n名")
        gb.configure_column("表紙",    header_name="表\n紙",)
        gb.configure_column("巻頭カラー", header_name="巻\n頭",)
        gb.configure_column("センターカラー", header_name="セ\nン\nタ\nー\nカ\nラ\nー")
        # 🔸 URL 列だけセルレンダラーを指定
        gb.configure_column("URL", header_name="参\n照\n元\nU\nR\nL", cellRenderer=link_renderer)
        grid_opts = gb.build()
        grid_opts["localeText"] = jp_locale      # ★ ここがポイント

        # ⑤ 表示
        AgGrid(
            show_df,
            gridOptions=grid_opts,
            height=600,
            fit_columns_on_grid_load=True,
            theme="streamlit",                  # 好みで light / dark テーマも可
            allow_unsafe_jscode=True,     # ← これを追加
        )
