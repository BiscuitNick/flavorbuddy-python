# Copilot Instructions for AI Coding Agents

## Project Overview
This is a Django backend project for "flavorbuddy". The codebase is organized as a standard Django app with customizations for scraping and serving data. The main components are:
- `config/`: Django project settings and entry points (ASGI, WSGI, URLs)
- `scrape_me/`: Main Django app for scraping logic, models, views, and templates
- `db.sqlite3`: Local development database

## Key Patterns & Conventions
- **App Structure**: All business logic is in `scrape_me/`. Models, views, and admin are in their respective files. Templates are in `scrape_me/templates/scrape_me/`.
- **Migrations**: Managed via Django's migration system. Migration files are in `scrape_me/migrations/`.
- **URLs**: Project-level URLs in `config/urls.py`, app-level in `scrape_me/urls.py`.
- **Templates**: Use Django templating. Example: `home.html` for the main view.
- **Database**: Uses SQLite for local development. Models are defined in `scrape_me/models.py`.

## Developer Workflows
- **Run server**: `python manage.py runserver`
- **Run migrations**: `python manage.py makemigrations && python manage.py migrate`
- **Create superuser**: `python manage.py createsuperuser`
- **Run tests**: `python manage.py test scrape_me`

## Integration Points
- No external APIs or services are integrated by default. All scraping logic should be implemented in `scrape_me/views.py` and related files.
- Templates are rendered via Django views.

## Project-Specific Notes
- Keep all scraping and business logic within the `scrape_me` app unless adding new apps is justified.
- Follow Django's conventions for models, views, and templates.
- Use relative imports within the app when possible.
- Do not hardcode database paths; use Django settings.

## Examples
- To add a new view, update `scrape_me/views.py`, register it in `scrape_me/urls.py`, and create a template in `scrape_me/templates/scrape_me/` if needed.
- To add a new model, define it in `scrape_me/models.py` and run migrations.

## References
- `config/settings.py`: Project settings
- `scrape_me/models.py`: Data models
- `scrape_me/views.py`: Business logic and scraping
- `scrape_me/templates/scrape_me/`: HTML templates

---
For questions or unclear patterns, ask for clarification or check the Django documentation.
