"""식약처 법령·입법예고 게시판에서 키워드가 들어간 글만 모아 data.json 으로 저장"""
import re, json, sys, time, hashlib, datetime as dt
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# ===== 여기만 바꾸면 됩니다 =====
KEYWORDS = ["건강기능식품", "식품"]   # 제목에 하나라도 들어가면 수집
EXCLUDE  = ["직제"]                  # 제목에 들어가면 제외 (노이즈 제거용)
PAGES    = 5                         # 게시판별로 최신 몇 페이지까지 볼지 (1페이지=10건)
BOARDS = {                           # 게시판 코드: 표시 이름
    "m_203": "법·시행령·시행규칙",
    "m_209": "입법/행정예고",
    "m_207": "제개정고시",
    "m_211": "고시훈령예규",
}
# =================================
URL = "https://www.mfds.go.kr/brd/{b}/list.do"
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
OUT = Path("data.json")

def parse(html, base, board):
    rows = []
    for el in BeautifulSoup(html, "html.parser").select("tr, li"):
        text = el.get_text(" ", strip=True)
        d = DATE.findall(text)
        a = el.find("a", href=True)
        if len(d) != 1 or not a:
            continue
        title = a.get_text(" ", strip=True)
        if len(title) < 6:
            continue
        m = re.search(r"담당부서[\s|]*(.*?)\s*" + d[0], text)
        rows.append({"board": BOARDS[board], "title": title, "date": d[0],
                     "dept": m.group(1).strip(" |") if m else "",
                     "url": urljoin(base, a["href"])})
    return rows

def fetch(url, params):
    for i in range(3):
        try:
            r = requests.get(url, params=params, headers=HEAD, timeout=30)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print("  재시도", i + 1, e)
            time.sleep(3)
    return None

def main():
    today = dt.date.today().isoformat()
    old = {}
    if OUT.exists():
        old = {x["id"]: x for x in json.loads(OUT.read_text(encoding="utf-8")).get("items", [])}
    found, ok = {}, 0
    for b in BOARDS:
        for p in range(1, PAGES + 1):
            html = fetch(URL.format(b=b), {"page": p})
            if html is None:
                print(f"[실패] {b} {p}p"); break
            rows = parse(html, URL.format(b=b), b)
            print(f"{b} {p}p -> {len(rows)}건")
            if not rows: break
            ok += 1
            for r in rows:
                if any(k in r["title"] for k in KEYWORDS) and not any(x in r["title"] for x in EXCLUDE):
                    r["id"] = hashlib.md5((r["board"] + r["title"] + r["date"]).encode()).hexdigest()[:12]
                    found[r["id"]] = r
            time.sleep(1)
    if ok == 0:
        print("아무것도 못 가져왔습니다 (접속 차단 또는 페이지 구조 변경)"); sys.exit(1)
    for i, r in found.items():
        r["first_seen"] = old.get(i, {}).get("first_seen", today)
    merged = {**old, **found}
    items = sorted(merged.values(), key=lambda x:
