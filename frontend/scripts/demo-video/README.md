# Narrated demo video

Records a guided, narrated walkthrough of every page of the console (synthetic data) as an MP4.

1. Tools (one-time, outside the repo): an `ffmpeg` binary (or `npm i ffmpeg-static`), and Piper for offline narration
   (`pip install piper-tts`, then `python -m piper.download_voices en_US-amy-medium`).
2. Build the preview: `npm run build:preview`
3. Rehearse (checks every click in about a minute, no video): `DEMO_FAST=1 node scripts/demo-video/record.mjs out`
4. Record:
   ```bash
   DEMO_FFMPEG=/path/to/ffmpeg DEMO_PIPER_PY=/path/to/python DEMO_VOICE=/path/to/en_US-amy-medium.onnx \
     node scripts/demo-video/record.mjs out
   ```
   Output: `out/ai-cfo-demo.mp4` and `out/chapters.txt`. Narration is generated on this machine; no text is sent anywhere.

Scenes, captions and narration live in `record.mjs` (`DESKTOP`, `MOBILE`, `OUTRO`). Edit them and re-run after UI changes.
