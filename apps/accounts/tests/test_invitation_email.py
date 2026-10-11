from django.conf import settings
from django.test import SimpleTestCase
from django.utils.html import escape
from invitations.adapters import get_invitations_adapter


class InvitationEmailTests(SimpleTestCase):
    def test_invitation_email_is_branded_and_preserves_the_acceptance_link(self):
        invite_url = "https://worship.example/invitations/accept-invite/token/?a=1&b=2"
        email = "invitee@example.test"

        message = get_invitations_adapter().render_mail(
            "invitations/email/email_invite",
            email,
            {"invite_url": invite_url, "email": email, "site_name": "example.com"},
        )

        self.assertEqual(
            message.subject,
            settings.ACCOUNT_EMAIL_SUBJECT_PREFIX
            + "Your invitation to Worship Prep Platform",
        )
        self.assertEqual(message.to, [email])
        self.assertIn(invite_url, message.body)
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn(f'href="{escape(invite_url)}"', html)
        self.assertIn("ACCEPT INVITATION", html)
        self.assertIn("CHAPEL OF MERCY", html)
        for body in (message.body, html):
            self.assertIn(email, body)
            self.assertIn("Choose a password, then sign in", body)
            self.assertNotIn("example.com", body)
