#!/bin/bash
# HAMSVIC Office — Video Assembly Pipeline
# Combines screen recording, captions, intro/outro into final-demo.mp4
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== HAMSVIC Office Video Assembly ==="
echo ""

# ── Directories ──
RECORDINGS="recordings"
SCREENSHOTS="screenshots"
FRAMES="frames"
mkdir -p "$FRAMES"

# ── Step 1: Create intro and outro frames ──
echo "[Step 1] Generating intro and outro frames..."

# Intro frame (5 seconds)
ffmpeg -y -f lavfi -i color=c=0x1e1b4b:s=1920x1080:d=5 \
  -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:\
text='HAMSVIC Office':fontsize=80:fontcolor=white:\
x=(w-text_w)/2:y=(h-text_h)/2-60,\
drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:\
text='Build Smarter, Estimate Faster':fontsize=36:fontcolor=0xA5B4FC:\
x=(w-text_w)/2:y=(h-text_h)/2+60,\
drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:\
text='Product Demo':fontsize=28:fontcolor=0x818CF8:\
x=(w-text_w)/2:y=(h-text_h)/2+120" \
  -c:v libx264 -preset fast -pix_fmt yuv420p \
  "$FRAMES/intro.mp4" 2>/dev/null

echo "  Intro frame created"

# Outro frame (5 seconds)
ffmpeg -y -f lavfi -i color=c=0x1e1b4b:s=1920x1080:d=5 \
  -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:\
text='Start Your Free Trial Today':fontsize=60:fontcolor=white:\
x=(w-text_w)/2:y=(h-text_h)/2-80,\
drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:\
text='hamsvic.com':fontsize=48:fontcolor=0xA5B4FC:\
x=(w-text_w)/2:y=(h-text_h)/2+20,\
drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:\
text='Build Smarter. Estimate Faster.':fontsize=28:fontcolor=0x818CF8:\
x=(w-text_w)/2:y=(h-text_h)/2+100" \
  -c:v libx264 -preset fast -pix_fmt yuv420p \
  "$FRAMES/outro.mp4" 2>/dev/null

echo "  Outro frame created"

# ── Step 2: Convert raw recording to standard MP4 ──
echo "[Step 2] Converting recording to MP4..."

RAW_VIDEO="$RECORDINGS/raw-demo.webm"
if [ ! -f "$RAW_VIDEO" ]; then
  echo "  ERROR: $RAW_VIDEO not found!"
  exit 1
fi

ffmpeg -y -i "$RAW_VIDEO" \
  -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p \
  -r 30 \
  "$FRAMES/main.mp4" 2>/dev/null

echo "  Main recording converted"

# ── Step 3: Create screenshot slideshow as additional footage ──
echo "[Step 3] Creating screenshot slideshow..."

SLIDE_IMGS=()
for img in "$SCREENSHOTS"/*.png; do
  [ -f "$img" ] && SLIDE_IMGS+=("$img")
done

if [ ${#SLIDE_IMGS[@]} -gt 0 ]; then
  # Create a file list for ffmpeg concat
  > "$FRAMES/slideshow_input.txt"
  for img in "${SLIDE_IMGS[@]}"; do
    echo "file '$(realpath "$img")'" >> "$FRAMES/slideshow_input.txt"
    echo "duration 3" >> "$FRAMES/slideshow_input.txt"
  done
  # Add last image again for proper ending
  echo "file '$(realpath "${SLIDE_IMGS[-1]}")'" >> "$FRAMES/slideshow_input.txt"

  ffmpeg -y -f concat -safe 0 -i "$FRAMES/slideshow_input.txt" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black" \
    -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p \
    -r 30 \
    "$FRAMES/slideshow.mp4" 2>/dev/null

  echo "  Slideshow created from ${#SLIDE_IMGS[@]} screenshots"
fi

# ── Step 4: Concatenate intro + main recording + outro ──
echo "[Step 4] Concatenating final video..."

cat > "$FRAMES/concat_list.txt" << EOF
file 'intro.mp4'
file 'main.mp4'
file 'outro.mp4'
EOF

ffmpeg -y -f concat -safe 0 -i "$FRAMES/concat_list.txt" \
  -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p \
  -r 30 \
  "$FRAMES/combined.mp4" 2>/dev/null

echo "  Videos concatenated"

# ── Step 5: Add captions (burn into video) ──
echo "[Step 5] Adding captions..."

CAPTIONS="captions.srt"
if [ -f "$CAPTIONS" ]; then
  ffmpeg -y -i "$FRAMES/combined.mp4" \
    -vf "subtitles=$CAPTIONS:force_style='FontSize=22,FontName=DejaVu Sans,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,BackColour=&H80000000,MarginV=40'" \
    -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p \
    -c:a copy \
    "final-demo.mp4" 2>/dev/null
  echo "  Captions burned into video"
else
  cp "$FRAMES/combined.mp4" "final-demo.mp4"
  echo "  No captions file found, skipping"
fi

# ── Step 6: Generate voice placeholder ──
echo "[Step 6] Voice generation status..."

if [ -n "$OPENAI_API_KEY" ] || [ -n "$ELEVEN_LABS_API_KEY" ]; then
  echo "  TTS API key found — voice generation available"
  echo "  Run: python3 generate-voice.py"
elif command -v espeak-ng &>/dev/null; then
  echo "  Using espeak-ng for local TTS..."
  espeak-ng -v en-us -f narration.txt -w voice.mp3 2>/dev/null && \
    echo "  Voice generated with espeak-ng" || \
    echo "  espeak-ng failed, no voice generated"
else
  echo "  No TTS service available."
  echo "  To add voice:"
  echo "    export OPENAI_API_KEY=sk-..."
  echo "    python3 generate-voice.py"
fi

# ── Step 7: Combine video + voice if voice exists ──
if [ -f "voice.mp3" ]; then
  echo "[Step 7] Combining video and voice..."
  mv final-demo.mp4 "$FRAMES/video-only.mp4"
  ffmpeg -y -i "$FRAMES/video-only.mp4" -i voice.mp3 \
    -c:v copy -c:a aac -b:a 192k \
    -shortest \
    final-demo.mp4 2>/dev/null
  echo "  Video + voice combined"
fi

# ── Final Report ──
echo ""
echo "=== Assembly Complete ==="
echo ""
if [ -f "final-demo.mp4" ]; then
  SIZE=$(du -h final-demo.mp4 | cut -f1)
  DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 final-demo.mp4 2>/dev/null | cut -d. -f1)
  echo "  Output: final-demo.mp4 ($SIZE, ${DURATION}s)"
fi
echo ""
echo "Files in youtube-demo/:"
ls -lh final-demo.mp4 captions.srt narration.txt 2>/dev/null
echo ""
echo "Missing voice? Set one of these environment variables and re-run:"
echo "  export OPENAI_API_KEY=sk-..."
echo "  export ELEVEN_LABS_API_KEY=..."
echo "Then run: python3 generate-voice.py && bash assemble-video.sh"
