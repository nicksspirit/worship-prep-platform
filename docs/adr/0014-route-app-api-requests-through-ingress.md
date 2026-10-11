# ADR-0014: Route App API Requests Through Ingress

## Status

Accepted

## Date

2026-10-11

## Context

Cloud Run maps `app.rccgcm.org` directly to the Django service. The Windows
exporter uses that platform URL, so its Bolt import path returns Django's 404.
The deployment has no load balancer with path-based routing.

## Decision

Run Nginx at the Django service's ingress. Forward `/api/` to the existing Bolt
service over verified HTTPS, and other requests to local Gunicorn. Cloud Build
discovers the Bolt service URL rather than hard-coding a production hostname.
Keep endpoint ownership and independent service scaling as defined in ADR-0004.

## Alternatives Considered

An external load balancer would add infrastructure and require DNS changes.
A redirect would require the streaming exporter to replay the request and send
its authorization header to another host. A Django proxy view would violate
ADR-0004. The ingress proxy avoids those changes.

## Consequences

The production image adds Debian's Nginx package. The Django launcher supervises
Gunicorn and Nginx, stopping both when either exits or Cloud Run stops the instance.
The existing Cloud Run HTTP/1 request limit remains 32 MiB; larger packages need
a separate HTTP/2 ingress change.
