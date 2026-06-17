# FurConnect

Convention schedule app built with Django. Started for furry cons, but nothing in the data model is fandom-specific—you can run it for any multi-day event.

Attendees get a searchable schedule with day/room/tag filters. Staff log in to manage conventions, days, panels, rooms, hosts, and tags. Each convention can export a printable PDF and an `.ics` calendar feed.

Optional [ConCat](https://concat.app/) integration handles OAuth login and panel RSVPs (with role and registration checks if you need them).

## Stack

- Python 3.11+, Django 5.2
- SQLite for local dev; PostgreSQL when `DB_HOST` is set
- Gunicorn in Docker; `runserver` for local work

## Local setup

```bash
git clone https://github.com/FurConnect/FurConnect.git
cd FurConnect
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`—at minimum set `DJANGO_SECRET_KEY` and `DEBUG=True` for development.

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Public schedule: http://127.0.0.1:8000/

After logging in, create a convention and its days, then add panels. The schedule page picks up changes immediately.

## Docker

**Dev** (bind-mounts the repo, auto-reload):

```bash
docker compose -f docker-compose-dev.yml up --build
```

**Production-style** (Postgres + named volumes):

```bash
docker compose up --build
```

Set `DJANGO_SECRET_KEY` and other env vars in `.env` or your orchestrator. The compose files run migrations and `collectstatic` on startup.

## ConCat (optional)

Copy the ConCat variables from `.env.example` and set `CONCAT_ENABLED=True`. You'll need OAuth client credentials and a redirect URI pointing at your site.

When registering your ConCat OAuth application, request these **service scopes**:

- `registration:read`
- `order:view`
- `user:read`

Set `CONCAT_SERVICE_SCOPES` in `.env` to match (space-separated), e.g. `registration:read order:view user:read`. User login still uses the `pii:basic` scope for the authorization flow.

Relevant settings:

| Variable | Purpose |
|----------|---------|
| `CONCAT_SERVICE_SCOPES` | Service token scopes (`registration:read order:view user:read`) |
| `CONCAT_EVENTS_ROLE` | ConCat role that can edit the schedule |
| `CONCAT_SKIP_RSVP_ROLES` | Roles that don't need to RSVP (staff, etc.) |
| `CONCAT_RSVP_REQUIRED_ROLES` | If set, only these roles can RSVP |
| `CONCAT_REQUIRE_PAID_REGISTRATION` | Gate RSVPs on paid registration |
| `CONCAT_RSVP_PRODUCT_IDS` | Limit RSVPs to specific badge products |

Leave `CONCAT_ENABLED=False` to use the built-in username/password auth only.

## Contributing

Bug reports and PRs are welcome. Open an issue first if you're planning a larger change so we don't duplicate work.

## License

Modified GNU GPL v3 — see [LICENSE](LICENSE).
