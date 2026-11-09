# DocxDeadline

DocxDeadline is a private, editorial-style workspace for documents, applications and deadlines. The first phase establishes the Django foundation, built-in authentication, profile settings and the reusable visual system for the later vault and tracking modules.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Create an account to enter the private overview.

## Phase 1 architecture

The `config` package owns settings, URL routing and WSGI. The `core` app owns authentication, documents, deadlines, applications, relationships, notifications, activity history, and the user `Profile` relationship. The database remains the source of truth for all dashboard, list, and calendar data.

The planned relationships are: `User 1—1 Profile`, `User 1—many Document`, `User 1—many Deadline`, `User 1—many Application`, `Application 1—many Requirement`, and `Requirement many—many Document` through `ApplicationDocument`. Notifications and activities are owned by `User` and point to the relevant domain object through explicit metadata or typed relations as the notification phase is implemented.

## Main routes

The application provides authenticated CRUD pages for documents, deadlines, and applications, a requirements/linking workflow, a monthly calendar JSON endpoint, in-app notifications, and activity history.

## Verification

```bash
python manage.py check
python manage.py test
```
