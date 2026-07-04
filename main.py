import os
import yaml
import html
import requests
import feedparser
from datetime import datetime
from openai import OpenAI

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

client = OpenAI(api_key=OPENAI_API_KEY)


def load_config():
    with open("config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_google_news(rss_urls):
    items = []

    for url in rss_urls:
        feed = feedparser.parse(url)

        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published", "")
            summary = entry.get("summary", "")

            items.append({
                "title": title,
                "link": link,
                "published": published,
                "summary": summary
            })

    return deduplicate(items)


def deduplicate(items):
    seen = set()
    unique = []

    for item in items:
        key = item["title"].strip().lower()

        if key and key not in seen:
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
            f"Published: {item['published']}\n"
            f"Summary: {item['summary']}\n"
            f"URL: {item['link']}\n"
        )

    return "\n".join(lines)


def generate_report(config, items):
    today = datetime.now().strftime("%d/%m/%Y")
    source_text = build_source_text(items)

    prompt = f"""
Bạn là Vietnam Media Intelligence Analyst.

Hãy viết báo cáo Telegram bằng tiếng Việt cho khách hàng: {config["client_name"]}.

Ngày báo cáo: {today}

Dữ liệu thu thập được:
{source_text}

Yêu cầu:
1. Phân loại rõ:
- CORPORATE NEWS: tin cấp tập đoàn Nam Long Group.
- PROJECT NEWS: tin theo từng dự án như Waterpoint, Izumi City, Mizuki Park, Akari City, Elyse Island, Southgate.
2. Với mỗi tin, ghi ngắn gọn:
- Nội dung chính
- Nguồn
- Thời gian
- Ý nghĩa chiến lược
3. Nếu không có tin đáng chú ý, ghi rõ không có cập nhật.
4. Cuối báo cáo có:
- Media Insight
- Strategic Observation
5. Format Telegram HTML.
6. Chỉ dùng tag HTML Telegram hỗ trợ: <b>, <i>, <a>.
7. Không dùng markdown.
8. Không bịa nguồn. Chỉ dùng dữ liệu được cung cấp.
9. Viết súc tích, chuyên nghiệp, theo giọng executive brief.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You write concise Vietnamese executive media intelligence reports."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

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
    items = collect_google_news(config["google_news_rss"])
    report = generate_report(config, items)

    if len(report) > 3900:
        report = report[:3900] + "\n\n<i>Báo cáo được rút gọn do giới hạn độ dài Telegram.</i>"

    send_telegram(report)


if __name__ == "__main__":
    main()
