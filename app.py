import streamlit as st
import pandas as pd
import numpy as np
import requests, base64, io, os
from datetime import datetime, timedelta, timezone

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
.odds-txt { color: #f87171; font-weight: bold; font-size: 16px; text-align: right; }
.score-pill { background: #2563eb; color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: bold; }
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
    if not tk: return False
    u = f"https://github.com{rp}/contents/{fn}"
    hd = {"Authorization": f"token {tk}"}
    rg = requests.get(u, headers=hd, timeout=10)
    pl = {"message": msg, "content": base64.b64encode(df_s.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")).decode("utf-8")}
    if rg.status_code == 200: pl["sha"] = rg.json().get("sha")
    return requests.put(u, headers=hd, json=pl, timeout=15).status_code in (200, 201)

if "cloud_loaded" not in st.session_state:
    st.session_state["my_preds_df"] = load_csv("my_predictions.csv", ("開催", "レース", "馬番", "My印", "Myメモ"))
    st.session_state["cloud_loaded"] = True

h1, h2 = st.columns((2, 1))
h1.markdown("### 🏇 競馬AI Pro")
with h2:
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        st.link_button("🔄 全体データ更新 (出馬表+オッズ)", "shortcuts://run-shortcut?name=KeibaAIUpdate", use_container_width=True)
    with c_btn2:
        st.link_button("⚡ 最新オッズ高速更新 (約15秒)", "shortcuts://run-shortcut?name=KeibaOddsFast", use_container_width=True)


if "jump_page" in st.session_state:
    st.session_state["nav_radio"] = st.session_state.pop("jump_page")
page_mode = st.radio("メニュー", ("🔥 勝負レース", "📋 出馬表・AI分析", "💰 買い目", "🌱 馬場傾向"), horizontal=True, label_visibility="collapsed", key="nav_radio")

if not os.path.exists("latest_races.csv"): st.stop()
all_df = pd.read_csv("latest_races.csv")
if all_df.empty: st.stop()
st.caption(f"🔄 最終更新: {all_df['更新日時'].head(1).squeeze() if '更新日時' in all_df.columns else '自動更新済'}")
def ai_comment(r, avg):
    df_a = round(float(r.get("能力スコア", 50)) - avg, 1)
    p, m = [], []
    if float(r.get("着順着差指数", 50)) >= 60: p.append(f"着順・着差({r.get('着順着差指数')}点)優秀")
    elif float(r.get("着順着差指数", 50)) <= 42: m.append(f"近走着差({r.get('着順着差指数')}点)割引")
    if float(r.get("不利補正値", 0)) > 0: p.append(f"不利補正(+{int(r.get('不利補正値'))}pt)")
    if float(r.get("ラップタイム指数", 50)) >= 60: p.append(f"タイム指数({r.get('ラップタイム指数')}点)上位")
    if float(r.get("血統適性", 50)) >= 60: p.append(f"血統適性({r.get('血統適性')}点)高")
    if float(r.get("枠順展開適合", 50)) >= 58: p.append(f"{int(r.get('枠番'))}枠・{r.get('脚質')}展開合致")
    if float(r.get("厩舎騎手勝負度", 50)) >= 58: p.append(f"{r.get('騎手')}勝負気配({r.get('厩舎騎手勝負度')}点)")
    if pd.notna(r.get("激変サイン")) and str(r.get("激変サイン")): p.append(f"激変【{r.get('激変サイン')}】")
    res = []
    if p: res.append("【プラス】" + "・".join(p[:3]))
    if m: res.append("【マイナス】" + "・".join(m[:2]))
    if float(r.get("期待値スコア", 100)) >= 120: res.append(f"勝率{r.get('AI予測勝率')}%に対し単勝{r.get('単勝オッズ')}倍は甘く期待値{r.get('期待値スコア')}pt。")
    return f"能力{r.get('能力スコア')}点（平均比 {df_a:+.1f}pt）：" + (" ／ ".join(res) if res else "平均水準のバランス型。")

if "勝負レース" in page_mode:
    st.subheader("🔥 本日のAI厳選 勝負レース（発走順）")
    picked = 0
    for idx_g, ((rno, ks, rn), g) in enumerate(all_df.sort_values(["レース番号", "開催"]).groupby(["レース番号", "開催", "レース"], sort=False)):
        sg = g.sort_values("能力スコア", ascending=False)
        t1 = sg.head(1).squeeze()
        t2 = sg.head(2).tail(1).squeeze() if len(sg) > 1 else t1
        d12 = round(float(t1["能力スコア"]) - float(t2["能力スコア"]), 1)
        sc1, od1, ev1 = float(t1["能力スコア"]), float(t1["単勝オッズ"]), float(t1["期待値スコア"])
        bg = "👑 AI鉄板・1強軸" if (sc1 >= 71.0 and d12 >= 5.5) else ("💎 激アツ中穴・期待値◎" if (ev1 >= 120.0 and 4.0 <= od1 <= 25.0) else ("🔥 有力軸・好勝負" if (sc1 >= 68.0 and d12 >= 4.5 and ev1 >= 105.0) else ""))
        if bg:
            picked += 1
            c_left, c_btn = st.columns([4.2, 1.3])
            with c_left:
                st.markdown(f"""<div class="nk-card" style="margin-bottom:4px;"><div><b>{ks} {rn}</b> <span style="color:#fbbf24;font-weight:bold;">{bg}</span><br><span style="font-size:13px;">◎{int(t1['馬番'])}{t1['馬名']}（能力{sc1}点 / 2位差+{d12} / 単勝{od1}倍 / 期待値{ev1}%）</span></div></div>""", unsafe_allow_html=True)
            with c_btn:
             if st.button("📋 出馬表", key=f"jmp_{idx_g}_{ks}_{rno}", use_container_width=True):
                st.session_state["jump_page"] = "📋 出馬表・AI分析"
                st.session_state["jump_kaisai"] = ks
                st.session_state["jump_rkey"] = f"{int(rno)}R"
                st.rerun()
    if picked == 0:
        st.info("本日の全レースは混戦傾向のため、突出した勝負レースはありません。")
    st.subheader("🏆 厳選！期待値Sランク お宝中穴 TOP5（単勝4〜30倍）")
    for idx_m, r in enumerate(all_df.query("期待値スコア >= 115.0 and 4.0 <= 単勝オッズ <= 30.0").sort_values(["レース番号", "期待値スコア"], ascending=[True, False]).head(5).to_dict("records")):
        c_ml, c_mb = st.columns([4.2, 1.3])
        with c_ml:
            st.markdown(f"""<div class="nk-card" style="margin-bottom:4px;"><div style="display:flex;align-items:center;"><div class="waku-box w{int(r.get('枠番',1))}">{int(r['馬番'])}</div><div><div style="font-size:11px;color:#9ca3af;">{r['開催']} {r['レース']}</div><a href="{r['netkeiba']}" target="_blank" style="color:#fff;font-weight:bold;text-decoration:none;">{r['馬名']} 🔗</a></div></div><div class="odds-txt">{r['単勝オッズ']}倍<br><span class="score-pill">能力{r['能力スコア']} / 期待値{r['期待値スコア']}%</span></div></div>""", unsafe_allow_html=True)
        with c_mb:
            if st.button("📋 出馬表", key=f"jmpm_{idx_m}_{r['開催']}_{int(r['レース番号'])}", use_container_width=True):
               st.session_state["jump_page"] = "📋 出馬表・AI分析"
               st.session_state["jump_kaisai"] = r["開催"]
               st.session_state["jump_rkey"] = f"{int(r['レース番号'])}R"
               st.rerun()

elif "馬場傾向" in page_mode:
    sk = st.selectbox("開催場を選択", tuple(all_df["開催"].unique()))
    sdf = all_df.query("開催 == @sk").sort_values("レース番号")
    bs = st.radio("コース", ("芝コース", "ダートコース"), horizontal=True)
    st.bar_chart(pd.DataFrame({"枠区分": ("1〜2枠", "3〜4枠", "5〜6枠", "7〜8枠"), "3着内率(%)": (28.5, 24.0, 19.5, 16.0) if bs == "芝コース" else (18.0, 21.5, 25.0, 27.5)}).set_index("枠区分"))
    tdf = sdf.query(f"馬場 == '{'芝' if bs == '芝コース' else 'ダート'}'")
    for r in tdf.query("枠番 <= 4 and 脚質 in ('逃げ','先行')" if bs == "芝コース" else "枠番 >= 5 and 脚質 in ('逃げ','先行')").sort_values("能力スコア", ascending=False).head(8).to_dict("records"):
        st.markdown(f"""<div class="nk-card"><div style="display:flex;align-items:center;"><div class="waku-box w{int(r['枠番'])}">{int(r['馬番'])}</div><div><div style="font-size:11px;color:#9ca3af;">{r['レース']}</div><b>{r['馬名']}</b> ({r['脚質']})</div></div><div class="odds-txt">{r['単勝オッズ']}倍</div></div>""", unsafe_allow_html=True)
else:
    k_opts = list(all_df["開催"].unique())
    def_k = st.session_state.pop("jump_kaisai", k_opts[0])
    if def_k not in k_opts: def_k = k_opts[0]
    sk = st.segmented_control("開催場", k_opts, default=def_k, label_visibility="collapsed") or def_k
    sdf = all_df.query("開催 == @sk").sort_values("レース番号")
    r_map = {f"{int(r['レース番号'])}R": r["レース"] for _, r in sdf.drop_duplicates("レース番号").iterrows()}
    r_keys = list(r_map.keys())
    def_rk = st.session_state.pop("jump_rkey", r_keys[0])
    if def_rk not in r_keys: def_rk = r_keys[0]
    sel_rk = st.segmented_control("レース", r_keys, default=def_rk, label_visibility="collapsed") or def_rk
    sr = r_map[sel_rk]
    st.markdown(f"<div style='font-size:15px;font-weight:bold;color:#f8fafc;background:#1e293b;padding:8px 12px;border-radius:8px;border-left:4px solid #38bdf8;margin:4px 0 8px 0;'>📍 {sk} {sr}</div>", unsafe_allow_html=True)
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

        st.markdown("""<style>
div[data-testid="stHorizontalBlock"]:has(.my-out-btn){display:flex !important;flex-direction:row !important;flex-wrap:nowrap !important;align-items:center !important;gap:8px !important;margin-bottom:8px !important;width:100% !important;}
div[data-testid="stHorizontalBlock"]:has(.my-out-btn) > div[data-testid="stColumn"]{min-width:0 !important;padding:0 !important;}
div[data-testid="stHorizontalBlock"]:has(.my-out-btn) > div[data-testid="stColumn"]:nth-child(1){flex:0 0 42px !important;width:42px !important;}
div[data-testid="stHorizontalBlock"]:has(.my-out-btn) > div[data-testid="stColumn"]:nth-child(2){flex:1 1 auto !important;}
div[data-testid="stHorizontalBlock"]:has(.my-out-btn) button{width:42px !important;height:48px !important;min-height:48px !important;padding:0 !important;margin:0 !important;border-radius:10px !important;font-size:17px !important;font-weight:bold !important;background:#1e293b !important;color:#fbbf24 !important;border:2px solid #fbbf24 !important;}
.ai-sq{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:6px;font-weight:bold;font-size:13px;border:1.5px solid #475569;color:#94a3b8;background:#0f172a;margin-right:8px;flex-shrink:0;}
.ai-◎{border-color:#ef4444;color:#ef4444;background:rgba(239,68,68,.15);}
.ai-○{border-color:#3b82f6;color:#60a5fa;background:rgba(59,130,246,.15);}
.ai-▲{border-color:#22c55e;color:#4ade80;background:rgba(34,197,94,.15);}
.ai-△{border-color:#eab308;color:#facc15;background:rgba(234,179,8,.15);}
.ai-☆{border-color:#a855f7;color:#c084fc;background:rgba(168,85,247,.15);}
</style>""", unsafe_allow_html=True)

        mk_cycle = ["", "◎", "○", "▲", "△", "☆", "✓", "消"]
        for r in rdf.to_dict("records"):
            u_no = int(r["馬番"])
            cur_my = smk.get(u_no, "")
            ai_m = r["AI印"] if r["AI印"] else "--"
            c_my, c_card = st.columns(2)
            with c_my:
                st.markdown('<span class="my-out-btn" style="display:none;"></span>', unsafe_allow_html=True)
                if st.button(cur_my if cur_my else "--", key=f"btn_mk_{sk}_{sr}_{u_no}"):
                    nxt_m = mk_cycle[(mk_cycle.index(cur_my) + 1) % len(mk_cycle)] if cur_my in mk_cycle else "◎"
                    op = pdf.query("not (開催 == @sk and レース == @sr and 馬番 == @u_no)")
                    nr = [{"開催": sk, "レース": sr, "馬番": u_no, "My印": nxt_m, "Myメモ": ""}] if nxt_m else []
                    upd = pd.concat([op, pd.DataFrame(nr, columns=["開催", "レース", "馬番", "My印", "Myメモ"])], ignore_index=True)
                    st.session_state["my_preds_df"] = upd
                    save_csv("my_predictions.csv", upd, f"Save {sk} {sr} #{u_no}")
                    st.rerun()
            with c_card:
                st.markdown(f"""<div class="nk-card" style="margin-bottom:0;"><div style="display:flex;align-items:center;"><div class="waku-box w{int(r.get('枠番',1))}">{u_no}</div><div class="ai-sq ai-{ai_m}">{ai_m}</div><div><div><a href="{r['netkeiba']}" target="_blank" style="color:#fff;font-weight:bold;text-decoration:none;">{r['馬名']}</a></div><div style="font-size:12px;color:#9ca3af;">{r.get('性齢','')} ｜ {r['騎手']} {r['斤量']} ｜ {r['脚質']}</div></div></div><div style="text-align:right;"><div class="odds-txt">{r['単勝オッズ']}倍</div><span class="score-pill">能力 {r['能力スコア']}</span></div></div>""", unsafe_allow_html=True)

            st.markdown("---")
            st.subheader("🤖 全頭AI評価一覧（AI能力順）")
            md = st.radio("評価基準", ("🎯 的中重視(能力順)", "💎 期待値重視(妙味順)"), horizontal=True, label_visibility="collapsed", key="ai_eval_md")
            sc = "能力スコア" if "的中" in md else "期待値スコア"
            rk = rdf.sort_values(sc, ascending=False).copy()
            avg = round(float(rk["能力スコア"].mean()), 1)
            for r in rk.to_dict("records"):
                mk_s = f"**{r['AI印']}** " if r["AI印"] else ""
                st.info(f"{mk_s}**{int(r['馬番'])} {r['馬名']}**（単勝{r['単勝オッズ']}倍 / 勝率{r['AI予測勝率']}% / 期待値{r['期待値スコア']}%）\n\n{ai_comment(r, avg)}")
                sh = st.selectbox("📊 詳細内訳グラフを見る馬を選択", tuple(rk["馬名"]), key="ai_detail_sh")
            inf = rk.query("馬名 == @sh").squeeze()
            fv = (float(inf["着順着差指数"]), float(inf["ラップタイム指数"]), float(inf["厩舎騎手勝負度"]), float(inf["枠順展開適合"]), float(inf["調教指数"]), float(inf["血統適性"]))
            st.bar_chart(pd.DataFrame({"項目": ("1_着順着差", "2_ラップ", "3_騎手勝負度", "4_枠順展開", "5_調教", "6_血統"), "スコア": fv}).set_index("項目"))

    elif "買い目" in page_mode:
        bt = st.radio("券種", ("単勝", "複勝", "枠連", "馬連", "ワイド", "馬単", "3連複", "3連単"), horizontal=True)
        bg = st.number_input("総予算(円)", 100, 1000000, 3000, 100)
        ms_df = rdf.loc[:, ("枠番", "馬番", "AI印", "My印", "馬名", "単勝オッズ")].copy()
        ms_df["1頭目"] = ms_df["My印"].isin(("◎",)) | (ms_df["AI印"].isin(("◎",)) & (ms_df["My印"] == ""))
        if bt not in ("単勝", "複勝"):
            ms_df["2頭目"] = ms_df["My印"].isin(("○", "▲", "△", "☆", "✓")) | (ms_df["AI印"].isin(("○", "▲", "△")) & (ms_df["My印"] == ""))
        if bt in ("3連複", "3連単"):
            ms_df["3頭目"] = ms_df["My印"].isin(("○", "▲", "△", "☆", "✓")) | (ms_df["AI印"].isin(("○", "▲", "△", "☆")) & (ms_df["My印"] == ""))
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
        if bt in ("単勝", "複勝"): cbs = [(a,) for a in n1]
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
                it = iter(cb)
                a, b, c = next(it, 0), next(it, 0), next(it, 0)
                if bt == "単勝": eo, lb = n2o[a], f"{a} {n2nm[a]}"
                elif bt == "複勝": eo, lb = round(max(1.1, n2o[a]*0.28+0.8), 1), f"{a} {n2nm[a]}"
                elif bt == "枠連": eo, lb = 12.5, f"{a}-{b}枠"
                elif bt == "馬連": eo, lb = round(max(1.5, 0.775/max(0.0005, wp[a]*wp[b]*2)), 1), f"{a}-{b}"
                elif bt == "ワイド": eo, lb = round(max(1.1, 0.775/max(0.001, wp[a]*wp[b]*5)), 1), f"{a}-{b}"
                elif bt == "馬単": eo, lb = round(max(2.0, 0.75/max(0.0003, wp[a]*wp[b])), 1), f"{a}→{b}"
                elif bt == "3連複": eo, lb = round(max(3.0, 0.75/max(0.0001, wp[a]*wp[b]*wp[c]*8)), 1), f"{a}-{b}-{c}"
                else: eo, lb = round(max(5.0, 0.725/max(0.00005, wp[a]*wp[b]*wp[c]*1.5)), 1), f"{a}→{b}→{c}"
                brows.append({"選択": True, "買い目": lb, "想定オッズ": eo})
            ed_exp = st.data_editor(pd.DataFrame(brows).sort_values("想定オッズ").reset_index(drop=True), column_config={"選択": st.column_config.CheckboxColumn("購入", width="small"), "買い目": st.column_config.TextColumn("組み合わせ", disabled=True), "想定オッズ": st.column_config.NumberColumn("想定オッズ", disabled=True, format="%.1f")}, use_container_width=True, hide_index=True, key=f"exp_{sk}_{sr}_{bt}_{len(brows)}")
            act = ed_exp.query("選択 == True").copy()
            if not act.empty:
                isum = sum(1.0 / o for o in act["想定オッズ"])
                syn = round(1.0 / isum, 2)
                act["推奨配分(円)"] = [max(100, int(round((bg * ((1.0/o)/isum))/100)*100)) for o in act["想定オッズ"]]
                act["払戻目安(円)"] = (act["想定オッズ"] * act["推奨配分(円)"]).astype(int)
                m1, m2, m3 = st.columns(3)
                m1.metric("選択済点数", f"{len(act)}点")
                m2.metric("合成オッズ", f"{syn}倍")
                m3.metric("配分合計", f"{act['推奨配分(円)'].sum():,}円")
                st.dataframe(act.drop(columns=["選択"]), use_container_width=True, hide_index=True)
