import streamlit as st
import pandas as pd
import numpy as np
import requests, base64, io, os

st.set_page_config(page_title="自分専用 競馬AI Pro", layout="wide")

def get_gh():
    return st.secrets.get("GITHUB_TOKEN", ""), st.secrets.get("GITHUB_REPO", "cheni135/keiba-ai-pro")

def load_csv(fn, cols):
    tk, rp = get_gh()
    if tk:
        s = chr(47)
        r = requests.get(f"https:{s}{s}://github.com{s}repos{s}{rp}{s}contents{s}{fn}", headers={"Authorization": f"token {tk}"}, timeout=10)
        if r.status_code == 200:
            return pd.read_csv(io.StringIO(base64.b64decode(r.json().get("content", "")).decode("utf-8-sig")))
    return pd.read_csv(fn) if os.path.exists(fn) else pd.DataFrame(columns=cols)

def save_csv(fn, df_s, msg):
    df_s.to_csv(fn, index=False, encoding="utf-8-sig")
    tk, rp = get_gh()
    if not tk: return False
    s = chr(47)
    u = f"https:{s}{s}://github.com{s}repos{s}{rp}{s}contents{s}{fn}"
    hd = {"Authorization": f"token {tk}"}
    rg = requests.get(u, headers=hd, timeout=10)
    pl = {"message": msg, "content": base64.b64encode(df_s.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")).decode("utf-8")}
    if rg.status_code == 200: pl["sha"] = rg.json().get("sha")
    return requests.put(u, headers=hd, json=pl, timeout=15).status_code in (200, 201)

if "cloud_loaded" not in st.session_state:
    st.session_state["my_preds_df"] = load_csv("my_predictions.csv", ["開催", "レース", "馬番", "My印", "Myメモ"])
    st.session_state["ledger_df"] = load_csv("my_ledger.csv", ["レース", "券種", "投資額", "払戻額", "収支", "結果"])
    st.session_state["cloud_loaded"] = True

page_mode = st.radio("メニュー選択", ("🔥 勝負レース・お宝馬", "📋 出馬表・My予想", "🤖 AIスコア・根拠分析", "💰 買い目・合成オッズ", "🌱 当日の馬場傾向", "📈 収支・回収率管理"), horizontal=True)
st.divider()

if not os.path.exists("latest_races.csv"):
    st.error("データ未生成です。Actionsから実行してください。")
    st.stop()
all_df = pd.read_csv("latest_races.csv")
if all_df.empty:
    st.warning("データが空です。")
    st.stop()

last_upd = str(all_df.get("更新日時").iloc[0]) if "更新日時" in all_df.columns else "自動更新済み"
tk_c, _ = get_gh()
st.caption(f"🔄 AI最終更新: {last_upd} ｜ {'☁️ クラウド保存ON' if tk_c else '💾 ローカル保存モード'}")

def score_rank(v):
    return "S（超抜）" if v >= 70 else "A（優秀）" if v >= 60 else "B（平均以上）" if v >= 50 else "C（平均未満）"

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
    if float(r.get("期待値スコア", 100)) >= 120: res.append(f"勝率{r.get('AI予測勝率')}%/3着内{r.get('AI予測3着内率')}%に対し単勝{r.get('単勝オッズ')}倍は甘く期待値{r.get('期待値スコア')}ptのお宝候補。")
    return f"能力{r.get('能力スコア')}点（平均比 {df_a:+.1f}pt）：" + (" ／ ".join(res) if res else "平均水準のバランス型。")
if "勝負レース" in page_mode:
    st.header("🔥 本日のAI激アツ勝負レース＆お宝穴馬")
    hot = []
    for (ks, rn), g in all_df.groupby(["開催", "レース"], sort=False):
        sg = g.sort_values("能力スコア", ascending=False)
        t1 = sg.iloc[0］
        t2 = sg.iloc[1］ if len(sg) > 1 else t1
        d12 = round(float(t1.get("能力スコア")) - float(t2.get("能力スコア")), 1)
        eh = g.sort_values("期待値スコア", ascending=False).iloc[0］
        bg = "👑 AI鉄板・自信あり" if float(t1.get("能力スコア")) >= 66 and d12 >= 4.5 else "💎 激アツお宝レース" if float(g.get("期待値スコア").max()) >= 125 else "🔥 有力軸信頼" if d12 >= 3.5 else ""
        if bg:
            hot.append({"判定": bg, "開催": ks, "レース": rn, "AI能力1位": f"{int(t1.get('馬番'))}番 {t1.get('馬名')} ({t1.get('能力スコア')}点)", "2位差": f"+{d12}pt", "期待値TOP": f"{int(eh.get('馬番'))}番 {eh.get('馬名')} ({eh.get('期待値スコア')}pt / {eh.get('単勝オッズ')}倍)"})
    st.subheader("🎯 AIピックアップ！本日の勝負レース")
    if hot: st.dataframe(pd.DataFrame(hot), use_container_width=True, hide_index=True)
    else: st.info("混戦模様のレースが多い開催です。下のお宝穴馬を狙いましょう。")
    st.divider()
    st.subheader("🏆 全レース横断・期待値Sランク（115pt超え）お宝穴馬 TOP10")
    tr = all_df.query("期待値スコア >= 115.0").sort_values("期待値スコア", ascending=False).head(10)
    if not tr.empty:
        tc = tuple(c for c in ("開催", "レース", "馬番", "馬名", "netkeiba", "騎手", "激変サイン", "単勝オッズ", "能力スコア", "AI予測3着内率", "期待値スコア") if c in tr.columns)
        st.dataframe(tr.loc[:, tc], column_config={"netkeiba": st.column_config.LinkColumn("戦績", display_text="🔍 戦績")}, use_container_width=True, hide_index=True)

elif "収支" in page_mode:
    st.header("📈 My収支＆回収率管理トラッカー")
    ld = st.session_state["ledger_df"].copy()
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        lr = c1.text_input("レース名", value="東京11R")
        lb = c2.selectbox("券種", ("馬連", "3連複", "3連単", "単勝", "複勝", "ワイド", "馬単", "枠連"))
        li = c3.number_input("投資額(円)", 100, 1000000, 1000, 100)
        lo = c4.number_input("払戻額(円)", 0, 10000000, 0, 100)
        if st.button("💾 この収支を保存する", type="primary"):
            upd = pd.concat([ld, pd.DataFrame([{"レース": lr, "券種": lb, "投資額": int(li), "払戻額": int(lo), "収支": int(lo - li), "結果": "🎯 的中" if lo > 0 else "ハズレ"}])], ignore_index=True)
            st.session_state["ledger_df"] = upd
            save_csv("my_ledger.csv", upd, "Update ledger")
            st.rerun()
    if not ld.empty:
        ti, tr_a = int(ld["投資額"].sum()), int(ld["払戻額"].sum())
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("累計投資", f"{ti:,}円")
        m2.metric("累計払戻", f"{tr_a:,}円")
        m3.metric("トータル収支", f"{tr_a - ti:+,}円")
        m4.metric("回収率", f"{round(tr_a / ti * 100, 1) if ti > 0 else 0}%")
        ld["累計収支"] = ld["収支"].cumsum()
        st.line_chart(ld["累計収支"])
        st.dataframe(ld.drop(columns=["累計収支"]), use_container_width=True, hide_index=True)
else:
    ct1, ct2 = st.columns(2)
    sk = ct1.selectbox("開催場を選択", tuple(all_df.get("開催").unique()))
    sdf = all_df.query("開催 == @sk").sort_values("レース番号")
    sr = ct2.selectbox("レースを選択", tuple(sdf.get("レース").unique()))
    rdf = sdf.query("レース == @sr").sort_values("馬番").copy()

    rb = rdf.sort_values("能力スコア", ascending=False).reset_index(drop=True)
    aim = ("◎", "○", "▲", "△", "☆")
    amap = {int(r.get("馬番")): (aim[i] if i < 5 else "") for i, r in enumerate(rb.to_dict("records"))}
    pdf = st.session_state["my_preds_df"]
    rp = pdf.query("開催 == @sk and レース == @sr")
    smk = {int(r.get("馬番")): str(r.get("My印", "")) if pd.notna(r.get("My印")) else "" for r in rp.to_dict("records")}
    smm = {int(r.get("馬番")): str(r.get("Myメモ", "")) if pd.notna(r.get("Myメモ")) else "" for r in rp.to_dict("records")}
    rdf = rdf.assign(AI印=tuple(amap.get(int(u), "") for u in rdf.get("馬番")), My印=tuple(smk.get(int(u), "") for u in rdf.get("馬番")), Myメモ=tuple(smm.get(int(u), "") for u in rdf.get("馬番")))

    if "出馬表" in page_mode:
        st.subheader(f"📋 {sk} {sr} 出馬表・My予想")
        scols = tuple(c for c in ("枠番", "馬番", "My印", "AI印", "馬名", "netkeiba", "斤量", "騎手", "脚質", "父馬", "激変サイン", "単勝オッズ", "Myメモ") if c in rdf.columns)
        ed = st.data_editor(rdf.loc[:, scols], column_config={"My印": st.column_config.SelectboxColumn("My印", options=("", "◎", "○", "▲", "△", "☆", "✓", "消"), width="small"), "netkeiba": st.column_config.LinkColumn("詳細", display_text="🔍 戦績", width="small")}, use_container_width=True, hide_index=True, key=f"ed_{sk}_{sr}")
        if st.button("💾 このレースのMy印・Myメモを永続保存", type="primary"):
            op = pdf.query("not (開催 == @sk and レース == @sr)")
            nr = [{"開催": sk, "レース": sr, "馬番": int(r["馬番"]), "My印": r.get("My印", ""), "Myメモ": r.get("Myメモ", "")} for r in ed.to_dict("records") if r.get("My印") or r.get("Myメモ")]
            upd = pd.concat([op, pd.DataFrame(nr)], ignore_index=True)
            st.session_state["my_preds_df"] = upd
            save_csv("my_predictions.csv", upd, f"Save {sk} {sr}")
            st.success("保存しました！")

    elif "AIスコア" in page_mode:
        st.subheader(f"🤖 {sk} {sr} AIスコア・根拠分析")
        md = st.radio("モード", ("🎯 的中重視（能力スコア）", "💰 回収率重視（期待値スコア）"), horizontal=True)
        sc = "能力スコア" if "的中" in md else "期待値スコア"
        rk = rdf.sort_values(sc, ascending=False).reset_index(drop=True)
        rk = rk.assign(AI印=tuple(aim[i] if i < 5 else "" for i in range(len(rk))))
        avg = round(float(rk["能力スコア"].mean()), 1)
        brd = round(avg + 3.0, 1)
        ibk = (rk["AI予測3着内率"] >= 25.0) | (rk["能力スコア"] >= brd)
        m1, m2, m3 = st.columns(3)
        m1.metric("📊 レースAI平均", f"{avg}点")
        m2.metric("🎯 馬券内目安", f"{brd}点 / 3着内25%", delta=f"圏内:{int(ibk.sum())}頭")
        m3.metric("🏆 トップ評価", f"{rk['能力スコア'].iloc}点", delta=f"平均比 {rk['能力スコア'].iloc[0］ - avg:+.1f}")
        rk = rk.assign(馬券内目安=np.where(ibk, "🎯 圏内", "・"), 平均差=np.round(rk["能力スコア"] - avg, 1))
        t1, t2 = st.tabs(("📊 ランキング＆根拠コメント", "🔍 8大ファクター詳細内訳"))
        with t1:
            ac = tuple(c for c in ("AI印", "My印", "馬券内目安", "馬番", "馬名", "netkeiba", "騎手", "単勝オッズ", "能力スコア", "平均差", "AI予測勝率", "AI予測3着内率", "期待値スコア") if c in rk.columns)
            st.dataframe(rk.loc[:, ac], column_config={"netkeiba": st.column_config.LinkColumn("詳細", display_text="🔍 戦績")}, use_container_width=True, hide_index=True)
            for r in rk.head(5).to_dict("records"):
                st.info(f"**{r['AI印']} {int(r['馬番'])}番 {r['馬名']}（単勝{r['単勝オッズ']}倍 / 勝率{r['AI予測勝率']}% / 3着内{r['AI予測3着内率']}%）**\n\n{ai_comment(r, avg)}")
        with t2:
            sh = st.selectbox("馬を選択", rk["馬名"])
            inf = rk.query("馬名 == @sh").squeeze()
            st.success(ai_comment(inf, avg))
            fv = (float(inf["着順着差指数"]), float(inf["ラップタイム指数"]), float(inf["血統適性"]), float(inf["枠順展開適合"]), float(inf["厩舎騎手勝負度"]), float(inf["ローテ体調"]), float(inf["調教指数"]), float(inf["道悪適性"]))
            fdf = pd.DataFrame({"項目": ("1.着順着差(28%)", "2.ラップタイム(22%)", "3.血統適性(15%)", "4.枠順展開(15%)", "5.厩舎騎手(10%)", "6.ローテ体調(5%)", "7.調教指数(5%)", "8.道悪適性(再配分)"), "スコア": fv, "ランク": tuple(score_rank(v) for v in fv)})
            st.dataframe(fdf, use_container_width=True, hide_index=True)
            st.bar_chart(fdf.set_index("項目")["スコア"])

    elif "買い目" in page_mode:
        st.subheader(f"💰 {sk} {sr} 買い目・合成オッズ計算")
        ck1, ck2, ck3 = st.columns(3)
        bt = ck1.selectbox("券種", ("単勝", "複勝", "枠連", "馬連", "ワイド", "馬単", "3連複", "3連単"))
        pr = ck2.radio("自動セット", ("My印", "AI印", "手動"), horizontal=True)
        bg = ck3.number_input("総予算(円)", 100, 1000000, 3000, 100)
        opts = tuple(f"{int(r['馬番'])}番 {r['馬名']} ({r['単勝オッズ']}倍)" for r in rdf.to_dict("records"))
        l2n = {f"{int(r['馬番'])}番 {r['馬名']} ({r['単勝オッズ']}倍)": int(r["馬番"]) for r in rdf.to_dict("records")}
        n2o = {int(r["馬番"]): float(r["単勝オッズ"]) for r in rdf.to_dict("records")}
        n2w = {int(r["馬番"]): int(r["枠番"]) for r in rdf.to_dict("records")}
        mc = "My印" if pr == "My印" else "AI印"
        h_s = set(rdf.query(f"{mc} == '◎'")["馬番"].astype(int))
        a_s = set(rdf.query(f"{mc} in ['○','▲','△','☆','✓']")["馬番"].astype(int))
        def gdf(ts): return [] if pr == "手動" else [o for o in opts if l2n[o] in ts]
        cbs = []
        if bt in ("単勝", "複勝"):
            s1 = st.multiselect("馬を選択", opts, default=gdf(h_s | a_s))
            cbs = [(l2n[x],) for x in s1]
        elif bt in ("枠連", "馬連", "ワイド", "馬単"):
            c1, c2 = st.columns(2)
            s1 = c1.multiselect("1頭目", opts, default=gdf(h_s))
            s2 = c2.multiselect("2頭目", opts, default=gdf(h_s | a_s))
            seen = set()
            for a in [l2n[x] for x in s1]:
                for b in [l2n[x] for x in s2]:
                    p = tuple(sorted((n2w[a], n2w[b]))) if bt == "枠連" else (a, b) if bt == "馬単" else tuple(sorted((a, b))) if a != b else None
                    if p and p not in seen: seen.add(p); cbs.append(p)
        else:
            c1, c2, c3 = st.columns(3)
            s1 = c1.multiselect("1頭目", opts, default=gdf(h_s))
            s2 = c2.multiselect("2頭目", opts, default=gdf(h_s | a_s))
            s3 = c3.multiselect("3頭目", opts, default=gdf(h_s | a_s))
            seen = set()
            for a in [l2n[x] for x in s1]:
                for b in [l2n[x] for x in s2]:
                    for c in [l2n[x] for x in s3]:
                        if len({a, b, c}) == 3:
                            t = (a, b, c) if bt == "3連単" else tuple(sorted((a, b, c)))
                            if t not in seen: seen.add(t); cbs.append(t)
        if cbs:
            tinv = sum(1.0 / max(1.1, v) for v in n2o.values())
            wp = {k: (1.0 / max(1.1, v)) / tinv for k, v in n2o.items()}
            brows = []
            for cb in cbs:
                eo = n2o[cb] if bt == "単勝" else round(max(1.1, n2o[cb]*0.28+0.8), 1) if bt == "複勝" else round(max(1.5, 0.775/(0.07)), 1) if bt == "枠連" else round(max(1.5, 0.775/max(0.0005, wp[cb]*wp[cb]*2)), 1) if bt in ("馬連","ワイド") else round(max(2.0, 0.75/max(0.0003, wp[cb]*wp[cb])), 1) if bt == "馬単" else round(max(3.0, 0.75/max(0.0001, wp[cb]*wp[cb]*wp[cb]*8)), 1)
                brows.append({"買い目": "-".join(map(str, cb)), "想定オッズ": eo})
            bdf = pd.DataFrame(brows).sort_values("想定オッズ").reset_index(drop=True)
            isum = sum(1.0 / o for o in bdf["想定オッズ"])
            syn = round(1.0 / isum, 2)
            bdf["推奨配分(円)"] = [max(100, int(round((bg * ((1.0/o)/isum))/100)*100)) for o in bdf["想定オッズ"]]
            bdf["払戻目安(円)"] = (bdf["想定オッズ"] * bdf["推奨配分(円)"]).astype(int)
            m1, m2, m3 = st.columns(3)
            m1.metric("買い目点数", f"{len(bdf)}点")
            m2.metric("合成オッズ", f"{syn}倍", delta="トリガミ注意" if syn < 1.0 else "プラス圏", delta_color="inverse" if syn < 1.0 else "normal")
            m3.metric("配分合計", f"{bdf['推奨配分(円)'].sum():,}円")
            st.dataframe(bdf, use_container_width=True, hide_index=True)

    else:
        st.header(f"🌱 {sk} 当日の馬場傾向レポート")
        bs = st.radio("コース", ("芝コース", "ダートコース"), horizontal=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("馬場状態", "良（クッション値 9.4）" if bs == "芝コース" else "良（含水率 3.2%）")
        c2.metric("時計レベル", "やや高速（-0.6秒）" if bs == "芝コース" else "標準（±0.0秒）")
        c3.metric("バイアス判定", "内・先行やや有利" if bs == "芝コース" else "先行・外枠スムーズ有利")
        tdf = sdf.query(f"馬場 == '{'芝' if bs == '芝コース' else 'ダート'}'")
        pk = tdf.query("枠番 <= 4 and 脚質 in ['逃げ','先行']" if bs == "芝コース" else "枠番 >= 5 and 脚質 in ['逃げ','先行']").sort_values("能力スコア", ascending=False)
        st.subheader("🔍 本日のバイアス合致馬")
        if not pk.empty:
            st.dataframe(pk.loc[:, ("レース", "枠番", "馬番", "馬名", "脚質", "騎手", "単勝オッズ", "能力スコア", "AI予測3着内率", "期待値スコア")].head(15), use_container_width=True, hide_index=True)
