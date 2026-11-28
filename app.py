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
page_mode = st.radio("メニュー", ("🔥 勝負レース", "📋 出馬表・AI分析", "💰 買い目", "🌱 馬場傾向", "📊 AI検証"), horizontal=True, label_visibility="collapsed", key="nav_radio")

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
        b_all = pd.read_csv("history_races.csv", encoding="utf-8-sig") if os.path.exists("history_races.csv") else pd.DataFrame()
        cur_b = all_df[all_df["実着順"] > 0].copy() if "実着順" in all_df.columns else pd.DataFrame()
        if not cur_b.empty:
            b_all = pd.concat([b_all, cur_b], ignore_index=True).drop_duplicates(subset=["開催", "レース番号", "馬番"], keep="last") if not b_all.empty else cur_b
        if b_all.empty:
            st.info("確定着順データがありません。「📊 AI検証」タブでレース結果を取得すると自動集計されます。")
        else:
            b_all["場名"] = b_all["開催"].astype(str).apply(lambda s: next((p for p in ("東京", "京都", "中山", "阪神", "中京", "新潟", "福島", "小倉", "札幌", "函館") if p in s), s))
            b_all["馬場区分"] = b_all["レース"].astype(str).apply(lambda s: "芝" if "芝" in s else "ダート")
            c_p, c_s = st.columns([1.4, 1.2])
            sel_p = c_p.radio("場", tuple(b_all["場名"].unique()), horizontal=True, label_visibility="collapsed", key="bb_p")
            sel_s = c_s.radio("馬場", ("芝", "ダート"), horizontal=True, label_visibility="collapsed", key="bb_s")
            sub = b_all[(b_all["場名"] == sel_p) & (b_all["馬場区分"] == sel_s)].copy()
            if sub.empty:
                st.caption("該当コースの結果データがまだありません。")
            else:
                k_uniq = list(dict.fromkeys(sub["開催"]))
                cur_ks = k_uniq[-2:] if len(k_uniq) >= 3 else k_uniq[-1:]
                prev_ks = [k for k in k_uniq if k not in cur_ks]
                df_now = sub[sub["開催"].isin(cur_ks)].copy()
                df_old = sub[sub["開催"].isin(prev_ks)].copy() if prev_ks else sub.copy()
                old_lbl = "先週" if prev_ks else "累計"
                df_now["枠ゾーン"] = pd.cut(df_now["枠番"], [0, 2, 5, 8], labels=["内(1-2枠)", "中(3-5枠)", "外(6-8枠)"])
                df_old["枠ゾーン"] = pd.cut(df_old["枠番"], [0, 2, 5, 8], labels=["内(1-2枠)", "中(3-5枠)", "外(6-8枠)"])
                best_w = max(["内(1-2枠)", "中(3-5枠)", "外(6-8枠)"], key=lambda z: df_now[df_now["枠ゾーン"]==z]["実着順"].le(3).mean() if not df_now[df_now["枠ゾーン"]==z].empty else -1)
                best_k = max(["逃げ", "先行", "差し", "追込"], key=lambda q: df_now[df_now["脚質"]==q]["実着順"].le(3).mean() if not df_now[df_now["脚質"]==q].empty else -1)
                bw_r = round(df_now[df_now["枠ゾーン"]==best_w]["実着順"].le(3).mean()*100, 1)
                bk_r = round(df_now[df_now["脚質"]==best_k]["実着順"].le(3).mean()*100, 1)
                st.markdown(f"<div style='background:#1e293b;border-left:4px solid #38bdf8;padding:8px 10px;border-radius:6px;margin-bottom:8px;font-size:13px;color:#f8fafc;'><b>🔄 今週トレンド：</b><span style='color:#fbbf24;font-weight:bold;'>{best_w}({bw_r}%)</span> × <span style='color:#f87171;font-weight:bold;'>{best_k}({bk_r}%)</span></div>", unsafe_allow_html=True)
                st.markdown("#### ① 枠順バイアス（先週 vs 今週）")
                wh = ""
                for z in ["内(1-2枠)", "中(3-5枠)", "外(6-8枠)"]:
                    n_s, o_s = df_now[df_now["枠ゾーン"]==z], df_old[df_old["枠ゾーン"]==z]
                    nf = round(n_s["実着順"].le(3).mean()*100, 1) if not n_s.empty else 0.0
                    of = round(o_s["実着順"].le(3).mean()*100, 1) if not o_s.empty else 0.0
                    nr = round((n_s["実着順"].eq(1)*n_s["単勝オッズ"]).sum()/len(n_s)*100, 1) if not n_s.empty else 0.0
                    or_ = round((o_s["実着順"].eq(1)*o_s["単勝オッズ"]).sum()/len(o_s)*100, 1) if not o_s.empty else 0.0
                    cf = "#f87171" if nf > of else "#f8fafc"
                    cr = "#f87171" if nr >= 100 else "#cbd5e1"
                    wh += f"<tr style='border-bottom:1px solid #334155;text-align:right;'><td style='text-align:left;font-weight:bold;color:#38bdf8;padding:6px 6px;'>{z}</td><td>{of}%</td><td style='color:{cf};font-weight:bold;'>{nf}%</td><td>{or_}%</td><td style='color:{cr};font-weight:bold;padding-right:6px;'>{nr}%</td></tr>"
                st.markdown(f"<table style='width:100%;border-collapse:collapse;background:#1e293b;color:#f8fafc;font-size:12px;border-radius:8px;overflow:hidden;'><thead><tr style='background:#0f172a;color:#94a3b8;text-align:right;'><th style='text-align:left;padding:6px 6px;'>枠ゾーン</th><th>{old_lbl}複</th><th>今週複</th><th>{old_lbl}単回</th><th style='padding-right:6px;'>今週単回</th></tr></thead><tbody>{wh}</tbody></table>", unsafe_allow_html=True)
                st.markdown("#### ② 脚質バイアス（先週 vs 今週）")
                kh = ""
                for q in ["逃げ", "先行", "差し", "追込"]:
                    n_s, o_s = df_now[df_now["脚質"]==q], df_old[df_old["脚質"]==q]
                    nf = round(n_s["実着順"].le(3).mean()*100, 1) if not n_s.empty else 0.0
                    of = round(o_s["実着順"].le(3).mean()*100, 1) if not o_s.empty else 0.0
                    nr = round((n_s["実着順"].eq(1)*n_s["単勝オッズ"]).sum()/len(n_s)*100, 1) if not n_s.empty else 0.0
                    or_ = round((o_s["実着順"].eq(1)*o_s["単勝オッズ"]).sum()/len(o_s)*100, 1) if not o_s.empty else 0.0
                    cf = "#f87171" if nf > of else "#f8fafc"
                    cr = "#f87171" if nr >= 100 else "#cbd5e1"
                    kh += f"<tr style='border-bottom:1px solid #334155;text-align:right;'><td style='text-align:left;font-weight:bold;color:#38bdf8;padding:6px 6px;'>{q}</td><td>{of}%</td><td style='color:{cf};font-weight:bold;'>{nf}%</td><td>{or_}%</td><td style='color:{cr};font-weight:bold;padding-right:6px;'>{nr}%</td></tr>"
                st.markdown(f"<table style='width:100%;border-collapse:collapse;background:#1e293b;color:#f8fafc;font-size:12px;border-radius:8px;overflow:hidden;'><thead><tr style='background:#0f172a;color:#94a3b8;text-align:right;'><th style='text-align:left;padding:6px 6px;'>脚質</th><th>{old_lbl}複</th><th>今週複</th><th>{old_lbl}単回</th><th style='padding-right:6px;'>今週単回</th></tr></thead><tbody>{kh}</tbody></table>", unsafe_allow_html=True)
elif "AI検証" in page_mode:
    st.link_button("🏁 本日のレース結果を取得 (約15秒)", "shortcuts://run-shortcut?name=%E7%AB%B6%E9%A6%AC%E7%B5%90%E6%9E%9C%E6%9B%B4%E6%96%B0", use_container_width=True)
    st.subheader("📊 能力スコア・予測勝率・実着順 三者比較分析")
    hist_df = pd.read_csv("history_races.csv", encoding="utf-8-sig") if os.path.exists("history_races.csv") else pd.DataFrame()
    cur_done = all_df[all_df["実着順"] > 0].copy() if "実着順" in all_df.columns else pd.DataFrame()
    if not cur_done.empty:
        hist_df = pd.concat([hist_df, cur_done], ignore_index=True).drop_duplicates(subset=["開催", "レース番号", "馬番"], keep="last") if not hist_df.empty else cur_done
    if hist_df.empty:
        st.info("まだ確定着順データがありません。レース終了後に「🏁 本日のレース結果を取得」を実行すると自動蓄積されます。")
    else:
        sc_mode = st.radio("集計期間", ("📈 全期間累計", "📅 直近開催のみ"), horizontal=True, label_visibility="collapsed", key="v_scope")
        vdf = (hist_df if sc_mode == "📈 全期間累計" else (cur_done if not cur_done.empty else hist_df)).copy()
        vdf["1着"] = (vdf["実着順"] == 1).astype(int)
        vdf["3着内"] = (vdf["実着順"] <= 3).astype(int)
        vdf["単勝払戻"] = vdf["1着"] * vdf["単勝オッズ"] * 100
        st.caption(f"集計対象：{vdf.groupby(['開催', 'レース']).ngroups}レース（延べ{len(vdf)}頭）")
        st.markdown("#### ① 能力スコア帯別の好走率（高スコアほど好走しているか？）")
        bins, lbls = [0, 54.9, 59.9, 64.9, 69.9, 100], ["55未満", "55〜59", "60〜64", "65〜69", "70以上"]
        vdf["スコア帯"] = pd.cut(vdf["能力スコア"], bins=bins, labels=lbls)
        s_h = ""
        for lb in reversed(lbls):
            sub = vdf[vdf["スコア帯"] == lb]
            if not sub.empty:
                wr, fr = round(sub["1着"].mean()*100, 1), round(sub["3着内"].mean()*100, 1)
                roi = round(sub["単勝払戻"].sum()/(len(sub)*100)*100, 1)
                cr = "#f87171" if roi >= 100 else "#cbd5e1"
                s_h += f"<tr style='border-bottom:1px solid #334155;text-align:right;'><td style='text-align:left;font-weight:bold;color:#38bdf8;padding:6px 8px;'>{lb}</td><td>{len(sub)}</td><td>{wr}%</td><td style='font-weight:bold;'>{fr}%</td><td style='color:{cr};font-weight:bold;padding-right:8px;'>{roi}%</td></tr>"
        st.markdown(f"<table style='width:100%;border-collapse:collapse;background:#1e293b;color:#f8fafc;font-size:12px;border-radius:8px;overflow:hidden;'><thead><tr style='background:#0f172a;color:#94a3b8;text-align:right;'><th style='text-align:left;padding:6px 8px;'>スコア帯</th><th>頭数</th><th>勝率</th><th>複勝率</th><th style='padding-right:8px;'>単回収</th></tr></thead><tbody>{s_h}</tbody></table>", unsafe_allow_html=True)
        st.markdown("#### ② 予測勝率 vs 実勝率（AIの確率予測は正確か？）")
        pbins, plbls = [0, 4.9, 9.9, 19.9, 29.9, 100], ["5%未満", "5〜9%", "10〜19%", "20〜29%", "30%以上"]
        vdf["勝率帯"] = pd.cut(vdf["AI予測勝率"], bins=pbins, labels=plbls)
        p_h = ""
        for lb in reversed(plbls):
            sub = vdf[vdf["勝率帯"] == lb]
            if not sub.empty:
                ap, wr, fr = round(sub["AI予測勝率"].mean(), 1), round(sub["1着"].mean()*100, 1), round(sub["3着内"].mean()*100, 1)
                cw = "#f87171" if wr >= ap else "#cbd5e1"
                p_h += f"<tr style='border-bottom:1px solid #334155;text-align:right;'><td style='text-align:left;font-weight:bold;color:#38bdf8;padding:6px 8px;'>{lb}</td><td>{len(sub)}</td><td>{ap}%</td><td style='color:{cw};font-weight:bold;'>{wr}%</td><td style='padding-right:8px;'>{fr}%</td></tr>"
        st.markdown(f"<table style='width:100%;border-collapse:collapse;background:#1e293b;color:#f8fafc;font-size:12px;border-radius:8px;overflow:hidden;'><thead><tr style='background:#0f172a;color:#94a3b8;text-align:right;'><th style='text-align:left;padding:6px 8px;'>予測勝率帯</th><th>頭数</th><th>平均予測</th><th>実勝率</th><th style='padding-right:8px;'>複勝率</th></tr></thead><tbody>{p_h}</tbody></table>", unsafe_allow_html=True)

        st.markdown("#### ③ AI印別 成績＆回収率（◎○の信頼度 ＆ ☆穴馬の爆発力）")
        vdf["_ai"] = ""
        for _, g in vdf.groupby(["開催", "レース"]):
            idxs = g.sort_values("能力スコア", ascending=False).index.tolist()
            for rank_i, ix in enumerate(idxs[:4]):
                vdf.loc[ix, "_ai"] = ["◎", "○", "▲", "△"][rank_i]
            rem = g.loc[idxs[4:]].query("単勝オッズ >= 10.0")
            if not rem.empty:
                vdf.loc[rem.sort_values("期待値スコア", ascending=False).index[0], "_ai"] = "☆"
        rows_h = ""
        for mk in ["◎", "○", "▲", "△", "☆"]:
            sub = vdf[vdf["_ai"] == mk]
            if not sub.empty:
                w_r = round(sub["1着"].mean()*100, 1)
                f_r = round(sub["3着内"].mean()*100, 1)
                roi = round(sub["単勝払戻"].sum()/(len(sub)*100)*100, 1)
                avo = round(sub["単勝オッズ"].mean(), 1)
                c_roi = "#f87171" if roi >= 100 else "#cbd5e1"
                rows_h += f"<tr style='border-bottom:1px solid #334155;text-align:right;'><td style='text-align:center;font-weight:bold;color:#fbbf24;padding:6px 4px;'>{mk}</td><td>{len(sub)}</td><td>{w_r}%</td><td style='font-weight:bold;'>{f_r}%</td><td style='color:{c_roi};font-weight:bold;'>{roi}%</td><td style='padding-right:4px;'>{avo}倍</td></tr>"
        st.markdown(f"<table style='width:100%;border-collapse:collapse;background:#1e293b;color:#f8fafc;font-size:12px;border-radius:8px;overflow:hidden;'><thead><tr style='background:#0f172a;color:#94a3b8;text-align:right;'><th style='text-align:center;padding:6px 4px;'>印</th><th>数</th><th>勝率</th><th>複勝</th><th>単回収</th><th style='padding-right:4px;'>平均倍</th></tr></thead><tbody>{rows_h}</tbody></table>", unsafe_allow_html=True)
        st.markdown("#### ④ ☆穴馬 激走・好走ピックアップ（3着以内）")
        hoshi_hit = vdf[(vdf["_ai"] == "☆") & (vdf["実着順"] <= 3)].sort_values("単勝オッズ", ascending=False)
        if hoshi_hit.empty:
            st.caption("本日の☆印の3着以内好走はまだありません。")
        else:
            for r in hoshi_hit.to_dict("records"):
                st.markdown(f"<div class='nk-card'><div><b>{r['開催']} {r['レース']}</b> ｜ <b>{int(r['実着順'])}着</b><br><span style='color:#fbbf24;'>☆ {int(r['馬番'])}{r['馬名']}</span>（単勝 {r['単勝オッズ']}倍 / 能力 {r['能力スコア']}点）</div></div>", unsafe_allow_html=True)

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
        st.markdown("<style>div.st-key-all_h_sort,div.st-key-all_h_sort>div,div.st-key-all_h_sort div[data-testid='stButtonGroup']{width:100% !important;}div.st-key-all_h_sort div[role='radiogroup']{display:grid !important;grid-template-columns:repeat(4,1fr) !important;width:100% !important;background:#0f172a !important;padding:4px !important;border-radius:8px !important;border:1px solid #334155 !important;gap:4px !important;margin-bottom:8px !important;}div.st-key-all_h_sort button{width:100% !important;min-width:0 !important;background:transparent !important;color:#94a3b8 !important;border:1px solid transparent !important;border-radius:6px !important;padding:6px 0 !important;font-size:11px !important;font-weight:bold !important;white-space:nowrap !important;justify-content:center !important;}div.st-key-all_h_sort button[kind='segmented_controlActive'],div.st-key-all_h_sort button[aria-pressed='true'],div.st-key-all_h_sort button[aria-checked='true']{background:#0284c7 !important;border-color:#38bdf8 !important;color:#ffffff !important;box-shadow:0 0 6px rgba(56,189,248,0.4) !important;}div[data-testid='stHorizontalBlock']:has(span.my-mk-anchor){display:flex !important;flex-direction:row !important;flex-wrap:nowrap !important;align-items:stretch !important;gap:6px !important;margin-bottom:7px !important;}div[data-testid='stHorizontalBlock']:has(span.my-mk-anchor)>div:nth-child(1){flex:0 0 42px !important;width:42px !important;min-width:42px !important;max-width:42px !important;}div[data-testid='stHorizontalBlock']:has(span.my-mk-anchor)>div:nth-child(2){flex:1 1 auto !important;min-width:0 !important;}div[data-testid='stHorizontalBlock']:has(span.my-mk-anchor) button{height:100% !important;min-height:46px !important;padding:0 !important;background:#1e293b !important;border:1px solid #334155 !important;border-radius:8px !important;color:#fbbf24 !important;font-size:16px !important;font-weight:bold !important;}summary.ai-det-sum{list-style:none;cursor:pointer;font-size:11px;color:#38bdf8;font-weight:bold;padding:5px 0 1px 0;user-select:none;}summary.ai-det-sum::-webkit-details-marker{display:none;}</style>", unsafe_allow_html=True)
        a_so = st.segmented_control("一覧並替", ["馬番順", "能力順", "期待値", "人気順"], default="馬番順", label_visibility="collapsed", key="all_h_sort") or "馬番順"
        rdf["_pop"] = rdf["単勝オッズ"].rank(method="min", ascending=True).astype(int)
        avg = float(rdf["能力スコア"].mean())
        rdf = rdf.sort_values("馬番" if a_so=="馬番順" else ("能力スコア" if a_so=="能力順" else ("期待値スコア" if a_so=="期待値" else "単勝オッズ")), ascending=(a_so in ("馬番順", "人気順"))).copy()
        w_hex_a = {1:"#f8fafc", 2:"#0f172a", 3:"#ef4444", 4:"#3b82f6", 5:"#eab308", 6:"#22c55e", 7:"#f97316", 8:"#ec4899"}
        mk_cycle = ["", "◎", "○", "▲", "△", "☆", "✓"]
        for r in rdf.to_dict("records"):
            u_no = int(r["馬番"])
            cur_my = smk.get(u_no, "")
            wc = w_hex_a.get(int(r.get("枠番", 1)), "#f8fafc")
            mk_t = str(r.get("AI印", r.get("印", "")))
            mk_b = f"<span style='background:#fbbf24;color:#0f172a;font-weight:bold;font-size:10px;padding:1px 5px;border-radius:4px;margin-left:5px;'>AI {mk_t}</span>" if mk_t in ("◎","○","▲","△","☆") else ""
            ev_a = float(r.get("期待値スコア", 0)); ev_ca = "#fbbf24" if ev_a >= 100 else "#cbd5e1"; pop_n = int(r["_pop"])
            top_r = f"<span style='color:#38bdf8;'>勝率 {float(r['AI予測勝率']):.1f}%</span>" if a_so=="馬番順" else (f"<span style='color:#fbbf24;'>能力 {float(r['能力スコア']):.1f}点</span>" if a_so=="能力順" else (f"<span style='color:{ev_ca};'>期待値 {ev_a:.1f}%</span>" if a_so=="期待値" else f"<span style='color:#f87171;'>{pop_n}番人気 ({float(r['単勝オッズ']):.1f}倍)</span>"))
            sub_r = f"<span><b style='color:#e2e8f0;'>{pop_n}番人気</b></span><span>単勝 <b style='color:#f87171;'>{float(r['単勝オッズ']):.1f}倍</b></span><span>勝率 <b style='color:#38bdf8;'>{float(r['AI予測勝率']):.1f}%</b></span><span>能力 <b style='color:#fbbf24;'>{float(r['能力スコア']):.1f}</b></span><span>期待値 <b style='color:{ev_ca};'>{ev_a:.1f}%</b></span>"
            cmt = "<br>".join(f"<div style='margin-top:3px;'>{' '.join(f'<span style=\"display:inline-block;background:#0f172a;padding:2px 6px;border-radius:4px;margin:2px 4px 2px 0;\">{w}</span>' for w in seg.split('・'))}</div>" for seg in ai_comment(r, avg).replace("：", "\n").replace("／", "\n").splitlines() if seg.strip()).replace("【プラス】", "<span style='color:#4ade80;font-weight:bold;'>【プラス】</span>").replace("【マイナス】", "<span style='color:#fb7185;font-weight:bold;'>【マイナス】</span>")
            items_v = [("1. 着順着差", float(r.get("着順着差指数",0))), ("2. ラップ", float(r.get("ラップタイム指数",0))), ("3. 騎手勝負度", float(r.get("厩舎・騎手勝負度",0))), ("4. 枠順展開", float(r.get("枠順・展開適合",0))), ("5. 調教", float(r.get("調教指数",0))), ("6. 血統", float(r.get("血統適性",0)))]
            bars_h = "".join(f"<div style='margin-bottom:5px;'><div style='display:flex;justify-content:space-between;font-size:11px;margin-bottom:2px;'><span style='color:#cbd5e1;'>{k}</span><span style='color:#38bdf8;font-weight:bold;'>{v:.1f}点</span></div><div style='background:#0f172a;border-radius:4px;height:6px;overflow:hidden;'><div style='background:linear-gradient(90deg,#0284c7,#38bdf8);width:{min(100,max(0,v))}%;height:100%;border-radius:4px;'></div></div></div>" for k, v in items_v)
            meta_s = f"{r.get('性齢','')} ｜ {r.get('騎手','')} {r.get('斤量','')} ｜ {r.get('脚質','')}"
            c_my, c_card = st.columns([1, 7])
            with c_my:
                st.markdown('<span class="my-mk-anchor"></span>', unsafe_allow_html=True)
                if st.button(cur_my if cur_my else "－", key=f"mk_{sk}_{sr}_{u_no}", use_container_width=True):
                    nxt_m = mk_cycle[(mk_cycle.index(cur_my) + 1) % len(mk_cycle)] if cur_my in mk_cycle else "◎"
                    op = pdf.query("not (開催 == @sk and レース == @sr and 馬番 == @u_no)")
                    nr = [{"開催": sk, "レース": sr, "馬番": u_no, "馬名": r["馬名"], "印": nxt_m}] if nxt_m else []
                    upd = pd.concat([op, pd.DataFrame(nr)], ignore_index=True) if nr else op
                    st.session_state["my_predictions"] = upd
                    save_csv("my_predictions.csv", upd)
                    st.rerun()
            with c_card:
                st.markdown(f"<div style='background:#1e293b;border:1px solid #334155;border-left:5px solid {wc};border-radius:8px;padding:9px 11px;'><div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;'><div style='display:flex;align-items:center;min-width:0;'><span class='waku-box w{int(r.get('枠番',1))}' style='margin-right:6px;flex-shrink:0;'>{u_no}</span><span style='font-size:14px;font-weight:bold;color:#f8fafc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{r['馬名']}</span>{mk_b}</div><span style='font-size:12px;font-weight:bold;flex-shrink:0;margin-left:4px;'>{top_r}</span></div><div style='font-size:11px;color:#94a3b8;margin-bottom:5px;'>{meta_s}</div><div style='display:flex;justify-content:space-between;font-size:10px;color:#94a3b8;background:#0f172a;padding:4px 6px;border-radius:5px;margin-bottom:5px;white-space:nowrap;'>{sub_r}</div><div style='font-size:11px;color:#cbd5e1;line-height:1.4;'>{cmt}</div><details style='margin-top:5px;border-top:1px solid #334155;padding-top:4px;'><summary class='ai-det-sum'>▾ 6項目スコア内訳を展開</summary><div style='padding-top:6px;'>{bars_h}</div></details></div>", unsafe_allow_html=True)        st.markdown("#### 印・数値サマリー表")
        top3_wr = set(rdf.nlargest(3, "AI予測勝率")["馬番"].astype(int))
        sum_rows = ""
        for r in rdf.to_dict("records"):
            u_no = int(r["馬番"])
            my_m = str(smk.get(u_no, "-")) or "-"
            ai_m = str(r.get("AI印", r.get("印", "-"))) or "-"
            wc = w_hex_a.get(int(r.get("枠番", 1)), "#f8fafc")
            pop_n = int(r["_pop"])
            od_v = float(r["単勝オッズ"])
            wr_v = float(r["AI予測勝率"])
            ev_v = float(r["期待値スコア"])
            pop_st = "background:#facc15;color:#0f172a;font-weight:bold;" if pop_n==1 else ("background:#38bdf8;color:#0f172a;font-weight:bold;" if pop_n==2 else ("background:#fb923c;color:#0f172a;font-weight:bold;" if pop_n==3 else "color:#94a3b8;"))
            od_st = "color:#f87171;font-weight:bold;" if od_v < 10.0 else "color:#cbd5e1;"
            wr_st = "color:#fbbf24;font-weight:bold;" if u_no in top3_wr else "color:#94a3b8;"
            ev_c = "#fbbf24" if ev_v >= 100 else "#cbd5e1"
            my_c = "#38bdf8" if my_m != "-" else "#64748b"
            ai_c = "#fbbf24" if ai_m in ("◎","○","▲","△","☆") else "#64748b"
            sum_rows += f"<tr style='border-bottom:1px solid #334155;white-space:nowrap;'><td style='text-align:center;color:{my_c};font-weight:bold;padding:5px 2px;'>{my_m}</td><td style='text-align:center;color:{ai_c};font-weight:bold;padding:5px 2px;'>{ai_m}</td><td style='border-left:4px solid {wc};padding:5px 2px 5px 5px;font-weight:bold;color:#f8fafc;'>{u_no} {r['馬名']}</td><td style='text-align:center;padding:5px 4px;{pop_st}'>{pop_n}</td><td style='text-align:right;padding:5px 3px;{od_st}'>{od_v:.1f}</td><td style='text-align:right;padding:5px 3px;{wr_st}'>{wr_v:.1f}%</td><td style='text-align:right;color:{ev_c};font-weight:bold;padding:5px 4px 5px 2px;'>{ev_v:.0f}%</td></tr>"
        st.markdown(f"<table style='width:100%;border-collapse:collapse;background:#1e293b;color:#f8fafc;font-size:10.5px;border-radius:8px;overflow:hidden;'><thead><tr style='background:#0f172a;color:#94a3b8;white-space:nowrap;'><th style='padding:6px 2px;text-align:center;'>自</th><th style='padding:6px 2px;text-align:center;'>AI</th><th style='text-align:left;padding:6px 2px 6px 5px;'>馬番・馬名</th><th style='text-align:center;padding:6px 4px;'>人気</th><th style='text-align:right;padding:6px 3px;'>オッズ</th><th style='text-align:right;padding:6px 3px;'>勝率</th><th style='text-align:right;padding:6px 4px 6px 2px;'>期待</th></tr></thead><tbody>{sum_rows}</tbody></table>", unsafe_allow_html=True)


    elif "買い目" in page_mode:
        c_bt, c_fm = st.columns([1.4, 1.6])
        st.markdown("<style>div[data-testid='stHorizontalBlock']{flex-wrap:nowrap !important;gap:4px !important;}div[data-testid='stHorizontalBlock']>div{min-width:0 !important;}</style>", unsafe_allow_html=True)
        bt = c_bt.selectbox("券種", ("3連複", "3連単", "馬連", "馬単", "ワイド", "枠連", "単勝", "複勝"), label_visibility="collapsed", key="nk_bt")
        fm = c_fm.radio("方式", ("フォーメ", "ボックス"), horizontal=True, label_visibility="collapsed", key="nk_fm")
        c_so, c_bg, c_cl = st.columns([1.3, 1.2, 0.8])
        so_m = c_so.radio("並替", ("枠番順", "人気順", "AI順"), horizontal=True, label_visibility="collapsed", key="nk_so")
        bg = c_bg.number_input("予算", 100, 1000000, 3000, 500, label_visibility="collapsed", key="nk_bg")
        rk_key = f"mk_{sk}_{sr}_{bt}"
        if rk_key not in st.session_state:
            has_my = rdf["My印"].ne("").any()
            t_col = "My印" if has_my else "AI印"
            st.session_state[rk_key] = {
                1: set(rdf.loc[rdf[t_col].isin(("◎", "○")), "馬番"].astype(int)),
                2: set(rdf.loc[rdf[t_col].isin(("◎", "○", "▲", "△")), "馬番"].astype(int)),
                3: set(rdf.loc[rdf[t_col].ne(""), "馬番"].astype(int)),
            }
        if c_cl.button("消去", key=f"clr_{rk_key}", use_container_width=True):
            st.session_state[rk_key] = {1: set(), 2: set(), 3: set()}
            st.rerun()
        mk_st = st.session_state[rk_key]
        cols_n = 1 if (bt in ("単勝", "複勝") or fm == "ボックス") else (2 if bt not in ("3連複", "3連単") else 3)
        h_cols = st.columns([2.7] + [0.65] * cols_n)
        next(iter(h_cols)).markdown("<div style='font-size:11px;color:#94a3b8;padding:2px 4px;'>枠 / 印 / 馬名・オッズ</div>", unsafe_allow_html=True)
        for ci in range(cols_n):
            lbl = "軸/BOX" if fm == "ボックス" else f"馬{ci+1}"
            h_cols[ci+1].markdown(f"<div style='text-align:center;font-size:11px;color:#38bdf8;font-weight:bold;'>{lbl}</div>", unsafe_allow_html=True)
        bdf = rdf.sort_values("馬番" if so_m == "枠番順" else ("単勝オッズ" if so_m == "人気順" else "能力スコア"), ascending=(so_m != "AI順"))
        for r in bdf.to_dict("records"):
            u = int(r["馬番"])
            mk_txt = f"<div style='line-height:1.1;text-align:center;'><div style='color:#fbbf24;font-size:11px;'>{r['AI印'] or '－'}</div><div style='color:#38bdf8;font-size:11px;font-weight:bold;'>{r['My印'] or '－'}</div></div>"
            w = int(r.get("枠番", 1))
            rc = st.columns([2.7] + [0.65] * cols_n)
            next(iter(rc)).markdown(f"<div style='display:flex;align-items:center;background:#1e293b;padding:5px 7px;border-radius:6px;margin-bottom:2px;'><div class='waku-box w{w}' style='margin-right:6px;'>{u}</div><div style='font-size:11px;color:#fbbf24;width:24px;'>{mk_txt}</div><div style='line-height:1.15;'><div style='font-size:13px;font-weight:bold;color:#f8fafc;'>{r['馬名']}</div><div style='font-size:11px;color:#f87171;'>{r['単勝オッズ']}倍 <span style='color:#94a3b8;'>(AI {r['能力スコア']})</span></div></div></div>", unsafe_allow_html=True)
            for ci in range(cols_n):
                c_idx = ci + 1
                on = u in mk_st[c_idx]
                if rc[c_idx].button("✓" if on else "・", key=f"b_{rk_key}_{u}_{c_idx}", type="primary" if on else "secondary", use_container_width=True):
                    if on: mk_st[c_idx].remove(u)
                    else: mk_st[c_idx].add(u)
                    st.rerun()
        n1, n2, n3 = sorted(mk_st.get(1, set())), sorted(mk_st.get(1 if fm == "ボックス" else 2, set())), sorted(mk_st.get(1 if fm == "ボックス" else 3, set()))
        n2o = {int(r["馬番"]): float(r["単勝オッズ"]) for r in rdf.to_dict("records")}
        n2w = {int(r["馬番"]): int(r.get("枠番", 1)) for r in rdf.to_dict("records")}
        n2nm = {int(r["馬番"]): str(r["馬名"])[:3] for r in rdf.to_dict("records")}
        tinv = sum(1.0 / max(1.1, v) for v in n2o.values())
        wp = {k: (1.0 / max(1.1, v)) / tinv for k, v in n2o.items()}
        cbs, seen = [], set()
        if bt in ("単勝", "複勝"): cbs = [(a,) for a in n1]
        elif bt in ("枠連", "馬連", "ワイド", "馬単"):
            for a in n1:
                for b in n2:
                    p = tuple(sorted((n2w[a], n2w[b]))) if bt == "枠連" else ((a, b) if bt == "馬単" else tuple(sorted((a, b))))
                    if (bt == "枠連" or a != b) and p not in seen: seen.add(p); cbs.append(p)
        else:
            for a in n1:
                for b in n2:
                    for c in n3:
                        if len({a, b, c}) == 3:
                            t = (a, b, c) if bt == "3連単" else tuple(sorted((a, b, c)))
                            if t not in seen: seen.add(t); cbs.append(t)
        if cbs:
            st.markdown("---")
            ex_rows = []
            for cb in cbs:
                it = iter(cb)
                a, b, c = next(it, 0), next(it, 0), next(it, 0)
                if bt == "単勝": eo, lb = round(n2o[a], 1), f"{a:02d} ({n2nm[a]})"
                elif bt == "複勝": eo, lb = round(max(1.1, n2o[a] * 0.28 + 0.5), 1), f"{a:02d} ({n2nm[a]})"
                elif bt == "枠連": eo, lb = round(max(1.5, 0.75 / max(0.002, sum(wp[k] for k, wv in n2w.items() if wv == a) * sum(wp[k] for k, wv in n2w.items() if wv == b) * (1 if a == b else 2))), 1), f"枠{a}-{b}"
                elif bt == "馬連": eo, lb = round(max(1.8, 0.775 / max(0.001, 2 * wp[a] * wp[b])), 1), f"{a:02d}-{b:02d} ({n2nm[a]}・{n2nm[b]})"
                elif bt == "ワイド": eo, lb = round(max(1.2, 0.775 / max(0.002, 5.5 * wp[a] * wp[b])), 1), f"{a:02d}-{b:02d} ({n2nm[a]}・{n2nm[b]})"
                elif bt == "馬単": eo, lb = round(max(2.2, 0.75 / max(0.0008, wp[a] * wp[b])), 1), f"{a:02d}→{b:02d} ({n2nm[a]}→{n2nm[b]})"
                elif bt == "3連複": eo, lb = round(max(3.0, 0.75 / max(0.0002, 6 * wp[a] * wp[b] * wp[c])), 1), f"{a:02d}-{b:02d}-{c:02d} ({n2nm[a]}・{n2nm[b]}・{n2nm[c]})"
                else: eo, lb = round(max(5.0, 0.725 / max(0.0001, wp[a] * wp[b] * wp[c])), 1), f"{a:02d}→{b:02d}→{c:02d} ({n2nm[a]}→{n2nm[b]}→{n2nm[c]})"
                ex_rows.append({"cb": str(cb), "lb": lb, "eo": eo})
            off_k = f"off_{rk_key}"
            if off_k not in st.session_state: st.session_state[off_k] = set()
            off_s = st.session_state[off_k]
            act_r = [x for x in ex_rows if x["cb"] not in off_s]
            if act_r:
                isum = sum(1.0 / x["eo"] for x in act_r)
                syn = round(1.0 / isum, 2)
                for x in act_r:
                    x["bet"] = max(100, int(round((bg / (x["eo"] * isum)) / 100.0)) * 100)
                m1, m2, m3 = st.columns(3)
                m1.metric("選択点数", f"{len(act_r)}点")
                m2.metric("合成オッズ", f"{syn}倍")
                m3.metric("購入合計", f"{sum(x['bet'] for x in act_r):,}円")
            for x in ex_rows:
                is_on = x["cb"] not in off_s
                bc1, bc2 = st.columns([4.2, 0.8])
                bet_t = f"配分 {x['bet']:,}円 (払戻 {int(x['bet']*x['eo']):,}円)" if is_on else "除外中"
                bc1.markdown(f"<div style='background:{'#1e293b' if is_on else '#0f172a'};opacity:{'1.0' if is_on else '0.45'};padding:6px 10px;border-radius:6px;border-left:3px solid {'#ef4444' if is_on else '#475569'};margin-bottom:3px;'><div style='font-size:13px;font-weight:bold;color:#f8fafc;'>{x['lb']} <span style='color:#f87171;float:right;'>{x['eo']}倍</span></div><div style='font-size:11px;color:#38bdf8;'>{bet_t}</div></div>", unsafe_allow_html=True)
                if bc2.button("✓" if is_on else "－", key=f"tg_{rk_key}_{x['cb']}", type="primary" if is_on else "secondary", use_container_width=True):
                    if is_on: off_s.add(x["cb"])
                    else: off_s.remove(x["cb"])
                    st.rerun()
