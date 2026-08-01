# Worship Prep Platform

## Project Overview
- **Purpose:** This tool coordinates Scripture, song lyrics, and service slides for ministers, choir members, and the tech booth, keeping all content in sync for worship services.

- **Roles:** 
  - Ministers: Select Scriptures, translations, and reading order.
  - Choir: Add/confirm worship lyrics, adjust verses from rehearsal notes.
  - Tech Booth: Review and prep content for projector output; ensure flow is smooth.

## Usage & Commands
- All project commands are aliases to Django's `python manage.py` commands defined in the `poe` section of `pyproject.toml`.

- To view available poe commands, run:
    ```bash
    poe --help
    ```
- To view available django commands, run:
    ```bash
    poe manage --help
    ```
- Common commands:
    - Start the development server:
        ```bash
        poe dev
        ```
    - Create migrations: 
        ```bash
        poe makemig
        ```
    - Migrate database changes: 
        ```bash
        poe migrate
        ```
    - Run the automated test suite (starts a throwaway Postgres via **Testcontainers**; **Docker must be running**):
        ```bash
        poe test
        ```
        The Docker `test` image runs `pytest` with `DJANGO_ENV=test`; mount the host Docker socket (e.g. `-v /var/run/docker.sock:/var/run/docker.sock`) if you execute that image locally, otherwise Testcontainers cannot start Postgres inside the container.
        GitHub Actions supplies PostgreSQL as a native service container and sets
        `WPP_TEST_POSTGRES_*`; local runs continue to use Testcontainers.

## Package Management
- All dependencies are managed in **pyproject.toml**.
- Add dependencies:  
    ```bash
    uv add <package-name>
    ```
- Remove dependencies: 
    ```bash
    uv remove <package-name>
    ```

## Code Style
- Follow [PEP 8](https://peps.python.org/pep-0008/) for Python formatting.
- Use [Google style docstrings](https://raw.githubusercontent.com/NilsJPWerner/autoDocstring/c9da64126fd9e667decd9d85b4e5b53c60372ea7/docs/google.md) for function/method documentation.
- **Function names**: Be concise, start with a verb/action, clearly reflect purpose (avoid excessive verbosity).
- **Class names**: Use nouns or concepts to represent their purpose.
- Use descriptive names and consistent casing across modules.

## Security & Dependencies
- Never hard-code secrets.
- Review new packages before adding, and document significant changes in the PR.

## Transport Boundaries
- Serve product and machine-facing JSON APIs with Django Bolt. Register them in an
  app's `api.py`; do not add those routes to Django's URLconf or return them from a
  Django/Reactivated view.
- Define every Django Bolt JSON request and response contract as a msgspec-backed
  Django Bolt `Serializer` in the owning app's `schema.py`; handlers must construct
  those schema types rather than ad hoc response dictionaries.
- Serve rendered UI with Django views and Reactivated templates. Keep domain and
  application services independent of both transports so an API handler and a view can
  reuse behavior without calling one another.
- Operational/framework routes such as health checks, readiness checks, Django admin,
  and authentication callbacks may remain on Django's standard HTTP stack.
- See `docs/adr/0004-separate-json-and-rendered-transports.md`.

## Agent skills

### Issue tracker

Issues and PRDs live in GitHub Issues for `nicksspirit/worship-prep-platform`; use the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repo with root `CONTEXT.md` and `docs/adr/`. See `docs/agents/domain.md`.
