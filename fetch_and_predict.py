import pandas as pd
import numpy as np
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta, timezone

# 日本時間の現在日時を取得し、直近の土曜・日曜を計算
JST = timezone(timedelta(hours=9))
now = datetime.now(JST)

target_dates = list()
for i in range(-1, 6):
    d = now + timedelta(days=i)
    if d.weekday() == 5 or d.weekday() == 6:
        target_dates.append(d.strftime("%Y%m%d"))

if not target_dates:
    target_dates.append(now.strftime("%Y%m%d"))

print("取得対象候補日:", target_dates)

s = chr(47)
base_domain = "https:" + s + s + "://netkeiba.com"

all_races = list()

with sync_playwright() as p:
    # 本物のChromiumブラウザをバックグラウンドで起動
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        locale="ja-JP"
    )
    page = context.new_page()

    for kaisai_date in target_dates[:2]:
        list_url = base_domain + s + "top" + s + "race_list.html?kaisai_date=" + kaisai_date
        print("アクセス中:", list_url)
        try:
            page.goto(list_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(3000) # JavaScriptの描画完了を3秒待機
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            race_links = list()
            for a in soup.select("a[href*='race_id=']"):
                href = a.get("href", "")
                m = re.search(r"race_id=(202\d{9})", href)
                if m:
                    rid = m.group(1)
                    if rid not in race_links:
                        race_links.append(rid)

            print(f"日付 {kaisai_date}: 見つかったレースID数 = {len(race_links)}")

            # まずは最初の3レース分で出馬表データ（枠・馬番・馬名・騎手・斤量・オッズ・人気）をテスト取得
            for rid in race_links[:3]:
                shutuba_url = base_domain + s + "race" + s + "shutuba.html?race_id=" + rid
                page.goto(shutuba_url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2000)
                s_soup = BeautifulSoup(page.content(), "html.parser")

                title_tag = s_soup.select_one(".RaceName")
                race_title = title_tag.text.strip() if title_tag else f"レース {rid[-2:]}R"
                
                data_tag = s_soup.select_one(".RaceData01")
                race_info = data_tag.text.strip() if data_tag else ""

                for tr in s_soup.select("tr.HorseList"):
                    tds = tr.select("td")
                    if len(tds) < 10:
                        continue
                    waku = tds.pop(0).text.strip()
                    umaban = tds.pop(0).text.strip()
                    tds.pop(0)
                    horse_name = tds.pop(0).text.strip()
                    sex_age = tds.pop(0).text.strip()
                    kinryo = tds.pop(0).text.strip()
                    jockey = tds.pop(0).text.strip()
                    tds.pop(0)
                    tds.pop(0)
                    odds_txt = tds.pop(0).text.strip()
                    pop_txt = tds.pop(0).text.strip()

                    try:
                        odds = float(odds_txt)
                    except:
                        odds = 99.9
                    try:
                        pop = int(pop_txt)
                    except:
                        pop = 99

                    if umaban.isdigit():
                        all_races.append({
                            "開催日": kaisai_date,
                            "race_id": rid,
                            "レース番号": int(rid[-2:]),
                            "レース名": race_title,
                            "条件": race_info,
                            "枠番": int(waku) if waku.isdigit() else 1,
                            "馬番": int(umaban),
                            "馬名": horse_name,
                            "性齢": sex_age,
                            "斤量": float(kinryo) if kinryo.replace(".", "").isdigit() else 56.0,
                            "騎手": jockey,
                            "単勝オッズ": odds,
                            "人気": pop
                        })
        except Exception as e:
            print("取得スキップ:", e)

    browser.close()

df = pd.DataFrame(all_races)
print(f"合計取得頭数: {len(df)} 頭")
df.to_csv("latest_races.csv", index=False, encoding="utf-8-sig")
