import json
import logging
import os
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

CONFIG_PATH = "config.json"
STATE_PATH = "state.json"
USER_AGENT = "rss-to-discord-py/1.0 (+https://github.com)"
REQUEST_TIMEOUT = 10


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def parse_datetime(entry):
    candidates = [
        entry.get("published_parsed"),
        entry.get("updated_parsed"),
        entry.get("published"),
        entry.get("updated"),
    ]

    for value in candidates:
        if not value:
            continue

        if hasattr(value, "tm_year"):
            try:
                dt = datetime(*value[:6], tzinfo=timezone.utc)
                return dt
            except Exception:
                continue

        if isinstance(value, str):
            try:
                dt = parsedate_to_datetime(value)
            except Exception:
                continue
            if dt is None:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

    return None


def fetch_feed(url):
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return feedparser.parse(response.content)


def select_image_url(entry):
    if entry.get("media_content"):
        for media in entry["media_content"]:
            if isinstance(media, dict) and media.get("url"):
                return media["url"]
    if entry.get("media_thumbnail"):
        for thumb in entry["media_thumbnail"]:
            if isinstance(thumb, dict) and thumb.get("url"):
                return thumb["url"]
    if entry.get("image") and isinstance(entry["image"], dict):
        return entry["image"].get("href") or entry["image"].get("url")
    return None


def build_embed(entry, category, source_url):
    title = entry.get("title") or "Untitled"
    url = entry.get("link") or entry.get("id") or ""
    description = entry.get("summary") or entry.get("description") or "No description available."
    description = description.strip()
    if len(description) > 300:
        description = description[:297].rstrip() + "..."

    published_dt = parse_datetime(entry)
    timestamp = published_dt.isoformat() if published_dt else None

    embed = {
        "title": title,
        "url": url,
        "description": description,
        "footer": {"text": f"{category} · {source_url}"},
    }
    if timestamp:
        embed["timestamp"] = timestamp

    author_name = entry.get("author") or entry.get("dc_creator")
    if author_name:
        embed["author"] = {"name": author_name}

    image_url = select_image_url(entry)
    if image_url:
        embed["image"] = {"url": image_url}

    return embed


def post_embed(webhook_url, embed, use_proxy=False):
    if use_proxy:
        webhook_url = webhook_url.replace("discord.com", "webhook.lewisakura.moe")

    payload = {"embeds": [embed]}
    response = requests.post(webhook_url, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()


def iso_to_datetime(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        try:
            dt = parsedate_to_datetime(value)
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def main():
    config = load_json(CONFIG_PATH, {})
    if not config or "categories" not in config:
        logging.error(f"{CONFIG_PATH} missing or invalid. Please copy config.json.example to config.json and fill in your webhook URLs.")
        sys.exit(1)

    use_proxy = config.get("use_proxy", False)
    state = load_json(STATE_PATH, {}) or {}
    updated_state = False

    for section in config.get("categories", []):
        category = section.get("name") or "general"
        webhook_url = section.get("discord_webhook_url")
        if not webhook_url:
            logging.warning(f"Skipping category {category}: missing webhook URL.")
            continue

        for source in section.get("rss_feed_urls", []):
            try:
                feed = fetch_feed(source)
            except Exception as exc:
                logging.error(f"Failed to fetch {source}: {exc}")
                continue

            stored_dt = iso_to_datetime(state.get(source))
            entries = []

            for entry in feed.entries:
                entry_dt = parse_datetime(entry)
                if entry_dt and (stored_dt is None or entry_dt > stored_dt):
                    entries.append((entry_dt, entry))

            if not entries:
                continue

            # Sort from oldest to newest
            entries.sort(key=lambda item: item[0])
            
            # If no state (initial run), send only the latest entry
            if stored_dt is None:
                entries = [entries[-1]]
                logging.info(f"Initial run: only the latest item from {source} will be posted.")

            last_sent_dt = stored_dt
            for entry_dt, entry in entries:
                embed = build_embed(entry, category, source)
                try:
                    post_embed(webhook_url, embed, use_proxy)
                    last_sent_dt = entry_dt
                    logging.info(f"Posted new item from {source} to {category}: {entry.get('title')}")
                except Exception as exc:
                    logging.error(f"Failed to post item for {source}: {exc}")
                    break  # Stop processing this feed on error; will retry in the next run

            if last_sent_dt and (stored_dt is None or last_sent_dt > stored_dt):
                state[source] = last_sent_dt.isoformat()
                updated_state = True

    if updated_state:
        save_json(STATE_PATH, state)
        logging.info(f"State updated: {STATE_PATH}")


if __name__ == "__main__":
    main()
