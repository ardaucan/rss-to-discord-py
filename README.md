# RSS to Discord Python

A lightweight and efficient Python script that monitors multiple RSS feeds and automatically forwards new entries to Discord channels using Webhooks.

## Features

- **Category-Based Routing**: Organize multiple feeds into categories and send them to different Discord channels.
- **Rich Discord Embeds**: Posts content as clean embeds including titles, descriptions, timestamps, and high-quality images.
- **Advanced Image Extraction**: Automatically finds images by checking MediaRSS tags, enclosures, and fallback HTML parsing for `<img>` tags.
- **YouTube Integration**: Detects YouTube links in video-only posts and generates high-quality thumbnails.
- **Smart Snippets**: Clean plain-text descriptions stripped of HTML tags and truncated for optimal Discord viewing.
- **Atomic Persistence**: Uses a `state.json` file to keep track of seen items. State is updated incrementally after each successful batch delivery to prevent duplicates and handle interruptions gracefully.
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
   - `use_proxy`: (Default: `false`) Set to `true` to route Discord requests through a proxy.
   - `batch_size`: (Default: `10`) Number of messages to batch per Discord request (max 10 is recommended).
   - `username`: Global display name for the webhook.
   - `avatar_url`: Global profile picture URL for the webhook.
   - `channels`: **[Required]** List of configuration objects for each Discord channel.
     - `name`: Label used in application logs to identify this group.
     - `discord_webhook_url`: **[Required]** Your Discord Webhook URL.
     - `rss_feed_urls`: **[Required]** A list of RSS feed URLs to monitor for this channel.
     - `username`: Overrides the global username for this specific channel.
     - `avatar_url`: Overrides the global avatar for this specific channel.

## Usage

Run the script:

```bash
python app.py
```

**state.json** file will be created automatically to store the latest seen items. This ensures that only new entries are posted to Discord on subsequent runs.

**Initial Run**: On the first execution, the script will fetch and post entries from the **last 24 hours** to initialize its state.

### Automation

It is recommended to run this script periodically using a task scheduler like `cron`.

Example Cron job (runs every 2 hours):

```cron
0 */2 * * * cd /path/to/rss-to-discord-py && /path/to/rss-to-discord-py/.venv/bin/python3 app.py >> /tmp/rss-dc.log 2>&1
```
