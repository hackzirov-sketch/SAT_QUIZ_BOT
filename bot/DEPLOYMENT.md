# SAT Quiz Bot Deployment

## Local Run

```bash
cd bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m bot.main
```

## Ubuntu VPS

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv
cd /var/www/sat-quiz-bot/bot
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env
.venv/bin/python -m bot.main
```

## systemd

Create `/etc/systemd/system/sat-quiz-bot.service`:

```ini
[Unit]
Description=SAT Quiz Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/var/www/sat-quiz-bot
EnvironmentFile=/var/www/sat-quiz-bot/bot/.env
ExecStart=/var/www/sat-quiz-bot/bot/.venv/bin/python -m bot.main
Restart=always
RestartSec=5
User=www-data

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sat-quiz-bot
sudo journalctl -u sat-quiz-bot -f
```

## Production Notes

- Rotate the Telegram token if it was ever shared publicly.
- Use polling for simple VPS deployments. Use webhook only with HTTPS and a strong `WEBHOOK_SECRET`.
- Pin Render/PaaS Python to 3.11 using `.python-version` or `PYTHON_VERSION=3.11.11`; Python 3.14 can force `pydantic-core` to build from Rust source.
- If you run a second Render service for the same repo, set `BOT_POLLING_ENABLED=0` there so only one service polls Telegram.
- Keep `bot/data/*.db*` and `.env` out of Git.
- Back up `bot/data/quiz_bot.db` regularly.

## Weekly Group Reports

The bot can post weekly quiz ratings and duel results to a Telegram group.

1. Add the bot to the group.
2. Send `/admin weekly_on` inside that group from an admin account.
3. Test immediately with `/admin weekly`.
4. Disable later with `/admin weekly_off`.

Default schedule is Monday 09:00 in `TZ=Asia/Tashkent`. Change it in `.env`:

```env
WEEKLY_REPORT_ENABLED=1
WEEKLY_REPORT_WEEKDAY=0
WEEKLY_REPORT_HOUR=9
WEEKLY_REPORT_MINUTE=0
```
