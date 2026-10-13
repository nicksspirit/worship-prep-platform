import hashlib
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

HASHED_NAME = re.compile(r"^(?P<stem>.+)\.(?P<hash>[0-9a-f]{12})\.(?P<ext>[a-z0-9]+)$")
CLIENT_DIR = settings.BASE_DIR / "client"
CACHED_FOREVER_DIRS = ("fonts", "images")


def hashed_assets() -> list[Path]:
    """List the files WhiteNoise is allowed to cache for a year."""

    return sorted(
        path
        for directory in CACHED_FOREVER_DIRS
        for path in (settings.BASE_DIR / "static" / directory).iterdir()
        if HASHED_NAME.match(path.name)
    )


class ImmutableStaticAssetTests(SimpleTestCase):
    def test_hashed_font_and_image_urls_are_immutable(self):
        pattern = re.compile(settings.WHITENOISE_IMMUTABLE_FILE_TEST)

        for url in (
            "/static/fonts/cormorant-garamond-latin-400-normal.8048ac209bec.woff2",
            "/static/images/rccgcm_logo-96.7f11592cbc62.webp",
        ):
            with self.subTest(url=url):
                self.assertTrue(pattern.search(url))

    def test_stable_names_keep_the_short_cache(self):
        pattern = re.compile(settings.WHITENOISE_IMMUTABLE_FILE_TEST)

        for url in (
            "/static/dist/index.js",
            "/static/dist/index.8048ac209bec.js",
            "/static/rccgcm_logo.png",
            "/static/fonts/README.txt",
            "/static/fonts/OFL-instrument-sans.txt",
            "/static/images/rccgcm_logo-96.png",
        ):
            with self.subTest(url=url):
                self.assertFalse(pattern.search(url))

    def test_hashed_filenames_match_file_contents(self):
        assets = hashed_assets()

        self.assertTrue(assets)
        for path in assets:
            with self.subTest(path=path.name):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(HASHED_NAME.match(path.name)["hash"], digest[:12])

    def test_client_references_only_existing_hashed_assets(self):
        shipped = {path.name for path in hashed_assets()}
        references = {
            name
            for source in ("Layout.tsx", "styles.css")
            for name in re.findall(
                r"[\w-]+\.[0-9a-f]{12}\.(?:woff2|webp|png)",
                (CLIENT_DIR / source).read_text(),
            )
        }

        self.assertTrue(references)
        self.assertEqual(references - shipped, set())
