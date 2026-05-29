"""
RSS to Discord Python Script
This script fetches RSS feeds and posts new entries to Discord via webhooks.
It maintains a state file to ensure only new entries are posted.
"""

import json
import time
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
import feedparser
import requests
from bs4 import BeautifulSoup

# Logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

DATA_DIR = os.getenv("RSSDC_DATA_DIR", ".")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
USER_AGENT = "rss-to-discord-py/1.0 (+https://github.com)"
REQUEST_TIMEOUT = 10


def load_json(path, default=None):
    """Loads JSON data from the specified path. If the file doesn't exist, returns the default value."""
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path, data):
    """Saves the given data as JSON to the specified path, creating directories if needed."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def clean_html(html_content):
    """
    Parses the HTML and returns only the visible text content. Achieves the same result as
    'contentSnippet' in JavaScript's rss-parser.
    """
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def parse_datetime(entry):
    """
    Tries to extract a datetime from the rss feed entry using common fields. Returns a
    timezone-aware datetime in UTC or None if not found.
    """
    for key in ["published_parsed", "updated_parsed", "published", "updated"]:
        value = entry.get(key)
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
    """Fetches the RSS feed from the given URL using requests and parses it with feedparser."""
    response = requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    return feedparser.parse(response.content)


def select_image_url(entry):
    """Tries to find a suitable image URL from the RSS entry using multiple strategies"""
    # 1. Check Media Content (Media RSS standard)
    if entry.get("media_content"):
        for media in entry["media_content"]:
            if isinstance(media, dict) and media.get("url"):
                return media["url"]
    # 2. Check Enclosures (Standard RSS attachments)
    if entry.get("links"):
        for link in entry["links"]:
            if link.get("rel") == "enclosure" and "image" in link.get("type", ""):
                return link.get("href")
    # 3. Check Media Thumbnail
    if entry.get("media_thumbnail"):
        for thumb in entry["media_thumbnail"]:
            if isinstance(thumb, dict) and thumb.get("url"):
                return thumb["url"]
    # 4. Check 'image' field
    if entry.get("image") and isinstance(entry["image"], dict):
        url = entry["image"].get("href") or entry["image"].get("url")
        if url:
            return url
    # 5. Fallback: Parse HTML content for the first <img> tag
    # Many feeds put images inside summary or description
    html_content = ""
    if entry.get("content"):
        html_content = entry["content"][0].get("value", "")
    if not html_content:
        html_content = entry.get("summary") or entry.get("description") or ""
    if html_content:
        soup = BeautifulSoup(html_content, "html.parser")
        img = soup.find("img")
        if img and img.get("src"):
            return img["src"]
    return None


def build_embed(entry, source_url, published_dt):
    """Constructs a Discord embed dictionary from the RSS feed entry."""
    title = entry.get("title") or "Untitled"
    url = entry.get("link") or entry.get("id") or ""
    raw_description = (
        entry.get("summary") or entry.get("description") or "No description available."
    )
    # Clean the HTML to get a snippet, then truncate to 300 characters
    description = clean_html(raw_description)
    if len(description) > 300:
        description = description[:297].rstrip() + "..."

    domain = urlparse(source_url).netloc
    embed = {
        "_meta": {
            "rss_url": source_url,
        },
        "title": title,
        "url": url,
        "description": description,
        "footer": {"text": domain},
        "timestamp": published_dt.isoformat(),
    }

    author_name = entry.get("author") or entry.get("dc_creator")
    if author_name:
        embed["author"] = {"name": author_name}

    image_url = select_image_url(entry)
    if image_url:
        embed["image"] = {"url": image_url}

    return embed


def post_embeds(settings, embeds, state):
    """
    Posts embeds to Discord in batches. Updates state for each successful batch.
    """
    webhook_url = settings.get("discord_webhook_url")
    use_proxy = settings.get("use_proxy", False)
    batch_size = settings.get("batch_size", 10)
    username = settings.get("username")
    avatar_url = settings.get("avatar_url")

    if use_proxy:
        webhook_url = webhook_url.replace("discord.com", "webhook.lewisakura.moe")

    for i in range(0, len(embeds), batch_size):
        batch = embeds[i : i + batch_size]
        batch_metas = [e.pop("_meta", {}) for e in batch]

        payload = {"embeds": batch}
        if username:
            payload["username"] = username
        if avatar_url:
            payload["avatar_url"] = avatar_url
        response = requests.post(webhook_url, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        for j, embed in enumerate(batch):
            rss_url = batch_metas[j].get("rss_url")
            state[rss_url] = embed["timestamp"]

        time.sleep(1)


def iso_to_datetime(value):
    """
    Converts an ISO 8601 string to a timezone-aware datetime in UTC.
    If parsing fails, returns None.
    """
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
    """Main entry point of the script."""
    config = load_json(CONFIG_PATH, {})
    if not config or "channels" not in config:
        logging.error(
            "%s missing or invalid. Please copy config.json.example to config.json and fill in your webhook URLs.",
            CONFIG_PATH,
        )
        sys.exit(1)

    state = load_json(STATE_PATH, {}) or {}
    state["_last_run"] = datetime.now(timezone.utc).isoformat()

    for channel in config.get("channels", []):
        channel_name = channel.get("name")
        if not channel.get("discord_webhook_url"):
            logging.warning("Skipping channel '%s': missing webhook URL.", channel_name)
            continue

        channel_embeds: list[dict] = []
        for rss_url in channel.get("rss_feed_urls", []):
            try:
                feed = fetch_feed(rss_url)
            except Exception as exc:
                logging.error("Failed to fetch %s: %s", rss_url, exc)
                continue

            stored_dt = iso_to_datetime(state.get(rss_url)) or (
                datetime.now(timezone.utc) - timedelta(days=1)
            )

            for entry in feed.entries:
                entry_dt = parse_datetime(entry)
                if not entry_dt or (stored_dt is not None and entry_dt <= stored_dt):
                    continue  # skip because it is outdated
                try:
                    embed = build_embed(entry, rss_url, entry_dt)
                    channel_embeds.append(embed)
                except Exception as exc:
                    logging.error(
                        "Error building embed for entry %s: %s",
                        entry.get("link"),
                        exc,
                    )
                    continue

        if channel_embeds:
            channel_embeds.sort(key=lambda e: e["timestamp"])  # oldest to newest
            try:
                # Merge global config with channel-specific settings, giving precedence to channel settings
                merged_settings = {**config, **channel}
                merged_settings.pop("channels", None)
                post_embeds(merged_settings, channel_embeds, state)
            except Exception as exc:
                logging.error(
                    "Failed to post embeds for channel %s: %s", channel_name, exc
                )

    save_json(STATE_PATH, state)
    logging.info("State updated: %s", STATE_PATH)


if __name__ == "__main__":
    main()
