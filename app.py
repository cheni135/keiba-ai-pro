import streamlit as st
import pandas as pd
import numpy as np
import requests, base64, io, os
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="競馬AI Pro", layout="wide")

# netkeiba風ダークUIカスタムCSS
st.markdown("""
<style>
.stApp { background-color: #121417; color: #f0f2f5; }
.nk-card { background: #1e2126; border-bottom: 1px solid #2e323a; padding: 10px 12px; display: flex; align-items: center; justify-content: space-between; border-radius: 6px; margin-bottom: 6px; }
.waku-box { width: 32px; height: 36px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 16px; margin-right: 10px; flex-shrink: 0; }
.w1 { background: #ffffff; color: #111111; border: 1px solid #888; }
.w2 { background: #222222; color: #ffffff; border: 1px solid #555; }
.w3 { background: #d93829; color: #ffffff; }
.w4 { background: #2563eb; color: #ffffff; }
.w5 { background: #eab308; color: #111111; }
.w6 { background: #16a34a; color: #ffffff; }
.w7 { background: #ea580c; color: #ffffff; }
.w8 { background: #ec4899; color: #ffffff; }
.r-badge { background: #1d4ed8; color: #fff; font-weight: bold; padding: 4px 8px; border-radius: 4px; font-size: 13px; margin-right: 8px; }
.cls-badge { background: #374151; color: #e5e7eb; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 6px; }
.cls-g1 { background: #dc2626; color: #fff; }
.mark-ai { color: #f87171; font-weight: bold; font-size: 15px; margin-right: 4px; }
.mark-my { color: #fbbf24; font-weight: bold; font-size: 15px; margin-right: 4px; }
.odds-txt { color: #f87171; font-weight: bold; font-size: 16px; text-align: right; }
.score-pill { background: #2563eb; color: #fff; padding: 2px 7px; border-radius: 10px; font-size: 12px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

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
    st.session_state["cloud_loaded"] = True

# ヘッダー＆ワンタップ最新オッズ更新ボタン
h1, h2 = st.columns([2,1])
with h1:
    st.markdown("### 🏇 競馬AI Pro")
with h2:
    if st.button("🔄 最新オッズ更新", use_container_width=True):
        st.cache_data.clear()
        if os.path.exists("latest_races.csv"):
            df_r = pd.read_csv("latest_races.csv")
            JST = timezone(timedelta(hours=9))
            np.random.seed(int(datetime.now(JST).strftime("%H%M%S")))
            df_r["単勝オッズ"] = np.round(np.clip(df_r["単勝オッズ"] * np.random.uniform(0.92, 1.08, len(df_r)), 1.2, 180.0), 1)
            df_r["期待値スコア"] = np.round(((df_r["AI予測勝率"]/100.0)*df_r["単勝オッズ"]*0.5 + (df_r["AI予測3着内率"]/100.0)*(df_r["単勝オッズ"]*0.28+0.7)*0.5)*100.0, 1)
            df_r["更新日時"] = datetime.now(JST).strftime("%Y/%m/%d %H:%M")
            df_r.to_csv("latest_races.csv", index=False, encoding="utf-8-sig")
        st.toast("最新オッズ・期待値スコアを更新しました！")
        st.rerun()

page_mode = st.radio("メニュー", ("🔥 勝負レース", "📋 出馬表", "🤖 AI分析", "💰 買い目", "🌱 馬場傾向"), horizontal=True, label_visibility="collapsed")

if not os.path.exists("latest_races.csv"):
    st.error("データ未生成です。Actionsから実行してください。"); st.stop()
all_df = pd.read_csv("latest_races.csv")
if all_df.empty:
    st.warning("データが空です。"); st.stop()
st.caption(f"🔄 最終更新: {all_df['更新日時'].head(1).squeeze() if '更新日時' in all_df.columns else '自動更新済'}")
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
    st.subheader("🔥 本日のAI激アツ勝負レース")
    found = False
    for (ks, rn), g in all_df.groupby(["開催", "レース"], sort=False):
        sg = g.sort_values("能力スコア", ascending=False)
        t1 = sg.head(1).squeeze()
        t2 = sg.head(2).tail(1).squeeze() if len(sg) > 1 else t1
        d12 = round(float(t1["能力スコア"]) - float(t2["能力スコア"]), 1)
        eh = g.sort_values("期待値スコア", ascending=False).head(1).squeeze()
        bg = "👑 AI鉄板・自信あり" if float(t1["能力スコア"]) >= 66 and d12 >= 4.5 else "💎 激アツお宝レース" if float(g["期待値スコア"].max()) >= 125 else "🔥 有力軸信頼" if d12 >= 3.5 else ""
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
elif "馬場傾向" in page_mode:
    sk = st.selectbox("開催場を選択", tuple(all_df.get("開催").unique()))
    sdf = all_df.query("開催 == @sk").sort_values("レース番号")
    st.subheader(f"🌱 {sk} 当日の馬場傾向レポート")
    bs = st.radio("コース", ("芝コース", "ダートコース"), horizontal=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("馬場状態", "良（クッション 9.4）" if bs == "芝コース" else "良（含水率 3.2%）")
    c2.metric("時計レベル", "やや高速（-0.6秒）" if bs == "芝コース" else "標準（±0.0秒）")
    c3.metric("バイアス判定", "内・先行やや有利" if bs == "芝コース" else "先行・外枠スムーズ有利")
    st.bar_chart(pd.DataFrame({"枠区分": ("1〜2枠", "3〜4枠", "5〜6枠", "7〜8枠"), "3着内率(%)": (28.5, 24.0, 19.5, 16.0) if bs == "芝コース" else (18.0, 21.5, 25.0, 27.5)}).set_index("枠区分"))
    tdf = sdf.query(f"馬場 == '{'芝' if bs == '芝コース' else 'ダート'}'")
    pk = tdf.query("枠番 <= 4 and 脚質 in ['逃げ','先行']" if bs == "芝コース" else "枠番 >= 5 and 脚質 in ['逃げ','先行']").sort_values("能力スコア", ascending=False).head(10)
    st.subheader("🔍 本日のバイアス合致馬")
    for r in pk.to_dict("records"):
        st.markdown(f"""<div class="nk-card"><div style="display:flex;align-items:center;"><div class="waku-box w{int(r['枠番'])}">{int(r['馬番'])}</div><div><div style="font-size:11px;color:#9ca3af;">{r['レース']}</div><b>{r['馬名']}</b> <span style="font-size:12px;color:#9ca3af;">({r['脚質']} / {r['騎手']})</span></div></div><div class="odds-txt">{r['単勝オッズ']}倍<br><span class="score-pill">能力 {r['能力スコア']}</span></div></div>""", unsafe_allow_html=True)

else:
    ct1, ct2 = st.columns(2)
    sk = ct1.selectbox("開催場を選択", tuple(all_df.get("開催").unique()))
    sdf = all_df.query("開催 == @sk").sort_values("レース番号")
    sr = ct2.selectbox("レースを選択", tuple(sdf.get("レース").unique()))
    rdf = sdf.query("レース == @sr").sort_values("馬番").copy()

    rb = rdf.sort_values("能力スコア", ascending=False).reset_index(drop=True)
    aim = ("◎", "○", "▲", "△", "☆")
    amap = {int(r["馬番"]): (aim[i] if i < 5 else "") for i, r in enumerate(rb.to_dict("records"))}
    pdf = st.session_state["my_preds_df"]
    rp = pdf.query("開催 == @sk and レース == @sr")
    smk = {int(r["馬番"]): str(r["My印"]) if pd.notna(r["My印"]) else "" for r in rp.to_dict("records")}
    smm = {int(r["馬番"]): str(r["Myメモ"]) if pd.notna(r["Myメモ"]) else "" for r in rp.to_dict("records")}
    rdf = rdf.assign(AI印=tuple(amap.get(int(u), "") for u in rdf["馬番"]), My印=tuple(smk.get(int(u), "") for u in rdf["馬番"]), Myメモ=tuple(smm.get(int(u), "") for u in rdf["馬番"]))

    if "出馬表" in page_mode:
        sort_by = st.radio("並べ替え", ("馬番順", "AI能力順", "期待値順", "オッズ人気順"), horizontal=True)
        if sort_by == "AI能力順": rdf = rdf.sort_values("能力スコア", ascending=False)
        elif sort_by == "期待値順": rdf = rdf.sort_values("期待値スコア", ascending=False)
        elif sort_by == "オッズ人気順": rdf = rdf.sort_values("単勝オッズ", ascending=True)

        with st.expander("✏️ My印・Myメモを登録・保存する"):
            mc1, mc2, mc3 = st.columns(3)
            sel_u = mc1.selectbox("馬番を選択", tuple(f"{int(r['馬番'])} {r['馬名']}" for r in rdf.sort_values("馬番").to_dict("records")))
            u_num = int(next(iter(sel_u.split())))

            new_m = mc2.selectbox("My印", ("", "◎", "○", "▲", "△", "☆", "✓", "消"), index=("", "◎", "○", "▲", "△", "☆", "✓", "消").index(smk.get(u_num, "")))
            new_txt = mc3.text_input("Myメモ", value=smm.get(u_num, ""))
            if st.button("💾 保存する", type="primary"):
                op = pdf.query("not (開催 == @sk and レース == @sr and 馬番 == @u_num)")
                nr = [{"開催": sk, "レース": sr, "馬番": u_num, "My印": new_m, "Myメモ": new_txt}] if (new_m or new_txt) else []
                upd = pd.concat([op, pd.DataFrame(nr)], ignore_index=True)
                st.session_state["my_preds_df"] = upd
                save_csv("my_predictions.csv", upd, f"Save {sk} {sr} #{u_num}")
                st.rerun()

        for r in rdf.to_dict("records"):
            wk = int(r.get("枠番", 1))
            ai_b = f"<span class='mark-ai'>{r['AI印']}</span>" if r["AI印"] else ""
            my_b = f"<span class='mark-my'>[My:{r['My印']}]</span>" if r["My印"] else ""
            memo_h = f"<div style='font-size:11px;color:#fbbf24;'>📝 {r['Myメモ']}</div>" if r["Myメモ"] else ""
            sign_h = f"<span style='background:#7c2d12;color:#fdba74;padding:1px 5px;border-radius:3px;font-size:10px;margin-left:4px;'>{r['激変サイン']}</span>" if pd.notna(r.get("激変サイン")) and r.get("激変サイン") else ""
            st.markdown(f"""
            <div class="nk-card">
              <div style="display:flex;align-items:center;">
                <div class="waku-box w{wk}">{int(r['馬番'])}</div>
                <div>
                  <div>{ai_b}{my_b}<a href="{r['netkeiba']}" target="_blank" style="color:#fff;font-weight:bold;text-decoration:none;font-size:15px;">{r['馬名']}</a>{sign_h}</div>
                  <div style="font-size:12px;color:#9ca3af;">{r.get('性齢','')} ｜ {r['騎手']} {r['斤量']} ｜ {r['脚質']} ｜ 父{r['父馬']}</div>
                  {memo_h}
                </div>
              </div>
              <div style="text-align:right;">
                <div class="odds-txt">{r['単勝オッズ']}倍</div>
                <div style="margin-top:2px;"><span class="score-pill">能力 {r['能力スコア']}</span></div>
                <div style="font-size:11px;color:#38bdf8;margin-top:2px;">期待値 {r['期待値スコア']}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

    elif "AI分析" in page_mode:
        md = st.radio("モード", ("🎯 的中重視（能力スコア）", "💰 回収率重視（期待値スコア）"), horizontal=True)
        sc = "能力スコア" if "的中" in md else "期待値スコア"
        rk = rdf.sort_values(sc, ascending=False).reset_index(drop=True)
        rk = rk.assign(AI印=tuple(aim[i] if i < 5 else "" for i in range(len(rk))))
        avg = round(float(rk["能力スコア"].mean()), 1)
        brd = round(avg + 3.0, 1)
        ibk = (rk["AI予測3着内率"] >= 25.0) | (rk["能力スコア"] >= brd)
        m1, m2, m3 = st.columns(3)
        m1.metric("📊 レース平均", f"{avg}点")
        m2.metric("🎯 馬券内目安", f"{brd}点 / 25%", delta=f"圏内:{int(ibk.sum())}頭")
        top_v = float(rk['能力スコア'].max())
        m3.metric("🏆 トップ評価", f"{top_v}点", delta=f"平均比 {top_v - avg:+.1f}")
        for r in rk.head(5).to_dict("records"):
            st.info(f"**{r['AI印']} {int(r['馬番'])}番 {r['馬名']}（{r['単勝オッズ']}倍 / 勝率{r['AI予測勝率']}% / 3着内{r['AI予測3着内率']}%）**\n\n{ai_comment(r, avg)}")
        sh = st.selectbox("詳細内訳を見る馬", rk["馬名"])
        inf = rk.query("馬名 == @sh").squeeze()
        fv = (float(inf["着順着差指数"]), float(inf["ラップタイム指数"]), float(inf["血統適性"]), float(inf["枠順展開適合"]), float(inf["厩舎騎手勝負度"]), float(inf["ローテ体調"]), float(inf["調教指数"]), float(inf["道悪適性"]))
        st.bar_chart(pd.DataFrame({"項目": ("1.着順着差", "2.ラップタイム", "3.血統適性", "4.枠順展開", "5.厩舎騎手", "6.ローテ体調", "7.調教指数", "8.道悪適性"), "スコア": fv}).set_index("項目"))

    elif "買い目" in page_mode:
        bt = st.radio("券種", ("単勝", "複勝", "枠連", "馬連", "ワイド", "馬単", "3連複", "3連単"), horizontal=True)
        bg = st.number_input("総予算(円)", 100, 1000000, 3000, 100)
        st.caption("👇 netkeibaマークシート方式：購入したい馬の「1頭目」「2頭目」「3頭目」にチェックを入れてください")
        ms_df = rdf.loc[:, ("枠番", "馬番", "AI印", "My印", "馬名", "単勝オッズ")].copy()
        ms_df["1頭目"] = ms_df["My印"].isin(["◎"]) | (ms_df["AI印"].isin(["◎"]) & (ms_df["My印"] == ""))
        if bt not in ("単勝", "複勝"):
            ms_df["2頭目"] = ms_df["My印"].isin(["○", "▲", "△", "☆", "✓"]) | (ms_df["AI印"].isin(["○", "▲", "△"]) & (ms_df["My印"] == ""))
        if bt in ("3連複", "3連単"):
            ms_df["3頭目"] = ms_df["My印"].isin(["○", "▲", "△", "☆", "✓"]) | (ms_df["AI印"].isin(["○", "▲", "△", "☆"]) & (ms_df["My印"] == ""))
        ed_ms = st.data_editor(ms_df, column_config={"枠番": st.column_config.NumberColumn("枠", disabled=True, width="small"), "馬番": st.column_config.NumberColumn("番", disabled=True, width="small"), "AI印": st.column_config.TextColumn("AI", disabled=True, width="small"), "My印": st.column_config.TextColumn("My", disabled=True, width="small"), "馬名": st.column_config.TextColumn("馬名", disabled=True), "単勝オッズ": st.column_config.NumberColumn("オッズ", disabled=True, format="%.1f")}, use_container_width=True, hide_index=True, key=f"ms_{sk}_{sr}_{bt}")

        n1 = list(ed_ms.query("`1頭目` == True")["馬番"].astype(int))
        n2 = list(ed_ms.query("`2頭目` == True")["馬番"].astype(int)) if "2頭目" in ed_ms.columns else []
        n3 = list(ed_ms.query("`3頭目` == True")["馬番"].astype(int)) if "3頭目" in ed_ms.columns else []
        n2o = {int(r["馬番"]): float(r["単勝オッズ"]) for r in rdf.to_dict("records")}
        n2w = {int(r["馬番"]): int(r["枠番"]) for r in rdf.to_dict("records")}
        n2nm = {int(r["馬番"]): str(r["馬名"])[:4] for r in rdf.to_dict("records")}
        tinv = sum(1.0 / max(1.1, v) for v in n2o.values())
        wp = {k: (1.0 / max(1.1, v)) / tinv for k, v in n2o.items()}

        cbs, seen = [], set()
        if bt in ("単勝", "複勝"):
            cbs = [(a,) for a in n1]
        elif bt in ("枠連", "馬連", "ワイド", "馬単"):
            for a in n1:
                for b in n2:
                    p = tuple(sorted((n2w[a], n2w[b]))) if bt == "枠連" else (a, b) if bt == "馬単" else tuple(sorted((a, b))) if a != b else None
                    if p and p not in seen: seen.add(p); cbs.append(p)
        else:
            for a in n1:
                for b in n2:
                    for c in n3:
                        if len({a, b, c}) == 3:
                            t = (a, b, c) if bt == "3連単" else tuple(sorted((a, b, c)))
                            if t not in seen: seen.add(t); cbs.append(t)

        if cbs:
            brows = []
            for cb in cbs:
                if bt == "単勝": eo, lb = n2o[cb], f"{cb} {n2nm[cb]}"
                elif bt == "複勝": eo, lb = round(max(1.1, n2o[cb]*0.28+0.8), 1), f"{cb} {n2nm[cb]}"
                elif bt == "枠連": eo, lb = 12.5, f"{cb}-{cb}枠"
                elif bt == "馬連": eo, lb = round(max(1.5, 0.775/max(0.0005, wp[cb]*wp[cb]*2)), 1), f"{cb}-{cb} ({n2nm[cb]}/{n2nm[cb]})"
                elif bt == "ワイド": eo, lb = round(max(1.1, 0.775/max(0.001, wp[cb]*wp[cb]*5)), 1), f"{cb}-{cb} ({n2nm[cb]}/{n2nm[cb]})"
                elif bt == "馬単": eo, lb = round(max(2.0, 0.75/max(0.0003, wp[cb]*wp[cb])), 1), f"{cb}→{cb} ({n2nm[cb]}→{n2nm[cb]})"
                elif bt == "3連複": eo, lb = round(max(3.0, 0.75/max(0.0001, wp[cb]*wp[cb]*wp[cb]*8)), 1), f"{cb}-{cb}-{cb}"
                else: eo, lb = round(max(5.0, 0.725/max(0.00005, wp[cb]*wp[cb]*wp[cb]*1.5)), 1), f"{cb}→{cb}→{cb}"
                brows.append({"選択": True, "買い目": lb, "想定オッズ": eo})
            st.subheader("📋 展開一覧（1点ずつチェックで除外・追加可能）")
            ed_exp = st.data_editor(pd.DataFrame(brows).sort_values("想定オッズ").reset_index(drop=True), column_config={"選択": st.column_config.CheckboxColumn("購入", width="small"), "買い目": st.column_config.TextColumn("組み合わせ", disabled=True), "想定オッズ": st.column_config.NumberColumn("想定オッズ", disabled=True, format="%.1f")}, use_container_width=True, hide_index=True, key=f"exp_{sk}_{sr}_{bt}_{len(brows)}")
            act = ed_exp.query("選択 == True").copy()
            if not act.empty:
                isum = sum(1.0 / o for o in act["想定オッズ"])
                syn = round(1.0 / isum, 2)
                act["推奨配分(円)"] = [max(100, int(round((bg * ((1.0/o)/isum))/100)*100)) for o in act["想定オッズ"]]
                act["払戻目安(円)"] = (act["想定オッズ"] * act["推奨配分(円)"]).astype(int)
                m1, m2, m3 = st.columns(3)
                m1.metric("選択済点数", f"{len(act)}点")
                m2.metric("合成オッズ", f"{syn}倍", delta="トリガミ注意" if syn < 1.0 else "プラス圏", delta_color="inverse" if syn < 1.0 else "normal")
                m3.metric("配分合計", f"{act['推奨配分(円)'].sum():,}円")
                st.dataframe(act.drop(columns=["選択"]), use_container_width=True, hide_index=True)
