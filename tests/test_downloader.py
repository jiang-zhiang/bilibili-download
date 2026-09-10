import unittest
from bilibili_downloader import normalize_input, validate_free_metadata, build_options


class DownloaderTests(unittest.TestCase):
    def test_bv_and_page(self):
        self.assertEqual(normalize_input(" BV1xx411c7mD "), "https://www.bilibili.com/video/BV1xx411c7mD?p=1")
        self.assertTrue(normalize_input("https://www.bilibili.com/video/BV1xx411c7mD/?p=2&x=1").endswith("?p=2"))

    def test_invalid_inputs(self):
        for value in ("BV123", "https://evil.com/video/BV1xx411c7mD", "https://www.bilibili.com/video/BV1xx411c7mD?p=0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_input(value)

    def test_free_allowed(self):
        validate_free_metadata({"code": 0, "data": {"rights": {"pay": 0, "ugc_pay": 0}}})

    def test_paid_preview_exclusive_blocked(self):
        for key in ("pay", "ugc_pay", "ugc_pay_preview", "is_upower_exclusive", "is_upower_pay", "arc_pay"):
            for location in ("rights", "data"):
                data = {"rights": {"pay": 0}}
                (data["rights"] if location == "rights" else data)[key] = 1
                with self.subTest(key=key, location=location), self.assertRaises(ValueError):
                    validate_free_metadata({"code": 0, "data": data})

    def test_unknown_status_blocked(self):
        for payload in ({}, {"code": -404}, {"code": 0, "data": {}}, {"code": 0, "data": {"rights": {}}}):
            with self.assertRaises(ValueError):
                validate_free_metadata(payload)

    def test_modes_and_no_credentials(self):
        audio = build_options("downloads", "audio", "ffmpeg")
        video = build_options("downloads", "video", "ffmpeg")
        self.assertEqual(audio["format"], "bestaudio")
        self.assertEqual(audio["postprocessors"][0]["preferredcodec"], "mp3")
        self.assertEqual(video["format"], "bestvideo+bestaudio/best")
        for options in (audio, video):
            self.assertNotIn("cookiefile", options)
            self.assertNotIn("cookiesfrombrowser", options)
            self.assertTrue(options["noplaylist"])


if __name__ == "__main__":
    unittest.main()
