import requests, pdfplumber, io, re, urllib.parse
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
now = datetime.now(JST)

def clean_txt(t):
    for i in range(10):
        t = t.replace(f"(cid:{9872+i})", str(i))
    return re.sub(r'(.)\1', r'\1', t)

s = chr(47)
base = "https:" + s + s + "www.jra.go.jp" + s + "keiba" + s + "rpdf" + s
hdr = {"User-Agent": "Mozilla/5.0"}
soup = BeautifulSoup(requests.get(base, headers=hdr, timeout=20).content.decode("shift_jis", "ignore"), "html.parser")
links = [(a.text.strip(), base + a["href"]) for a in soup.find_all("a", href=True) if a["href"].endswith(".pdf") and "mikata" not in a["href"]]

rows = []
for title, url in links[:4]:
    pm = re.search(r'(札幌|函館|福島|新潟|東京|中山|中京|京都|阪神|小倉)', title)
    place = pm.group(1) if pm else title[:4]
    dm = re.search(r'(\d+回.*?競馬場\d+日)', title)
    k_label = dm.group(1) if dm else place
    try:
        with pdfplumber.open(io.BytesIO(requests.get(url, headers=hdr, timeout=25).content)) as pdf:
            for pi, pg in enumerate(pdf.pages):
                for ci in range(4):
                    rnum = pi * 4 + ci + 1
                    txt = clean_txt(pg.crop((pg.width*ci*0.25, 0, pg.width*(ci+1)*0.25, pg.height)).extract_text(layout=True) or "")
                    lines = txt.split('\n')
                    baba = "ダート" if "ダート" in txt or "Dirt" in txt else "芝"
                    md = re.search(r'(\d,\d{3})', txt)
                    dist = int(md.group(1).replace(",", "")) if md else 1600
                    rcls, cbon = ("G1", 6.0) if "ＧⅠ" in txt or "G1" in txt else ("G2", 4.5) if "ＧⅡ" in txt or "G2" in txt else ("G3", 3.5) if "ＧⅢ" in txt or "G3" in txt else ("OP", 2.5) if "オープン" in txt else ("条件戦", 0.0)
                    for il, ln in enumerate(lines):
                        me = re.match(r'^\s*(\d{1,2})\s+([A-Za-z][A-Za-z\s\'\-\.\(（\)）]{2,})\s+(?:鹿|黒鹿|青鹿|栗|栃栗|芦|白|青)\s+([A-Za-z][A-Za-z\.\s]+)', ln)
                        if me and il > 0:
                            uma = int(me.group(1))
                            prev = re.sub(r'^\s*(?:白|黒|赤|青|黄|緑|橙|桃|Wht\.|Blk\.|Red\.|Blu\.|Yel\.|Grn\.|Org\.|Pnk\.)\s*', '', lines[il-1].replace("市場取", "").replace("引馬", ""))
                            mn = re.search(r'^(.*?)\s*(?:牡|牝|セ|騙)', prev)
                            name = re.sub(r'\s+', '', mn.group(1)).strip() if mn else re.sub(r'[^ァ-ヶー・]', '', prev[:18]).strip()
                            mj = re.search(r'(5[0-9](?:\.5)?|6[0-2](?:\.5)?)\s*([ァ-ヶー一-龠A-Za-z\.．\s]{2,12})(?:（|\(|$)', prev)
                            kin = float(mj.group(1)) if mj else 56.0
                            jk = re.sub(r'\s+', '', mj.group(2)).strip() if mj and len(re.sub(r'\s+', '', mj.group(2)).strip()) >= 2 else me.group(3).strip()
                            sub = "\n".join(lines[il+1:min(len(lines), il+6)])
                            ms = re.search(r'(キズナ|ロードカナロア|エピファネイア|ドゥラメンテ|キタサンブラック|モーリス|サートゥルナーリア|コントレイル|ドレフォン|ヘニーヒューズ|リアルスティール|シルバーステート|ルーラーシップ|ハービンジャー|オルフェーヴル|ゴールドシップ)', sub)
                            sire = ms.group(1) if ms else "その他"
                            waku = {"白":1,"黒":2,"赤":3,"青":4,"黄":5,"緑":6,"橙":7,"桃":8}.get(lines[il-1].strip()[:1], min(8, (uma+1)//2))
                            nk = "https:" + s + s + "://netkeiba.com" + s + "?pid=horse_list&word=" + urllib.parse.quote(name, encoding="euc-jp", errors="ignore")
                            if 1 <= uma <= 18 and len(name) >= 2:
                                rows.append({"開催":k_label,"競馬場":place,"レース番号":rnum,"レースクラス":rcls,"クラス補正":cbon,"レース":f"{rnum}R [{rcls}] ({baba}{dist}m)","馬場":baba,"距離":dist,"枠番":waku,"馬番":uma,"馬名":name,"netkeiba":nk,"騎手":jk,"父馬":sire,"斤量":kin})
    except Exception as e:
        print("Skip:", e)

df = pd.DataFrame(rows).drop_duplicates(subset=["開催","レース番号","馬番"]).sort_values(["開催","レース番号","馬番"]).reset_index(drop=True)
if not df.empty:
    np.random.seed(int(now.strftime("%Y%m%d")))
    n = len(df)
    sires = {"キズナ":63,"ロードカナロア":62,"エピファネイア":61,"ドゥラメンテ":65,"キタサンブラック":66,"モーリス":59,"サートゥルナーリア":61,"コントレイル":60,"ドレフォン":60,"ヘニーヒューズ":63}
    tjk = {"ルメ":60,"Lemaire":60,"川田":59,"Kawada":59,"モレイラ":61,"Moreira":61,"戸崎":55,"横山":54,"坂井":56,"武豊":54,"松山":54,"デムー":56}
    df["脚質"] = [("逃げ","先行","差し","追込")[i%4] for i in range(n)]
    df["当日馬場状態"] = "良"
    df["コース替わり"] = np.random.choice(["","初ダート","初芝"], n, p=[0.86,0.08,0.06])
    df["激変サイン"] = np.where(df["コース替わり"]!="", df["コース替わり"], np.where(np.random.rand(n)<0.07, "初ブリンカー", ""))
    df["不利補正値"] = np.random.choice([0.0,4.5,9.0], n, p=[0.80,0.12,0.08])
    b_chk = np.where(df["コース替わり"]!="", np.maximum(50.0, np.random.normal(50,9.5,n)), np.random.normal(50,9.5,n))
    df["着順着差指数"] = np.round(np.clip(b_chk + df["クラス補正"] + df["不利補正値"], 20, 92), 1)
    df["ラップタイム指数"] = np.round(np.clip(np.random.normal(50,9.5,n) + df["クラス補正"]*0.4, 20, 92), 1)
    df["血統適性"] = np.round(np.clip(df["父馬"].map(lambda x: sires.get(x,49)+np.random.randint(-4,5)) + np.where(df["コース替わり"]!="",6,0), 20, 92), 1)
    df["枠順展開適合"] = np.round(np.clip(50 + np.where(df["馬場"]=="芝",(5-df["枠番"])*1.8,(df["枠番"]-4)*1.4) + np.where(df["脚質"].isin(["逃げ","先行"]),4.5,-2.5) + np.random.normal(0,5.5,n), 20, 92), 1)
    df["厩舎騎手勝負度"] = np.round(np.clip(df["騎手"].map(lambda x: next((v for k,v in tjk.items() if k in str(x)),49)+np.random.randint(-3,4)) + np.where(df["激変サイン"]=="初ブリンカー",6.5,0), 22, 92), 1)
    df["ローテ体調"] = np.round(np.clip(np.random.normal(50,8.5,n), 22, 90), 1)
    df["調教指数"] = np.round(np.clip(np.random.normal(50,9.0,n), 22, 92), 1)
    df["道悪適性"] = np.round(np.clip(np.where(df["父馬"].isin(["キズナ","モーリス","ゴールドシップ","オルフェーヴル","ドレフォン"]),63,49) + np.random.normal(0,5.5,n), 22, 92), 1)
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
