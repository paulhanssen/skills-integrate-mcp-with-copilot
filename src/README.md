# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Sign up for activities

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Run the application:

   ```
   python app.py
   ```

3. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## Organizer Setup

Organizer access is disabled until credentials and a session secret are configured. Create a PBKDF2-SHA256 password hash without putting the plaintext password in a file:

```sh
python - <<'PY'
import getpass
import hashlib
import secrets

password = getpass.getpass("Organizer password: ").encode()
salt = secrets.token_bytes(16)
iterations = 260000
digest = hashlib.pbkdf2_hmac("sha256", password, salt, iterations)
print(f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}")
PY
```

Set the resulting hash and other values in the environment used to start the app:

```sh
export ADMIN_USERNAME="organizer"
export ADMIN_PASSWORD_HASH="<generated-hash>"
export SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export COOKIE_SECURE="false" # Set to true when served over HTTPS
export ADMIN_AUDIT_LOG="/path/to/persistent/admin-audit.jsonl"
```

Do not commit these values. Open the app and use the Organizer Tools sign-in form. Sessions expire after eight hours. Activity management endpoints require the signed, HttpOnly session cookie. Keep the audit log path on persistent storage in production.

Activity and signup data still lives in memory and resets when the server restarts; durable storage is tracked separately.

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Sign up for an activity                                             |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Unregister (organizer sign-in required)                             |
| POST   | `/admin/login`                                                    | Sign in as the configured organizer                                 |
| POST   | `/admin/logout`                                                   | Sign out and clear the organizer session                            |
| GET    | `/admin/me`                                                       | Check whether the current browser has an organizer session          |
| POST   | `/admin/activities`                                               | Create an activity (organizer only)                                 |
| PATCH  | `/admin/activities/{activity_name}`                               | Edit activity details or open/close signups (organizer only)        |
| DELETE | `/admin/activities/{activity_name}/participants/{email}`          | Remove a participant (organizer only)                               |
| GET    | `/admin/audit-log`                                                | View recent organizer actions (organizer only)                      |

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

All data is stored in memory, which means data will be reset when the server restarts.
