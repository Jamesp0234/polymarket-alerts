# Polymarket Alerts — @neobrother Monitor

Monitors [@neobrother](https://polymarket.com/@neobrother)'s trades on Polymarket and sends Telegram alerts.

## How it works

A GitHub Actions cron job runs every 10 minutes, polls the Polymarket Data API for new trades, and sends formatted alerts to Telegram with market name, direction, price, and size.

Trades on the same market within 60 seconds are batched into a single alert.

## Setup

1. Fork or push this repo to GitHub (public repo = free unlimited Actions minutes)
2. Add repository secrets in Settings → Secrets → Actions:
   - `TELEGRAM_BOT_TOKEN` — your Telegram bot token
   - `TELEGRAM_CHAT_ID` — your Telegram chat ID
3. The workflow runs automatically every 10 minutes, or trigger manually via Actions → Run workflow

## Local testing

```bash
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
python monitor.py
```
