import json
import re

import requests
from bs4 import BeautifulSoup

url = "https://zh.wikipedia.org/w/api.php"
params = {
    "action": "parse",
    "page": "香港迪士尼樂園",
    "format": "json",
    "prop": "text",
}

# Always include a User-Agent header identifying your application per Wikipedia API etiquette
headers = {"User-Agent": "MyTableExtractorBot/1.0 (contact@example.com)"}
response = requests.get(url, params=params, headers=headers)
data = response.json()

html_content = data["parse"]["text"]["*"]
soup = BeautifulSoup(html_content, "html.parser")
tables = soup.find_all("table", {"class": "wikitable"})


def parse_pct(text: str) -> int | None:
    text = text.strip()
    if not text or "未有" in text:
        return None
    m = re.search(r"([\d.]+)\s*%?", text)
    return int(float(m.group(1))) if m else None


def parse_attendance_wan(text: str) -> int | None:
    """入場人次（萬） → absolute visitor count."""
    text = text.strip()
    if not text or "未有" in text:
        return None
    return int(float(text.replace(",", ""))) * 10_000


def parse_hkd_yi(text: str) -> int | None:
    """Values like '25.41億', '▼15.74億', '▲1.09億' → HKD integer."""
    text = text.strip()
    if not text or "未有" in text:
        return None
    is_loss = "▼" in text or "↓" in text
    is_profit_mark = "▲" in text or "↑" in text
    m = re.search(r"([\d.]+)\s*億", text)
    if not m:
        return None
    value = int(round(float(m.group(1)) * 100_000_000))
    if is_loss:
        return -value
    if is_profit_mark:
        return value
    return value


def table_to_records(table) -> list[dict]:
    rows = table.find_all("tr")
    if not rows:
        return []

    headers = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    if not any("入場" in h for h in headers):
        return []

    records = []
    for row in rows[1:]:
        cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
        if len(cells) < 7:
            continue
        year, attendance, local, mainland, international, revenue, profit = cells[:7]
        records.append(
            {
                "year": year.strip().rstrip("*"),
                "attendance": parse_attendance_wan(attendance),
                "local_visitor_pct": parse_pct(local),
                "mainland_visitor_pct": parse_pct(mainland),
                "international_visitor_pct": parse_pct(international),
                "revenue_hkd": parse_hkd_yi(revenue),
                "net_profit_hkd": parse_hkd_yi(profit),
            }
        )
    return records


records = []
for table in tables:
    records = table_to_records(table)
    if records:
        break

print(f"Found {len(tables)} tables; extracted {len(records)} rows.")
print(json.dumps(records, ensure_ascii=False, indent=2))

out_path = "wiki_disney_metric.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(f"Wrote {out_path}")
