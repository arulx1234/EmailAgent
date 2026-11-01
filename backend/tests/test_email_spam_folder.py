import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from pathlib import Path

from fastapi import HTTPException
from googleapiclient.errors import HttpError

from app.api.emails import get_emails
from app.services import mail_cache


class GmailSpamFolderTests(unittest.TestCase):
    def setUp(self):
        self.cache_directory = tempfile.TemporaryDirectory()
        self.cache_path_patcher = patch.object(
            mail_cache,
            "MAIL_CACHE_DB_FILE",
            Path(self.cache_directory.name) / "mail-cache.sqlite3",
        )
        self.cache_path_patcher.start()

    def tearDown(self):
        self.cache_path_patcher.stop()
        self.cache_directory.cleanup()

    @staticmethod
    def make_session():
        return SimpleNamespace(
            credentials=object(),
            profile={"email": f"{uuid4()}@example.com"},
        )

    @patch("app.services.email_classifier._get_provider_factories", return_value=[])
    @patch("app.api.emails.get_gmail_service")
    def test_does_not_return_gmail_drafts(self, service_factory, _provider_factories):
        service = service_factory.return_value
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "draft-1"}, {"id": "email-1"}]
        }
        details_by_id = {
            "draft-1": {
                "id": "draft-1",
                "payload": {"headers": []},
                "labelIds": ["DRAFT"],
            },
            "email-1": {
                "id": "email-1",
                "payload": {"headers": []},
                "labelIds": ["INBOX"],
            },
        }

        class SuccessfulBatch:
            def __init__(self, callback):
                self.callback = callback
                self.request_ids = []

            def add(self, _request, request_id):
                self.request_ids.append(request_id)

            def execute(self):
                for request_id in self.request_ids:
                    self.callback(request_id, details_by_id[request_id], None)

        service.new_batch_http_request.side_effect = lambda callback: SuccessfulBatch(
            callback
        )

        result = get_emails(max_results=2, session=self.make_session())

        self.assertEqual(result["count"], 1)
        self.assertEqual([email["id"] for email in result["emails"]], ["email-1"])

    @patch("app.api.emails.get_gmail_service")
    def test_fetch_excludes_drafts_in_gmail_query(self, service_factory):
        service = service_factory.return_value
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }

        get_emails(max_results=10, session=self.make_session())

        service.users.return_value.messages.return_value.list.assert_called_once_with(
            userId="me",
            maxResults=10,
            q="-in:drafts",
        )

    @patch("app.services.email_classifier._get_provider_factories", return_value=[])
    @patch("app.api.emails.get_gmail_service")
    def test_fetch_returns_keyword_classification_with_email(
        self,
        service_factory,
        _provider_factories,
    ):
        service = service_factory.return_value
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "invoice-1"}]
        }
        details = {
            "id": "invoice-1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Billing <billing@example.com>"},
                    {"name": "Subject", "value": "Invoice payment due today"},
                ]
            },
            "snippet": "Action required: please pay the invoice today.",
            "labelIds": ["INBOX"],
        }

        class SuccessfulBatch:
            def __init__(self, callback):
                self.callback = callback
                self.request_ids = []

            def add(self, _request, request_id):
                self.request_ids.append(request_id)

            def execute(self):
                for request_id in self.request_ids:
                    self.callback(request_id, details, None)

        service.new_batch_http_request.side_effect = lambda callback: SuccessfulBatch(
            callback
        )

        result = get_emails(max_results=1, session=self.make_session())

        self.assertEqual(result["emails"][0]["classification"]["category"], "finance")
        self.assertEqual(result["emails"][0]["classification"]["priority"], "urgent")
        self.assertTrue(
            result["emails"][0]["classification"]["time_sensitive"]
        )

    @patch("app.services.email_classifier._get_provider_factories", return_value=[])
    @patch("app.api.emails.get_gmail_service")
    def test_cached_mail_avoids_fetching_details_and_reclassifying(
        self,
        service_factory,
        _provider_factories,
    ):
        service = service_factory.return_value
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "cached-email"}]
        }
        session = self.make_session()
        details = {
            "id": "cached-email",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Friend <friend@example.com>"},
                    {"name": "Subject", "value": "Hello"},
                ],
                "mimeType": "text/plain",
                "body": {},
            },
            "snippet": "How are you?",
            "labelIds": ["INBOX"],
            "internalDate": "1000",
        }

        class SuccessfulBatch:
            def __init__(self, callback):
                self.callback = callback
                self.request_ids = []

            def add(self, _request, request_id):
                self.request_ids.append(request_id)

            def execute(self):
                for request_id in self.request_ids:
                    self.callback(request_id, details, None)

        service.new_batch_http_request.side_effect = lambda callback: SuccessfulBatch(
            callback
        )

        first_result = get_emails(max_results=1, session=session)
        second_result = get_emails(max_results=1, session=session)

        self.assertEqual(first_result["emails"], second_result["emails"])
        service.new_batch_http_request.assert_called_once()

    @patch("app.api.emails.get_gmail_service")
    def test_category_filter_uses_cached_classifications_without_gmail(
        self,
        service_factory,
    ):
        session = self.make_session()
        account_email = session.profile["email"].casefold()
        mail_cache.store_cached_emails(
            account_email,
            [
                (
                    {
                        "id": "personal",
                        "labels": ["INBOX"],
                        "classification": {"category": "personal"},
                    },
                    2,
                ),
                (
                    {
                        "id": "work",
                        "labels": ["INBOX"],
                        "classification": {"category": "work"},
                    },
                    1,
                ),
            ],
        )

        result = get_emails(
            max_results=25,
            category="personal",
            session=session,
        )

        self.assertEqual([email["id"] for email in result["emails"]], ["personal"])
        service_factory.assert_not_called()

    @patch("app.api.emails.get_gmail_service")
    def test_refresh_bypasses_cached_category_results(
        self,
        service_factory,
    ):
        session = self.make_session()
        account_email = session.profile["email"].casefold()
        mail_cache.store_cached_emails(
            account_email,
            [
                (
                    {
                        "id": "cached-personal",
                        "labels": ["INBOX"],
                        "classification": {"category": "personal"},
                    },
                    2,
                ),
            ],
        )
        service = service_factory.return_value
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }

        result = get_emails(
            max_results=25,
            category="personal",
            refresh=True,
            session=session,
        )

        self.assertEqual(result, {"count": 0, "emails": []})
        service.users.return_value.messages.return_value.list.assert_called_once()

    @patch("app.api.emails.get_gmail_service")
    def test_custom_label_filter_uses_cached_label_mapping_and_mail(
        self,
        service_factory,
    ):
        session = self.make_session()
        account_email = session.profile["email"].casefold()
        mail_cache.store_cached_gmail_labels(
            account_email,
            [{"name": "Friends", "id": "Label_friends"}],
        )
        mail_cache.store_cached_emails(
            account_email,
            [
                (
                    {
                        "id": "friend-email",
                        "labels": ["INBOX", "Label_friends"],
                        "classification": {"category": "personal"},
                    },
                    2,
                ),
                (
                    {
                        "id": "work-email",
                        "labels": ["INBOX"],
                        "classification": {"category": "work"},
                    },
                    1,
                ),
            ],
        )

        result = get_emails(
            max_results=25,
            label="Friends",
            session=session,
        )

        self.assertEqual(
            [email["id"] for email in result["emails"]],
            ["friend-email"],
        )
        service_factory.assert_not_called()

    @patch("app.api.emails.get_gmail_service")
    def test_custom_category_uses_label_name_for_classification(
        self,
        service_factory,
    ):
        session = self.make_session()
        account_email = session.profile["email"].casefold()
        mail_cache.store_cached_gmail_labels(
            account_email,
            [{"name": "GitHub", "id": "Label_github"}],
        )
        mail_cache.store_cached_emails(
            account_email,
            [
                (
                    {
                        "id": "github-email",
                        "labels": ["INBOX", "Label_github"],
                        "classification": {"category": "other"},
                    },
                    2,
                ),
            ],
        )

        result = get_emails(
            max_results=25,
            category_label="GitHub",
            custom_labels=["GitHub"],
            session=session,
        )

        self.assertEqual(result["emails"][0]["category_label"], "GitHub")
        self.assertEqual(
            result["emails"][0]["classification"]["category"],
            "other",
        )
        service_factory.assert_not_called()

    @patch("app.services.email_classifier._get_provider_factories", return_value=[])
    @patch("app.api.emails.get_gmail_service")
    def test_returns_successful_messages_when_batch_is_partially_limited(
        self,
        service_factory,
        _provider_factories,
    ):
        service = service_factory.return_value
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "email-1"}, {"id": "email-2"}]
        }

        class PartialBatch:
            def __init__(self, callback):
                self.callback = callback
                self.request_ids = []

            def add(self, _request, request_id):
                self.request_ids.append(request_id)

            def execute(self):
                self.callback(
                    "email-1",
                    {
                        "id": "email-1",
                        "payload": {"headers": []},
                        "labelIds": [],
                    },
                    None,
                )
                self.callback(
                    "email-2",
                    None,
                    HttpError(
                        SimpleNamespace(status=403, reason="Forbidden"),
                        b'{"error":{"errors":[{"reason":"rateLimitExceeded"}]}}',
                    ),
                )

        service.new_batch_http_request.side_effect = lambda callback: PartialBatch(
            callback
        )

        result = get_emails(max_results=2, session=self.make_session())

        self.assertEqual(result["count"], 1)
        self.assertEqual([email["id"] for email in result["emails"]], ["email-1"])
        self.assertEqual(len(result["warnings"]), 2)

    @patch("app.api.emails.get_gmail_service")
    def test_returns_service_unavailable_when_all_messages_are_rate_limited(
        self,
        service_factory,
    ):
        service = service_factory.return_value
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "email-1"}]
        }

        class LimitedBatch:
            def __init__(self, callback):
                self.callback = callback

            def add(self, _request, request_id):
                self.request_id = request_id

            def execute(self):
                self.callback(
                    self.request_id,
                    None,
                    HttpError(
                        SimpleNamespace(status=403, reason="Forbidden"),
                        b'{"error":{"errors":[{"reason":"userRateLimitExceeded"}]}}',
                    ),
                )

        service.new_batch_http_request.side_effect = lambda callback: LimitedBatch(
            callback
        )

        with self.assertRaises(HTTPException) as raised:
            get_emails(max_results=1, session=self.make_session())

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("rate-limited", raised.exception.detail)

    @patch("app.api.emails.get_gmail_service")
    def test_custom_label_fetch_uses_gmail_label_id(self, service_factory):
        service = service_factory.return_value
        service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": [{"id": "Label_123", "name": "LinkedIn"}]
        }
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }

        result = get_emails(
            max_results=100,
            label="LinkedIn",
            session=self.make_session(),
        )

        self.assertEqual(result, {"count": 0, "emails": []})
        service.users.return_value.messages.return_value.list.assert_called_once_with(
            userId="me",
            maxResults=100,
            labelIds=["Label_123"],
            q="-in:drafts",
        )

    @patch("app.api.emails.get_gmail_service")
    def test_spam_folder_requests_gmail_spam_label(self, service_factory):
        service = service_factory.return_value
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }

        result = get_emails(
            max_results=50,
            folder="spam",
            session=self.make_session(),
        )

        self.assertEqual(result, {"count": 0, "emails": []})
        service.users.return_value.messages.return_value.list.assert_called_once_with(
            userId="me",
            maxResults=50,
            labelIds=["SPAM"],
            q="-in:drafts",
        )

    @patch("app.api.emails.get_gmail_service")
    def test_default_folder_does_not_change_existing_all_mail_request(
        self,
        service_factory,
    ):
        service = service_factory.return_value
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }

        get_emails(max_results=10, session=self.make_session())

        service.users.return_value.messages.return_value.list.assert_called_once_with(
            userId="me",
            maxResults=10,
            q="-in:drafts",
        )


if __name__ == "__main__":
    unittest.main()
