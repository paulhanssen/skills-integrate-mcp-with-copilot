import hashlib
import os
import secrets
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response


class OrganizerAdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_environment = {
            key: os.environ.get(key)
            for key in (
                "ADMIN_USERNAME",
                "ADMIN_PASSWORD_HASH",
                "SESSION_SECRET",
                "ADMIN_AUDIT_LOG",
            )
        }
        salt = secrets.token_bytes(16)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", b"test-password", salt, 260000
        )
        os.environ["ADMIN_USERNAME"] = "test-organizer"
        os.environ["ADMIN_PASSWORD_HASH"] = (
            f"pbkdf2_sha256$260000${salt.hex()}${password_hash.hex()}"
        )
        os.environ["SESSION_SECRET"] = secrets.token_hex(32)

        import app

        cls.api = app

    @classmethod
    def tearDownClass(cls):
        for key, value in cls.original_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.api.ADMIN_AUDIT_LOG = Path(self.temp_dir.name) / "audit.jsonl"
        self.original_activities = {
            name: {
                **details,
                "participants": list(details["participants"]),
            }
            for name, details in self.api.activities.items()
        }
        self.username = "test-organizer"
        self.token = self.api._create_admin_session(self.username)

    def tearDown(self):
        self.api.activities.clear()
        self.api.activities.update(self.original_activities)
        self.temp_dir.cleanup()

    def make_request(self, token=""):
        headers = []
        if token:
            headers.append(
                (
                    b"cookie",
                    f"{self.api.ADMIN_SESSION_COOKIE}={token}".encode(),
                )
            )
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": headers,
                "query_string": b"",
                "server": ("testserver", 80),
                "scheme": "http",
                "client": ("testclient", 50000),
                "root_path": "",
            }
        )

    def test_login_sets_signed_cookie_and_rejects_invalid_password(self):
        response = Response()
        with self.assertRaises(HTTPException) as context:
            self.api.admin_login(
                self.api.AdminCredentials(
                    username=self.username, password="incorrect"
                ),
                response,
            )
        self.assertEqual(context.exception.status_code, 401)

        response = Response()
        self.api.admin_login(
            self.api.AdminCredentials(
                username=self.username, password="test-password"
            ),
            response,
        )
        cookie = response.headers["set-cookie"].split(";", 1)[0]
        token = cookie.split("=", 1)[1]
        self.assertEqual(self.api.require_admin(self.make_request(token)), self.username)
        with self.assertRaises(HTTPException):
            self.api.require_admin(self.make_request(token + "tampered"))

    def test_activity_management_requires_auth_and_writes_audit_entries(self):
        with self.assertRaises(HTTPException) as context:
            self.api.require_admin(self.make_request())
        self.assertEqual(context.exception.status_code, 401)

        payload = self.api.ActivityCreate(
            name="New Club",
            description="A new activity",
            schedule="Fridays",
            max_participants=12,
        )
        self.api.create_activity(payload, self.username)
        self.api.update_activity(
            "New Club", self.api.ActivityUpdate(schedule="Saturdays"), self.username
        )
        self.assertEqual(self.api.activities["New Club"]["schedule"], "Saturdays")
        audit_entries = self.api.get_admin_audit_log(self.username)
        self.assertEqual([entry["action"] for entry in audit_entries], ["updated", "created"])

    def test_signup_capacity_closure_and_participant_removal(self):
        payload = self.api.ActivityCreate(
            name="Limited Club",
            description="One place",
            schedule="Mondays",
            max_participants=1,
        )
        self.api.create_activity(payload, self.username)
        self.api.signup_for_activity("Limited Club", "student@example.edu")

        with self.assertRaises(HTTPException) as context:
            self.api.signup_for_activity("Limited Club", "other@example.edu")
        self.assertEqual(context.exception.status_code, 400)

        self.api.update_activity(
            "Limited Club", self.api.ActivityUpdate(is_open=False), self.username
        )
        with self.assertRaises(HTTPException):
            self.api.signup_for_activity("Limited Club", "other@example.edu")
        with self.assertRaises(HTTPException) as context:
            self.api.unregister_from_activity("Limited Club", "student@example.edu")
        self.assertEqual(context.exception.status_code, 401)

        self.api.admin_remove_participant(
            "Limited Club", "student@example.edu", self.username
        )
        self.assertEqual(self.api.activities["Limited Club"]["participants"], [])

    def test_activity_validation_rejects_path_names_and_blank_schedules(self):
        with self.assertRaises(HTTPException) as context:
            self.api.create_activity(
                self.api.ActivityCreate(
                    name="../unsafe",
                    description="Bad name",
                    schedule="Fridays",
                    max_participants=5,
                ),
                self.username,
            )
        self.assertEqual(context.exception.status_code, 422)

        with self.assertRaises(HTTPException) as context:
            self.api.update_activity(
                "Chess Club", self.api.ActivityUpdate(schedule="   "), self.username
            )
        self.assertEqual(context.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()