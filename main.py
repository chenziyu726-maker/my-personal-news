import os
import feedparser
import requests
import trafilatura
from openai import OpenAI

# 1. 自动读取在 GitHub Secrets 中配置的密钥
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
LLM_API_KEY = os.getenv("LLM_API_KEY")
# 默认使用 DeepSeek 接口，若用硅基流动可改为 https://api.siliconflow.cn/v1
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")

# 2. 全球新闻 RSS 源（已加入 CNBC 头条与科技财经源，可随时自由增删）
RSS_FEEDS = {
    "CNBC Top News": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "CNBC Tech": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
    "CNBC Finance": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "TechCrunch": "https://techcrunch.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Hacker News": "https://news.ycombinator.com/rss"
}

def fetch_and_summarize():
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    raw_news_list = []

    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]:  # 源变多了，每个源取最新 2 条，避免总字数超限
                downloaded = trafilatura.fetch_url(entry.link)
                content = trafilatura.extract(downloaded) or entry.get("summary", "")
                raw_news_list.append(
                    f"【来源】{source}\n【标题】{entry.title}\n【链接】{entry.link}\n【正文节选】{content[:500]}\n"
                )
        except Exception as e:
            print(f"抓取 {source} 失败: {e}")

    combined_text = "\n---\n".join(raw_news_list)

    prompt = (
        "你是一个专业的全球财经、科技与国际新闻情报官。请将以下抓取的英文实时新闻整理成中文简报。\n"
        "要求：每条新闻用 1-2 句话精炼总结核心事实与数据，附带原链接，按【全球财经与市场】、【科技与AI前沿】、【国际动态】三个板块分类排版：\n\n"
        f"{combined_text}"
    )
    response = client.chat.completions.create(
        model="deepseek-chat",  # 若用其他平台，改成对应的模型名称即可
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content

def send_to_feishu(summary_markdown):
    # 标题包含“新闻”二字，用于通过飞书机器人的安全关键词校验
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🌍 全球实时财经与科技新闻简报"},
                "template": "blue"
            },
            "elements": [
                {"tag": "markdown", "content": summary_markdown}
            ]
        }
    }
    requests.post(FEISHU_WEBHOOK, json=payload)

if __name__ == "__main__":
    summary = fetch_and_summarize()
    send_to_feishu(summary)
