"""Spanish narration for the social videos, with the voices built into macOS (free, offline).

speak(text, path) -> seconds      writes an AAC .m4a with `say`
fit(groups) -> (durations, starts) stretches each group of frames so its narration fits
mux(silent_mp4, clips, out_mp4)    lays the clips over the video (mux.swift)
VOICE picks the voice (default Paulina, Mexican Spanish); NOVOICE=1 turns narration off.
"""
import os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
VOICE = os.environ.get("VOICE", "Paulina")
ENABLED = not os.environ.get("NOVOICE")
PAD = 0.6  # silence after each line before the picture changes


def speak(text, path):
    # say -> AIFF, then AAC 48 kHz stereo 128 kbps (what Instagram, Facebook and YouTube recommend)
    raw = path + ".aiff"
    subprocess.run(["say", "-v", VOICE, "-r", "180", "-o", raw, text], check=True, capture_output=True)
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac@48000", "-b", "128000", "-c", "2", raw, path],
                   check=True, capture_output=True)
    os.remove(raw)
    info = subprocess.run(["afinfo", path], capture_output=True, text=True).stdout
    return float(re.search(r"estimated duration: ([\d.]+)", info).group(1))


def fit(groups):
    """groups: [(seconds per frame..., narration seconds)] -> (all frame seconds, start time of each group)."""
    secs, starts, t = [], [], 0.0
    for frames, spoken in groups:
        need = spoken + PAD + 0.2
        have = sum(frames)
        k = max(1.0, need / have) if spoken else 1.0
        starts.append(t + 0.2)
        for s in frames:
            secs.append(round(s * k, 2))
            t += s * k
    return secs, starts


def mux(silent, clips, out):
    args = ["swift", "-suppress-warnings", os.path.join(HERE, "mux.swift"), silent, out]
    for path, start in clips:
        args += [path, f"{start:.2f}"]
    subprocess.run(args, check=True)


END_LINE = "Compara gratis en manda más dinero punto com."
