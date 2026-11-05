"""Narration with Piper, a free offline neural voice (more natural than the Windows voices in tts.ps1).

    pip install piper-tts
    python -m piper.download_voices en_US-ljspeech-high --data-dir <voices dir>
    python tts_piper.py <voices dir>/en_US-ljspeech-high.onnx [length_scale]

Use a voice whose training data allows public use: en_US-ljspeech is trained on the public-domain
LJ Speech dataset. Some Piper voices (e.g. en_US-lessac) come from research-only datasets."""
import json
import sys
import wave
from pathlib import Path

from piper import PiperVoice, SynthesisConfig

HERE = Path(__file__).parent
model = sys.argv[1]
pace = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0  # < 1 speaks faster

voice = PiperVoice.load(model)
config = SynthesisConfig(length_scale=pace)
for scene in json.loads((HERE / "scenes.json").read_text("utf-8")):
    out = HERE / f"audio_{scene['id']}.wav"
    with wave.open(str(out), "wb") as wav:
        voice.synthesize_wav(scene["speech"], wav, syn_config=config)
    print("wrote", out.name)
