# FlavorBuddy implementation

Django 5.2 / Python 3.13 and PostgreSQL 16. Install requirements.lock into .venv;
regenerate with `uv pip compile requirements.txt -o requirements.lock`.
Run `docker compose up -d db`, migrations, and `python manage.py test scrape_me integrations kitchen`.
Tests use a separate PostgreSQL test database. Never substitute SQLite as release evidence.

Read docs/execution/README.md and the linked change sets before changes.
Keep legacy data and user working-tree changes. Consumer queries must be owned.
External recipe HTML and Replicate outputs are untrusted; fetching, schema validation,
and paid usage controls belong in services. No live paid calls in tests.
Frontend lives in frontend/ and uses same-origin session/CSRF APIs.
