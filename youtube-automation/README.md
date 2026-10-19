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
