# Installing paperboy

This walks through a clean install on a Linux host with systemd. If you've
read the README quickstart and want more detail (or you hit a snag), this is
the page.

## Prereqs

### 1. A Linux box with systemd

Any small VPS works. Lightsail, Digital Ocean, Hetzner, Raspberry Pi, your old
laptop — anything that runs systemd. Tested on:

- Ubuntu 22.04 / 24.04
- Debian 12

### 2. Python 3.10+

```bash
python3 --version    # should report 3.10 or newer
```

If you're on Debian/Ubuntu and need it:

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
```

### 3. Ollama

[Install Ollama](https://ollama.com/download/linux):

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Pull two models — a fast one for the news drafter and a stronger one for paper
scoring:

```bash
ollama pull llama3.2:3b     # ~2GB, runs on any GPU or CPU
ollama pull qwen2.5:7b      # ~4.5GB, needs ~6GB VRAM (or use CPU)
```

Verify they're loaded:

```bash
curl -s http://127.0.0.1:11434/api/tags | python3 -m json.tool
```

If you don't have a GPU, the paper scorer will still work but each paper takes
~30s to score instead of ~3s. With ~80 papers a day, that's a 40-minute job
overnight — fine for a daily timer.

### 4. A Discord webhook

In your Discord server, go to:

> Server Settings → Integrations → Webhooks → New Webhook

Copy the URL. You'll paste it into `/etc/paperboy/paperboy.env` in a moment.

Alternative: a bot token. If you want richer formatting (no "via webhook"
label, no rate limit on long messages), create a Discord bot at
https://discord.com/developers/applications, grab its token, and the channel
ID where you want posts. Set `DISCORD_BOT_TOKEN` + `DISCORD_CHANNEL_ID` and
paperboy will use the bot path automatically.

## Install

```bash
git clone https://github.com/cgallic/paperboy.git
cd paperboy
sudo ./scripts/bootstrap.sh
```

The bootstrap script:

1. Creates a venv at `/opt/paperboy/.venv` and pip-installs paperboy into it.
2. Copies example configs into `/etc/paperboy/`.
3. Initializes the SQLite database at `/var/lib/paperboy/events.db`.
4. Installs all 8 systemd units to `/etc/systemd/system/`.
5. Enables all 7 timers.

It's idempotent — safe to re-run if you change something.

## Configure

### `/etc/paperboy/paperboy.env`

The only REQUIRED change is setting your Discord webhook:

```bash
sudo nano /etc/paperboy/paperboy.env
```

Set:

```
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
```

Everything else has sensible defaults. See `config/env.example` in the repo
for all knobs.

### `/etc/paperboy/research-interests.md`

This is **the most important file**. The paper scorer reads it on every run
and uses it to decide which papers are relevant to YOU.

Without good content here, the scorer will rank everything 3-5/10. With good
content, you'll get genuine signal — papers that actually apply to YOUR stack.

Edit it:

```bash
sudo nano /etc/paperboy/research-interests.md
```

Replace the placeholder slugs with YOUR actual systems. Be concrete:

```markdown
- **`my-rag`** — semantic search over my Obsidian vault.
  Uses nomic-embed-text + Qdrant.
```

The scorer uses these slugs verbatim in its `applies_to` output. Anything
under "Active themes" and "Tech stack" feeds into the LLM's reasoning.

### `/etc/paperboy/news_sources.yaml`

Add the RSS feeds you actually care about. The default has AI/ML feeds; swap
or augment with your verticals.

Rule of thumb: 3-5 high-signal feeds per vertical. Generic firehoses (HN RSS,
Google News) drown the deduper in noise.

### `/etc/paperboy/topical-map.md` (optional)

Your "questions I want to answer publicly" list, grouped by content pillar.
The `topical_questions` scanner rotates 2/day into your morning digest.

If you don't write content, you can disable this:

```bash
sudo systemctl disable --now paperboy-topical-questions.timer
```

### Daily briefs (optional)

If you want the `🎯 today` section to surface things, drop a markdown file
at `~/.paperboy/daily-briefs/<YYYY-MM-DD>.md` each morning. See
`config/daily-brief.md.example` for the format.

Most users skip this. The other six scanners work fine without it.

## Verify

Check the timers are enabled:

```bash
systemctl list-timers | grep paperboy
```

You should see 7 timers ticking. Run the news scanner once manually:

```bash
sudo systemctl start paperboy-news-opinion.service
sudo journalctl -u paperboy-news-opinion.service -n 20
```

If you see `news_opinion: N prompts emitted`, you're good. Check Discord
tomorrow morning at 11:15 UTC.

To trigger the morning digest right now (e.g. to test):

```bash
sudo systemctl start paperboy-prompt-digest.service
```

## Troubleshooting

### "No DISCORD_WEBHOOK configured"

Check `/etc/paperboy/paperboy.env` actually has the variable set without
quotes:

```bash
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
```

Then restart the service.

### Scanner runs but no posts

The bot is conservative — by default it won't post if there are no fresh
prompts (last 48h). Run `news-opinion` manually first to seed some.

### Ollama "connection refused"

Make sure Ollama is running and bound to 127.0.0.1:11434:

```bash
sudo systemctl status ollama
curl http://127.0.0.1:11434/api/tags
```

If it's on a different host, set `OLLAMA_URL=http://...` in your env file.

### Paper scoring is slow

That's expected on CPU. The scorer hits a 240-second timeout per paper by
default. Either:

- Use a smaller scoring model: `PAPERBOY_RESEARCH_MODEL=llama3.2:3b`
- Run it on a machine with a GPU
- Set `PAPERS_LOOKBACK_HOURS=12` to score fewer papers per night

### Database is locked

You might be running two scanners simultaneously. The timers are staggered
(11:00, 11:05, 11:08, 11:10, 11:15) specifically to avoid this. If you start
several services manually at once, expect contention — SQLite will retry but
might log warnings.

## Updating

```bash
cd /path/to/paperboy
git pull
sudo /opt/paperboy/.venv/bin/pip install --upgrade -e .
```

Your `/etc/paperboy/*` configs are untouched.

## Uninstalling

```bash
for t in news-opinion research-ingest research-score papers-to-prompts \
         topical-questions today-briefing prompt-digest research-digest; do
    sudo systemctl disable --now "paperboy-${t}.timer"
    sudo rm /etc/systemd/system/paperboy-${t}.{service,timer}
done
sudo systemctl daemon-reload
sudo rm -rf /opt/paperboy /etc/paperboy /var/lib/paperboy
```
