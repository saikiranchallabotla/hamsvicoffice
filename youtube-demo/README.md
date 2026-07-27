# HAMSVIC Office — YouTube Product Demo Video

This folder contains everything needed to produce a professional product demonstration video of HAMSVIC Office.

## Quick Start

```bash
# 1. Set up the environment
pip install -r ../requirements.txt
python3 create_demo_data.py

# 2. Start the Django dev server
cd .. && python3 manage.py runserver 0.0.0.0:8000 &

# 3. Start virtual display (headless environments)
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# 4. Record the browser demo
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node record-demo.js

# 5. (Optional) Generate AI voice narration
export OPENAI_API_KEY=sk-...   # or ELEVEN_LABS_API_KEY=...
python3 generate-voice.py

# 6. Assemble the final video
bash assemble-video.sh
```

## Files

| File | Purpose |
|------|---------|
| `final-demo.mp4` | The finished demo video (1920x1080, H.264, 30fps) |
| `narration.txt` | Full narration script for voice-over |
| `captions.srt` | Subtitle file (SRT format) burned into video |
| `voice.mp3` | Generated voice narration audio |
| `record-demo.js` | Playwright browser automation script |
| `assemble-video.sh` | FFmpeg video assembly pipeline |
| `generate-voice.py` | Text-to-Speech voice generator (multi-provider) |
| `create_demo_data.py` | Django demo data seeder |
| `recordings/` | Raw browser recording (WebM) |
| `screenshots/` | Individual scene screenshots (PNG) |
| `frames/` | Intermediate video frames (intro, outro, etc.) |

## Prerequisites

- **Node.js** 18+ with npm
- **Python** 3.10+ with Django dependencies
- **FFmpeg** (video processing)
- **Playwright** (`npm install playwright`)
- **Chromium** (Playwright-managed or system-installed)
- **Xvfb** (for headless recording on Linux)
- **espeak-ng** (local TTS fallback, optional)

## Regenerating After Website Updates

1. **Update demo data** if new modules or features were added:
   ```bash
   python3 create_demo_data.py
   ```

2. **Re-record the browser demo:**
   ```bash
   # Edit record-demo.js to add new scenes for new features
   node record-demo.js
   ```

3. **Update narration** in `narration.txt` and `captions.srt` to cover new features.

4. **Regenerate voice** (if using AI TTS):
   ```bash
   python3 generate-voice.py
   ```

5. **Re-assemble the video:**
   ```bash
   bash assemble-video.sh
   ```

## Voice Generation

The `generate-voice.py` script tries these providers in order:

1. **OpenAI TTS** (`OPENAI_API_KEY`) — Best quality, natural voice
2. **ElevenLabs** (`ELEVEN_LABS_API_KEY`) — Premium multilingual voices
3. **Google Cloud TTS** (`GOOGLE_APPLICATION_CREDENTIALS`) — Indian English voice
4. **espeak-ng** (local) — Free fallback, robotic but functional

For a professional YouTube video, we recommend OpenAI TTS (`tts-1-hd`, voice: `onyx`) or ElevenLabs for natural-sounding narration.

## Scenes Covered

1. Landing page with branding and tagline
2. OTP-based login flow
3. Dashboard with module overview
4. Estimate creation wizard (work type, category, SOR items)
5. Workslip module
6. Bill generation
7. Self-Formatted Forms
8. Saved Works file manager
9. Temporary Works module
10. AMC (Annual Maintenance Contract) module
11. Letter Settings configuration
12. Pricing page
13. User Profile
14. My Subscription
15. Final dashboard view

## Notes

- No production data is used — all demo data is generated synthetically
- No API keys, passwords, or secrets are exposed in the video
- The video uses demo credentials that only work in development mode
- The OTP popup shown in the login scene only appears in Django DEBUG mode
