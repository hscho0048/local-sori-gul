import tempfile
import unittest
from pathlib import Path

from library import Library, keywords


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.lib = Library(Path(self.folder.name) / "notes.db")

    def tearDown(self):
        self.lib.close()
        self.folder.cleanup()

    def test_create_update_delete(self):
        note = self.lib.create("출시 회의", "audio", "출시일은 십일월 십오일로 확정됐습니다.")
        self.lib.update(note, title="새 제목", transcript="새 본문", duration=12.5)
        row = self.lib.get(note)
        self.assertEqual((row["title"], row["transcript"], row["duration"]), ("새 제목", "새 본문", 12.5))
        with self.assertRaises(ValueError):
            self.lib.update(note, summary="회의록")
        self.lib.delete(note)
        self.assertIsNone(self.lib.get(note))

    def test_audio_is_copied_and_removed(self):
        source = Path(self.folder.name) / "talk.mp3"
        source.write_bytes(b"abc")
        note = self.lib.create("녹음", "audio", "", audio=source)
        copied = self.lib.audio_path(self.lib.get(note))
        self.assertTrue(copied.exists() and copied.name.endswith("-talk.mp3"))
        self.lib.delete(note)
        self.assertFalse(copied.exists())

    def test_attach_audio_finishes_a_live_note_but_never_replaces_existing_audio(self):
        wav = Path(self.folder.name) / "live.wav"
        wav.write_bytes(b"RIFF" + bytes(60))
        note = self.lib.create("실시간 전사", "live")
        name = self.lib.attach_audio(note, wav)
        self.assertTrue(name.endswith("-live.wav"))
        self.assertTrue(self.lib.audio_path(self.lib.get(note)).exists())
        self.assertEqual(self.lib.get(note)["source"], "audio")
        self.assertIsNone(self.lib.attach_audio(note, wav))
        self.assertEqual(self.lib.get(note)["audio"], name)

    def test_folders_star_trash_and_views(self):
        work = self.lib.create_folder("회의")
        a = self.lib.create("주간 회의", "audio", "예산 회의 예산 확정")
        b = self.lib.create("녹음 중", "live")
        self.lib.update(a, folder_id=work, starred=True)
        ids = lambda view, q="": [n["id"] for n in self.lib.list(view, q)]
        self.assertEqual(ids("all"), [b, a])
        self.assertEqual(ids("starred"), [a])
        self.assertEqual(ids("live"), [b])
        self.assertEqual(ids(f"folder:{work}"), [a])
        self.assertEqual(ids("all", "예산"), [a])
        self.assertEqual(self.lib.list("all")[1]["folder"], "회의")
        self.lib.update(b, trashed=True)
        self.assertEqual((ids("all"), ids("trash"), ids("live")), ([a], [b], []))
        self.lib.update(b, trashed=False)
        self.assertEqual(ids("trash"), [])
        self.lib.delete_folder(work)
        self.assertIsNone(self.lib.get(a)["folder_id"])
        self.assertEqual(list(self.lib.folders()), [])
        with self.assertRaises(ValueError):
            self.lib.create_folder("  ")

    def test_a_new_note_can_start_in_a_folder_that_still_exists(self):
        work = self.lib.create_folder("회의")
        self.assertEqual(self.lib.get(self.lib.create("안건", "audio", folder_id=work))["folder_id"], work)
        self.lib.delete_folder(work)
        self.assertIsNone(self.lib.get(self.lib.create("안건", "live", folder_id=work))["folder_id"])  # deleted meanwhile

    def test_keywords_strip_particles_and_skip_filler(self):
        text = "화자 1: 예산 회의에서 예산을 확정했습니다. 그리고 회의가 길었습니다. 예산"
        self.assertEqual(keywords(text, 2), ["예산", "회의"])
        self.assertNotIn("그리고", keywords(text, 10))
        self.assertNotIn("화자", keywords(text, 10))
        self.assertEqual(keywords(""), [])

    def test_concurrent_first_open_of_a_new_database(self):
        # an installed app's first page load opens several connections at once on a database that does not exist yet
        import threading
        errors = []

        def open_close(path):
            try:
                Library(path).close()
            except Exception as error:
                errors.append(error)
        for _ in range(30):
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
                threads = [threading.Thread(target=open_close, args=(Path(folder) / "library" / "notes.db",))
                           for _ in range(5)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
