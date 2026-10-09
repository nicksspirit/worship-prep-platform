from django.test import SimpleTestCase
from django.urls import resolve, reverse


class AccountUiRouteTests(SimpleTestCase):
    def test_social_account_pages_use_styled_views(self):
        routes = {
            "socialaccount_login_cancelled": "social_login_cancelled_view",
            "socialaccount_login_error": "social_login_error_view",
            "socialaccount_signup": "SocialSignupView",
        }

        for name, expected_view in routes.items():
            with self.subTest(name=name):
                callback = resolve(reverse(name)).func
                view = getattr(callback, "view_class", callback)
                self.assertEqual(view.__name__, expected_view)

    def test_account_email_and_login_code_pages_use_styled_views(self):
        routes = {
            "account_inactive": "AccountInactiveView",
            "account_email_verification_sent": "account_email_verification_sent_view",
            "account_confirm_email": "AccountConfirmEmailView",
            "account_confirm_login_code": "AccountConfirmLoginCodeView",
        }

        for name, expected_view in routes.items():
            kwargs = {"key": "test-key"} if name == "account_confirm_email" else None
            with self.subTest(name=name):
                callback = resolve(reverse(name, kwargs=kwargs)).func
                view = getattr(callback, "view_class", callback)
                self.assertEqual(view.__name__, expected_view)
