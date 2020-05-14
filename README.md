# zendesk-discord-webhook-bot
Discord Webhook Bot for Zendesk

## Usage

Tested with Python 3.8.2:
```bash
pip3 install -r requirements.txt

export ZDWB_DISCORD_WEBHOOK="https://discordapp.com/api/webhooks/...."
export ZDWB_ZENDESK_EMAIL="richard.hendricks@piedpiper.com"
export ZDWB_ZENDESK_TOKEN="abcdefghijklmnopqrstuvwxyz1234567890"
export ZDWB_ZENDESK_SUBDOMAIN="piedpiper"

python3 bot.py
```

`ZDWB_HISTORY_MINUTES` may also be set as an environment variable to signal the application on first run to collect the number of minutes you specify of historical data from Zendesk to post to the webhook channel.

## Screenshots

![](https://i.cwlf.uk/evKB)

![](https://i.cwlf.uk/AZPl)

![](https://i.cwlf.uk/1rKl)

![](https://i.cwlf.uk/eodb)
