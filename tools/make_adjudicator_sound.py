#!/usr/bin/env python3
"""Original procedural BHCJExecution foley; no samples, voice, numpy or downloads.

Rebuild: python3 tools/make_adjudicator_sound.py
Preview WAV: python3 tools/make_adjudicator_sound.py --wav /tmp/BHCJExecution.wav
Requires only Python's standard library and ffmpeg with libvorbis.

Timeline (seconds): boots 0.035–1.35; wooden door kick/break 1.39–2.13;
parchment unfolded 2.14–2.93; low, airless thud 3.03–3.94; cut to silence.
No simulated speech: the judgement is conveyed by the role's separate text.
PCM is deterministic; OGG bytes are deterministic with the same ffmpeg/libvorbis
build (codec upgrades may change bytes). Nothing is recorded or sampled.
"""
from __future__ import annotations

import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / 'data' / 'BHCJExecution.ogg'
SAMPLE_RATE = 44100
DURATION = 4.04
SEED = 0x4248434A
PEAK = 0.74  # -2.62 dBFS before Vorbis, leaving intersample/codec headroom.


def lowpass(values: list[float], hz: float) -> list[float]:
    alpha = 1.0 - math.exp(-2.0 * math.pi * hz / SAMPLE_RATE)
    state, result = 0.0, []
    for value in values:
        state += alpha * (value - state)
        result.append(state)

    return result


def noise(rng: random.Random, count: int, low: float, high: float) -> list[float]:
    raw = [rng.uniform(-1.0, 1.0) for _ in range(count)]
    upper = lowpass(raw, high)
    if low <= 0.0:
        return upper

    lower = lowpass(raw, low)
    return [a - b for a, b in zip(upper, lower)]


def edge(t: float, duration: float, attack: float, release: float) -> float:
    """Sine-squared edge: no waveform discontinuities masquerading as impacts."""
    x = min(1.0, t / attack, (duration - t) / release)
    return math.sin(max(0.0, x) * math.pi / 2.0) ** 2


def synthesize() -> bytes:
    rng = random.Random(SEED)
    frames = round(SAMPLE_RATE * DURATION)
    left, right = [0.0] * frames, [0.0] * frames

    def mix(start: float, samples: list[float], gain: float, pan: float = 0.0,
            room: float = 0.12) -> None:
        # Small stone/wood hallway reflections, NOT an explosive/reverberant boom.
        taps = ((0.0, 1.0, pan), (0.037, room, -pan),
                (0.071, room * 0.57, pan * 0.5), (0.109, room * 0.26, -pan))
        for delay, level, position in taps:
            offset = round((start + delay) * SAMPLE_RATE)
            lg = gain * level * math.sqrt((1.0 - position) / 2.0)
            rg = gain * level * math.sqrt((1.0 + position) / 2.0)
            for i, value in enumerate(samples[:max(0, frames - offset)]):
                left[offset + i] += value * lg
                right[offset + i] += value * rg

    def impact(duration: float, modes: tuple[tuple[float, float, float], ...],
               grit: float, brightness: float) -> list[float]:
        count = round(duration * SAMPLE_RATE)
        rough = noise(rng, count, 100.0, brightness)
        phases = [rng.uniform(-0.16, 0.16) for _ in modes]
        result = []
        for i in range(count):
            t = i / SAMPLE_RATE
            body = sum(amp * math.sin(2.0 * math.pi * hz * t + phase)
                       * math.exp(-t / decay)
                       for (hz, amp, decay), phase in zip(modes, phases))
            scrape = grit * rough[i] * math.exp(-t / 0.035)
            result.append((body + scrape) * edge(t, duration, 0.0018, 0.025))

        return result

    # Heavy boots accelerate toward the listener: sole thump, heel tick, scuff.
    steps = ((0.035, 0.51), (0.307, 0.57), (0.565, 0.63),
             (0.809, 0.69), (1.041, 0.76), (1.250, 0.84))
    for index, (start, gain) in enumerate(steps):
        boot = impact(0.235, ((69 + index * 1.2, 0.85, 0.048),
                             (127, 0.33, 0.029), (267, 0.12, 0.015)), 1.5, 2300)
        mix(start, boot, gain, -0.13 if index % 2 == 0 else 0.13)
        heel = impact(0.07, ((390, 0.20, 0.009), (813, 0.09, 0.006)), 0.65, 3600)
        mix(start + 0.018, heel, gain * 0.55, room=0.05)

    # One forceful kick: broad, damp wood modes, with a second jamb fracture.
    door = impact(0.67, ((57, 0.43, 0.105), (112, 1.0, 0.112),
                         (186, 0.68, 0.083), (317, 0.37, 0.055),
                         (493, 0.23, 0.036), (871, 0.09, 0.024)), 2.1, 3800)
    mix(1.39, door, 1.12, room=0.19)
    for start, gain in ((1.425, 0.68), (1.477, 0.48), (1.558, 0.31),
                        (1.697, 0.19), (1.843, 0.12)):
        chip = impact(0.19, ((rng.uniform(430, 720), 0.44, 0.024),
                             (rng.uniform(1100, 1900), 0.17, 0.013)), 2.9, 6500)
        mix(start, chip, gain, rng.uniform(-0.3, 0.3), room=0.10)

    # Wood fibers briefly give way: irregular friction, not a long noise blast.
    fibers = noise(rng, round(0.43 * SAMPLE_RATE), 240, 2900)
    for i in range(len(fibers)):
        t = i / SAMPLE_RATE
        fibers[i] *= (0.45 + 0.55 * math.sin(2 * math.pi * 31 * t) ** 8) \
                     * math.exp(-t / 0.13) * edge(t, 0.43, 0.009, 0.05)
    mix(1.465, fibers, 0.68, room=0.08)

    # Two dry parchment folds: amplitude-modulated high-pass noise and tiny
    # individual creases; no vowels/formants or intelligible/synthetic speech.
    for start, duration, gain in ((2.14, 0.39, 0.55), (2.47, 0.44, 0.43)):
        paper = noise(rng, round(duration * SAMPLE_RATE), 800, 10000)
        for i in range(len(paper)):
            t = i / SAMPLE_RATE
            folds = 0.27 + 0.73 * math.sin(2 * math.pi * 11 * t + 0.7) ** 6
            paper[i] *= folds * edge(t, duration, 0.025, 0.06)
        mix(start, paper, gain, -0.06, room=0.035)

    for _ in range(17):
        start = rng.uniform(2.19, 2.83)
        crease = impact(0.025, ((rng.uniform(1800, 3400), 0.08, 0.0025),), 0.55, 9000)
        mix(start, crease, 0.16, rng.uniform(-0.15, 0.15), room=0.0)

    # Gavel-like low wooden knock then compressed, airless movement. Detuned
    # decaying modes avoid a musical drone; no vocal growl or thunder sample.
    final = impact(0.53, ((73, 0.9, 0.12), (143, 0.55, 0.072),
                          (227, 0.24, 0.042), (401, 0.10, 0.022)), 0.75, 950)
    mix(3.03, final, 0.9, room=0.07)
    duration = 0.86
    pressure = noise(rng, round(duration * SAMPLE_RATE), 65, 680)
    for i in range(len(pressure)):
        t = i / SAMPLE_RATE
        swell = min(1.0, t / 0.13) * (0.8 + 0.2 * math.sin(2 * math.pi * 5.7 * t))
        pressure[i] = (pressure[i] * 2.0 + 0.17 * math.sin(2 * math.pi * 61 * t)
                       + 0.10 * math.sin(2 * math.pi * 93.3 * t)) \
                      * swell * edge(t, duration, 0.025, 0.008)
    mix(3.08, pressure, 0.63, room=0.0)

    # Gentle saturation rounds transient edges; global peak trim, not clipping
    # or per-event normalization (which would erase the approach dynamics).
    channels = [[math.tanh(v * 0.85) for v in channel] for channel in (left, right)]
    peak = max(abs(v) for channel in channels for v in channel)
    dc = [sum(channel) / frames for channel in channels]
    centered_peak = max(abs(v - dc[c]) for c, channel in enumerate(channels) for v in channel)
    gain = PEAK / max(peak, centered_peak)
    pcm = array('h')
    for i in range(frames):
        t = i / SAMPLE_RATE
        # Explicit final 8ms cut, then 100ms of silence. DC correction also
        # fades here rather than introducing a nonzero endpoint.
        gate = edge(t, DURATION, 0.006, 0.008) if t < 3.94 else 0.0
        if 3.932 < t < 3.94:
            gate *= math.sin((3.94 - t) / 0.008 * math.pi / 2.0) ** 2

        for c in range(2):
            pcm.append(round((channels[c][i] - dc[c]) * gain * gate * 32767))

    if sys.byteorder != 'little':
        pcm.byteswap()

    return pcm.tobytes()


def write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        audio.writeframes(pcm)


def encode_ogg(wav_path: Path, out: Path) -> None:
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-fflags', '+bitexact',
        '-i', str(wav_path), '-map_metadata', '-1', '-vn', '-c:a', 'libvorbis',
        '-q:a', '5', '-flags:a', '+bitexact', '-fflags', '+bitexact', str(out),
    ], check=True)


def metrics(pcm: bytes) -> dict:
    samples = array('h')
    samples.frombytes(pcm)
    if sys.byteorder != 'little':
        samples.byteswap()

    peak = max(abs(x) for x in samples) / 32768.0
    rms = math.sqrt(sum(x * x for x in samples) / len(samples)) / 32768.0
    return {'duration_s': len(samples) / (2 * SAMPLE_RATE),
            'sample_rate': SAMPLE_RATE, 'channels': 2,
            'peak': round(peak, 6), 'peak_dbfs': round(20 * math.log10(peak), 3),
            'rms': round(rms, 6), 'rms_dbfs': round(20 * math.log10(rms), 3),
            'pcm_sha256': hashlib.sha256(pcm).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--wav', type=Path, help='optionally keep PCM for listening; otherwise temporary')
    args = parser.parse_args()
    pcm = synthesize()
    with tempfile.TemporaryDirectory(prefix='bhcj-sound-') as directory:
        wav_path = args.wav if args.wav else Path(directory) / 'BHCJExecution.wav'
        write_wav(wav_path, pcm)
        encode_ogg(wav_path, args.out)

    report = metrics(pcm)
    report.update(ogg_bytes=args.out.stat().st_size,
                  ogg_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest())
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
