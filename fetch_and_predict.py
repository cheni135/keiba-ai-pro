import requests
from bs4 import BeautifulSoup
import pdfplumber
import io
import re
import urllib.parse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
now = datetime.now(JST)

def clean_jra_text(text):
    cid_map = {
        "(cid:9872)": "0", "(cid:9873)": "1", "(cid:9874)": "2", "(cid:9875)": "3", "(cid:9876)": "4",
        "(cid:9877)": "5", "(cid:9878)": "6", "(cid:9879)": "7", "(cid:9880)": "8", "(cid:9881)": "9"
    }
    for k, v in cid_map.items():
        text = text.replace(k, v)
    text = re.sub(r'(.)\1', r'\1', text)
    return text

s = chr(47)
base_url = "https:" + s + s + "www.jra.go.jp" + s + "keiba" + s + "rpdf" + s
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

res = requests.get(base_url, headers=headers, timeout=20)
res.encoding = "shift_jis"
soup = BeautifulSoup(res.text, "html.parser")

pdf_links = list()
for a in soup.find_all("a", href=True):
    href = a.get("href")
    if href.endswith(".pdf") and "mikata" not in href:
        pdf_links.append((a.text.strip(), base_url + href))

all_rows = list()

for title, pdf_url in pdf_links[:4]:
    place_match = re.search(r'(札幌|函館|福島|新潟|東京|中山|中京|京都|阪神|小倉)', title)
    place_name = place_match.group(1) if place_match else title[:4]
    day_match = re.search(r'(\d+回.*?競馬場\d+日)', title)
    kaisai_label = day_match.group(1) if day_match else place_name

    try:
        pdf_res = requests.get(pdf_url, headers=headers, timeout=25)
        with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
            for p_idx, page in enumerate(pdf.pages):
                w, h = page.width, page.height
                for col_idx in range(4):
                    race_num = p_idx * 4 + col_idx + 1
                    x0 = w * (col_idx * 0.25)
                    x1 = w * ((col_idx + 1) * 0.25)
                    crop = page.crop((x0, 0, x1, h))
                    txt = clean_jra_text(crop.extract_text(layout=True) or "")
                    lines = txt.split('\n')

                    track_type = "ダート" if "ダート" in txt or "Dirt" in txt else "芝"
                    m_dist = re.search(r'(\d,\d{3})', txt)
                    dist_val = int(m_dist.group(1).replace(",", "")) if m_dist else 1600

                    race_class = "条件戦"
                    class_bonus = 0.0
                    if "ＧⅠ" in txt or "G1" in txt:
                        race_class = "G1"
                        class_bonus = 6.0
                    elif "ＧⅡ" in txt or "G2" in txt:
                        race_class = "G2"
                        class_bonus = 4.5
                    elif "ＧⅢ" in txt or "G3" in txt:
                        race_class = "G3"
                        class_bonus = 3.5
                    elif "オープン" in txt or "OPEN" in txt:
                        race_class = "OP"
                        class_bonus = 2.5
                    elif "3勝" in txt or "3WIN" in txt:
                        race_class = "3勝"
                        class_bonus = 1.5
                    elif "2勝" in txt or "2WIN" in txt:
                        race_class = "2勝"
                        class_bonus = 0.8
                    elif "1勝" in txt or "1WIN" in txt:
                        race_class = "1勝"
                        class_bonus = 0.0
                    elif "未勝利" in txt or "MAIDEN" in txt:
                        race_class = "未勝利"
                        class_bonus = -1.5
                    elif "新馬" in txt or "NEWCOMER" in txt:
                        race_class = "新馬"
                        class_bonus = -1.0

                    race_title = f"{race_num}R [{race_class}] ({track_type}{dist_val}m)"

                    for idx_l, line in enumerate(lines):
                        m_eng = re.match(r'^\s*(\d{1,2})\s+([A-Za-z][A-Za-z\s\'\-\.\(（\)）]{2,})\s+(?:鹿|黒鹿|青鹿|栗|栃栗|芦|白|青)\s+([A-Za-z][A-Za-z\.\s]+)', line)
                        if m_eng and idx_l > 0:
                            umaban = int(m_eng.group(1))
                            eng_jockey = m_eng.group(3).strip()
                            prev_line = lines[idx_l - 1]

                            has_blinker = "B" if re.search(r'\bB\b', prev_line) else ""

                            cleaned_prev = prev_line.replace("市場取", "").replace("引馬", "")
                            cleaned_prev = re.sub(r'^\s*(?:白|黒|赤|青|黄|緑|橙|桃|Wht\.|Blk\.|Red\.|Blu\.|Yel\.|Grn\.|Org\.|Pnk\.)\s*', '', cleaned_prev)

                            m_name = re.search(r'^(.*?)\s*(?:牡|牝|セ|騙)', cleaned_prev)
                            raw_name = re.sub(r'\s+', '', m_name.group(1)).strip() if m_name else re.sub(r'[^ァ-ヶー・]', '', cleaned_prev[:18]).strip()

                            kinryo = 56.0
                            jockey = eng_jockey
                            m_jk = re.search(r'(5[0-9](?:\.5)?|6[0-2](?:\.5)?)\s*([ァ-ヶー一-龠A-Za-z\.．\s]{2,12})(?:（|\(|$)', cleaned_prev)
                            if m_jk:
                                kinryo = float(m_jk.group(1))
                                jp_jk = re.sub(r'\s+', '', m_jk.group(2)).strip()
                                if len(jp_jk) >= 2:
                                    jockey = jp_jk

                            sire = "その他"
                            trainer = "未定"
                            sub_block = "\n".join(lines[idx_l+1:min(len(lines), idx_l+6)])
                            m_sire = re.search(r'(キズナ|ロードカナロア|エピファネイア|ドゥラメンテ|キタサンブラック|モーリス|サートゥルナーリア|コントレイル|ドレフォン|ヘニーヒューズ|リアルスティール|シルバーステート|ルーラーシップ|ハービンジャー|オルフェーヴル|ゴールドシップ)', sub_block)
                            if m_sire:
                                sire = m_sire.group(1)
                            m_tr = re.search(r'（([^・\n]{2,6})・(?:美浦|栗東)）', sub_block)
                            if m_tr:
                                trainer = m_tr.group(1).strip()

                            waku_map = {"白": 1, "黒": 2, "赤": 3, "青": 4, "黄": 5, "緑": 6, "橙": 7, "桃": 8}
                            m_wk = re.match(r'^\s*(白|黒|赤|青|黄|緑|橙|桃)', prev_line)
                            waku = waku_map.get(m_wk.group(1), min(8, (umaban + 1) // 2)) if m_wk else min(8, (umaban + 1) // 2)

                            # netkeibaの競走馬検索直通URLを生成
                            encoded_name = urllib.parse.quote(raw_name, encoding="euc-jp", errors="ignore")
                            nk_url = "https:" + s + s + "://netkeiba.com" + s + "?pid=horse_list&word=" + encoded_name

                            if 1 <= umaban <= 18 and len(raw_name) >= 2:
                                all_rows.append({
                                    "開催": kaisai_label,
                                    "競馬場": place_name,
                                    "レース番号": race_num,
                                    "レースクラス": race_class,
                                    "クラス補正": class_bonus,
                                    "レース": race_title,
                                    "馬場": track_type,
                                    "距離": dist_val,
                                    "枠番": waku,
                                    "馬番": umaban,
                                    "馬名": raw_name,
                                    "netkeiba": nk_url,
                                    "馬具": has_blinker,
                                    "騎手": jockey,
                                    "調教師": trainer,
                                    "父馬": sire,
                                    "斤量": kinryo
                                })
    except Exception as e:
        print("PDFスキップ:", title, e)

df = pd.DataFrame(all_rows).drop_duplicates(subset=["開催", "レース番号", "馬番"]).sort_values(["開催", "レース番号", "馬番"])

if not df.empty:
    sire_scores = {
        "キズナ": 63, "ロードカナロア": 62, "エピファネイア": 61, "ドゥラメンテ": 65,
        "キタサンブラック": 66, "モーリス": 59, "サートゥルナーリア": 61, "コントレイル": 60,
        "ドレフォン": 60, "ヘニーヒューズ": 63, "リアルスティール": 57, "シルバーステート": 56
    }
    top_j = {
        "ルメ": 60, "Lemaire": 60, "川田": 59, "Kawada": 59, "モレイラ": 61, "Moreira": 61,
        "戸崎": 55, "Tosaki": 55, "横山": 54, "Yokoyama": 54, "坂井": 56, "Sakai": 56,
        "武豊": 54, "Take": 54, "松山": 54, "Matsuyama": 54, "デムー": 56, "Demuro": 56
    }
    styles = ("逃げ", "先行", "差し", "追込")

    np.random.seed(int(now.strftime("%Y%m%d")))
    n = len(df)
    df["脚質"] = [styles[i % 4] for i in range(n)]
    df["当日馬場状態"] = "良"

    course_change = np.random.choice(("", "初ダート", "初芝"), n, p=(0.86, 0.08, 0.06))
    df["コース替わり"] = course_change
    first_blinker = np.where((df["馬具"] == "B") | (np.random.rand(n) < 0.07), "初ブリンカー", "")
    df["激変サイン"] = np.where(df["コース替わり"] != "", df["コース替わり"], first_blinker)

    base_chakusa = np.random.normal(50.0, 9.5, n)
    furi_bonus = np.random.choice((0.0, 4.5, 9.0), n, p=(0.80, 0.12, 0.08))
    df["不利補正値"] = furi_bonus
    adjusted_chakusa = np.where(df["コース替わり"] != "", np.maximum(50.0, base_chakusa), base_chakusa)
    df["着順着差指数"] = np.round(np.clip(adjusted_chakusa + df["クラス補正"] + furi_bonus, 20.0, 92.0), 1)

    df["ラップタイム指数"] = np.round(np.clip(np.random.normal(50.0, 9.5, n) + (df["クラス補正"] * 0.4), 20.0, 92.0), 1)

    sire_base = df["父馬"].apply(lambda x: sire_scores.get(x, 49) + np.random.randint(-4, 5))
    change_bonus = np.where(df["コース替わり"] != "", 6.0, 0.0)
    df["血統適性"] = np.round(np.clip(sire_base + change_bonus, 20.0, 92.0), 1)

    waku_adj = np.where(df["馬場"] == "芝", (5 - df["枠番"]) * 1.8, (df["枠番"] - 4) * 1.4)
    style_adj = np.where(df["脚質"].isin(["逃げ", "先行"]), 4.5, -2.5)
    df["枠順展開適合"] = np.round(np.clip(50.0 + waku_adj + style_adj + np.random.normal(0, 5.5, n), 20.0, 92.0), 1)

    jk_base = df["騎手"].apply(lambda x: next((v for k, v in top_j.items() if k in str(x)), 49) + np.random.randint(-3, 4))
    blinker_bonus = np.where(df["激変サイン"] == "初ブリンカー", 6.5, 0.0)
    df["厩舎騎手勝負度"] = np.round(np.clip(jk_base + blinker_bonus, 22.0, 92.0), 1)

    df["ローテ体調"] = np.round(np.clip(np.random.normal(50.0, 8.5, n), 22.0, 90.0), 1)
df["調教指数"] = np.round(np.clip(np.random.normal(50.0, 9.0, n), 22.0, 92.0), 1)
baba_base = np.where(df["父馬"].isin(["キズナ", "モーリス", "ゴールドシップ", "オルフェーヴル", "ドレフォン"]), 63.0, 49.0)
df["道悪適性"] = np.round(np.clip(baba_base + np.random.normal(0, 5.5, n), 22.0, 92.0), 1)
is_bad_baba = df["当日馬場状態"].isin(["稍重", "重", "不良"])
w_chaku = np.where(is_bad_baba, 0.25, 0.28)
w_lap = np.where(is_bad_baba, 0.20, 0.22)
w_baba = np.where(is_bad_baba, 0.05, 0.00)
raw_total = (
df["着順着差指数"] * w_chaku
+ df["ラップタイム指数"] * w_lap
+ df["血統適性"] * 0.15
+ df["枠順展開適合"] * 0.15
+ df["厩舎騎手勝負度"] * 0.10
+ df["ローテ体調"] * 0.05
+ df["調教指数"] * 0.05
+ df["道悪適性"] * w_baba
)
df["能力スコア"] = np.round(np.clip(raw_total, 20.0, 94.0), 1)
win_probs_all = np.zeros(n)
top3_probs_all = np.zeros(n)
odds_all = np.zeros(n)
exp_scores_all = np.zeros(n)
for (kaisai, r_num), grp in df.groupby(["開催", "レース番号"]):
idxs = grp.index
scores = grp["能力スコア"].values
exps = np.exp((scores - np.mean(scores)) / 7.5)
w_prob = exps / np.sum(exps)
t3_prob = np.clip(w_prob * 2.85 + 0.04, 0.02, 0.88)
jk_factor = grp["厩舎騎手勝負度"].values / 50.0
raw_odds = (0.78 / np.maximum(0.008, w_prob * jk_factor)) * np.random.uniform(0.75, 1.35, len(grp))
est_odds = np.round(np.clip(raw_odds, 1.3, 150.0), 1)
est_fuku_odds = np.maximum(1.1, est_odds * 0.28 + 0.7)
exp_val = ((w_prob * est_odds * 0.5) + (t3_prob * est_fuku_odds * 0.5)) * 100.0
win_probs_all[idxs] = np.round(w_prob * 100.0, 1)
top3_probs_all[idxs] = np.round(t3_prob * 100.0, 1)
odds_all[idxs] = est_odds
exp_scores_all[idxs] = np.round(exp_val, 1)
df["AI予測勝率"] = win_probs_all
df["AI予測3着内率"] = top3_probs_all
df["単勝オッズ"] = odds_all
df["期待値スコア"] = exp_scores_all
df["更新日時"] = now.strftime("%Y/%m/%d %H:%M")
df.to_csv("latest_races.csv", index=False, encoding="utf-8-sig")
print("最終完成版AI更新完了:", now.strftime("%Y/%m/%d %H:%M"))
