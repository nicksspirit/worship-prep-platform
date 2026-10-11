from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.utils.html import strip_tags


class AdminBreadcrumbTests(SimpleTestCase):
    def test_matching_app_and_model_labels_keep_the_model_link(self):
        html = render_to_string("unfold/helpers/header_title.html", {"parts": [
            {"title": "Sites", "link": "/admin/sites/"},
            {"title": "sites", "link": "/admin/sites/site/"},
            {"title": "example.com", "link": "/admin/sites/site/1/change/"},
        ]})

        self.assertEqual(
            " ".join(strip_tags(html).split()), "Sites chevron_right Example.com"
        )
        self.assertNotIn('href="/admin/sites/"', html)
        self.assertIn('href="/admin/sites/site/"', html)
        self.assertIn('href="/admin/sites/site/1/change/"', html)

    def test_distinct_app_and_model_labels_remain_visible(self):
        html = render_to_string("unfold/helpers/header_title.html", {"parts": [
            {"title": "Accounts", "link": "/admin/accounts/"},
            {"title": "users", "link": "/admin/accounts/user/"},
        ]})

        self.assertEqual(
            " ".join(strip_tags(html).split()), "Accounts chevron_right Users"
        )

    def test_matching_multiword_labels_ignore_capitalization(self):
        for app_title, model_title, url, expected in [
            ("API Keys", "API keys", "/admin/api_keys/integrationapikey/", "API keys"),
            (
                "Social Accounts", "social accounts",
                "/admin/socialaccount/socialaccount/", "Social accounts",
            ),
        ]:
            with self.subTest(app=app_title):
                html = render_to_string("unfold/helpers/header_title.html", {"parts": [
                    {"title": app_title, "link": "/admin/app/"},
                    {"title": model_title, "link": url},
                ]})

                self.assertEqual(" ".join(strip_tags(html).split()), expected)
                self.assertNotIn('href="/admin/app/"', html)
                self.assertIn(f'href="{url}"', html)

    def test_single_dashboard_title_remains_visible(self):
        html = render_to_string("unfold/helpers/header_title.html", {"parts": [
            {"title": "Submissions"},
        ]})

        self.assertEqual(strip_tags(html).strip(), "Submissions")

    def test_object_title_matching_model_label_remains_visible(self):
        html = render_to_string("unfold/helpers/header_title.html", {"parts": [
            {"title": "Sites", "link": "/admin/sites/"},
            {"title": "sites", "link": "/admin/sites/site/"},
            {"title": "Sites", "link": "/admin/sites/site/1/change/"},
        ]})

        self.assertEqual(
            " ".join(strip_tags(html).split()), "Sites chevron_right Sites"
        )
