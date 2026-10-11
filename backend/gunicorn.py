"""Use the platform JSON logger; Django emits the safe request completion events."""

from django.conf import settings

logconfig_dict = settings.LOGGING
accesslog = None
errorlog = "-"
