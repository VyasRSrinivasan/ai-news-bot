<div align="center">

# AI News Bot

🤖 **Your AI-Powered News Assistant** — Automated daily digests *and* on-demand topic search, delivered to Telegram, email, and more

[![GitHub Stars](https://img.shields.io/github/stars/giftedunicorn/ai-news-bot?style=flat-square&logo=github&color=yellow)](https://github.com/giftedunicorn/ai-news-bot/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/giftedunicorn/ai-news-bot?style=flat-square&logo=github&color=blue)](https://github.com/giftedunicorn/ai-news-bot/network/members)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg?style=flat-square)](LICENSE)

[![Discord](https://img.shields.io/badge/Discord-Join_Community-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.gg/AtfQPh8T2T)
[![Email](https://img.shields.io/badge/Email-Gmail_SMTP-00D4AA?style=flat-square)](https://gmail.com/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-00D4AA?style=flat-square)](https://telegram.org/)
[![Slack](https://img.shields.io/badge/Slack-Integration-00D4AA?style=flat-square)](https://slack.com/)
[![Webhook](https://img.shields.io/badge/Webhook-Support-00D4AA?style=flat-square)](#)

[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automation-2088FF?style=flat-square&logo=github-actions&logoColor=white)](https://github.com/giftedunicorn/ai-news-bot)
[![Claude](https://img.shields.io/badge/Claude-Sonnet_4.5-FF6B6B?style=flat-square&logo=anthropic&logoColor=white)](https://www.anthropic.com)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-Supported-4285F4?style=flat-square&logo=ai&logoColor=white)](https://www.deepseek.com)

</div>

---

## 📑 Quick Navigation

<div align="center">

| [✨ Features](#features) | [🚀 Quick Start](#quick-start-local-development) | [🔍 Topic Search](#interactive-topic-search) | [⚙️ Configuration](#configuration) |
| :----------------------: | :----------------------------------------------: | :------------------------------------------: | :---------------------------------: |
| [🤖 LLM Providers](#llm-provider-configuration) | [🌍 Languages](#language-configuration) | [📧 Email Setup](#email-setup-guide) | [🔧 Troubleshooting](#troubleshooting) |

</div>

---

## Features

- **Two Modes**: Run a scheduled daily digest *or* search for any topic on demand
- **Agentic Topic Search**: Claude autonomously selects and fetches from 20+ RSS sources based on your prompt
- **Interactive Category Menu**: Pick from preset categories (Technology, Finance, Science…) or enter a custom topic
- **Structured JSON Digest**: LLM returns categorized stories with importance ratings — not raw text
- **Styled HTML Email**: Digest is rendered from structured JSON into a clean, mobile-friendly HTML email
- **Telegram & Discord Short Summaries**: Concise embeds with headline + top stories per category
- **Deduplication Memory**: `seen_urls.json` tracks sent articles across runs — no repeated stories
- **Multi-Provider LLM Support**: Claude, DeepSeek, Gemini, Grok, or OpenAI
- **20+ RSS Sources**: TechCrunch, VentureBeat, arXiv, OpenAI Blog, DeepMind, The Verge, and more
- **Multilingual Support**: Generate digests in 13+ languages
- **Multiple Notification Channels**: Email (Gmail SMTP), Telegram, Discord, Slack, and Webhooks
- **GitHub Actions Automation**: Daily cron job with automatic `seen_urls.json` commit
- **Robust Error Handling**: 3-retry loop on LLM calls, graceful fallbacks

### 📸 Example Screenshots

<div align="center">

| Chinese Email | English Email |
|:-------------:|:-------------:|
| ![Chinese AI News Digest](image/screenshot1.png) | ![English AI News Digest](image/screenshot2.png) |

</div>

---

## How It Works

### Scheduled Daily Digest (`main.py`)

```
RSS Feeds (20+)
     │
     ▼
NewsFetcher.fetch_recent_news()
     │
     ▼
deduplicate_news_data()  ──► seen_urls.json (persisted)
     │
     ▼
Summarizer.summarize()  ──► JSON digest {date, headline, categories[]}
     │
     ├──► EmailNotifier.send_digest()        → styled HTML email
     ├──► TelegramNotifier.send_digest_summary() → short Telegram message
     ├──► DiscordNotifier.send_digest_summary()  → Discord embed
     └──► SlackNotifier / WebhookNotifier        → text summary
```

### Interactive Topic Search (`topic_search.py`)

```
User selects category or enters custom topic
     │
     ▼
TopicNewsAgent  (Claude tool-calling loop)
  │  Claude decides which RSS feeds are relevant
  │  Calls fetch_rss_feed() for each → up to 20 sources
     │
     ▼
deduplicate_news()   (in-session dedup)
     │
     ▼
Summarizer.summarize(topics=[user_topic])
     │
     ▼
TelegramNotifier.send_digest_summary()
```

---

## 🚀 Deployment Options

| Method | Configuration | When to Use |
| --- | --- | --- |
| **GitHub Actions** | Repository Secrets | Automated daily digest (recommended) |
| **Local — Daily** | `.env` file | Manual runs of the full digest |
| **Local — Topic Search** | `.env` file | On-demand search for any topic |

---

## Quick Start (GitHub Actions — Recommended)

### Step 1: Fork or Clone

```bash
git clone <your-repo-url>
cd ai-news-bot
```

### Step 2: Add GitHub Repository Secrets

```
Repository → Settings → Secrets and variables → Actions → New repository secret
```

#### ✅ Required

| Secret | Example | Description |
| --- | --- | --- |
| `LLM_PROVIDER` | `claude` | Provider: `claude`, `deepseek`, `gemini`, `grok`, `openai` |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Anthropic key (if using Claude) |
| `NOTIFICATION_METHODS` | `telegram` | Comma-separated: `email`, `telegram`, `discord`, `slack`, `webhook` |

#### 📧 Email (if using `email`)

| Secret | Example | Description |
| --- | --- | --- |
| `GMAIL_ADDRESS` | `you@gmail.com` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | `xxxx xxxx xxxx xxxx` | [Gmail App Password](https://myaccount.google.com/apppasswords) |
| `EMAIL_TO` | `recipient@example.com` | Recipient address |

#### 📱 Telegram (if using `telegram`)

| Secret | Example | Description |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | `123456:ABC...` | Token from [@BotFather](https://t.me/botfather) |
| `TELEGRAM_CHAT_ID` | `123456789` | Your chat ID ([@userinfobot](https://t.me/userinfobot)) |

#### 🎮 Discord (if using `discord`)

| Secret | Example | Description |
| --- | --- | --- |
| `DISCORD_WEBHOOK_URL` | `https://discord.com/api/webhooks/...` | Discord Webhook URL |

#### 💬 Slack (if using `slack`)

| Secret | Example | Description |
| --- | --- | --- |
| `SLACK_WEBHOOK_URL` | `https://hooks.slack.com/services/...` | Slack Incoming Webhook URL |

#### 🌍 Optional

| Secret | Example | Description |
| --- | --- | --- |
| `AI_RESPONSE_LANGUAGE` | `en` or `en,zh,ja` | Output language(s), defaults to `en` |
| `LLM_MODEL` | `claude-sonnet-4-5-20250929` | Override default model |

### Step 3: Enable GitHub Actions

```
Repository → Settings → Actions → General → Allow all actions
```

### Step 4: Test Manually

```
Repository → Actions → Daily AI News Digest → Run workflow
```

### Step 5: Automated Schedule

The workflow runs daily at midnight UTC. Edit `.github/workflows/daily-news.yml` to change the time:

```yaml
schedule:
  - cron: "0 7 * * *"   # 7:00 AM UTC
  - cron: "0 0 * * *"   # midnight UTC (default)
```

> After each run the workflow automatically commits `seen_urls.json` back to the repo so tomorrow's run skips already-sent articles.

---

## Quick Start (Local Development)

### 1. Clone and Install

```bash
git clone <your-repo-url>
cd ai-news-bot
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env   # then edit .env with your credentials
```

Minimum `.env` for Telegram delivery:

```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...

NOTIFICATION_METHODS=telegram
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
```

### 3. Run the Daily Digest

```bash
python main.py
```

### 4. Run the Interactive Topic Search

```bash
python topic_search.py
```

---

## Interactive Topic Search

`topic_search.py` lets you search for news on **any topic right now** — no schedule required. Claude acts as an agent, selecting which of the 20+ RSS sources are relevant, fetching them, and publishing a digest to Telegram.

### Usage

```bash
# Interactive category menu (recommended)
python topic_search.py

# Pass topic directly
python topic_search.py "electric vehicles"
python topic_search.py "climate policy"

# Print to terminal instead of sending to Telegram
python topic_search.py technology --no-telegram

# Limit sources fetched (default: 20)
python topic_search.py finance --max-sources 10
```

### Category Menu

When run without arguments, the script displays a menu:

```
┌─────────────────────────────────────────────────┐
│          AI News Bot — Topic Selection          │
├────┬────────────────────────┬───────────────────┤
│  1 │ Technology             │ AI, software, ...  │
│  2 │ Business & Finance     │ markets, M&A, ...  │
│  3 │ Science & Research     │ papers, climate... │
│  4 │ Health & Medicine      │ biotech, pharma... │
│  5 │ Politics & Policy      │ regulation, ...    │
│  6 │ Robotics & EVs         │ autonomous, ...    │
│  7 │ Custom                 │ enter your own...  │
└────┴────────────────────────┴───────────────────┘

Select a category [1-7]:
```

Options 1–6 map to a preset topic string. Option 7 prompts for free text.

### How the Agent Works

1. Claude is given the user's topic and the full list of 20+ available RSS feeds.
2. Claude calls `fetch_rss_feed(url)` for each source it deems relevant — autonomously deciding which feeds match the topic.
3. Articles are collected as each tool call completes.
4. After all relevant feeds are fetched, the articles are deduplicated and passed to `Summarizer`.
5. The resulting JSON digest is sent to Telegram via `send_digest_summary()`.

For non-Claude providers (or if tool-calling fails), the agent falls back to keyword filtering across all feeds.

---

## Project Structure

```
ai-news-bot/
├── .github/
│   └── workflows/
│       └── daily-news.yml          # Cron job + seen_urls.json commit
├── src/
│   ├── config.py                   # Config management (reads config.yaml + env)
│   ├── logger.py                   # Logging setup
│   ├── news/
│   │   ├── fetcher.py              # RSS feed fetching (20+ sources)
│   │   ├── deduper.py              # In-session + cross-run deduplication
│   │   ├── summarizer.py           # LLM call → JSON digest
│   │   ├── agent.py                # TopicNewsAgent (agentic RSS fetch)
│   │   ├── generator.py            # Two-stage news generation (legacy)
│   │   └── web_search.py           # DuckDuckGo search tool
│   ├── llm_providers/
│   │   ├── base_provider.py        # Abstract provider interface
│   │   ├── claude_provider.py      # Anthropic Claude
│   │   ├── deepseek_provider.py    # DeepSeek
│   │   ├── gemini_provider.py      # Google Gemini
│   │   ├── grok_provider.py        # xAI Grok
│   │   └── openai_provider.py      # OpenAI
│   └── notifiers/
│       ├── email_notifier.py       # Gmail SMTP — send_digest() renders JSON → HTML
│       ├── telegram_notifier.py    # Telegram — send_digest_summary()
│       ├── discord_notifier.py     # Discord embeds — send_digest_summary()
│       ├── slack_notifier.py       # Slack
│       └── webhook_notifier.py     # Generic JSON webhook
├── main.py                         # Daily digest orchestrator
├── topic_search.py                 # Interactive topic search CLI
├── config.yaml                     # LLM, news topics, prompt templates
├── seen_urls.json                  # Persisted deduplication log (auto-updated)
├── requirements.txt
└── .env.example
```

---

## Configuration

### `config.yaml`

```yaml
llm:
  provider: claude          # claude | deepseek | gemini | grok | openai
  # model: claude-sonnet-4-5-20250929   # optional override

news:
  enable_web_search: false
  max_items_per_source: 10

  # Topics passed to the Summarizer to guide story selection
  topics:
    - Artificial Intelligence
    - Machine Learning
    - Large Language Models
    - AI Research
    - AI Products & Startups
    - AI Policy & Regulation

  # Two-stage prompt templates (stage1 = selection, stage2 = summarization)
  stage1_prompt_template: |
    ...
  stage2_prompt_template: |
    ...

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `LLM_PROVIDER` | Optional | `claude` (default), `deepseek`, `gemini`, `grok`, `openai` |
| `ANTHROPIC_API_KEY` | If using Claude | Anthropic API key |
| `DEEPSEEK_API_KEY` | If using DeepSeek | DeepSeek API key |
| `GOOGLE_API_KEY` | If using Gemini | Google API key |
| `XAI_API_KEY` | If using Grok | xAI API key |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `LLM_MODEL` | Optional | Override provider's default model |
| `NOTIFICATION_METHODS` | ✅ Required | Comma-separated: `email`, `telegram`, `discord`, `slack`, `webhook` |
| `AI_RESPONSE_LANGUAGE` | Optional | Language code(s), default `en`. Comma-separate for multiple: `en,zh,ja` |
| `GMAIL_ADDRESS` | Email only | Your Gmail address |
| `GMAIL_APP_PASSWORD` | Email only | 16-char Gmail App Password |
| `EMAIL_TO` | Email only | Recipient address |
| `TELEGRAM_BOT_TOKEN` | Telegram only | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Telegram only | User, group, or channel ID |
| `DISCORD_WEBHOOK_URL` | Discord only | Discord Webhook URL |
| `SLACK_WEBHOOK_URL` | Slack only | Slack Incoming Webhook URL |
| `WEBHOOK_URL` | Webhook only | Generic JSON webhook endpoint |

---

## LLM Provider Configuration

```yaml
# config.yaml
llm:
  provider: claude
  # model: claude-sonnet-4-5-20250929
```

| Provider | Default Model | Strengths |
| --- | --- | --- |
| **Claude** | `claude-sonnet-4-5-20250929` | Best tool-calling for the agent, top quality |
| **DeepSeek** | `deepseek-reasoner` | Very low cost, extended reasoning |
| **Gemini** | `gemini-3-pro-preview` | Fast, multimodal, free tier |
| **Grok** | `grok-4-1-fast-reasoning` | Real-time data, fast reasoning |
| **OpenAI** | `gpt-5.1` | Broad capability |

> **Note**: The `TopicNewsAgent` agentic path uses Claude's tool-calling (`generate_with_tools`). Other providers fall back to keyword-based RSS filtering.

---

## Language Configuration

Set `AI_RESPONSE_LANGUAGE` to control the output language of generated digests:

```env
# Single language
AI_RESPONSE_LANGUAGE=zh

# Multiple languages — generates a separate digest for each
AI_RESPONSE_LANGUAGE=en,zh,ja
```

**Supported:** `en` · `zh` · `es` · `fr` · `ja` · `de` · `ko` · `pt` · `ru` · `ar` · `hi` · `it` · `nl`

---

## Email Format

Emails are rendered from the structured JSON digest into a styled HTML template:

- Category headers with blue dividers
- Per-story cards with title (linked), two-sentence summary, source, and importance badge (🔴 High / 🟡 Medium / 🔵 Low)
- Mobile-responsive layout, works in Gmail, Outlook, Apple Mail

---

## Email Setup Guide

### Step 1: Enable 2-Step Verification

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** (required for App Passwords)

### Step 2: Create an App Password

1. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
2. Select **Mail** → **Other** → name it "AI News Bot"
3. Copy the generated 16-character password

### Step 3: Configure

```env
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_TO=recipient@example.com
NOTIFICATION_METHODS=email
```

**Troubleshooting:**
- *Authentication failed* — use the App Password, not your regular password
- *App Passwords missing* — enable 2-Step Verification first

---

## Notification Channels Setup

### Telegram

1. Message [@BotFather](https://t.me/botfather) → `/newbot` → copy the token
2. Message [@userinfobot](https://t.me/userinfobot) → copy your chat ID
3. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` or GitHub Secrets

For channels/groups: add the bot as admin and use the channel/group ID (starts with `-100`).

### Discord

1. Server Settings → Integrations → Webhooks → New Webhook
2. Select channel, copy the URL
3. Set `DISCORD_WEBHOOK_URL`

### Slack

1. [api.slack.com/apps](https://api.slack.com/apps) → Create App → Incoming Webhooks → Add webhook
2. Set `SLACK_WEBHOOK_URL`

### Webhook

Receives a JSON POST with the plain-text digest:

```json
{
  "title": "AI News Digest — 2025-03-24",
  "content": "...",
  "timestamp": "2025-03-24T07:00:00",
  "source": "AI News Bot"
}
```

---

## Deduplication

`seen_urls.json` at the repo root tracks every article URL that has been sent. On each run:

1. `deduplicate_news_data()` filters out any article whose URL is already in the file.
2. After delivering the digest, all new URLs are appended and the file is saved.
3. In GitHub Actions, a post-run step commits and pushes `seen_urls.json` automatically.

To reset the history and re-send all articles, clear the file:

```bash
echo "[]" > seen_urls.json
```

---

## Error Handling

- **LLM retries**: `Summarizer` retries up to 3 times with a 2-second delay between attempts
- **Agent fallback**: If Claude tool-calling fails, `TopicNewsAgent` falls back to keyword-based RSS filtering
- **Graceful delivery**: If one notification channel fails, the others still run
- **Comprehensive logging**: All operations logged with timestamps; GitHub Actions uploads logs as artifacts on failure

---

## Troubleshooting

| Problem | Solution |
| --- | --- |
| `Config file not found` | Ensure `config.yaml` exists in the project root |
| `No new articles after deduplication` | Clear `seen_urls.json` (`echo "[]" > seen_urls.json`) |
| Email not sending | Use the 16-char App Password, not your Gmail password |
| Telegram not sending | Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are correct |
| Agent fetches 0 articles | Check RSS feed connectivity; fallback keyword mode should activate |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |

---

## Development

```bash
# Set up virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run daily digest
python main.py

# Run interactive topic search
python topic_search.py
```

---

## License

GPL-3.0 — see LICENSE file for details.

---

## Support

- **Discord Community**: [discord.gg/AtfQPh8T2T](https://discord.gg/AtfQPh8T2T)
- **GitHub Issues**: [github.com/giftedunicorn/ai-news-bot/issues](https://github.com/giftedunicorn/ai-news-bot/issues)

---

## Credits

Powered by [Anthropic Claude](https://www.anthropic.com) · [DeepSeek](https://www.deepseek.com) · [GitHub Actions](https://github.com/features/actions)

---

## ⭐ Star History

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=giftedunicorn/ai-news-bot&type=Date)](https://star-history.com/#giftedunicorn/ai-news-bot&Date)

</div>

---

<div align="center">

**[⬆ Back to Top](#ai-news-bot)**

Made with ❤️ by the open source community

</div>
