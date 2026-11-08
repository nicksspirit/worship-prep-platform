from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def on_authentication_error(
        self,
        request: HttpRequest,
        provider,
        error=None,
        exception=None,
        extra_context=None,
    ) -> None:
        raise ImmediateHttpResponse(
            HttpResponseRedirect(reverse("socialaccount_login_error"))
        )
