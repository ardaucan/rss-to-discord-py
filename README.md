# RSS to Discord Python

A lightweight and efficient Python script that monitors multiple RSS feeds and automatically forwards new entries to Discord channels using Webhooks.

## Features

- **Category-Based Routing**: Organize multiple feeds into categories and send them to different Discord channels.
- **Rich Discord Embeds**: Posts content as clean embeds including titles, descriptions, and high-quality images.
- **Advanced Image Extraction**: Automatically finds images by checking MediaRSS tags, enclosures, and fallback HTML parsing for `<img>` tags.
- **YouTube Integration**: Detects YouTube links in video-only posts and generates high-quality thumbnails.
- **Smart Snippets**: Clean plain-text descriptions stripped of HTML tags and truncated for optimal Discord viewing.
- **Persistence**: Uses a `state.json` file to keep track of seen items and prevent duplicate notifications.
- **Proxy Support**: Optional support for `webhook.lewisakura.moe` proxy to help manage Discord rate limits.

## Prerequisites

- Python 3.8+
- Discord Webhook URL(s)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/rss-to-discord-py.git
   cd rss-to-discord-py
   ```
2. Create a virtual environment (optional):

   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. Create your configuration file from the example:

   ```bash
   cp config.json.example config.json
   ```

2. Edit `config.json` with your specific settings:
   - `use_proxy`: Set to `true` to route Discord requests through the Lewisakura proxy.
   - `categories`: List your feed groups here.
     - `name`: Friendly name for logs.
     - `discord_webhook_url`: Your Discord channel webhook.
     - `rss_feed_urls`: List of RSS feeds to watch for this category.

## Usage

Run the script:

```bash
python app.py
```

**state.json** file will be created automatically to store the latest seen items. This ensures that only new entries are posted to Discord on subsequent runs.

**Initial Run**: On the first execution, the script will only post the **latest** item from each feed to initialize its state without spamming your channel.

### Automation

It is recommended to run this script periodically using a task scheduler like `cron`.

Example Cron job (runs every 2 hours):

```cron
0 */2 * * * cd /path/to/rss-to-discord-py && /path/to/rss-to-discord-py/.venv/bin/python3 app.py >> /tmp/rss-dc.log 2>&1
```
