"""Generate narration clips offline with Piper. Usage: tts.py <voice.onnx> <lines.json> <out_dir>"""

import json
import sys
import wave
from pathlib import Path

from piper import PiperVoice

voice = PiperVoice.load(sys.argv[1])
lines = json.loads(Path(sys.argv[2]).read_text())
out = Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
durations = {}
for key, text in lines.items():
    path = out / f"{key}.wav"
    with wave.open(str(path), "wb") as w:
        voice.synthesize_wav(text, w)
    with wave.open(str(path), "rb") as r:
        durations[key] = round(r.getnframes() / r.getframerate() * 1000)
(out / "durations.json").write_text(json.dumps(durations))
print(f"{len(durations)} clips, {sum(durations.values()) / 1000:.0f} s of narration")
