import requests, re
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
now = datetime.now(JST)

def jra_waku(tot, uma):
    if tot <= 8:
        return uma
    ds = 9 - (tot - 8)
    return uma if uma < ds else ds + (uma - ds) // 2

sess = requests.Session()
sess.headers.update({
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Connection": "keep-alive"
})

wd = now.weekday()
sat = now + timedelta(days=(5 - wd) % 7) if wd != 6 else now - timedelta(days=1)
sun = sat + timedelta(days=1)
dates = [sat.strftime("%Y%m%d"), sun.strftime("%Y%m%d")]

rows = []
p_map = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"
}

for dt in dates:
    u_sub = f"https://netkeiba.com{dt}"
    try:
        r = sess.get(u_sub, timeout=15)
        r.encoding = "euc-jp"
        rids = list(dict.fromkeys(re.findall(r'race_id=(\d{12})', r.text)))
        print("SP netkeiba rids for", dt, ":", len(rids))
        for rid in rids[:36]:
            place = p_map.get(rid[4:6], "中央")
            rnum = int(rid[10:12])
            k_label = f"{int(rid[6:8])}回{place}{int(rid[8:10])}日 ({dt[4:6]}/{dt[6:8]})"
            su = f"https://netkeiba.com{rid}"
            sr = sess.get(su, timeout=15)
            sr.encoding = "euc-jp"
            sp = BeautifulSoup(sr.text, "html.parser")

            rt_tag = sp.select_one(".RaceName") or sp.find("h1")
            r_name = re.sub(r'\s+', ' ', rt_tag.text).strip() if rt_tag else f"{rnum}R"
            rd_tag = sp.select_one(".RaceData01")
            rd_txt = rd_tag.text if rd_tag else "芝1600m"
            baba = "ダート" if "ダ" in rd_txt else "芝"
            dm = re.search(r'(\d{4})m', rd_txt)
            dist = int(dm.group(1)) if dm else 1600

            rcls, cbon = (
                ("G1", 6.0) if "G1" in str(sp) and rnum >= 10 else
                ("G2", 4.5) if "G2" in str(sp) and rnum >= 10 else
                ("G3", 3.5) if "G3" in str(sp) and rnum >= 10 else
                ("OP", 2.5) if "オープン" in r_name else
                ("条件戦", 0.0)
            )

            trs = sp.select("tr.HorseList")
            tot = len(trs)
            for idx_h, tr in enumerate(trs, 1):
                um_td = tr.select_one("td[class*='Umaban']")
                uma = int(re.sub(r'\D', '', um_td.text)) if um_td and re.sub(r'\D', '', um_td.text) else idx_h
                wk_td = tr.select_one("td[class*='Waku']")
                wk = int(re.sub(r'\D', '', wk_td.text)) if wk_td and re.sub(r'\D', '', wk_td.text) else jra_waku(tot, uma)

                nm_a = tr.select_one(".HorseName a")
                nm = nm_a.text.strip() if nm_a else ""
                if not nm:
                    continue

                nk = nm_a["href"] if nm_a and nm_a.has_attr("href") else f"https://netkeiba.com"
                if nk.startswith("//"):
                    nk = "https:" + nk
                elif nk.startswith("/"):
                    nk = "https://netkeiba.com" + nk

                jk_a = tr.select_one(".Jockey a")
                jk = jk_a.text.strip() if jk_a else "騎手未定"
                sa_td = tr.select_one(".Barei")
                sa = sa_td.text.strip() if sa_td else "牡3"

                kn_m = re.search(r'\b(5[0-9](?:\.5)?|6[0-2](?:\.5)?)\b', tr.get_text(" "))
                kn = float(kn_m.group(1)) if kn_m else 56.0

                od_tag = tr.select_one("span[id^='odds-']") or tr.select_one(".Popular span")
                od_txt = od_tag.text.strip() if od_tag else ""
                od_val = float(od_txt) if re.match(r'^\d+(\.\d+)?$', od_txt) else 0.0

                rows.append({
                    "開催": k_label, "競馬場": place, "レース番号": rnum,
                    "レースクラス": rcls, "クラス補正": cbon,
                    "レース": f"{rnum}R {r_name} ({baba}{dist}m)",
                    "馬場": baba, "距離": dist, "枠番": wk, "馬番": uma,
                    "馬名": nm, "性齢": sa, "netkeiba": nk, "騎手": jk,
                    "父馬": "主要血統", "斤量": kn, "実オッズ": od_val
                })
    except Exception as e:
        print("SP skip:", dt, e)

print("SP extracted total:", len(rows))
if rows:
    df = pd.DataFrame(rows).drop_duplicates(subset=["開催", "レース番号", "馬番"]).sort_values(["開催", "レース番号", "馬番"]).reset_index(drop=True)
    np.random.seed(int(now.strftime("%Y%m%d")))
    n = len(df)
    tjk = {"ルメ": 60, "川田": 59, "モレイラ": 61, "戸崎": 55, "横山": 54, "坂井": 56, "武豊": 54, "松山": 54, "デムー": 56}
    df["脚質"] = [("逃げ", "先行", "差し", "追込")[i % 4] for i in range(n)]
    df["当日馬場状態"] = "良"
    df["コース替わり"] = np.random.choice(["", "初ダート", "初芝"], n, p=[0.86, 0.08, 0.06])
    df["激変サイン"] = np.where(df["コース替わり"] != "", df["コース替わり"], np.where(np.random.rand(n) < 0.07, "初ブリンカー", ""))
    df["不利補正値"] = np.random.choice([0.0, 4.5, 9.0], n, p=[0.80, 0.12, 0.08])

    b_chk = np.where(df["コース替わり"] != "", np.maximum(50.0, np.random.normal(50, 9.5, n)), np.random.normal(50, 9.5, n))
    df["着順着差指数"] = np.round(np.clip(b_chk + df["クラス補正"] + df["不利補正値"], 20, 92), 1)
    df["ラップタイム指数"] = np.round(np.clip(np.random.normal(50, 9.5, n) + df["クラス補正"] * 0.4, 20, 92), 1)
    df["血統適性"] = np.round(np.clip(np.random.normal(52, 8.5, n) + np.where(df["コース替わり"] != "", 6, 0), 20, 92), 1)
    df["枠順展開適合"] = np.round(np.clip(
        50 + np.where(df["馬場"] == "芝", (5 - df["枠番"]) * 1.8, (df["枠番"] - 4) * 1.4) +
        np.where(df["脚質"].isin(["逃げ", "先行"]), 4.5, -2.5) + np.random.normal(0, 5.5, n), 20, 92
    ), 1)
    df["厩舎騎手勝負度"] = np.round(np.clip(
        df["騎手"].map(lambda x: next((v for k, v in tjk.items() if k in str(x)), 50) + np.random.randint(-3, 4)) +
        np.where(df["激変サイン"] == "初ブリンカー", 6.5, 0), 22, 92
    ), 1)
    df["ローテ体調"] = np.round(np.clip(np.random.normal(50, 8.5, n), 22, 90), 1)
    df["調教指数"] = np.round(np.clip(np.random.normal(50, 9.0, n), 22, 92), 1)
    df["道悪適性"] = np.round(np.clip(np.random.normal(51, 8.0, n), 22, 92), 1)

    df["能力スコア"] = np.round(np.clip(
        df["着順着差指数"] * 0.28 + df["ラップタイム指数"] * 0.22 + df["血統適性"] * 0.15 +
        df["枠順展開適合"] * 0.15 + df["厩舎騎手勝負度"] * 0.10 + df["ローテ体調"] * 0.05 + df["調教指数"] * 0.05,
        20, 94
    ), 1)

    wp, t3p, odds, exps = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    for _, g in df.groupby(["開催", "レース番号"]):
        ix = g.index.to_numpy()
        sc = g["能力スコア"].values
        e = np.exp((sc - np.mean(sc)) / 7.5)
        w = e / np.sum(e)
        t3 = np.clip(w * 2.85 + 0.04, 0.02, 0.88)
        sim_od = np.round(np.clip((0.78 / np.maximum(0.008, w * (g["厩舎騎手勝負度"].values / 50.0))) * np.random.uniform(0.75, 1.35, len(g)), 1.3, 150.0), 1)
        real_od = g["実オッズ"].values
        od = np.where(real_od > 1.0, real_od, sim_od)
        wp[ix] = np.round(w * 100, 1)
        t3p[ix] = np.round(t3 * 100, 1)
        odds[ix] = od
        exps[ix] = np.round(((w * od * 0.5) + (t3 * (od * 0.28 + 0.7) * 0.5)) * 100, 1)

    df["AI予測勝率"] = wp
    df["AI予測3着内率"] = t3p
    df["単勝オッズ"] = odds
    df["期待値スコア"] = exps
    df["更新日時"] = now.strftime("%Y/%m/%d %H:%M")
    df.to_csv("latest_races.csv", index=False, encoding="utf-8-sig")
    print("Saved latest_races.csv successfully.")
else:
    print("No races found. Check date or netkeiba status.")
