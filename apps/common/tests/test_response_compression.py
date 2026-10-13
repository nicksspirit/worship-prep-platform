import gzip

from django.test import TestCase
from django.urls import reverse


class ResponseCompressionTests(TestCase):
    def test_html_is_gzipped_when_the_client_accepts_gzip(self):
        response = self.client.get(
            reverse("account_login"), headers={"accept-encoding": "gzip, br"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Encoding"], "gzip")
        self.assertIn("Accept-Encoding", response["Vary"])
        self.assertIn(b"<html", gzip.decompress(response.content))

    def test_html_is_not_compressed_without_accept_encoding(self):
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Content-Encoding", response)
        self.assertIn(b"<html", response.content)
