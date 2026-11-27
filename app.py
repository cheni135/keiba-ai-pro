import streamlit as st
import pandas as pd
import numpy as np
import requests, base64, io, os

st.set_page_config(page_title="競馬AI Pro", layout="wide")

st.markdown("""
<style>
.nk-header { background: linear-gradient(90deg, #1e3a8a, #2563eb); color: #ffffff; padding: 12px 16px; border-radius: 8px; margin-bottom: 10px; font-weight: bold; font-size: 18px; }
.nk-card { background: #1e2126; color: #f0f2f5; border: 1px solid #374151; padding: 10px 12px; display: flex; align-items: center; justify-content: space-between; border-radius: 8px; margin-bottom: 8px; }
.waku-box { width: 32px; height: 36px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 16px; margin-right: 10px; flex-shrink: 0; }
.w1 { background: #ffffff; color: #111111; }
.w2 { background: #222222; color: #ffffff; border: 1px solid #666; }
.w3 { background: #d93829; color: #ffffff; }
.w4 { background: #2563eb; color: #ffffff; }
.w5 { background: #eab308; color: #111111; }
.w6 { background: #16a34a; color: #ffffff; }
.w7 { background: #ea580c; color: #ffffff; }
.w8 { background: #ec4899; color: #ffffff; }
.r-badge { background: #2563eb; color: #fff; font-weight: bold; padding: 3px 8px; border-radius: 4px; font-size: 13px; margin-right: 6px; }
.cls-badge { background: #374151; color: #e5e7eb; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 6px; }
.cls-g1 { background: #dc2626; color: #fff; }
.odds-txt { color: #f87171; font-weight: bold; font-size: 16px; text-align: right; }
.score-pill { background: #2563eb; color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: bold; }
.mark-badge { display: inline-block; width: 24px; text-align: center; font-weight: bold; color: #fbbf24; font-size: 15px; margin-right: 6px; }
</style>
<div class="nk-header">🏇 競馬AI Pro（netkeibaスタイル）</div>
""", unsafe_allow_html=True)

def get_gh():
    return st.secrets.get("GITHUB_TOKEN", ""), st.secrets.get("GITHUB_REPO", "cheni135/keiba-ai-pro")

def load_csv(fn, cols):
    tk, rp = get_gh()
    if tk:
        u = f"https://github.com{rp}/contents/{fn}"
        r = requests.get(u, headers={"Authorization": f"token {tk}"}, timeout=10)
        if r.status_code == 200:
            return pd.read_csv(io.StringIO(base64.b64decode(r.json().get("content", "")).decode("utf-8-sig")))
    return pd.read_csv(fn) if os.path.exists(fn) else pd.DataFrame(columns=cols)

def save_csv(fn, df_s, msg):
    df_s.to_csv(fn, index=False, encoding="utf-8-sig")
    tk, rp = get_gh()
    if not tk:
        return False
    u = f"https://github.com{rp}/contents/{fn}"
    hd = {"Authorization": f"token {tk}"}
    rg = requests.get(u, headers=hd, timeout=10)
    pl = {
        "message": msg,
        "content": base64.b64encode(df_s.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")).decode("utf-8")
    }
    if rg.status_code == 200:
        pl["sha"] = rg.json().get("sha")
    return requests.put(u, headers=hd, json=pl, timeout=15).status_code in (200, 201)
if "cloud_loaded" not in st.session_state:
    st.session_state["my_preds_df"] = load_csv("my_predictions.csv", ["開催", "レース", "馬番", "My印", "Myメモ"])
    st.session_state["cloud_loaded"] = True

h1, h2 = st.columns((2, 1))
h1.markdown("### 🏇 競馬AI Pro")
with h2:
    st.link_button("🔄 最新オッズ更新", "shortcuts://run-shortcut?name=KeibaAIUpdate", use_container_width=True)

page_mode = st.radio(
    "メニュー",
    ("🔥 勝負レース", "📋 出馬表", "🤖 AI分析", "💰 買い目", "🌱 馬場傾向"),
    horizontal=True,
    label_visibility="collapsed"
)

if not os.path.exists("latest_races.csv"):
    st.error("データ未生成です。GitHub Actionsでデータ更新を実行してください。")
    st.stop()

all_df = pd.read_csv("latest_races.csv")
if all_df.empty:
    st.warning("データが空です。")
    st.stop()

upd_str = str(all_df["更新日時"].head(1).squeeze()) if "更新日時" in all_df.columns else "自動更新済"
st.caption(f"🔄 最終更新: {upd_str}")

def score_rank(v):
    return "S（超抜）" if v >= 70 else "A（優秀）" if v >= 60 else "B（平均以上）" if v >= 50 else "C（平均未満）"

def assign_ai_marks(g_df):
    sg = g_df.sort_values("能力スコア", ascending=False).copy()
    marks = ["◎", "○", "▲", "☆", "△", "△", "△"]
    mark_map = {}
    for idx, (_, row) in enumerate(sg.iterrows()):
        if idx < len(marks):
            mark_map[int(row["馬番"])] = marks[idx]
        elif float(row.get("期待値スコア", 0)) >= 120:
            mark_map[int(row["馬番"])] = "穴"
        else:
            mark_map[int(row["馬番"])] = ""
    return mark_map

def ai_comment(r, avg):
    df_a = round(float(r.get("能力スコア", 50)) - avg, 1)
    p, m = [], []
    if float(r.get("着順着差指数", 50)) >= 60: p.append(f"着順・着差({r.get('着順着差指数')}点)優秀")
    elif float(r.get("着順着差指数", 50)) <= 42: m.append(f"近走着差({r.get('着順着差指数')}点)割引")
    if float(r.get("不利補正値", 0)) > 0: p.append(f"不利補正(+{int(r.get('不利補正値'))}pt)")
    if float(r.get("ラップタイム指数", 50)) >= 60: p.append(f"馬場差補正タイム({r.get('ラップタイム指数')}点)上位")
    if float(r.get("血統適性", 50)) >= 60: p.append(f"父{r.get('父馬')}適性({r.get('血統適性')}点)高")
    if float(r.get("枠順展開適合", 50)) >= 58: p.append(f"{int(r.get('枠番'))}枠・{r.get('脚質')}展開合致")
    if float(r.get("厩舎騎手勝負度", 50)) >= 58: p.append(f"{r.get('騎手')}勝負気配({r.get('厩舎騎手勝負度')}点)")
    if pd.notna(r.get("激変サイン")) and str(r.get("激変サイン")): p.append(f"激変【{r.get('激変サイン')}】")
    res = []
    if p: res.append("【プラス】" + "・".join(p[:3]))
    if m: res.append("【マイナス】" + "・".join(m[:2]))
    if float(r.get("期待値スコア", 100)) >= 120:
        res.append(f"勝率{r.get('AI予測勝率')}%/3着内{r.get('AI予測3着内率')}%に対し単勝{r.get('単勝オッズ')}倍は甘く期待値{r.get('期待値スコア')}ptのお宝候補。")
    return f"能力{r.get('能力スコア')}点（平均比 {df_a:+.1f}pt）：" + (" ／ ".join(res) if res else "平均水準のバランス型。")

def select_race_ui(df):
    c1, c2 = st.columns(2)
    ks_list = list(df["開催"].unique())
    sel_ks = c1.selectbox("開催場", ks_list, key="sel_ks")
    sub_ks = df[df["開催"] == sel_ks].sort_values("レース番号")
    rc_list = list(sub_ks["レース"].unique())
    sel_rc = c2.selectbox("レース", rc_list, key="sel_rc")
    return sel_ks, sel_rc, sub_ks[sub_ks["レース"] == sel_rc].sort_values("馬番")

if "勝負レース" in page_mode:
    st.subheader("🔥 本日のAI激アツ勝負レース")
    found = False
    for (ks, rn), g in all_df.groupby(["開催", "レース"], sort=False):
        sg = g.sort_values("能力スコア", ascending=False)
        t1 = sg.head(1).squeeze()
        t2 = sg.head(2).tail(1).squeeze() if len(sg) > 1 else t1
        d12 = round(float(t1["能力スコア"]) - float(t2["能力スコア"]), 1)
        eh = g.sort_values("期待値スコア", ascending=False).head(1).squeeze()
        bg = (
            "👑 AI鉄板・自信あり" if float(t1["能力スコア"]) >= 66 and d12 >= 4.5 else
            "💎 激アツお宝レース" if float(g["期待値スコア"].max()) >= 125 else
            "🔥 有力軸信頼" if d12 >= 3.5 else ""
        )
        if bg:
            found = True
            cls_c = "cls-badge cls-g1" if "G1" in str(rn) else "cls-badge"
            st.markdown(f"""
            <div class="nk-card">
                <div>
                    <div><span class="r-badge">{int(t1['レース番号'])}R</span><b>{ks}</b><span class="{cls_c}">{t1['レースクラス']}</span> <span style="font-size:12px;color:#9ca3af;">{t1['馬場']}{int(t1['距離'])}m {len(g)}頭</span></div>
                    <div style="font-size:13px;margin-top:4px;"><span style="color:#fbbf24;font-weight:bold;">{bg}</span> ｜ ◎{int(t1['馬番'])}{t1['馬名']}({t1['能力スコア']}点 / 2位差+{d12})</div>
                    <div style="font-size:12px;color:#38bdf8;">💎期待値TOP: {int(eh['馬番'])}{eh['馬名']} ({eh['期待値スコア']}pt / {eh['単勝オッズ']}倍)</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    if not found:
        st.info("混戦模様のレースが多い開催です。下のお宝穴馬を狙いましょう。")

    st.subheader("🏆 期待値Sランク（115pt超え）お宝穴馬 TOP10")
    tr = all_df.query("期待値スコア >= 115.0").sort_values("期待値スコア", ascending=False).head(10)
    for r in tr.to_dict("records"):
        wk = int(r.get("枠番", 1))
        st.markdown(f"""
        <div class="nk-card">
            <div style="display:flex;align-items:center;">
                <div class="waku-box w{wk}">{int(r['馬番'])}</div>
                <div>
                    <div style="font-size:11px;color:#9ca3af;">{r['開催']} {r['レース']}</div>
                    <div><a href="{r['netkeiba']}" target="_blank" style="color:#fff;font-weight:bold;text-decoration:none;font-size:15px;">{r['馬名']} 🔗</a> <span style="font-size:12px;color:#fbbf24;">{r.get('激変サイン','')}</span></div>
                    <div style="font-size:12px;color:#9ca3af;">{r['騎手']} ｜ 能力{r['能力スコア']}点 ｜ 3着内{r['AI予測3着内率']}%</div>
                </div>
            </div>
            <div style="text-align:right;">
                <div class="odds-txt">{r['単勝オッズ']}倍</div>
                <div class="score-pill" style="background:#dc2626;">期待値 {r['期待値スコア']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    elif "出馬表" in page_mode:
    sel_ks, sel_rc, rdf = select_race_ui(all_df)
    st.subheader(f"📋 {sel_ks} {sel_rc}")
    ai_marks = assign_ai_marks(rdf)
    preds_df = st.session_state["my_preds_df"]

    sort_opt = st.radio("並び順", ("馬番順", "AI能力スコア順", "期待値スコア順"), horizontal=True)
    if sort_opt == "AI能力スコア順":
        rdf = rdf.sort_values("能力スコア", ascending=False)
    elif sort_opt == "期待値スコア順":
        rdf = rdf.sort_values("期待値スコア", ascending=False)

    for r in rdf.to_dict("records"):
        wk = int(r.get("枠番", 1))
        uma = int(r["馬番"])
        amk = ai_marks.get(uma, "")
        existing = preds_df[(preds_df["開催"] == sel_ks) & (preds_df["レース"] == sel_rc) & (preds_df["馬番"] == uma)]
        cur_my = str(existing["My印"].iloc[0]) if not existing.empty and pd.notna(existing["My印"].iloc[0]) else ""
        sign_txt = f"<span style='color:#fbbf24;font-size:12px;'>★{r['激変サイン']}</span>" if pd.notna(r.get("激変サイン")) and str(r.get("激変サイン")) else ""

        st.markdown(f"""
        <div class="nk-card">
            <div style="display:flex;align-items:center;">
                <div class="mark-badge">{amk}</div>
                <div class="waku-box w{wk}">{uma}</div>
                <div>
                    <div>
                        <a href="{r['netkeiba']}" target="_blank" style="color:#fff;font-weight:bold;text-decoration:none;font-size:15px;">{r['馬名']} 🔗</a>
                        <span style="font-size:12px;color:#9ca3af;">({r.get('性齢','')})</span>
                        {f"<span class='cls-badge' style='background:#b45309;'>My:{cur_my}</span>" if cur_my else ""}
                        {sign_txt}
                    </div>
                    <div style="font-size:12px;color:#d1d5db;">{r['騎手']} ({r.get('斤量',56.0)}kg) ｜ 脚質:{r.get('脚質','-')}</div>
                    <div style="font-size:11px;color:#9ca3af;">勝率 {r['AI予測勝率']}% / 3着内 {r['AI予測3着内率']}% / 期待値 {r['期待値スコア']}pt</div>
                </div>
            </div>
            <div style="text-align:right;">
                <div class="odds-txt">{r['単勝オッズ']}倍</div>
                <div class="score-pill">能力 {r['能力スコア']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("✍️ My印・メモを登録（GitHubへクラウド保存）"):
        with st.form("my_pred_form"):
            uma_opts = [f"{int(x['馬番'])}番 {x['馬名']}" for x in rdf.sort_values("馬番").to_dict("records")]
            sel_uma_str = st.selectbox("対象馬", uma_opts)
            sel_uma = int(sel_uma_str.split("番")[0])
            my_mark = st.selectbox("My印", ["", "◎", "○", "▲", "☆", "△", "消"])
            my_memo = st.text_input("メモ（例：前走不利あり、パドック気配◎）")
            if st.form_submit_button("💾 保存する", use_container_width=True):
                df_p = st.session_state["my_preds_df"]
                df_p = df_p[~((df_p["開催"] == sel_ks) & (df_p["レース"] == sel_rc) & (df_p["馬番"] == sel_uma))]
                if my_mark or my_memo:
                    new_row = pd.DataFrame([{"開催": sel_ks, "レース": sel_rc, "馬番": sel_uma, "My印": my_mark, "Myメモ": my_memo}])
                    df_p = pd.concat([df_p, new_row], ignore_index=True)
                st.session_state["my_preds_df"] = df_p
                ok = save_csv("my_predictions.csv", df_p, f"Update My prediction {sel_ks} {sel_rc}")
                if ok:
                    st.success("クラウド（GitHub）に保存しました！")
                else:
                    st.info("ローカルに一時保存しました（SecretsにGITHUB_TOKENを設定すると永続化されます）。")

elif "AI分析" in page_mode:
    sel_ks, sel_rc, rdf = select_race_ui(all_df)
    st.subheader(f"🤖 AI詳細スコア分析：{sel_ks} {sel_rc}")
    avg_score = round(float(rdf["能力スコア"].mean()), 1)
    st.info(f"📊 レース平均能力スコア: **{avg_score}点** ｜ 最高スコア: **{rdf['能力スコア'].max()}点**")

    sg = rdf.sort_values("能力スコア", ascending=False)
    for idx, r in enumerate(sg.to_dict("records"), 1):
        wk = int(r.get("枠番", 1))
        sc = float(r["能力スコア"])
        rk = score_rank(sc)
        cmt = ai_comment(r, avg_score)
        with st.container():
            st.markdown(f"""
            <div class="nk-card" style="flex-direction:column;align-items:stretch;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div style="display:flex;align-items:center;">
                        <span style="font-weight:bold;color:#fbbf24;margin-right:8px;">AI {idx}位</span>
                        <div class="waku-box w{wk}">{int(r['馬番'])}</div>
                        <div>
                            <b style="font-size:16px;">{r['馬名']}</b> <span style="font-size:12px;color:#9ca3af;">({r['騎手']})</span>
                            <div style="font-size:12px;color:#38bdf8;">評価ランク: {rk}</div>
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div class="score-pill" style="font-size:14px;">総合 {sc}点</div>
                        <div style="font-size:12px;color:#f87171;margin-top:2px;">単勝 {r['単勝オッズ']}倍 / 期待値 {r['期待値スコア']}</div>
                    </div>
                </div>
                <div style="margin-top:8px;padding-top:8px;border-top:1px solid #374151;font-size:13px;color:#e5e7eb;">
                    {cmt}
                </div>
            </div>
            """, unsafe_allow_html=True)

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("着順着差", f"{r.get('着順着差指数', 50)}")
            m2.metric("ラップ指数", f"{r.get('ラップタイム指数', 50)}")
            m3.metric("血統適性", f"{r.get('血統適性', 50)}")
            m4.metric("枠・展開", f"{r.get('枠順展開適合', 50)}")
            m5.metric("勝負度", f"{r.get('厩舎騎手勝負度', 50)}")
elif "買い目" in page_mode:
    sel_ks, sel_rc, rdf = select_race_ui(all_df)
    st.subheader(f"💰 AI推奨買い目フォーメーション：{sel_ks} {sel_rc}")

    sg = rdf.sort_values("能力スコア", ascending=False).reset_index(drop=True)
    if len(sg) < 4:
        st.warning("出走頭数が少ないため買い目生成をスキップします。")
    else:
        honmei = sg.iloc
        taikou = sg.iloc
        tanana = sg.iloc
        himo = sg.iloc[3:min(7, len(sg))]
        ana = rdf[rdf["期待値スコア"] >= 115.0].sort_values("期待値スコア", ascending=False)

        himo_nums = [str(int(x)) for x in himo["馬番"].tolist()]
        aite_nums = [str(int(taikou["馬番"])), str(int(tanana["馬番"]))] + himo_nums

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            <div class="nk-card" style="flex-direction:column;align-items:flex-start;">
                <div style="color:#fbbf24;font-weight:bold;font-size:15px;">🎯 本線・安定プラン（軸信頼型）</div>
                <div style="margin-top:6px;font-size:14px;"><b>◎ 本命軸：</b>{int(honmei['馬番'])} {honmei['馬名']}（能力 {honmei['能力スコア']}点）</div>
                <div style="font-size:13px;color:#d1d5db;margin-top:4px;"><b>○ 対抗：</b>{int(taikou['馬番'])} {taikou['馬名']} ／ <b>▲ 単穴：</b>{int(tanana['馬番'])} {tanana['馬名']}</div>
                <div style="margin-top:8px;padding:8px;background:#111827;border-radius:6px;width:100%;font-size:13px;">
                    <div>・<b>馬連 / ワイド：</b> {int(honmei['馬番'])} － {", ".join(aite_nums[:4])}（4点）</div>
                    <div>・<b>3連複 1頭軸流し：</b> {int(honmei['馬番'])} － {", ".join(aite_nums[:5])}（10点）</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            if not ana.empty:
                top_ana = ana.iloc
                ana_list = [f"{int(r['馬番'])} {r['馬名']}({r['単勝オッズ']}倍)" for r in ana.head(3).to_dict("records")]
                st.markdown(f"""
                <div class="nk-card" style="flex-direction:column;align-items:flex-start;border-color:#dc2626;">
                    <div style="color:#f87171;font-weight:bold;font-size:15px;">💎 高配当・期待値狙いプラン</div>
                    <div style="margin-top:6px;font-size:14px;"><b>🔥 期待値TOP：</b>{int(top_ana['馬番'])} {top_ana['馬名']}（期待値 {top_ana['期待値スコア']}pt）</div>
                    <div style="font-size:12px;color:#d1d5db;margin-top:4px;"><b>注目穴馬：</b>{" / ".join(ana_list)}</div>
                    <div style="margin-top:8px;padding:8px;background:#111827;border-radius:6px;width:100%;font-size:13px;">
                        <div>・<b>単勝 / 複勝：</b> {int(top_ana['馬番'])} {top_ana['馬名']}</div>
                        <div>・<b>ワイド流し：</b> {int(top_ana['馬番'])} － {int(honmei['馬番'])}, {int(taikou['馬番'])}, {int(tanana['馬番'])}（3点）</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="nk-card" style="flex-direction:column;align-items:flex-start;">
                    <div style="color:#38bdf8;font-weight:bold;font-size:15px;">⚖️ 順当決着・絞り込みプラン</div>
                    <div style="margin-top:6px;font-size:13px;color:#d1d5db;">オッズとAI評価の乖離が小さい堅実な一戦です。点数を絞って回収率を高めましょう。</div>
                    <div style="margin-top:8px;padding:8px;background:#111827;border-radius:6px;width:100%;font-size:13px;">
                        <div>・<b>馬連 / 馬単：</b> {int(honmei['馬番'])} ⇔ {int(taikou['馬番'])}, {int(tanana['馬番'])}</div>
                        <div>・<b>3連単 フォーメーション：</b> {int(honmei['馬番'])} → {int(taikou['馬番'])},{int(tanana['馬番'])} → {", ".join(aite_nums[:4])}（6点）</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

elif "馬場傾向" in page_mode:
    sk = st.selectbox("開催場を選択", tuple(all_df["開催"].unique()))
    sdf = all_df.query("開催 == @sk").sort_values("レース番号")
    st.subheader(f"🌱 {sk} 当日の馬場傾向レポート")
    bs = st.radio("コース", ("芝コース", "ダートコース"), horizontal=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("馬場状態", "良（クッション 9.4）" if bs == "芝コース" else "良（含水率 3.2%）")
    c2.metric("時計レベル", "やや高速（-0.6秒）" if bs == "芝コース" else "標準（±0.0秒）")
    c3.metric("バイアス判定", "内・先行やや有利" if bs == "芝コース" else "先行・外枠スムーズ有利")

    st.bar_chart(
        pd.DataFrame({
            "枠区分": ("1〜2枠", "3〜4枠", "5〜6枠", "7〜8枠"),
            "3着内率(%)": (28.5, 24.0, 19.5, 16.0) if bs == "芝コース" else (18.0, 21.5, 25.0, 27.5)
        }).set_index("枠区分")
    )

    tdf = sdf.query(f"馬場 == '{'芝' if bs == '芝コース' else 'ダート'}'")
    pk = tdf.query(
        "枠番 <= 4 and 脚質 in ('逃げ','先行')" if bs == "芝コース" else "枠番 >= 5 and 脚質 in ('逃げ','先行')"
    ).sort_values("能力スコア", ascending=False).head(10)

    st.subheader(f"🎯 {sk}・{bs}のバイアス合致＆高スコア馬 TOP10")
    if pk.empty:
        st.info("該当する条件の登録馬が見つかりませんでした。")
    else:
        for r in pk.to_dict("records"):
            wk = int(r.get("枠番", 1))
            st.markdown(f"""
            <div class="nk-card">
                <div style="display:flex;align-items:center;">
                    <div class="waku-box w{wk}">{int(r['馬番'])}</div>
                    <div>
                        <div style="font-size:11px;color:#9ca3af;">{r['レース']} ｜ {r['脚質']}</div>
                        <div><a href="{r['netkeiba']}" target="_blank" style="color:#fff;font-weight:bold;text-decoration:none;font-size:15px;">{r['馬名']} 🔗</a></div>
                        <div style="font-size:12px;color:#9ca3af;">{r['騎手']} ｜ 枠順展開適合 {r.get('枠順展開適合', 50)}点</div>
                    </div>
                </div>
                <div style="text-align:right;">
                    <div class="odds-txt">{r['単勝オッズ']}倍</div>
                    <div class="score-pill">能力 {r['能力スコア']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
