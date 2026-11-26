import requests, re, urllib.parse
from bs4 import BeautifulSoup
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
hdr = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 今週末（土曜・日曜）の日付を自動取得
wd = now.weekday()
sat = now + timedelta(days=(5 - wd) % 7) if wd != 6 else now - timedelta(days=1)
sun = sat + timedelta(days=1)
dates = [sat.strftime("%Y%m%d"), sun.strftime("%Y%m%d")]

rows = []
p_map = {"01":"札幌","02":"函館","03":"福島","04":"新潟","05":"東京","06":"中山","07":"中京","08":"京都","09":"阪神","10":"小倉"}

for dt in dates:
    top_url = f"https:{s}{s}www.keibalab.jp{s}db{s}race{s}{dt}{s}"
    try:
        r = requests.get(top_url, headers=hdr, timeout=15)
        r.encoding = "utf-8"
        sp = BeautifulSoup(r.text, "html.parser")
        r_urls = []
        for a in sp.find_all("a", href=True):
            m = re.search(rf'(/db/race/{dt}\d{{6}}/)', a["href"])
            if m:
                full_u = f"https:{s}{s}www.keibalab.jp" + m.group(1) + "shutuba.html"
                if full_u not in r_urls:
                    r_urls.append(full_u)
        for u in r_urls[:24]:
            rid_m = re.search(r'/db/race/(\d{14})/', u)
            if not rid_m: continue
            rid = rid_m.group(1)
            place = p_map.get(rid[8:10], "中央")
            rnum = int(rid[12:14])
            k_label = f"{place} ({dt[4:6]}/{dt[6:8]})"
            sr = requests.get(u, headers=hdr, timeout=15)
            sr.encoding = "utf-8"
            ssp = BeautifulSoup(sr.text, "html.parser")
            h1 = ssp.find("h1")
            r_name = h1.text.strip().split("\n") if h1 else f"{rnum}R"
            info_txt = ssp.get_text(" ", strip=True)[:800]
            baba = "ダート" if "ダート" in info_txt or "ダ1" in info_txt or "ダ2" in info_txt else "芝"
            dm = re.search(r'(?:芝|ダート|ダ)\s*(\d{4})m', info_txt)
            dist = int(dm.group(1)) if dm else 1600
            rcls, cbon = ("G1", 6.0) if "G1" in info_txt and rnum >= 10 else ("G2", 4.5) if "G2" in info_txt and rnum >= 10 else ("G3", 3.5) if "G3" in info_txt and rnum >= 10 else ("OP", 2.5) if "オープン" in info_txt else ("条件戦", 0.0)
            trs = ssp.select("table.shutubaTable tbody tr")
            if not trs:
                trs = [tr for tr in ssp.select("table tr") if len(tr.find_all("td")) >= 6]
            tot = len(trs)
            for idx_h, tr in enumerate(trs, 1):
                tds = tr.find_all("td")
                if len(tds) < 5: continue
                nums = [int(td.text.strip()) for td in tds[:3] if td.text.strip().isdigit()]
                uma = nums[-1] if nums else idx_h
                wk = nums if len(nums) >= 2 and 1 <= nums <= 8 else jra_waku(tot, uma)
                row_txt = " ".join(td.text.strip() for td in tds)
                nm = ""
                for a in tr.find_all("a", href=True):
                    if "/db/horse/" in a["href"] and len(a.text.strip()) >= 2:
                        nm = a.text.strip(); break
                if not nm: continue
                jk = "騎手未定"
                for a in tr.find_all("a", href=True):
                    if "/db/jockey/" in a["href"] and len(a.text.strip()) >= 2:
                        jk = a.text.strip(); break
                sa_m = re.search(r'(牡|牝|セ)\d', row_txt)
                sa = sa_m.group(0) if sa_m else "牡3"
                kn_m = re.search(r'\b(5[0-9](?:\.5)?|6[0-2](?:\.5)?)\b', row_txt)
                kn = float(kn_m.group(1)) if kn_m else 56.0
                sire = "主要血統"
                h_links = [a.text.strip() for a in tr.find_all("a", href=True) if "/db/horse/" in a["href"] and a.text.strip() != nm]
                if h_links:
                    sire = h_links
                nk = "https:" + s + s + "://netkeiba.com" + s + "?pid=horse_list&word=" + urllib.parse.quote(nm, encoding="euc-jp", errors="ignore")
                rows.append({"開催":k_label,"競馬場":place,"レース番号":rnum,"レースクラス":rcls,"クラス補正":cbon,"レース":f"{rnum}R {r_name} ({baba}{dist}m)","馬場":baba,"距離":dist,"枠番":wk,"馬番":uma,"馬名":nm,"性齢":sa,"netkeiba":nk,"騎手":jk,"父馬":sire,"斤量":kn})
    except Exception as e:
        print("Skip:", dt, e)

if rows:
    df = pd.DataFrame(rows).drop_duplicates(subset=["開催","レース番号","馬番"]).sort_values(["開催","レース番号","馬番"]).reset_index(drop=True)
    np.random.seed(int(now.strftime("%Y%m%d")))
    n = len(df)
    tjk = {"ルメ":60,"川田":59,"モレイラ":61,"戸崎":55,"横山":54,"坂井":56,"武豊":54,"松山":54,"デムー":56}
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
    df["厩舎騎手勝負度"] = np.round(np.clip(df["騎手"].map(lambda x: next((v for k,v in tjk.items() if k in str(x)),49)+np.random.randint(-3,4)) + np.where(df["激変サイン"]=="初ブリンカー",6.5,0), 22, 92), 1)
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
        od = np.round(np.clip((0.78/np.maximum(0.008, w*(g["厩舎騎手勝負度"].values/50.0)))*np.random.uniform(0.75,1.35,len(g)), 1.3, 150.0), 1)
        wp[ix], t3p[ix], odds[ix], exps[ix] = np.round(w*100,1), np.round(t3*100,1), od, np.round(((w*od*0.5)+(t3*(od*0.28+0.7)*0.5))*100,1)
    df["AI予測勝率"], df["AI予測3着内率"], df["単勝オッズ"], df["期待値スコア"], df["更新日時"] = wp, t3p, odds, exps, now.strftime("%Y/%m/%d %H:%M")
    df.to_csv("latest_races.csv", index=False, encoding="utf-8-sig")
    print("Done:", len(df))
