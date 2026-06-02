import os
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

POLYMARKET_ACTIVITY_URL = "https://data-api.polymarket.com/activity"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

TARGET_WALLET = "0x6297b93ea37ff92a57fd636410f3b71ebf74517e"
TARGET_USERNAME = "neobrother"

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "last_seen.json"
POLL_LIMIT = 50


def load_state() -> int:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f).get("last_timestamp", 0)
    return 0


def save_state(ts: int):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_timestamp": ts}, f)


def fetch_activity(since_ts: int) -> list[dict]:
    params = urllib.parse.urlencode({
        "user": TARGET_WALLET,
        "limit": POLL_LIMIT,
        "type": "TRADE",
        "sortBy": "TIMESTAMP",
        "sortDirection": "DESC",
    })
    url = f"{POLYMARKET_ACTIVITY_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "polymarket-alerts/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        trades = json.loads(resp.read().decode())

    new_trades = [t for t in trades if t.get("timestamp", 0) > since_ts]
    new_trades.sort(key=lambda t: t["timestamp"])
    return new_trades


def clean_title(title: str) -> str:
    return title.replace("Â°", "°").replace("Â°", "°")


def format_trade(trade: dict) -> str:
    ts = trade.get("timestamp", 0)
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = clean_title(trade.get("title", "Unknown Market"))
    side = trade.get("side", "?")
    outcome = trade.get("outcome", "?")
    price = trade.get("price", 0)
    size = trade.get("size", 0)
    usdc = trade.get("usdcSize", 0)
    event_slug = trade.get("eventSlug", "")

    direction_emoji = "\U0001f7e2" if side == "BUY" else "\U0001f534"
    market_url = f"https://polymarket.com/event/{event_slug}" if event_slug else ""

    lines = [
        f"{direction_emoji} *{side} {outcome}*",
        f"Market: {title}",
        f"Price: {price:.3f} | Shares: {size:.2f} | Cost: ${usdc:.2f}",
        f"Time: {dt}",
    ]
    if market_url:
        lines.append(f"[View Market]({market_url})")

    return "\n".join(lines)


def send_telegram(message: str):
    url = TELEGRAM_API_URL.format(token=TELEGRAM_BOT_TOKEN)
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())
        if not result.get("ok"):
            print(f"Telegram error: {result}")


def batch_trades(trades: list[dict]) -> list[dict]:
    """Group all trades on the same market+side+outcome into a single summary."""
    if not trades:
        return []

    groups: dict[tuple, list[dict]] = {}
    for trade in trades:
        key = (trade.get("conditionId"), trade.get("side"), trade.get("outcomeIndex"))
        groups.setdefault(key, []).append(trade)

    summaries = []
    for group in groups.values():
        if len(group) == 1:
            summaries.append(group[0])
        else:
            merged = dict(group[-1])
            total_size = sum(t.get("size", 0) for t in group)
            total_usdc = sum(t.get("usdcSize", 0) for t in group)
            avg_price = total_usdc / total_size if total_size else 0
            merged["size"] = total_size
            merged["usdcSize"] = total_usdc
            merged["price"] = avg_price
            merged["_batch_count"] = len(group)
            summaries.append(merged)

    summaries.sort(key=lambda t: t.get("timestamp", 0))
    return summaries


def main():
    last_ts = load_state()
    print(f"Checking trades for @{TARGET_USERNAME} since timestamp {last_ts}")

    trades = fetch_activity(last_ts)

    if not trades:
        print("No new trades found.")
        return

    print(f"Found {len(trades)} new trade(s)")

    batched = batch_trades(trades)
    max_ts = max(t.get("timestamp", 0) for t in trades)

    for trade in batched:
        batch_count = trade.pop("_batch_count", None)
        header = f"*@{TARGET_USERNAME}* new trade"
        if batch_count:
            header = f"*@{TARGET_USERNAME}* {batch_count} trades (batched)"
        msg = f"{header}\n\n{format_trade(trade)}"
        print(f"Sending alert: {trade.get('title')} {trade.get('side')}")
        send_telegram(msg)
        time.sleep(0.5)

    save_state(max_ts)
    print(f"Updated last_seen timestamp to {max_ts}")


if __name__ == "__main__":
    main()
