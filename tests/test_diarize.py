import threading
import unittest

import numpy as np

import diarize
from diarize import FRAME, FRAMES, RATE, cluster, fbank, speech_regions, quiet_threshold
from engine import render


def tone(seconds, hz, amplitude=3000, seed=None):
    t = np.arange(int(seconds * RATE)) / RATE
    signal = np.sin(2 * np.pi * hz * t) * amplitude
    if seed is not None:
        signal += np.random.default_rng(seed).standard_normal(len(t)) * amplitude / 3
    return signal.astype(np.int16)


class FeatureTests(unittest.TestCase):
    def test_fbank_shape_frame_count_and_rms(self):
        features, rms = fbank(tone(2.0, 440))
        self.assertEqual(features.shape, ((2 * RATE - FRAME) // 160 + 1, 80))
        self.assertEqual(len(rms), len(features))
        self.assertTrue(np.all(np.isfinite(features)))
        self.assertGreater(rms.mean(), 2000)  # 3000-amplitude sine: RMS ≈ 2121
        quiet, quiet_rms = fbank(np.zeros(RATE, dtype=np.int16))
        self.assertTrue(np.allclose(quiet, np.log(1.1920929e-07)))  # Kaldi epsilon floor, no NaN on silence
        self.assertEqual(quiet_rms.max(), 0)

    def test_speech_regions_split_at_pauses_and_bound_length(self):
        pcm = np.concatenate([tone(3, 300), np.zeros(RATE, dtype=np.int16), tone(2, 300), np.zeros(RATE // 5, dtype=np.int16), tone(1, 300)])
        threshold = quiet_threshold(pcm)
        regions = speech_regions(pcm, threshold)
        self.assertEqual(len(regions), 2)                 # a 1 s pause splits, a 0.2 s pause does not
        self.assertLess(abs(regions[0][0]), RATE // 5)
        self.assertLess(abs(regions[0][1] - 3 * RATE), RATE // 2)
        self.assertLess(abs(regions[1][0] - 4 * RATE), RATE // 2)
        long = tone(130, 300)
        self.assertTrue(all(end - start <= diarize.MAX_REGION for start, end in speech_regions(long, quiet_threshold(long))))


class ClusterTests(unittest.TestCase):
    def test_average_linkage_stops_at_threshold(self):
        rng = np.random.default_rng(0)
        centers = rng.standard_normal((3, 256))
        vectors, truth = [], []
        for label, center in enumerate(centers):
            for _ in range(10):
                v = center + rng.standard_normal(256) * 0.4
                vectors.append(v / np.linalg.norm(v))
                truth.append(label)
        labels = cluster(np.asarray(vectors), threshold=0.5)
        self.assertEqual(len(set(labels)), 3)
        for label in range(3):
            self.assertEqual(len({labels[i] for i in range(30) if truth[i] == label}), 1)
        self.assertEqual(len(set(cluster(np.asarray(vectors), threshold=-1.0))), 1)  # everything merges


class FakeEmbedder:
    """Two 'voices': the embedding depends on the tone frequency, read back from the fbank frames' spectral centroid."""
    def embed(self, features):
        centroid = float(np.argmax(features.mean(axis=0)))
        vector = np.zeros(256, dtype=np.float32)
        vector[0 if centroid < 30 else 1] = 1.0
        return vector


class DiarizeTests(unittest.TestCase):
    def test_two_voices_with_pauses_become_two_speakers_in_order_of_appearance(self):
        gap = np.zeros(RATE, dtype=np.int16)
        pcm = np.concatenate([tone(4, 200), gap, tone(4, 3000), gap, tone(4, 200), gap, tone(3, 3000)])
        spans = diarize.diarize(pcm, FakeEmbedder())
        self.assertEqual([label for _, _, label in spans], [0, 1, 0, 1])
        self.assertEqual(spans[0][0], 0)
        self.assertEqual(spans[-1][1], len(pcm))
        self.assertTrue(all(a[1] == b[0] for a, b in zip(spans, spans[1:])))  # spans tile the recording
        self.assertLess(abs(spans[1][0] - 5 * RATE), RATE)                    # change near the pause, not mid-turn

    def test_speaker_change_without_a_pause_is_still_found(self):
        pcm = np.concatenate([tone(5, 200), tone(5, 3000)])
        spans = diarize.diarize(pcm, FakeEmbedder())
        self.assertEqual([label for _, _, label in spans], [0, 1])
        self.assertLess(abs(spans[1][0] - 5 * RATE), 2 * RATE)

    def test_silence_only_or_one_voice_gives_one_speaker(self):
        self.assertEqual(diarize.diarize(np.zeros(3 * RATE, dtype=np.int16), FakeEmbedder()), [(0, 3 * RATE, 0)])
        self.assertEqual([label for _, _, label in diarize.diarize(tone(6, 200), FakeEmbedder())], [0])

    def test_render_labels_only_when_more_than_one_speaker(self):
        self.assertEqual(render([(0, "안녕하세요."), (0, "반갑습니다.")]), "안녕하세요.\n\n반갑습니다.")
        self.assertEqual(render([(None, "가"), (None, "나")]), "가\n\n나")
        self.assertEqual(render([(0, "안녕하세요."), (0, "반갑습니다."), (1, "네."), (0, "그럼 시작하죠.")]),
                         "화자 1: 안녕하세요. 반갑습니다.\n\n화자 2: 네.\n\n화자 1: 그럼 시작하죠.")


if __name__ == "__main__":
    unittest.main()
