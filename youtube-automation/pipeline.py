"""Faceless Hindi explainer video pipeline.

topic -> script (Claude) -> Hindi voiceover (edge-tts) -> slides (Pillow) -> video (ffmpeg) -> private upload (YouTube API)

Usage:
  python pipeline.py make "topic" [--notes "..."]   # script + voice + video
  python pipeline.py batch topics.csv               # make for every row
  python pipeline.py shorts output/<slug>          # cut 3 vertical Shorts from the script
  python pipeline.py upload output/<slug>           # upload as PRIVATE after you review
"""
import argparse, asyncio, csv, json, os, re, subprocess, sys
from pathlib import Path

W, H = 1920, 1080
OUT = Path("output")
FONT = os.environ.get("HINDI_FONT", "fonts/NotoSansDevanagari-Bold.ttf")
VOICE = os.environ.get("HINDI_VOICE", "hi-IN-SwaraNeural")  # or hi-IN-MadhurNeural
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

PROMPT = """You write scripts for faceless Hindi explainer videos on YouTube.
Topic: {topic}
Notes: {notes}

This is a "explained simply" video about everyday money, rules, rights or how things work in India.
Write in simple, conversational Hindi (Devanagari). Use a concrete worked example with numbers or a real-life
situation, and a clear point of view, not a generic summary. Open with a hook in the first sentence, build in
logical steps, end with a takeaway. For money, legal or health topics say once that this is general information,
not professional advice, and that rules can change. Target 5-7 minutes
(about 700-900 words of narration). State only facts you are confident are correct; where unsure, say so
in the narration. Return ONLY JSON:
{{"title": "...(under 70 chars, Hindi)", "description": "...(Hindi, 2-3 short paragraphs)",
 "tags": ["..."],
 "scenes": [{{"heading": "short on-screen heading", "bullets": ["max 3 short points"], "narration": "spoken text"}}]}}
Use 8-12 scenes."""


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "video"


def write_script(topic, notes, d):
    import anthropic
    msg = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=8000,
        messages=[{"role": "user", "content": PROMPT.format(topic=topic, notes=notes or "-")}])
    text = msg.content[0].text
    data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    (d / "script.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


async def _tts(text, path):
    import edge_tts
    await edge_tts.Communicate(text, VOICE).save(str(path))


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def wrap(draw, text, font, width):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur); cur = word
    return lines + [cur] if cur else lines


def slide(scene, path, size=(W, H)):
    from PIL import Image, ImageDraw, ImageFont
    w, h = size
    img = Image.new("RGB", size, (18, 32, 56))
    d = ImageDraw.Draw(img)
    k = w / W
    big, small = ImageFont.truetype(FONT, int(84 * k * (1.3 if h > w else 1))), ImageFont.truetype(FONT, int(54 * k * (1.3 if h > w else 1)))
    y = int(150 * k) if h <= w else 300
    for line in wrap(d, scene["heading"], big, w - 160):
        d.text((80, y), line, font=big, fill=(255, 200, 60)); y += int(big.size * 1.3)
    y += 40
    for b in scene.get("bullets", [])[:3]:
        for i, line in enumerate(wrap(d, b, small, w - 200)):
            d.text((80, y), ("• " if i == 0 else "  ") + line, font=small, fill=(240, 240, 240))
            y += int(small.size * 1.5)
        y += 20
    img.save(path)


def build_video(data, d, name="video", size=(W, H)):
    clips = []
    for i, sc in enumerate(data["scenes"]):
        mp3, png, mp4 = d / f"{name}_s{i}.mp3", d / f"{name}_s{i}.png", d / f"{name}_s{i}.mp4"
        asyncio.run(_tts(sc["narration"], mp3))
        slide(sc, png, size)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(png), "-i", str(mp3),
                        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", "24",
                        "-c:a", "aac", "-shortest", str(mp4)], check=True)
        clips.append(mp4)
    lst = d / f"{name}_list.txt"
    lst.write_text("".join(f"file '{c.name}'\n" for c in clips))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(d / f"{name}.mp4")], check=True)
    return d / f"{name}.mp4"


SHORTS_PROMPT = """From this Hindi explainer script, pick the {n} most useful or surprising points and write one YouTube
Short for each. Each Short: hook in the first line, one clear point, spoken length 30-45 seconds (80-110 Hindi
words in total), 3-4 scenes, and a last line inviting viewers to watch the full video. Stay faithful to the
facts in the script. Return ONLY JSON:
{{"shorts": [{{"title": "...(Hindi, under 60 chars)", "scenes": [{{"heading": "...", "bullets": ["max 2 short points"], "narration": "..."}}]}}]}}

Script:
{script}"""


def make_shorts(d, n=3):
    import anthropic
    d = Path(d)
    sp = d / "shorts.json"
    if not sp.exists():
        script = (d / "script.json").read_text(encoding="utf-8")
        msg = anthropic.Anthropic().messages.create(model=MODEL, max_tokens=6000,
            messages=[{"role": "user", "content": SHORTS_PROMPT.format(n=n, script=script)}])
        text = msg.content[0].text
        sp.write_text(json.dumps(json.loads(text[text.index("{"): text.rindex("}") + 1]), ensure_ascii=False, indent=2), encoding="utf-8")
    for i, sh in enumerate(json.loads(sp.read_text(encoding="utf-8"))["shorts"], 1):
        v = build_video(sh, d, f"short{i}", (1080, 1920))
        print(f"Short {i}: {v} ({duration(v):.0f}s)")


def make(topic, notes=""):
    d = OUT / slugify(topic); d.mkdir(parents=True, exist_ok=True)
    sp = d / "script.json"
    data = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else write_script(topic, notes, d)
    v = build_video(data, d)
    print(f"Done: {v} ({duration(v)/60:.1f} min). Review script.json and the video, then run: "
          f"python pipeline.py upload {d}")


def upload(d, kids=False):
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    d = Path(d); tok = Path("token.json")
    creds = Credentials.from_authorized_user_file(tok, scopes) if tok.exists() else None
    if not creds or not creds.valid:
        creds = InstalledAppFlow.from_client_secrets_file("client_secret.json", scopes).run_local_server(port=0)
        tok.write_text(creds.to_json())
    yt = build("youtube", "v3", credentials=creds)
    data = json.loads((d / "script.json").read_text(encoding="utf-8"))
    jobs = [(d / "video.mp4", data["title"], data["description"], data["tags"])]
    sf = d / "shorts.json"
    if sf.exists():
        for i, sh in enumerate(json.loads(sf.read_text(encoding="utf-8"))["shorts"], 1):
            if (d / f"short{i}.mp4").exists():
                jobs.append((d / f"short{i}.mp4", sh["title"] + " #Shorts", data["description"] + "\n\n#Shorts", data["tags"]))
    for f, title, desc, tags in jobs:
        _upload_one(yt, f, title, desc, tags, kids)


def _upload_one(yt, f, title, desc, tags, kids):
    from googleapiclient.http import MediaFileUpload
    body = {"snippet": {"title": title, "description": desc,
                        "tags": tags, "categoryId": "27", "defaultLanguage": "hi"},
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": kids}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(f), resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    print(f"{f.name} uploaded as PRIVATE: https://youtu.be/" + resp["id"] + " - review in YouTube Studio, then publish.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make"); m.add_argument("topic"); m.add_argument("--notes", default="")
    sh = sub.add_parser("shorts"); sh.add_argument("dir"); sh.add_argument("-n", type=int, default=3)
    b = sub.add_parser("batch"); b.add_argument("csv")
    u = sub.add_parser("upload"); u.add_argument("dir"); u.add_argument("--kids", action="store_true", help="declare Made for Kids")
    a = ap.parse_args()
    if a.cmd == "make": make(a.topic, a.notes)
    elif a.cmd == "shorts": make_shorts(a.dir, a.n)
    elif a.cmd == "upload": upload(a.dir, a.kids)
    else:
        for r in csv.DictReader(open(a.csv, encoding="utf-8")): make(r["topic"], r.get("notes", ""))
