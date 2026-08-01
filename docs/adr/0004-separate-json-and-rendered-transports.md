# ADR-0004: Separate JSON APIs from Rendered UI Transports

## Status

Accepted

## Date

2026-08-01

## Context

Worship Prep Platform runs Django Bolt and Django/Reactivated as distinct HTTP
transports. Without an explicit ownership rule, a product endpoint can be implemented
as a conventional Django JSON view even though a dedicated API service exists. That
creates duplicate routing conventions, makes deployment ownership ambiguous, and
encourages UI views and machine interfaces to depend on one another.

The application still needs Django-native operational and framework routes, including
health and readiness probes, admin, invitations, and authentication callbacks. A rule
based only on response media type would incorrectly force those framework concerns into
the product API service.

## Decision

Serve product and machine-facing JSON APIs through Django Bolt. Define those endpoints
in an installed app's `api.py`, where Bolt autodiscovery owns routing, validation,
authentication, response serialization, and OpenAPI metadata. Do not duplicate their
paths in Django's URLconf or implement them as Django `JsonResponse` views.

Serve rendered product UI through Django views and Reactivated templates. Views own
browser-page concerns such as template props, sessions, redirects, and form flows; they
do not act as JSON API controllers.

Keep domain and application behavior below the transport boundary in ordinary services.
Bolt handlers and Reactivated views may call the same service, but must not call each
other. Tests for a JSON API should verify Bolt registration and, where useful, verify
that Django's URLconf does not expose the same path.

Operational and framework endpoints are exceptions rather than product JSON APIs.
Health/readiness probes, Django admin, static assets, invitation flows, and authentication
callbacks may remain on Django's standard HTTP stack even when they return non-HTML
responses.

## Alternatives Considered

### Use Django views for both HTML and JSON

Rejected because it leaves the dedicated Bolt service without clear ownership and
mixes browser-rendering conventions with machine API conventions.

### Serve rendered UI and JSON from Bolt

Rejected because Reactivated is integrated with Django views, middleware, sessions, and
template rendering. Moving page rendering would discard that established application
stack without a product benefit.

### Decide transport endpoint by endpoint

Rejected because local flexibility produces inconsistent routing, authentication,
testing, and deployment behavior across apps.

## Consequences

- New JSON APIs have one discoverable home: `apps/<app>/api.py`.
- New rendered pages have one discoverable home: Django/Reactivated views.
- Transport handlers remain thin and reuse transport-neutral services.
- The Django and Bolt services can evolve and scale independently.
- Reviewers and agents must treat JSON routes added to Django URLconfs as an
  architectural violation unless they are an explicit operational/framework exception.
- ADR-0003 applies this boundary to the Catalog Importer's machine endpoint.
