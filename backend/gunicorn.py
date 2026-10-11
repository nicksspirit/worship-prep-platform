"""Use the platform JSON logger; Django emits the safe request completion events."""

from django.conf import settings

logconfig_dict = settings.LOGGING
accesslog = None
errorlog = "-"

# Avoid the control thread holding a buffered stderr lock when workers fork.
control_socket_disable = True
