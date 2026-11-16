import os
import feedparser
import requests
import trafilatura
from openai import OpenAI

# 1. 自动读取在 GitHub Secrets 中配置的密钥
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
LLM_API_KEY = os.getenv("LLM_API_KEY")

# 阿里云通义千问（百炼）兼容接口地址（若使用了其他中转站请保持你刚才跑通的网址）
LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 2. 扩容版全球新闻 RSS 源（涵盖 11 个主流财经、科技、国际权威频道）
RSS_FEEDS = {
    "CNBC Top News": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "CNBC Tech": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
    "CNBC Finance": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "CNBC Markets": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "TechCrunch": "https://techcrunch.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "MIT Tech Review": "https://www.technologyreview.com/feed/"
}

def fetch_and_summarize():
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    raw_news_list = []

    for source, url in RSS_FEEDS.items():
        try:
            # 增加超时与请求头，防止部分外媒拦截导致漏抓
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            feed = feedparser.parse(resp.content)
            # 每个源抓取最新 5 条（11个源共 55 条新闻）
            for entry in feed.entries[:5]:
                downloaded = trafilatura.fetch_url(entry.link)
                content = trafilatura.extract(downloaded) or entry.get("summary", "")
                # 正文提取长度提升至 1200 字符，保留更多细节与数据
                raw_news_list.append(
                    f"【来源】{source}\n【标题】{entry.title}\n【链接】{entry.link}\n【正文内容】{content[:1200]}\n"
                )
        except Exception as e:
            print(f"抓取 {source} 失败: {e}")

    combined_text = "\n---\n".join(raw_news_list)

    prompt = (
        "你是一位资深的全球宏观财经、科技与国际新闻主编。请将以下抓取到的英文实时新闻整理成一份详尽的深度中文情报内参。\n\n"
        "【严格输出要求】：\n"
        "1. 数量要求：请从素材中精选至少 20 到 25 条高价值新闻进行汇报，严禁过度删减或只挑寥寥几条！\n"
        "2. 内容深度：每条新闻必须包含【加粗中文标题】+【80-120字的详细深度摘要】。摘要需交代清楚：背景原因、核心事件、关键财务/市场数据、涉及的公司或人物，以及潜在行业影响，切勿只写空洞的一句话。\n"
        "3. 格式规范：每条新闻末尾附上 `[原文链接](URL)`，并标注来源媒体名称。\n"
        "4. 分类排版：请按以下四个板块清晰分类，每个板块至少包含 5-7 条新闻：\n"
        "   - 📈 【全球宏观与金融市场】\n"
        "   - 🤖 【硬核科技与AI前沿】\n"
        "   - 🏢 【商业巨头与产业动态】\n"
        "   - 🌍 【国际政经要闻】\n\n"
        f"待处理的新闻素材如下：\n{combined_text}"
    )

    response = client.chat.completions.create(
        model="qwen-plus",  # 若使用其他中转平台请保持你对应的模型名
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4000     # 显式放开最大输出字数限制，允许生成长篇深度报告
    )
    return response.choices[0].message.content

def send_to_feishu(summary_markdown):
    # 飞书单张卡片如果文字太长，自动切分或直接展示完整富文本
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🌍 全球实时财经与科技深度新闻内参"},
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
