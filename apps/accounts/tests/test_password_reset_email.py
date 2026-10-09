from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class PasswordResetEmailTests(SimpleTestCase):
    def test_password_reset_email_is_branded_and_preserves_generated_link(self):
        reset_url = "https://worship.example/accounts/password/reset/key/opaque-token/"
        context = {"password_reset_url": reset_url}

        subject = render_to_string(
            "account/email/password_reset_key_subject.txt", context
        ).strip()
        text = render_to_string(
            "account/email/password_reset_key_message.txt", context
        )
        html = render_to_string(
            "account/email/password_reset_key_message.html", context
        )

        self.assertEqual(settings.ACCOUNT_EMAIL_SUBJECT_PREFIX, "Worship Prep Platform | ")
        self.assertEqual(subject, "Reset your Worship Prep Platform password")
        self.assertIn(reset_url, text)
        self.assertIn(f'href="{reset_url}"', html)
        self.assertIn("Your password will stay the same unless you use the link", text)
        self.assertIn("CHAPEL OF MERCY", html)
        self.assertNotIn("example.com", subject + text + html)
