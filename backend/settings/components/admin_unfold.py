from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

UNFOLD = {
    "SITE_TITLE": "Worship Prep Admin",
    "SITE_HEADER": "Worship Prep Platform",
    "SITE_URL": "/",
    "SITE_ICON": {
        "light": lambda request: "/static/rccgcm_logo.png",
        "dark": lambda request: "/static/rccgcm_logo.png",
    },
    "SITE_LOGO": {
        "light": lambda request: "/static/rccgcm_logo.png",
        "dark": lambda request: "/static/rccgcm_logo.png",
    },
    "SITE_FAVICONS": [
        {
            "rel": "apple-touch-icon",
            "sizes": "180x180",
            "href": lambda request: "/static/apple-touch-icon.png",
        },
        {
            "rel": "icon",
            "type": "image/png",
            "sizes": "32x32",
            "href": lambda request: "/static/favicon-32x32.png",
        },
        {
            "rel": "icon",
            "type": "image/png",
            "sizes": "16x16",
            "href": lambda request: "/static/favicon-16x16.png",
        },
        {
            "rel": "shortcut icon",
            "href": lambda request: "/static/favicon.ico",
        },
    ],
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": _("Song Catalog"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Import runs"),
                        "icon": "cloud_download",
                        "link": reverse_lazy("admin:catalog_catalogimportrun_changelist"),
                    },
                    {
                        "title": _("Snapshots"),
                        "icon": "history",
                        "link": reverse_lazy("admin:catalog_catalogsnapshot_changelist"),
                    },
                    {
                        "title": _("Import events"),
                        "icon": "diagnosis",
                        "link": reverse_lazy("admin:catalog_catalogimportevent_changelist"),
                    },
                ],
            },
            {
                "title": _("Access Management"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Users"),
                        "icon": "person",
                        "link": reverse_lazy("admin:accounts_user_changelist"),
                    },
                    {
                        "title": _("Invitations"),
                        "icon": "mail",
                        "link": reverse_lazy("admin:invitations_invitation_changelist"),
                    },
                    {
                        "title": _("Invitation Requests"),
                        "icon": "mark_email_unread",
                        "link": reverse_lazy("admin:accounts_invitationrequest_changelist"),
                    },
                    {
                        "title": _("Groups"),
                        "icon": "group",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                    {
                        "title": _("API Keys"),
                        "icon": "vpn_key",
                        "link": reverse_lazy("admin:api_keys_integrationapikey_changelist"),
                    },
                ],
            },
            {
                "title": _("System"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Sites"),
                        "icon": "language",
                        "link": reverse_lazy("admin:sites_site_changelist"),
                    },
                    {
                        "title": _("Social Accounts"),
                        "icon": "share",
                        "link": reverse_lazy("admin:socialaccount_socialaccount_changelist"),
                    },
                    {
                        "title": _("Social Applications"),
                        "icon": "settings_applications",
                        "link": reverse_lazy("admin:socialaccount_socialapp_changelist"),
                    },
                    {
                        "title": _("Email Addresses"),
                        "icon": "email",
                        "link": reverse_lazy("admin:account_emailaddress_changelist"),
                    },
                ],
            },
        ],
    },
}
