import os
import yaml
import requests
import feedparser
from datetime import datetime
from urllib.parse import quote
from openai import OpenAI

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

client = OpenAI(api_key=OPENAI_API_KEY)


def load_config():
    with open("config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_google_news_urls(config):
    urls = []

    keywords = config.get("google_news", config.get("keywords", []))
    news_sources = config.get("news_sources", [])

    # 1. Broad keyword search
    for keyword in keywords:
        query = f'"{keyword}" when:1d'
        url = (
            "https://news.google.com/rss/search?q="
            + quote(query)
            + "&hl=vi&gl=VN&ceid=VN:vi"
        )
        urls.append({
            "url": url,
            "keyword": keyword,
            "source_filter": "Google News"
        })

    # 2. Site-specific search
    for keyword in keywords:
        for source in news_sources:
            query = f'site:{source} "{keyword}" when:1d'
            url = (
                "https://news.google.com/rss/search?q="
                + quote(query)
                + "&hl=vi&gl=VN&ceid=VN:vi"
            )
            urls.append({
                "url": url,
                "keyword": keyword,
                "source_filter": source
            })

    return urls


def collect_google_news(search_urls, max_items=80):
    items = []

    for item in search_urls:
        feed = feedparser.parse(item["url"])

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            published = entry.get("published", "").strip()
            summary = entry.get("summary", "").strip()

            if not title or not link:
                continue

            items.append({
                "title": title,
                "link": link,
                "published": published,
                "summary": summary,
                "keyword": item["keyword"],
                "source_filter": item["source_filter"]
            })

            if len(items) >= max_items:
                return deduplicate(items)

    return deduplicate(items)


def deduplicate(items):
    seen = set()
    unique = []

    for item in items:
        key = item["title"].lower().strip()

        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def build_source_text(items):
    if not items:
        return "Không tìm thấy tin mới trong 24 giờ gần nhất."

    lines = []

    for i, item in enumerate(items, 1):
        lines.append(
            f"{i}. Title: {item['title']}\n"
            f"Keyword: {item['keyword']}\n"
            f"Source filter: {item['source_filter']}\n"
            f"Published: {item['published']}\n"
            f"Summary: {item['summary']}\n"
            f"URL: {item['link']}\n"
        )

    return "\n".join(lines)


def generate_report(config, items):
    today = datetime.now().strftime("%d/%m/%Y")
    source_text = build_source_text(items)
    client_name = config.get("client_name", "Nam Long Group")

    prompt = f"""
Bạn là Vietnam Media Intelligence Analyst.

Hãy viết báo cáo Telegram bằng tiếng Việt cho khách hàng: {client_name}.

Ngày báo cáo: {today}

Dữ liệu thu thập được:
{source_text}

Yêu cầu báo cáo:

1. Mở đầu bằng tiêu đề:
NAM LONG MORNING MEDIA BRIEF
Ngày: {today}

2. Phân loại rõ thành 2 phần chính:

A. CORPORATE NEWS
Chỉ gồm tin cấp tập đoàn Nam Long Group:
- ESG
- CSR
- tài chính
- lãnh đạo
- đối tác
- giải thưởng
- thương hiệu
- hoạt động doanh nghiệp
- truyền thông corporate

B. PROJECT NEWS
Tin theo từng dự án:
- Waterpoint
- Izumi City
- Mizuki Park
- Akari City
- Elyse Island
- Southgate
- các dự án khác nếu có

3. Với mỗi tin, ghi ngắn gọn:
- Nội dung chính
- Nguồn
- Thời gian
- Ý nghĩa chiến lược

4. Nếu không có tin đáng chú ý ở một nhóm, ghi rõ:
Không ghi nhận cập nhật đáng chú ý trong 24 giờ gần nhất.

5. Cuối báo cáo có:
MEDIA INSIGHT
STRATEGIC OBSERVATION

6. Chỉ dùng dữ liệu được cung cấp. Không bịa nguồn, không bịa link, không suy đoán quá mức.

7. Viết súc tích, chuyên nghiệp, theo giọng executive brief.

8. Không dùng HTML, không dùng Markdown phức tạp. Chỉ dùng text thuần để tránh lỗi Telegram.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "You write concise Vietnamese executive media intelligence reports based only on provided sources."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    return response.choices[0].message.content


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    if len(message) > 3900:
        message = message[:3900] + "\n\n[Báo cáo được rút gọn do giới hạn độ dài Telegram.]"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }

    response = requests.post(url, json=payload, timeout=30)

    print("TELEGRAM STATUS:", response.status_code)
    print("TELEGRAM RESPONSE:", response.text)

    response.raise_for_status()


def main():
    config = load_config()

    search_urls = build_google_news_urls(config)
    max_news = config.get("report", {}).get("max_news", 80)

    items = collect_google_news(search_urls, max_items=max_news)

    report = generate_report(config, items)

    send_telegram(report)


if __name__ == "__main__":
    main()
