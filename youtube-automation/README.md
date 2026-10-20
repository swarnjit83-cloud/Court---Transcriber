# Faceless Hindi explainer video pipeline

topic -> script (Claude) -> Hindi voiceover (edge-tts) -> slides (Pillow) -> video (ffmpeg) -> private upload.
Each topic gives one 5-7 minute explainer plus 3 vertical Shorts cut from it.

## Setup
1. `pip install -r requirements.txt`; install `ffmpeg`.
2. Download Noto Sans Devanagari Bold to `fonts/NotoSansDevanagari-Bold.ttf` (or set `HINDI_FONT`).
3. `export ANTHROPIC_API_KEY=...`
4. For upload: create an OAuth "Desktop" client in Google Cloud, enable YouTube Data API v3, save as `client_secret.json`.

## Use
    python pipeline.py make "your topic" --notes "audience and angle"
    python pipeline.py shorts output/<slug>          # 3 vertical Shorts from the same script
    python pipeline.py upload output/<slug>          # uploads video + Shorts as PRIVATE; add --kids only for Made for Kids content

`topics.csv` holds starter topics; run them all with `python pipeline.py batch topics.csv`.

For money, legal or health topics, check every number and rule against an official source (RBI, government sites) before publishing. Always read `script.json` and watch the video before publishing. Add your own examples and opinion; templated
uploads risk demonetisation under YouTube's inauthentic-content policy.

## Weekly 5-hour routine
Research and fact-check topics (1.5h), edit scripts (1.5h), review and fix videos (1h), thumbnails, upload, schedule (1h).

## Hands-off mode (GitHub Actions)
`.github/workflows/weekly-video.yml` runs `python pipeline.py autopilot` every Tuesday and Friday: it picks a new topic
(never repeating `done.json`), writes the script, fact-checks it with a second pass, renders the video plus 3 Shorts and
uploads them. If the fact-check confidence is low, it skips the topic and writes `REVIEW_NEEDED.txt` instead.

One-time setup (about 20 minutes):
1. Run `python pipeline.py upload` once on your computer to sign in to Google; this creates `token.json`.
2. In Google Cloud, set the OAuth consent screen to **In production**, otherwise the login expires after 7 days.
3. In the GitHub repo add secrets `ANTHROPIC_API_KEY`, `YT_CLIENT_SECRET` (contents of `client_secret.json`) and `YT_TOKEN` (contents of `token.json`).
4. Optional repo variables: `NICHE`, and `YT_PRIVACY` (`private` by default).

Limits to know about: YouTube locks videos uploaded through the API to **private** until the Google Cloud project passes
YouTube's API compliance audit, so until then you must tap Publish in YouTube Studio (about 2 minutes a video). Fully
automatic, unreviewed publishing also carries a real risk of factual errors and of demonetisation as mass-produced content.

## Fiction story mode (default for the weekly run, no cost beyond the Claude API)
`python story.py make` writes the next episode of a fictional Hindi series with a recurring cast (`cast.json`), runs a
safety/originality check instead of a fact-check, draws every scene itself (scenery, characters, captions, slow zoom;
no paid image service) and also makes 3 cliffhanger Shorts. `python story.py autopilot` does the same and uploads.
Edit `cast.json` to change the series name and characters. Episodes alternate between light suspense and comedy.
Set the repo variable `MODE=explainer` to run the money/rights explainers instead.
The drawn visuals are deliberately simple; quality comes from the story and voice. Upgrade visuals later if the channel grows.
