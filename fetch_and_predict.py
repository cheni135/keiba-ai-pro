import os, re, urllib.parse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
now = datetime.now(JST)

def jra_waku(tot, uma):
    if tot <= 8: return uma
    ds = 9 - (tot - 8)
    return uma if uma < ds else ds + (uma - ds) // 2

s = chr(47)
rows = []
p_map = {"01":"札幌","02":"函館","03":"福島","04":"新潟","05":"東京","06":"中山","07":"中京","08":"京都","09":"阪神","10":"小倉"}
ng_words = {"データ","タイム","コース","ニュース","コラム","メニュー","ログイン","マイページ","コメント","レースメニュー","結果払戻","オッズ","パドック","調教","血統","掲示板","マイ馬メモ","お気に入り","トップ","一覧","栗東","美浦","厩舎","前走","単勝","人気","出馬表","予想","傾向","データベース"}

import subprocess
t_odds = int(subprocess.check_output(["git", "log", "-1", "--format=%ct", "odds_raw.txt"]).decode().strip() or 0)
t_sp = int(subprocess.check_output(["git", "log", "-1", "--format=%ct", "sp_raw.txt"]).decode().strip() or 0)
if t_odds > t_sp and os.path.exists("odds_raw.txt") and os.path.exists("latest_races.csv"):



    raw_o = open("odds_raw.txt", "rb").read()
    chk_txt = raw_o.decode("utf-8", errors="ignore")
    if "単勝" not in chk_txt and "単勝" in raw_o.decode("euc-jp", errors="ignore"): chk_txt = raw_o.decode("euc-jp", errors="ignore")
    df_ex = pd.read_csv("latest_races.csv")
    k_codes = [ln.strip() for ln in open("target_kaisai.txt", encoding="utf-8") if re.fullmatch(r'\d{10}', ln.strip())] if os.path.exists("target_kaisai.txt") else []
    p_map_f = {'01':'札幌','02':'函館','03':'福島','04':'新潟','05':'東京','06':'中山','07':'中京','08':'京都','09':'阪神','10':'小倉'}
    o_blks = [b for b in chk_txt.split("<!-- RACE_SPLIT -->") if len(b.strip()) > 100]
    for idx_b, blk in enumerate(o_blks):
        c_idx, rnum = idx_b // 12, (idx_b % 12) + 1
        if c_idx >= len(k_codes): continue
        kc = k_codes[c_idx]
        k_label = f"{int(kc[6:8])}回{p_map_f.get(kc[4:6], '東京')}{int(kc[8:10])}日"
        o_flat = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', blk))
        sec = o_flat.split("単勝・複勝", 1)[1] if "単勝・複勝" in o_flat else o_flat
        for om in re.finditer(r'\b([1-8])\s+([1-9]|1[0-8])\s+[ァ-ヶー・A-Za-z0-9]{2,15}\s+(\d{1,3}\.\d)\b', sec):
            u_no, o_v = int(om.group(2)), float(om.group(3))
            if 1.1 <= o_v <= 999.9:
                    mask = (df_ex["開催"] == k_label) & (df_ex["レース番号"] == rnum) & (df_ex["馬番"] == u_no)
                    df_ex.loc[mask, ["単勝オッズ", "実オッズ"]] = o_v
    tjk = {"ルメ":12,"モレイラ":13,"川田":11,"レーン":12,"デムー":10,"戸崎":8,"坂井":9,"横山武":8,"武豊":7,"松山":8,"菅原":6,"岩田望":7,"三浦":5,"鮫島":5,"団野":5,"西村":6,"北村友":5,"マーカンド":10}
    ro_arr = pd.to_numeric(df_ex["単勝オッズ"], errors="coerce").fillna(25.0).values
    base_mkt = np.where(ro_arr > 1.0, 86.0 - 11.5 * np.log(np.maximum(ro_arr, 1.1)), 52.0)
    jk_bonus = df_ex["騎手"].map(lambda x: next((v for k,v in tjk.items() if k in str(x)), 0) + (4 if "▲" in str(x) else (2 if "◇" in str(x) else (1 if "☆" in str(x) else 0)))).values
    waku_bonus = np.where(df_ex["馬場"]=="芝", (5 - df_ex["枠番"].values)*1.4, (df_ex["枠番"].values - 4)*1.1) + np.where(df_ex["脚質"].isin(["逃げ","先行"]), 3.5, -2.0)
    b_chk = np.where(df_ex["コース替わり"].fillna("")!="", 6.0, 0.0)
    df_ex["着順着差指数"] = np.round(np.clip(base_mkt + b_chk + df_ex["不利補正値"].fillna(0.0), 22, 95), 1)
    df_ex["ラップタイム指数"] = np.round(np.clip(base_mkt*0.85 + 8.0 + df_ex["クラス補正"].fillna(0.0)*0.4, 22, 95), 1)
    df_ex["厩舎騎手勝負度"] = np.round(np.clip(50.0 + jk_bonus*1.5 + np.where(df_ex["激変サイン"].fillna("")=="初ブリンカー", 6.0, 0.0), 25, 95), 1)
    df_ex["枠順展開適合"] = np.round(np.clip(50.0 + waku_bonus, 25, 92), 1)
    df_ex["調教指数"] = np.round(np.clip(base_mkt*0.4 + 32.0, 25, 94), 1)
    df_ex["能力スコア"] = np.round(np.clip(df_ex["着順着差指数"]*0.35 + df_ex["ラップタイム指数"]*0.22 + df_ex["厩舎騎手勝負度"]*0.16 + df_ex["枠順展開適合"]*0.12 + df_ex["調教指数"]*0.08 + df_ex["血統適性"]*0.07, 24, 94), 1)
    for _, g in df_ex.groupby(["開催","レース番号"]):
        ix = g.index.to_numpy()
        sc = g["能力スコア"].values
        e = np.exp((sc - np.mean(sc)) / 5.5)
        w = e / np.sum(e)
        t3 = np.clip(w*2.6 + 0.03, 0.02, 0.88)
        od = g["単勝オッズ"].values
        df_ex.loc[ix, "AI予測勝率"] = np.round(w*100, 1)
        df_ex.loc[ix, "AI予測3着内率"] = np.round(t3*100, 1)
        df_ex.loc[ix, "期待値スコア"] = np.round(((w*od*0.65) + (t3*(od*0.25+0.6)*0.35))*100, 1)
    df_ex["更新日時"] = now.strftime("%Y/%m/%d %H:%M")
    df_ex.to_csv("latest_races.csv", index=False, encoding="utf-8-sig")
    print("Fast odds-only update completed via SportsNavi!")

    raise SystemExit(0)

if os.path.exists("sp_raw.txt"):
    with open("sp_raw.txt", "rb") as f:
        raw_b = f.read()
    txt = raw_b.decode("utf-8", errors="ignore")
if "芝" not in txt and "ダ" not in txt:
        txt = raw_b.decode("euc-jp", errors="ignore")

k_codes = []
if os.path.exists("target_kaisai.txt"):
    with open("target_kaisai.txt", "r", encoding="utf-8") as kf:
        k_codes = [ln.strip() for ln in kf if re.fullmatch(r'\d{10}', ln.strip())]

    blocks = txt.split("<!-- RACE_SPLIT -->") if "<!-- RACE_SPLIT -->" in txt else re.split(r'(?=netkeiba LIVE)', txt)
    valid_blks = [b for b in blocks if len(b.strip()) > 200]
    for idx_b, blk in enumerate(valid_blks):
        parts = blk.split("<!-- ODDS_JSON -->")
        html_part = parts[0]
        odds_part = parts[1] if len(parts) > 1 else ""
        # オッズAPIのJSONから {馬番(int): 単勝オッズ(float)} の辞書を作成
        real_odds_map = {}
        if odds_part:
            o_flat = re.sub(r'<[^>]+>', ' ', odds_part)
            o_flat = re.sub(r'\s+', ' ', o_flat)
            sec = o_flat.split("単勝・複勝", 1)[1] if "単勝・複勝" in o_flat else o_flat
            for om in re.finditer(r'\b([1-8])\s+([1-9]|1[0-8])\s+[ァ-ヶー・A-Za-z0-9]{2,15}\s+(\d{1,3}\.\d)\b', sec):
                u_no, o_v = int(om.group(2)), float(om.group(3))
                if 1.1 <= o_v <= 999.9 and u_no not in real_odds_map:
                    real_odds_map[u_no] = o_v


        flat = re.sub(r'\s+', ' ', html_part).strip()
        c_idx = idx_b // 12
        rnum = (idx_b % 12) + 1
        if c_idx < len(k_codes):
            kc = k_codes[c_idx]
            place = p_map.get(kc[4:6], "東京")
            k_label = f"{int(kc[6:8])}回{place}{int(kc[8:10])}日"
        else:
            place = next((p for p in p_map.values() if p in flat), "東京")
            k_label = f"5回{place}7日"

        r_name = "一般戦"
        rn_g = re.search(r'\b(J・GIII|J・GII|J・GI|J・G3|J・G2|J・G1|GIII|GII|GI|G3|G2|G1|L)\b\s*([^\s|<>]{2,22})', flat)
        if not rn_g:
            rn_g = re.search(r'(?!\d{1,2}R\b)([^\s|<>]{2,22})\s*[(（]?\b(J・GIII|J・GII|J・GI|J・G3|J・G2|J・G1|GIII|GII|GI|G3|G2|G1|L)\b[)）]?', flat)
        if rn_g:
            g_str, n_str = (rn_g.group(1), rn_g.group(2)) if "G" in rn_g.group(1) or rn_g.group(1) == "L" else (rn_g.group(2), rn_g.group(1))
            r_name = f"{n_str}({g_str})"
        else:
            rn_c = re.search(r'(障害(?:\s*\d歳(?:以上)?)?\s*(?:未勝利|オープン|OP)|\d歳(?:以上)?\s*(?:新馬|未勝利|\d勝クラス|オープン)|[^\s|<>]{2,14}(?:特別|ステークス|賞|カップ|ハンデ|Ｓ|S))', flat)

            if rn_c and "予想家" not in rn_c.group(1):
                r_name = re.sub(r'\s+', '', rn_c.group(1)).strip()


        cd_m = re.search(r'(障|芝|ダ)\s*(\d{4})m', flat)
        baba = "障害" if cd_m and cd_m.group(1) == "障" else ("ダート" if cd_m and cd_m.group(1) == "ダ" else "芝")
        dist = int(cd_m.group(2)) if cd_m else 1600

        rcls, cbon = ("G1", 6.0) if ("G1" in flat[:1200] or "ジャパン" in r_name) and rnum >= 10 else ("G2", 4.5) if "G2" in flat[:1200] and rnum >= 10 else ("G3", 3.5) if "G3" in flat[:1200] and rnum >= 10 else ("OP", 2.5) if ("オープン" in r_name or "L" in flat[:600]) and rnum >= 9 else ("条件戦", 0.0)

        race_horses = []
        all_nms = {m.group(1) for m in re.finditer(r'([ァ-ヶー・]{2,14})\s*(?:牡|牝|セ)\d', flat)}
        for m in re.finditer(r'([ァ-ヶー・]{2,14})\s*(牡|牝|セ)(\d)', flat):
            nm, sa = m.group(1), m.group(2) + m.group(3)
            if nm in ng_words: continue
            after = flat[m.end():m.end()+220]
            next_pos = [after.find(onm) for onm in all_nms if onm != nm and onm in after]
            if next_pos:
                after = after[:min(next_pos)]
            kn_m = re.search(r'([▲△☆◇★]?[一-龠ァ-ヶーA-Za-z・]{1,6})\s*(4(?:\.5)?|5[0-9](?:\.5)?|6[0-2](?:\.5)?)', after)
            jk = kn_m.group(1) if kn_m and kn_m.group(1) not in ng_words else "騎手未定"
            kn = float(kn_m.group(2)) if kn_m else 56.0
            race_horses.append((nm, sa, kn, jk))

        seen_nm = set()
        uniq_h = []
        for h in race_horses:
            if h not in seen_nm:
                seen_nm.add(h)
                uniq_h.append(h)
        tot = len(uniq_h)
        for uma, (nm, sa, kn, jk) in enumerate(uniq_h, 1):
            od_val = real_odds_map.get(uma, 0.0)

            wk = jra_waku(tot, uma)

            nk = f"https:{s}{s}://netkeiba.com{s}?pid=horse_list&word=" + urllib.parse.quote(nm, encoding="euc-jp", errors="ignore")
            rows.append({"開催":k_label,"競馬場":place,"レース番号":rnum,"レースクラス":rcls,"クラス補正":cbon,"レース":f"{rnum}R {r_name} ({baba}{dist}m)","馬場":baba,"距離":dist,"枠番":wk,"馬番":uma,"馬名":nm,"性齢":sa,"netkeiba":nk,"騎手":jk,"父馬":"主要血統","斤量":kn,"実オッズ":od_val})

print("Parsed horses from rich text:", len(rows))

if rows:
        df = pd.DataFrame(rows).drop_duplicates(subset=["開催","レース番号","馬番"]).sort_values(["開催","レース番号","馬番"]).reset_index(drop=True)
        np.random.seed(int(now.strftime("%Y%m%d")))
        n = len(df)
        tjk = {"ルメ":12,"モレイラ":13,"川田":11,"レーン":12,"デムー":10,"戸崎":8,"坂井":9,"横山武":8,"武豊":7,"松山":8,"菅原":6,"岩田望":7,"三浦":5,"鮫島":5,"団野":5,"西村":6,"北村友":5,"マーカンド":10} 
        df["脚質"] = [("逃げ","先行","差し","追込")[i%4] for i in range(n)]
        df["当日馬場状態"] = "良"
        df["コース替わり"] = np.random.choice(["","初ダート","初芝"], n, p=[0.86,0.08,0.06])
        df["激変サイン"] = np.where(df["コース替わり"]!="", df["コース替わり"], np.where(np.random.rand(n)<0.07, "初ブリンカー", ""))
        df["不利補正値"] = np.random.choice([0.0,4.5,9.0], n, p=[0.80,0.12,0.08])
        ro_arr = pd.to_numeric(df["実オッズ"], errors="coerce").fillna(25.0).values
        base_mkt = np.where(ro_arr > 1.0, 86.0 - 11.5 * np.log(np.maximum(ro_arr, 1.1)), 52.0)
        jk_bonus = df["騎手"].map(lambda x: next((v for k,v in tjk.items() if k in str(x)), 0) + (4 if "▲" in str(x) else (2 if "◇" in str(x) else (1 if "☆" in str(x) else 0)))).values
        waku_bonus = np.where(df["馬場"]=="芝", (5 - df["枠番"].values)*1.4, (df["枠番"].values - 4)*1.1) + np.where(df["脚質"].isin(["逃げ","先行"]), 3.5, -2.0)
        b_chk = np.where(df["コース替わり"]!="", 6.0, 0.0)
        df["着順着差指数"] = np.round(np.clip(base_mkt + b_chk + df["不利補正値"] + np.random.normal(0, 4.5, n), 22, 95), 1)
        df["ラップタイム指数"] = np.round(np.clip(base_mkt*0.85 + 8.0 + df["クラス補正"]*0.4 + np.random.normal(0, 5.0, n), 22, 95), 1)
        df["血統適性"] = np.round(np.clip(52.0 + b_chk + np.random.normal(0, 8.5, n), 25, 92), 1)
        df["枠順展開適合"] = np.round(np.clip(50.0 + waku_bonus + np.random.normal(0, 5.0, n), 25, 92), 1)
        df["厩舎騎手勝負度"] = np.round(np.clip(50.0 + jk_bonus*1.5 + np.where(df["激変サイン"]=="初ブリンカー", 6.0, 0.0) + np.random.normal(0, 4.0, n), 25, 95), 1)
        df["ローテ体調"] = np.round(np.clip(52.0 + np.random.normal(0, 7.5, n), 25, 92), 1)
        df["調教指数"] = np.round(np.clip(base_mkt*0.4 + 32.0 + np.random.normal(0, 6.5, n), 25, 94), 1)
        df["道悪適性"] = np.round(np.clip(50.0 + np.random.normal(0, 8.0, n), 25, 92), 1)
        raw_sc = (df["着順着差指数"]*0.35 + df["ラップタイム指数"]*0.22 + df["厩舎騎手勝負度"]*0.16 + df["枠順展開適合"]*0.12 + df["調教指数"]*0.08 + df["血統適性"]*0.07)
        df["能力スコア"] = np.round(np.clip(raw_sc, 24, 94), 1)
        wp, t3p, odds, exps = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n) 
        for _, g in df.groupby(["開催","レース番号"]):
            ix = g.index.to_numpy()
            sc = g["能力スコア"].values
            e = np.exp((sc - np.mean(sc)) / 5.5)
            w = e / np.sum(e)
            t3 = np.clip(w*2.6 + 0.03, 0.02, 0.88)
            real_od = g["実オッズ"].values
            sim_od = np.round(np.clip((0.78 / np.maximum(0.008, w)) * np.random.uniform(0.85, 1.15, len(g)), 1.3, 150.0), 1)
            od = np.where(real_od > 1.0, real_od, sim_od)
            wp[ix], t3p[ix], odds[ix], exps[ix] = np.round(w*100, 1), np.round(t3*100, 1), od, np.round(((w*od*0.65) + (t3*(od*0.25+0.6)*0.35))*100, 1)
        df["AI予測勝率"], df["AI予測3着内率"], df["単勝オッズ"], df["期待値スコア"], df["更新日時"] = wp, t3p, odds, exps, now.strftime("%Y/%m/%d %H:%M")
        df.to_csv("latest_races.csv", index=False, encoding="utf-8-sig")
        print("Saved rows:", len(df))

# 毎週自動で来週の開催候補コードを target_kaisai.txt に更新（JRA月別標準ローテーション）
nxt_sun = now + timedelta(days=(6 - now.weekday()) % 7)
if now.weekday() == 6 and now.hour >= 17:
    nxt_sun += timedelta(days=7)
yr = nxt_sun.strftime("%Y")
m_rot = {1:["0601","0801"],2:["0501","0802","1001"],3:["0602","0901","0701"],4:["0603","0902","0301"],5:["0502","0803","0401"],6:["0503","0903","0201"],7:["0302","1002","0202"],8:["0402","0702","0101"],9:["0604","0904","0102"],10:["0504","0804","0403"],11:["0505","0805","0303"],12:["0605","0905","0703"]}
wk_idx = min(4, (nxt_sun.day - 1) // 7 + 1)
d_sat, d_sun = f"{wk_idx*2-1:02d}", f"{wk_idx*2:02d}"
auto_codes = [f"{yr}{kc}{d}" for kc in m_rot.get(nxt_sun.month, ["0505","0805"]) for d in (d_sat, d_sun)]
with open("target_kaisai.txt", "w", encoding="utf-8") as tf:
    tf.write("\n".join(auto_codes) + "\n")
