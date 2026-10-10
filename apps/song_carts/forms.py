from django import forms

from apps.song_carts.models import ServiceSection


class AddSongForm(forms.Form):
    service_date = forms.DateField()
    section = forms.ChoiceField(choices=ServiceSection.choices)


class CommentForm(forms.Form):
    body = forms.CharField(max_length=5000, strip=True)


class RejectionForm(forms.Form):
    reason = forms.CharField(max_length=2000, strip=True)


class SubmissionReplyForm(forms.Form):
    body = forms.CharField(max_length=10000, strip=True)
    request_id = forms.UUIDField()


class UnlistedSongForm(AddSongForm):
    title = forms.CharField(max_length=512, strip=True)
    lyrics = forms.CharField(max_length=20000, strip=False)
