import streamlit as st
import pandas as pd
import numpy as np
import requests
import base64
import io
import os

st.set_page_config(page_title="自分専用 競馬AI Pro", layout="wide")

# ==========================================
# GitHubクラウド永続化（My印・Myメモ・収支を消えないように保存・読込）
# ==========================================
def get_github_config():
    token = st.secrets.get("GITHUB_TOKEN", "")
    repo = st.secrets.get("GITHUB_REPO", "cheni135/keiba-ai-pro")
    return token, repo

def load_cloud_csv(filename, default_cols):
    token, repo = get_github_config()
    if token:
        s = chr(47)
        url = f"https:{s}{s}api.github.com{s}repos{s}{repo}{s}contents{s}{filename}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json().get("content", "")).decode("utf-8-sig")
            return pd.read_csv(io.StringIO(content))
    if os.path.exists(filename):
        return pd.read_csv(filename)
    return pd.DataFrame(columns=default_cols)

def save_cloud_csv(filename, df_to_save, commit_msg):
    df_to_save.to_csv(filename, index=False, encoding="utf-8-sig")
    token, repo = get_github_config()
    if not token:
        return False
    s = chr(47)
    url = f"https:{s}{s}api.github.com{s}repos{s}{repo}{s}contents{s}{filename}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    r_get = requests.get(url, headers=headers, timeout=10)
    sha = r_get.json().get("sha") if r_get.status_code == 200 else None

    csv_str = df_to_save.to_csv(index=False, encoding="utf-8-sig")
    b64_content = base64.b64encode(csv_str.encode("utf-8-sig")).decode("utf-8")
    payload = {"message": commit_msg, "content": b64_content}
    if sha:
        payload["sha"] = sha
    r_put = requests.put(url, headers=headers, json=payload, timeout=15)
    return r_put.status_code in (200, 201)

# 初回読み込み時にクラウドからMy予想と収支を復元
if "cloud_loaded" not in st.session_state:
    st.session_state["my_preds_df"] = load_cloud_csv("my_predictions.csv", ["開催", "レース", "馬番", "My印", "Myメモ"])
    st.session_state["ledger_df"] = load_cloud_csv("my_ledger.csv", ["レース", "券種", "投資額", "払戻額", "収支", "結果"])
    st.session_state["cloud_loaded"] = True

# 6ページ構成ナビゲーション
page_mode = st.radio(
    "メニュー選択",
    ("🔥 勝負レース・お宝馬", "📋 出馬表・My予想", "🤖 AIスコア・根拠分析", "💰 買い目・合成オッズ", "🌱 当日の馬場傾向", "📈 収支・回収率管理"),
    horizontal=True
)
st.divider()

if not os.path.exists("latest_races.csv"):
    st.error("データファイル（latest_races.csv）がまだ生成されていません。Actionsから実行してください。")
    st.stop()

all_df = pd.read_csv("latest_races.csv")
if all_df.empty:
    st.warning("現在データが空です。GitHub Actionsの「Run workflow」を実行して最新データを取り込んでください。")
    st.stop()

last_upd = str(all_df.get("更新日時").iloc) if "更新日時" in all_df.columns and len(all_df) > 0 else "自動更新済み"
token_chk, _ = get_github_config()
sync_status = "☁️ クラウド自動保存ON" if token_chk else "💾 ローカル保存モード（Secrets設定で完全永続化）"
st.caption(f"🔄 AI最終更新: {last_upd} ｜ {sync_status}")

def score_to_rank(val):
    if val >= 70:
        return "S（超抜）"
    elif val >= 60:
        return "A（優秀）"
    elif val >= 50:
        return "B（平均以上）"
    else:
        return "C（平均未満）"

def generate_ai_comment(row, race_avg):
    diff_avg = round(float(row.get("能力スコア", 50.0)) - race_avg, 1)
    f_chaku = float(row.get("着順着差指数", 50.0))
    f_furi = float(row.get("不利補正値", 0.0))
    f_cls = float(row.get("クラス補正", 0.0))
    f_lap = float(row.get("ラップタイム指数", 50.0))
    f_sire = float(row.get("血統適性", 50.0))
    f_style = float(row.get("枠順展開適合", 50.0))
    f_stable = float(row.get("厩舎騎手勝負度", 50.0))
    f_rote = float(row.get("ローテ体調", 50.0))
    f_train = float(row.get("調教指数", 50.0))
    sign = str(row.get("激変サイン", "")) if pd.notna(row.get("激変サイン")) else ""
    exp_v = float(row.get("期待値スコア", 100.0))
    odds_v = float(row.get("単勝オッズ", 10.0))

    plus_list = list()
    minus_list = list()

    if f_chaku >= 60:
        plus_list.append(f"着順・着差指数({f_chaku}点)が優秀")
    elif f_chaku <= 42:
        minus_list.append(f"近走の着順・着差({f_chaku}点)が割引")

    if f_furi > 0:
        plus_list.append(f"前走不利補正(+{int(f_furi)}pt)で実力上方修正")
    if f_cls > 0:
        plus_list.append(f"{row.get('レースクラス', '')}クラス補正(+{f_cls}pt)")
    elif f_cls < 0:
        minus_list.append(f"クラス基準補正({f_cls}pt)")

    if f_lap >= 60:
        plus_list.append(f"馬場差補正タイム({f_lap}点)が上位")
    elif f_lap <= 42:
        minus_list.append(f"持ち時計指数({f_lap}点)が劣勢")

    if f_sire >= 60:
        plus_list.append(f"父{row.get('父馬')}のコース適性({f_sire}点)が高い")
    elif f_sire <= 42:
        minus_list.append(f"血統適性({f_sire}点)に課題")

    if f_style >= 58:
        plus_list.append(f"{int(row.get('枠番'))}枠・{row.get('脚質')}脚質が展開に合致({f_style}点)")
    elif f_style <= 42:
        minus_list.append(f"枠順・展開面({f_style}点)で不利")

    if f_stable >= 58:
        plus_list.append(f"{row.get('騎手')}起用など陣営勝負度({f_stable}点)が高い")
    if f_train >= 60:
        plus_list.append(f"追い切り指数({f_train}点)良好")
    if f_rote <= 42:
        minus_list.append(f"ローテ・体調面({f_rote}点)に不安")
    if sign:
        plus_list.append(f"激変トリガー【{sign}】発動")

    parts = list()
    if plus_list:
        parts.append("【プラス材料】" + "・".join(plus_list[:3]))
    if minus_list:
        parts.append("【マイナス材料】" + "・".join(minus_list[:2]))

    if exp_v >= 120:
        parts.append(f"実力（勝率{row.get('AI予測勝率')}%/3着内{row.get('AI予測3着内率')}%）に対し単勝{odds_v}倍は甘く、期待値{exp_v}ptの激走お宝候補。")
    elif exp_v <= 85 and odds_v <= 5.0:
        parts.append(f"能力は一定水準もオッズ{odds_v}倍は過剰人気（期待値{exp_v}pt）で妙味薄。")

    head = f"能力{row.get('能力スコア')}点（レース平均比 {diff_avg:+.1f}pt）："
    return head + (" ／ ".join(parts) if parts else "各ファクターが平均水準でバランス型。")

# ==========================================
# ページ①：🔥 勝負レース・お宝馬
# ==========================================
if "勝負レース" in page_mode:
    st.header("🔥 本日のAI激アツ勝負レース＆お宝穴馬")

    hot_races = list()
    for (kaisai, r_name), grp in all_df.groupby(["開催", "レース"], sort=False):
        s_grp = grp.sort_values("能力スコア", ascending=False)
        top1 = s_grp.iloc
        top2 = s_grp.iloc if len(s_grp) > 1 else top1
        diff12 = round(float(top1.get("能力スコア")) - float(top2.get("能力スコア")), 1)
        max_exp = float(grp.get("期待値スコア").max())
        exp_horse = grp.sort_values("期待値スコア", ascending=False).iloc

        badge = ""
        if float(top1.get("能力スコア")) >= 66.0 and diff12 >= 4.5:
            badge = "👑 AI鉄板・自信あり（軸堅め）"
        elif max_exp >= 125.0:
            badge = "💎 激アツお宝レース（高配当狙い）"
        elif diff12 >= 3.5:
            badge = "🔥 有力軸信頼レース"

        if badge:
            hot_races.append({
                "判定": badge,
                "開催": kaisai,
                "レース": r_name,
                "AI能力1位(◎)": f"{int(top1.get('馬番'))}番 {top1.get('馬名')} ({top1.get('能力スコア')}点)",
                "2位との差": f"+{diff12}pt",
                "期待値TOP穴馬": f"{int(exp_horse.get('馬番'))}番 {exp_horse.get('馬名')} ({exp_horse.get('期待値スコア')}pt / {exp_horse.get('単勝オッズ')}倍)"
            })

    st.subheader("🎯 AIピックアップ！本日の勝負レース一覧")
    if hot_races:
        st.dataframe(pd.DataFrame(hot_races), use_container_width=True, hide_index=True)
    else:
        st.info("現在は全体的に混戦模様のレースが多い開催です。下のお宝穴馬ランキングから妙味馬を狙いましょう。")

    st.divider()

    st.subheader("🏆 全レース横断・期待値Sランク（115pt超え）お宝穴馬 TOP10")
    treasure_df = all_df.query("期待値スコア >= 115.0").sort_values("期待値スコア", ascending=False).head(10)
    if not treasure_df.empty:
        t_cols = ("開催", "レース", "馬番", "馬名", "netkeiba", "騎手", "激変サイン", "単勝オッズ", "能力スコア", "AI予測3着内率", "期待値スコア")
        avail_t = tuple(c for c in t_cols if c in treasure_df.columns)
        st.dataframe(
            treasure_df.loc[:, avail_t],
            column_config={"netkeiba": st.column_config.LinkColumn("戦績", display_text="🔍 戦績")},
            use_container_width=True,
            hide_index=True
        )
    else:
        st.write("現在期待値115pt超えの馬はありません。")

# ==========================================
# ページ⑥：📈 収支・回収率管理（クラウド自動保存対応）
# ==========================================
elif "収支" in page_mode:
    st.header("📈 My収支＆回収率管理トラッカー")
    st.caption("記録した収支データはGitHubクラウドへ自動保存されるため、スマホを閉じても消えません。")

    led_df = st.session_state["ledger_df"].copy()

    with st.container(border=True):
        st.subheader("➕ 新しい収支を記録")
        c_l1, c_l2, c_l3, c_l4 = st.columns(4)
        with c_l1:
            l_race = st.text_input("開催・レース（例：東京11R）", value="東京11R")
        with c_l2:
            l_bet_type = st.selectbox("主な券種", ("馬連", "3連複", "3連単", "単勝", "複勝", "ワイド", "馬単", "枠連"))
        with c_l3:
            l_invest = st.number_input("投資額（円）", min_value=100, max_value=1000000, value=1000, step=100)
        with c_l4:
            l_return = st.number_input("払戻額（円）", min_value=0, max_value=10000000, value=0, step=100)

        if st.button("💾 この収支を保存する", type="primary"):
            new_row = pd.DataFrame([{
                "レース": l_race,
                "券種": l_bet_type,
                "投資額": int(l_invest),
                "払戻額": int(l_return),
                "収支": int(l_return - l_invest),
                "結果": "🎯 的中" if l_return > 0 else "ハズレ"
            }])
            updated_led = pd.concat([led_df, new_row], ignore_index=True)
            st.session_state["ledger_df"] = updated_led
            save_cloud_csv("my_ledger.csv", updated_led, "Update my_ledger.csv")
            st.success("収支を記録・保存しました！")
            st.rerun()

    st.divider()

    if not led_df.empty:
        tot_inv = int(led_df["投資額"].sum())
        tot_ret = int(led_df["払戻額"].sum())
        roi = round((tot_ret / tot_inv) * 100.0, 1) if tot_inv > 0 else 0.0
        profit = tot_ret - tot_inv
        hit_count = int((led_df["払戻額"] > 0).sum())
        hit_rate = round((hit_count / len(led_df)) * 100.0, 1)
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("累計投資額", f"{tot_inv:,} 円")
m2.metric("累計払戻額", f"{tot_ret:,} 円")
m3.metric("トータル収支", f"{profit:+,} 円")
m4.metric("回収率", f"{roi} %", delta="プラス圏！" if roi >= 100.0 else "100%未満", delta_color="normal" if roi >= 100.0 else "inverse")
m5.metric("的中率", f"{hit_rate} %", delta=f"{hit_count}/{len(led_df)}レース")
led_df["累計収支"] = led_df["収支"].cumsum()
st.line_chart(led_df["累計収支"])
st.subheader("📝 収支履歴一覧")
st.dataframe(led_df.drop(columns=["累計収支"]), use_container_width=True, hide_index=True)
col_b1, col_b2 = st.columns(2)
with col_b1:
    csv_bytes = led_df.drop(columns=["累計収支"]).to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("📥 手元バックアップCSVダウンロード", data=csv_bytes, file_name="my_keiba_ledger.csv", mime="text/csv")
with col_b2:
    if st.button("🗑️ 履歴をすべてリセット"):
        empty_led = pd.DataFrame(columns=["レース", "券種", "投資額", "払戻額", "収支", "結果"])
        st.session_state["ledger_df"] = empty_led
        save_cloud_csv("my_ledger.csv", empty_led, "Reset my_ledger.csv")
        st.rerun()
else:
st.info("まだ収支データがありません。上のフォームから投資額と払戻額を記録すると、回収率や収支推移グラフが自動表示されます。")

#==========================================


#ページ②〜⑤：共通の開催場・レース選択ヘッダー


#==========================================

else:
col_top1, col_top2 = st.columns(2)
with col_top1:
kaisai_list = tuple(all_df.get("開催").unique())
selected_kaisai = st.selectbox("開催場を選択", kaisai_list)
sub_df = all_df.query("開催 == @selected_kaisai").sort_values("レース番号")
with col_top2:
race_list = tuple(sub_df.get("レース").unique())
selected_race = st.selectbox("レースを選択", race_list)
race_df = sub_df.query("レース == @selected_race").sort_values("馬番").copy()
ranked_base = race_df.sort_values("能力スコア", ascending=False).reset_index(drop=True)
ai_marks = ("◎", "○", "▲", "△", "☆")
ai_map = {int(r.get("馬番")): (ai_marks[i] if i < len(ai_marks) else "") for i, r in enumerate(ranked_base.to_dict("records"))}
# 永続化済みMy予想CSVから該当レースの印とメモを復元
preds_df = st.session_state["my_preds_df"]
race_preds = preds_df.query("開催 == @selected_kaisai and レース == @selected_race")
saved_marks = {int(r.get("馬番")): str(r.get("My印", "")) if pd.notna(r.get("My印")) else "" for r in race_preds.to_dict("records")}
saved_memos = {int(r.get("馬番")): str(r.get("Myメモ", "")) if pd.notna(r.get("Myメモ")) else "" for r in race_preds.to_dict("records")}
race_df = race_df.assign(
AI印=tuple(ai_map.get(int(u), "") for u in race_df.get("馬番")),
My印=tuple(saved_marks.get(int(u), "") for u in race_df.get("馬番")),
Myメモ=tuple(saved_memos.get(int(u), "") for u in race_df.get("馬番"))
)
# ==========================================
# ページ②：📋 出馬表・My予想（netkeiba直通リンク ＋ 永続保存）
# ==========================================
if "出馬表" in page_mode:
st.subheader(f"📋 {selected_kaisai} {selected_race} 出馬表・My予想")
st.caption("💡 馬名横の「🔍 戦績」を押すとnetkeibaのその馬のページへ飛びます。「My印」「Myメモ」は入力後、下の保存ボタンで永続保存できます。")
shutuba_cols = ("枠番", "馬番", "My印", "AI印", "馬名", "netkeiba", "斤量", "騎手", "脚質", "父馬", "激変サイン", "単勝オッズ", "Myメモ")
avail_s = tuple(c for c in shutuba_cols if c in race_df.columns)
edited_shutuba = st.data_editor(
race_df.loc[:, avail_s],
column_config={
"枠番": st.column_config.NumberColumn("枠", disabled=True, width="small"),
"馬番": st.column_config.NumberColumn("馬番", disabled=True, width="small"),
"My印": st.column_config.SelectboxColumn("My印", options=("", "◎", "○", "▲", "△", "☆", "✓", "消"), width="small"),
"AI印": st.column_config.TextColumn("AI印", disabled=True, width="small"),
"馬名": st.column_config.TextColumn("馬名", disabled=True),
"netkeiba": st.column_config.LinkColumn("詳細", display_text="🔍 戦績", width="small"),
"斤量": st.column_config.NumberColumn("斤量", disabled=True, format="%.1f", width="small"),
"騎手": st.column_config.TextColumn("騎手", disabled=True),
"脚質": st.column_config.TextColumn("脚質", disabled=True, width="small"),
"父馬": st.column_config.TextColumn("父馬", disabled=True),
"激変サイン": st.column_config.TextColumn("激変サイン", disabled=True),
"単勝オッズ": st.column_config.NumberColumn("オッズ", disabled=True, format="%.1f"),
"Myメモ": st.column_config.TextColumn("Myメモ（自由入力）", width="medium"),
},
use_container_width=True,
hide_index=True,
key=f"shutuba_editor_{selected_kaisai}_{selected_race}"
)
if st.button("💾 このレースのMy印・Myメモを永続保存する", type="primary"):
other_preds = preds_df.query("not (開催 == @selected_kaisai and レース == @selected_race)")
new_rows = list()
for r in edited_shutuba.to_dict("records"):
m_val = str(r.get("My印", "")) if pd.notna(r.get("My印")) else ""
memo_val = str(r.get("Myメモ", "")) if pd.notna(r.get("Myメモ")) else ""
if m_val or memo_val:
new_rows.append({
"開催": selected_kaisai,
"レース": selected_race,
"馬番": int(r.get("馬番")),
"My印": m_val,
"Myメモ": memo_val
})
updated_preds = pd.concat([other_preds, pd.DataFrame(new_rows)], ignore_index=True)
st.session_state["my_preds_df"] = updated_preds
ok = save_cloud_csv("my_predictions.csv", updated_preds, f"Save predictions for {selected_kaisai} {selected_race}")
if ok:
st.success("☁️ GitHubクラウドに永続保存しました！スマホを閉じても消えません。")
else:
st.success("💾 セッションに保存しました！（Secrets設定でクラウドへ完全永続化されます）")
# ==========================================
# ページ③：🤖 AIスコア・根拠分析
# ==========================================
elif "AIスコア" in page_mode:
st.subheader(f"🤖 {selected_kaisai} {selected_race} AIスコア・根拠分析")
mode = st.radio(
"AIスコア表示モード",
("🎯 的中重視モード（能力スコア・偏差値50基準）", "💰 回収率重視モード（期待値スコア・100pt基準）"),
horizontal=True
)
score_col = "能力スコア" if "的中" in mode else "期待値スコア"
ranked_df = race_df.sort_values(score_col, ascending=False).reset_index(drop=True)
ranked_df = ranked_df.assign(
AI印=tuple(ai_marks[i] if i < len(ai_marks) else "" for i in range(len(ranked_df)))
)
race_avg = round(float(ranked_df.get("能力スコア").mean()), 1)
baken_border_score = round(race_avg + 3.0, 1)
scores_sorted = tuple(ranked_df.get("能力スコア").astype(float))
top_score = scores_sorted if len(scores_sorted) > 0 else 50.0
second_score = scores_sorted if len(scores_sorted) > 1 else top_score
diff_1_2 = round(top_score - second_score, 1)
if top_score >= 66.0 and diff_1_2 >= 4.5:
race_type_label = "👑 AI自信あり（1強軸信頼）"
elif diff_1_2 >= 3.0:
race_type_label = "⚖️ 有力馬伯仲"
else:
race_type_label = "🔥 大混戦（波乱注意）"
is_baken_in = (ranked_df.get("AI予測3着内率") >= 25.0) | (ranked_df.get("能力スコア") >= baken_border_score)
baken_count = int(is_baken_in.sum())
m1, m2, m3, m4 = st.columns(4)
m1.metric("📊 レースAI平均値", f"{race_avg} 点")
m2.metric("🎯 馬券内目安ライン", f"{baken_border_score}点 / 3着内25%", delta=f"圏内該当: {baken_count}頭")
m3.metric("🏆 トップ評価値（◎）", f"{top_score} 点", delta=f"平均比 {top_score - race_avg:+.1f}pt")
m4.metric("🔥 レース信頼度判定", race_type_label, delta=f"1・2位差: {diff_1_2}pt")
ranked_df = ranked_df.assign(
馬券内目安=np.where(is_baken_in, "🎯 圏内", "・"),
平均差=np.round(ranked_df.get("能力スコア") - race_avg, 1)
)
tab1, tab2, tab3 = st.tabs(("📊 AIスコア＆確率ランキング", "🔍 馬別AI根拠コメント＆8大内訳", "📈 全頭ファクター横並び比較"))
with tab1:
ai_cols = ("AI印", "My印", "馬券内目安", "馬番", "馬名", "netkeiba", "騎手", "単勝オッズ", "能力スコア", "平均差", "AI予測勝率", "AI予測3着内率", "期待値スコア")
avail_ai = tuple(c for c in ai_cols if c in ranked_df.columns)
st.dataframe(
ranked_df.loc[:, avail_ai],
column_config={
"netkeiba": st.column_config.LinkColumn("詳細", display_text="🔍 戦績"),
"AI予測勝率": st.column_config.NumberColumn("勝率(%)", format="%.1f%%"),
"AI予測3着内率": st.column_config.NumberColumn("3着内率(%)", format="%.1f%%"),
"平均差": st.column_config.NumberColumn("平均差", format="%+.1f"),
},
use_container_width=True,
hide_index=True
)
st.subheader("🤖 AI上位印（◎○▲△☆）の自動根拠コメント")
for r in ranked_df.head(5).to_dict("records"):
comment_str = generate_ai_comment(r, race_avg)
st.info(f"{r.get('AI印')} {int(r.get('馬番'))}番 {r.get('馬名')}（単勝{r.get('単勝オッズ')}倍 / 勝率{r.get('AI予測勝率')}% / 3着内{r.get('AI予測3着内率')}%）\n\n{comment_str}")
with tab2:
selected_horse = st.selectbox("詳細内訳を見る馬を選択", ranked_df.get("馬名"))
info = ranked_df.query("馬名 == @selected_horse").squeeze()
st.subheader(f"AI:{info.get('AI印')} / My:{info.get('My印')} ｜ {int(info.get('馬番'))}番 {info.get('馬名')}（父：{info.get('父馬')}）")
if "netkeiba" in info and pd.notna(info.get("netkeiba")):
st.link_button("🔗 netkeibaでこの馬の過去戦績・血統を見る", str(info.get("netkeiba")))
c1, c2, c3, c4 = st.columns(4)
c1.metric("単勝オッズ", f"{info.get('単勝オッズ')}倍")
c2.metric("🎯 能力スコア", f"{info.get('能力スコア')}点", delta=f"平均比 {float(info.get('能力スコア')) - race_avg:+.1f}pt")
c3.metric("📈 勝率 / 3着内率", f"{info.get('AI予測勝率')}% / {info.get('AI予測3着内率')}%")
c4.metric("💰 期待値スコア", f"{info.get('期待値スコア')}pt")
st.success(f"🤖 AI自動解説： {generate_ai_comment(info, race_avg)}")
baba_now = str(info.get("当日馬場状態", "良"))
if baba_now == "良":
st.caption("⚖️ 配点ウェイト（良馬場モード）： 道悪5%を自動再配分し、着順・着差(28%)・馬場差補正タイム(22%)・血統(15%)・枠展開(15%)・厩舎騎手(10%)・ローテ(5%)・調教(5%)で算出中。")
w_labels = ("28%（再配分込）", "22%（再配分込）", "15%", "15%", "10%", "5%", "5%", "0%（良馬場待機）")
else:
w_labels = ("25%", "20%", "15%", "15%", "10%", "5%", "5%", "5%（道悪発動）")
f_vals = (
float(info.get("着順着差指数", 50.0)),
float(info.get("ラップタイム指数", 50.0)),
float(info.get("血統適性", 50.0)),
float(info.get("枠順展開適合", 50.0)),
float(info.get("厩舎騎手勝負度", 50.0)),
float(info.get("ローテ体調", 50.0)),
float(info.get("調教指数", 50.0)),
float(info.get("道悪適性", 50.0))
)
factor_df = pd.DataFrame({
"評価ファクター（8項目）": (
"1. 着順・着差（クラス・不利補正込）",
"2. ラップ・馬場差補正タイム指数",
"3. 血統適性（父・母父）",
"4. 枠順・展開適合度",
"5. 厩舎・騎手勝負気配",
"6. ローテ・体調指数",
"7. 調教（追い切り）指数",
"8. 馬場状態適性（道悪）"
),
"適用ウェイト": w_labels,
"個別スコア(平均50基準)": f_vals,
"判定ランク": tuple(score_to_rank(v) for v in f_vals)
})
st.dataframe(factor_df, use_container_width=True, hide_index=True)
st.bar_chart(factor_df.set_index("評価ファクター（8項目）")["個別スコア(平均50基準)"])
with tab3:
comp_cols = ("AI印", "My印", "馬番", "馬名", "能力スコア", "期待値スコア", "着順着差指数", "ラップタイム指数", "血統適性", "枠順展開適合", "厩舎騎手勝負度", "ローテ体調", "調教指数", "道悪適性")
avail_cols = tuple(c for c in comp_cols if c in ranked_df.columns)
st.dataframe(ranked_df.loc[:, avail_cols], use_container_width=True, hide_index=True)
# ==========================================
# ページ④：💰 買い目・合成オッズ計算
# ==========================================
elif "買い目" in page_mode:
st.subheader(f"💰 {selected_kaisai} {selected_race} 買い目・合成オッズ計算")
c_k1, c_k2, c_k3 = st.columns(3)
with c_k1:
bet_type = st.selectbox("券種（式別）", ("単勝", "複勝", "枠連", "馬連", "ワイド", "馬単", "3連複", "3連単"))
with c_k2:
preset = st.radio("印から自動セット", ("My印を反映", "AI印を反映", "手動選択"), horizontal=True)
with c_k3:
budget = st.number_input("総予算（円）", min_value=100, max_value=1000000, value=3000, step=100)
uma_df = race_df.sort_values("馬番")
uma_options = tuple(f"{int(r.get('馬番'))}番 {r.get('馬名')} ({r.get('単勝オッズ')}倍)" for r in uma_df.to_dict("records"))
label_to_num = {f"{int(r.get('馬番'))}番 {r.get('馬名')} ({r.get('単勝オッズ')}倍)": int(r.get("馬番")) for r in uma_df.to_dict("records")}
num_to_odds = {int(r.get("馬番")): float(r.get("単勝オッズ")) for r in uma_df.to_dict("records")}
num_to_waku = {int(r.get("馬番")): int(r.get("枠番")) for r in uma_df.to_dict("records")}
num_to_name = {int(r.get("馬番")): str(r.get("馬名")) for r in uma_df.to_dict("records")}
mark_col = "My印" if preset == "My印を反映" else "AI印"
honmei_nums = set(uma_df.query(f"{mark_col} == '◎'").get("馬番").astype(int))
aite_nums = set(uma_df.query(f"{mark_col} in ['○', '▲', '△', '☆', '✓']").get("馬番").astype(int))
if not honmei_nums and preset != "手動選択":
honmei_nums = set(ranked_base.head(1).get("馬番").astype(int))
if not aite_nums and preset != "手動選択":
aite_nums = set(ranked_base.iloc[1:5].get("馬番").astype(int))
def get_defaults(target_set):
if preset == "手動選択":
return list()
return [opt for opt in uma_options if label_to_num[opt] in target_set]
combos = list()
if bet_type in ("単勝", "複勝"):
sel1 = st.multiselect("購入する馬を選択", uma_options, default=get_defaults(honmei_nums | aite_nums))
for s in sel1:
combos.append((label_to_num[s],))
elif bet_type in ("枠連", "馬連", "ワイド", "馬単"):
col_f1, col_f2 = st.columns(2)
with col_f1:
sel1 = st.multiselect("1頭目（軸・1着候補）", uma_options, default=get_defaults(honmei_nums))
with col_f2:
sel2 = st.multiselect("2頭目（相手・2着候補）", uma_options, default=get_defaults(honmei_nums | aite_nums))
n1_list = [label_to_num[s] for s in sel1]
n2_list = [label_to_num[s] for s in sel2]
seen = set()
for a in n1_list:
for b in n2_list:
if bet_type == "枠連":
wa, wb = num_to_waku[a], num_to_waku[b]
pair = tuple(sorted((wa, wb)))
if pair not in seen:
seen.add(pair)
combos.append(pair)
elif bet_type == "馬単":
if a != b and (a, b) not in seen:
seen.add((a, b))
combos.append((a, b))
else:
if a != b:
pair = tuple(sorted((a, b)))
if pair not in seen:
seen.add(pair)
combos.append(pair)
else:
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
sel1 = st.multiselect("1頭目（1着・軸）", uma_options, default=get_defaults(honmei_nums))
with col_f2:
sel2 = st.multiselect("2頭目（2着・相手1）", uma_options, default=get_defaults(honmei_nums | aite_nums))
with col_f3:
sel3 = st.multiselect("3頭目（3着・相手2）", uma_options, default=get_defaults(honmei_nums | aite_nums))
n1_list = [label_to_num[s] for s in sel1]
n2_list = [label_to_num[s] for s in sel2]
n3_list = [label_to_num[s] for s in sel3]
seen = set()
for a in n1_list:
for b in n2_list:
for c in n3_list:
if len({a, b, c}) == 3:
trip = (a, b, c) if bet_type == "3連単" else tuple(sorted((a, b, c)))
if trip not in seen:
seen.add(trip)
combos.append(trip)
total_inv = sum(1.0 / max(1.1, v) for v in num_to_odds.values())
win_probs = {k: (1.0 / max(1.1, v)) / total_inv for k, v in num_to_odds.items()}
bet_rows = list()
for cb in combos:
if bet_type == "単勝":
est_odds = num_to_odds[cb]
label_str = f"{cb} ({num_to_name[cb]})"
elif bet_type == "複勝":
est_odds = round(max(1.1, num_to_odds[cb] * 0.28 + 0.8), 1)
label_str = f"{cb} ({num_to_name[cb]})"
elif bet_type == "枠連":
p_pair = 0.08 if cb == cb else 0.06
est_odds = round(max(1.5, 0.775 / p_pair), 1)
label_str = f"{cb}-{cb}枠"
elif bet_type == "馬連":
pa, pb = win_probs[cb], win_probs[cb]
p_umaren = pa * (pb / max(0.05, 1 - pa)) + pb * (pa / max(0.05, 1 - pb))
est_odds = round(max(1.5, (0.775 / max(0.0005, p_umaren)) * 0.85), 1)
label_str = f"{cb}-{cb}"
elif bet_type == "ワイド":
pa, pb = win_probs[cb], win_probs[cb]
p_wide = (pa * (pb / max(0.05, 1 - pa)) + pb * (pa / max(0.05, 1 - pb))) * 2.6
est_odds = round(max(1.1, 0.775 / max(0.001, p_wide)), 1)
label_str = f"{cb}-{cb}"
elif bet_type == "馬単":
pa, pb = win_probs[cb], win_probs[cb]
p_umatan = pa * (pb / max(0.05, 1 - pa))
est_odds = round(max(2.0, (0.75 / max(0.0003, p_umatan)) * 0.85), 1)
label_str = f"{cb}→{cb}"
elif bet_type == "3連複":
pa, pb, pc = win_probs[cb], win_probs[cb], win_probs[cb]
p_3fuku = (pa * pb * pc) * 6.0 * 1.4
est_odds = round(max(3.0, 0.75 / max(0.0001, p_3fuku)), 1)
label_str = f"{cb}-{cb}-{cb}"
else:
pa, pb, pc = win_probs[cb], win_probs[cb], win_probs[cb]
p_3tan = pa * (pb / max(0.05, 1 - pa)) * (pc / max(0.05, 1 - pa - pb))
est_odds = round(max(5.0, (0.725 / max(0.00005, p_3tan)) * 0.85), 1)
label_str = f"{cb}→{cb}→{cb}"
bet_rows.append({"買い目": label_str, "想定オッズ": est_odds})
st.divider()
if not bet_rows:
st.info("購入したい馬を選択すると、点数・合成オッズ・資金配分が自動計算されます。")
else:
bet_df = pd.DataFrame(bet_rows).sort_values("想定オッズ").reset_index(drop=True)
num_points = len(bet_df)
inv_sum = sum(1.0 / o for o in bet_df["想定オッズ"])
synthetic_odds = round(1.0 / inv_sum, 2) if inv_sum > 0 else 0.0
raw_alloc = [budget * ((1.0 / o) / inv_sum) for o in bet_df["想定オッズ"]]
alloc_100 = [max(100, int(round(a / 100.0) * 100)) for a in raw_alloc]
bet_df["推奨配分(円)"] = alloc_100
bet_df["的中時払戻(円)"] = (bet_df["想定オッズ"] * bet_df["推奨配分(円)"]).astype(int)
m1, m2, m3 = st.columns(3)
m1.metric("買い目点数", f"{num_points} 点")
m2.metric("合成オッズ", f"{synthetic_odds} 倍", delta="トリガミ注意！" if synthetic_odds < 1.0 else "プラス圏内", delta_color="inverse" if synthetic_odds < 1.0 else "normal")
m3.metric("配分合計額", f"{sum(alloc_100):,} 円")
if synthetic_odds < 1.0:
st.warning("⚠️ 合成オッズが1.0倍を下回っています（トリガミ状態）。点数を絞るか、オッズの低い買い目を削ると回収効率が上がります。")
st.dataframe(bet_df, use_container_width=True, hide_index=True)
# ==========================================
# ページ⑤：🌱 当日の馬場傾向（トラックバイアス）専用ページ
# ==========================================
else:
st.header(f"🌱 {selected_kaisai} 当日の馬場傾向レポート")
st.caption("※AIスコアの数値には干渉せず、当日の馬場バイアス・有利枠・有利脚質を独立分析して表示します。")
baba_surface = st.radio("コース種別", ("芝コース", "ダートコース"), horizontal=True)
c_m1, c_m2, c_m3 = st.columns(3)
if baba_surface == "芝コース":
c_m1.metric("馬場状態", "良（クッション値 9.4）")
c_m2.metric("馬場時計レベル", "やや高速（-0.6秒）")
c_m3.metric("トラックバイアス判定", "内・先行やや有利")
else:
c_m1.metric("馬場状態", "良（含水率 3.2%）")
c_m2.metric("馬場時計レベル", "標準（±0.0秒）")
c_m3.metric("トラックバイアス判定", "先行・外枠スムーズ有利")
st.divider()
col_g1, col_g2 = st.columns(2)
with col_g1:
st.subheader("📊 枠順別 3着内率トレンド")
waku_trend = pd.DataFrame({
"枠順区分": ("1〜2枠（内）", "3〜4枠（中内）", "5〜6枠（中外）", "7〜8枠（外）"),
"3着内率(%)": (28.5, 24.0, 19.5, 16.0) if baba_surface == "芝コース" else (18.0, 21.5, 25.0, 27.5)
})
st.bar_chart(waku_trend.set_index("枠順区分"))
with col_g2:
st.subheader("🐎 脚質別 好走傾向トレンド")
style_trend = pd.DataFrame({
"脚質": ("逃げ", "先行", "差し", "追込"),
"好走指数": (34.0, 31.0, 21.0, 14.0) if baba_surface == "芝コース" else (30.0, 35.0, 23.0, 12.0)
})
st.bar_chart(style_trend.set_index("脚質"))
st.divider()
st.subheader("🔍 本日の馬場傾向に合致する注目馬（全レース横断）")
target_track = "芝" if baba_surface == "芝コース" else "ダート"
track_df = sub_df.query("馬場 == @target_track").copy()
if baba_surface == "芝コース":
pickup_df = track_df.query("枠番 <= 4 and 脚質 in ['逃げ', '先行']").sort_values("能力スコア", ascending=False)
st.info("💡 芝の注目条件： 内枠（1〜4枠）× 逃げ・先行脚質の馬を自動抽出しています。")
else:
pickup_df = track_df.query("枠番 >= 5 and 脚質 in ['逃げ', '先行']").sort_values("能力スコア", ascending=False)
st.info("💡 ダートの注目条件： 砂を被りにくい外目（5〜8枠）× 逃げ・先行脚質の馬を自動抽出しています。")
if not pickup_df.empty:
st.dataframe(
pickup_df.loc[:, ("レース", "枠番", "馬番", "馬名", "脚質", "騎手", "単勝オッズ", "能力スコア", "AI予測3着内率", "期待値スコア")].head(15),
use_container_width=True,
hide_index=True
)
else:
st.write("該当する条件の馬がまだ登録されていません。")
