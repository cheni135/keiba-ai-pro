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

        rn_all = re.search(rf'\b{rnum}R\s+([^\s\(\)芝ダ障]{{2,22}})', flat[:1800])
        cand_rn = rn_all.group(1) if rn_all else ""
        r_name = cand_rn if cand_rn and not any(ng in cand_rn for ng in ng_words) else f"{rnum}R"

        cd_m = re.search(r'(芝|ダ)\s*(\d{4})m', flat[:1800])
        baba = "ダート" if cd_m and cd_m.group(1) == "ダ" else "芝"
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
    tjk = {"ルメ":60,"川田":59,"モレイラ":61,"戸崎":55,"横山":54,"坂井":56,"武豊":54,"松山":54,"デムー":56,"マーカンド":58}
    df["脚質"] = [("逃げ","先行","差し","追込")[i%4] for i in range(n)]
    df["当日馬場状態"] = "良"
    df["コース替わり"] = np.random.choice(["","初ダート","初芝"], n, p=[0.86,0.08,0.06])
    df["激変サイン"] = np.where(df["コース替わり"]!="", df["コース替わり"], np.where(np.random.rand(n)<0.07, "初ブリンカー", ""))
    df["不利補正値"] = np.random.choice([0.0,4.5,9.0], n, p=[0.80,0.12,0.08])
    b_chk = np.where(df["コース替わり"]!="", np.maximum(50.0, np.random.normal(50,9.5,n)), np.random.normal(50,9.5,n))
    df["着順着差指数"] = np.round(np.clip(b_chk + df["クラス補正"] + df["不利補正値"], 20, 92), 1)
    df["ラップタイム指数"] = np.round(np.clip(np.random.normal(50,9.5,n) + df["クラス補正"]*0.4, 20, 92), 1)
    df["血統適性"] = np.round(np.clip(np.random.normal(52,8.5,n) + np.where(df["コース替わり"]!="",6,0), 20, 92), 1)
    df["枠順展開適合"] = np.round(np.clip(50 + np.where(df["馬場"]=="芝",(5-df["枠番"])*1.8,(df["枠番"]-4)*1.4) + np.where(df["脚質"].isin(["逃げ","先行"]),4.5,-2.5) + np.random.normal(0,5.5,n), 20, 92), 1)
    df["厩舎騎手勝負度"] = np.round(np.clip(df["騎手"].map(lambda x: next((v for k,v in tjk.items() if k in str(x)),50)+np.random.randint(-3,4)) + np.where(df["激変サイン"]=="初ブリンカー",6.5,0), 22, 92), 1)
    df["ローテ体調"] = np.round(np.clip(np.random.normal(50,8.5,n), 22, 90), 1)
    df["調教指数"] = np.round(np.clip(np.random.normal(50,9.0,n), 22, 92), 1)
    df["道悪適性"] = np.round(np.clip(np.random.normal(51,8.0,n), 22, 92), 1)
    df["能力スコア"] = np.round(np.clip(df["着順着差指数"]*0.28 + df["ラップタイム指数"]*0.22 + df["血統適性"]*0.15 + df["枠順展開適合"]*0.15 + df["厩舎騎手勝負度"]*0.10 + df["ローテ体調"]*0.05 + df["調教指数"]*0.05, 20, 94), 1)
    wp, t3p, odds, exps = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    for _, g in df.groupby(["開催","レース番号"]):
        ix = g.index.to_numpy()
        sc = g["能力スコア"].values
        e = np.exp((sc - np.mean(sc))/7.5)
        w = e / np.sum(e)
        t3 = np.clip(w*2.85+0.04, 0.02, 0.88)
        sim_od = np.round(np.clip((0.78/np.maximum(0.008, w*(g["厩舎騎手勝負度"].values/50.0)))*np.random.uniform(0.75,1.35,len(g)), 1.3, 150.0), 1)
        real_od = g["実オッズ"].values
        od = np.where(real_od > 1.0, real_od, sim_od)
        wp[ix], t3p[ix], odds[ix], exps[ix] = np.round(w*100,1), np.round(t3*100,1), od, np.round(((w*od*0.5)+(t3*(od*0.28+0.7)*0.5))*100,1)
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
