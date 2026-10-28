#!/usr/bin/env python3
"""BHCJExecution: deterministic synthesis, real OGG decode and boot2 sound catalog.

Run: python3 tools/test_adjudicator_sound.py
Only a temporary copy of the baseline is modified, using real write_sounds /
sc2map / mpqtool; this is NOT a full map build and never deploys anything.
"""
from __future__ import annotations

from array import array
from collections import Counter
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import boot2_build as build
import make_adjudicator_sound as sound

EVENT = 'BHCJExecution'
MEMBER = r'Assets\Sounds\BHCJExecution.ogg'
ASSET = sound.DEFAULT_OUT


def decode_ogg(path: Path) -> array:
    proc = subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(path),
        '-map', '0:a:0', '-f', 'f32le', '-acodec', 'pcm_f32le', '-',
    ], capture_output=True, check=True)
    samples = array('f')
    samples.frombytes(proc.stdout)
    if sys.byteorder != 'little':
        samples.byteswap()

    return samples


def rms(values) -> float:
    return math.sqrt(sum(v * v for v in values) / len(values))


class AdjudicatorSoundTests(unittest.TestCase):
    def test_sound_catalog_real_mpq_round_trip(self):
        """Exercise production catalog generation, not a hand-made XML fixture."""
        entries = [item for item in build.CUSTOM_SOUNDS if item[0] == EVENT]
        self.assertEqual(len(entries), 1)
        sid, source, member, block = entries[0]
        self.assertEqual(source, ASSET)
        self.assertEqual(member, MEMBER)
        self.assertNotIn('\\\\', member)  # one real slash, not two XML escapes
        self.assertNotIn('\\\\', block)

        with tempfile.TemporaryDirectory(prefix='bhcj-catalog-test-') as directory:
            archive = Path(directory) / 'sounds-only.SC2Map'
            shutil.copy2(build.DEFAULT_BASE, archive)
            original_xml = build.sc2map.read(archive, build.SOUND_DATA)
            with patch.object(build.sc2map, 'write', wraps=build.sc2map.write) as writes:
                with contextlib.redirect_stdout(io.StringIO()):
                    returned = build.write_sounds(archive)

                counts = Counter(call.args[1] for call in writes.call_args_list)
                self.assertTrue(all(count == 1 for count in counts.values()), counts)
                self.assertLessEqual(counts[build.SOUND_DATA], 1)
                self.assertIn(member, returned)
                xml_bytes = build.sc2map.read(archive, build.SOUND_DATA)
                catalog = ET.fromstring(xml_bytes)
                nodes = catalog.findall(f"CSound[@id='{sid}']")
                self.assertEqual(len(nodes), 1)
                node = nodes[0]
                self.assertEqual(node.find('AssetArray').get('File'), member)
                self.assertEqual(node.find('Mode').get('value'), '2D')
                self.assertEqual(node.find('LoopCount').get('value'), '0')
                self.assertEqual(node.find('Category').get('value'), 'Dialogue')
                self.assertEqual(node.find('Volume').get('value'), '0.000000,0.000000')

                # Also apply the production final read-back criteria: event ID
                # AND audio member listed, plus byte equality (stronger check).
                files = [name for _, name in build.sc2map.ls(archive)]
                for event, src, audio_member, _ in build.CUSTOM_SOUNDS:
                    self.assertIn(audio_member, files)
                    self.assertIn(f'id="{event}"', xml_bytes.decode('utf-8'))
                    self.assertEqual(build.sc2map.read(archive, audio_member), src.read_bytes())

                # Every pre-existing catalog object remains byte-for-byte in
                # the XML prefix; rerun adds neither a duplicate nor MPQ bloat.
                prefix = original_xml.decode('utf-8').rstrip().removesuffix('</Catalog>')
                self.assertTrue(xml_bytes.decode('utf-8').startswith(prefix))
                writes.reset_mock()
                with contextlib.redirect_stdout(io.StringIO()):
                    build.write_sounds(archive)

                self.assertEqual(writes.call_count, 0)
                self.assertEqual(build.sc2map.read(archive, build.SOUND_DATA), xml_bytes)

    def test_ogg_integrity_loudness_and_timeline(self):
        probe = json.loads(subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries',
            'stream=codec_name,sample_rate,channels,duration', '-of', 'json', str(ASSET),
        ], capture_output=True, text=True, check=True).stdout)['streams']
        self.assertEqual(len(probe), 1)
        self.assertEqual(probe[0]['codec_name'], 'vorbis')
        self.assertEqual(int(probe[0]['sample_rate']), sound.SAMPLE_RATE)
        self.assertEqual(probe[0]['channels'], 2)
        self.assertAlmostEqual(float(probe[0]['duration']), sound.DURATION, places=3)

        samples = decode_ogg(ASSET)
        frames = len(samples) // 2
        self.assertEqual(frames, round(sound.SAMPLE_RATE * sound.DURATION))
        self.assertTrue(all(math.isfinite(v) for v in samples))
        peak, level = max(abs(v) for v in samples), rms(samples)
        self.assertGreater(peak, 0.60)
        self.assertLess(peak, 0.95, 'Vorbis peak overshoot needs more headroom')
        self.assertGreater(level, 0.055, 'too quiet overall')
        self.assertLess(level, 0.15, 'too loud/compressed overall')
        for channel in (samples[0::2], samples[1::2]):
            self.assertLess(abs(sum(channel) / len(channel)), 0.0015)

        def segment(start, end):
            return samples[round(start * sound.SAMPLE_RATE) * 2:
                           round(end * sound.SAMPLE_RATE) * 2]

        segments = {'boots': segment(0.035, 1.39), 'door': segment(1.39, 2.14),
                    'paper': segment(2.14, 2.95), 'muffled_cut': segment(3.03, 3.94)}
        self.assertGreater(rms(segments['door']), rms(segments['boots']) * 1.5)
        self.assertGreater(rms(segments['paper']), 0.025)
        self.assertGreater(rms(segments['muffled_cut']), 0.05)

        # Dry high-frequency paper vs low-pass airless final sound.
        def roughness(values):
            mono = values[0::2]
            return rms([b - a for a, b in zip(mono, mono[1:])]) / rms(mono)

        self.assertGreater(roughness(segments['paper']),
                           roughness(segments['muffled_cut']) * 3.0)

        # No long dead interval, clipped sample or discontinuity at endpoints.
        longest, run = 0, 0
        for l, r in zip(samples[0::2], samples[1::2]):
            run = run + 1 if max(abs(l), abs(r)) < 0.001 else 0
            longest = max(longest, run)

        self.assertLess(longest / sound.SAMPLE_RATE, 0.18)
        self.assertLess(max(abs(v) for v in segment(0, 0.006)), 0.005)
        self.assertLess(max(abs(v) for v in segment(3.97, 4.04)), 0.0001)
        self.assertGreater(rms(segment(3.78, 3.90)), 0.025)
        self.assertLess(rms(segment(3.95, 4.04)), 0.0001)
        print('\nDecoded audio:', json.dumps({
            'seconds': frames / sound.SAMPLE_RATE, 'peak': round(peak, 6),
            'peak_dbfs': round(20 * math.log10(peak), 3),
            'rms': round(level, 6), 'rms_dbfs': round(20 * math.log10(level), 3),
            'longest_silence_s': round(longest / sound.SAMPLE_RATE, 4),
            'segment_rms_dbfs': {name: round(20 * math.log10(rms(data)), 2)
                                 for name, data in segments.items()},
        }, ensure_ascii=False))

    def test_reproducible_pcm_and_ogg(self):
        first, second = sound.synthesize(), sound.synthesize()
        self.assertEqual(first, second)
        self.assertEqual(len(first), round(sound.SAMPLE_RATE * sound.DURATION) * 4)
        with tempfile.TemporaryDirectory(prefix='bhcj-determinism-test-') as directory:
            wav_path = Path(directory) / 'source.wav'
            out_a, out_b = Path(directory) / 'a.ogg', Path(directory) / 'b.ogg'
            sound.write_wav(wav_path, first)
            sound.encode_ogg(wav_path, out_a)
            sound.encode_ogg(wav_path, out_b)
            self.assertEqual(out_a.read_bytes(), out_b.read_bytes())
            self.assertEqual(out_a.read_bytes(), ASSET.read_bytes(),
                             'asset differs: regenerate with the current ffmpeg/libvorbis build')

        print('\nDeterministic PCM SHA256:', hashlib.sha256(first).hexdigest())
        print('Deterministic OGG SHA256:', hashlib.sha256(ASSET.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main(verbosity=2)
