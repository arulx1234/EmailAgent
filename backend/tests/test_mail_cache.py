import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import mail_cache


class MailCacheTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "mail-cache.sqlite3"
        self.database_patcher = patch.object(
            mail_cache,
            "MAIL_CACHE_DB_FILE",
            self.database_path,
        )
        self.database_patcher.start()

    def tearDown(self):
        self.database_patcher.stop()
        self.directory.cleanup()

    def test_cache_is_account_scoped_and_keeps_the_newest_fifty(self):
        mail_cache.store_cached_emails(
            "first@example.com",
            [
                ({"id": f"email-{index}"}, index)
                for index in range(60)
            ],
        )

        first_account = mail_cache.get_cached_emails(
            "first@example.com",
            [f"email-{index}" for index in range(60)],
        )
        second_account = mail_cache.get_cached_emails(
            "second@example.com",
            ["email-59"],
        )

        self.assertEqual(len(first_account), 50)
        self.assertNotIn("email-9", first_account)
        self.assertIn("email-10", first_account)
        self.assertIn("email-59", first_account)
        self.assertEqual(second_account, {})

    def test_filtered_cache_matches_category_labels_and_spam(self):
        mail_cache.store_cached_emails(
            "owner@example.com",
            [
                (
                    {
                        "id": "personal",
                        "labels": ["INBOX", "Label_friends"],
                        "classification": {"category": "personal"},
                    },
                    3,
                ),
                (
                    {
                        "id": "work",
                        "labels": ["INBOX"],
                        "classification": {"category": "work"},
                    },
                    2,
                ),
                (
                    {
                        "id": "spam",
                        "labels": ["SPAM"],
                        "classification": {"category": "other"},
                    },
                    1,
                ),
            ],
        )

        personal = mail_cache.get_latest_cached_emails(
            "owner@example.com",
            25,
            category="personal",
        )
        custom_label = mail_cache.get_latest_cached_emails(
            "owner@example.com",
            25,
            label_ids=["Label_friends"],
            exclude_spam=True,
        )
        spam = mail_cache.get_latest_cached_emails(
            "owner@example.com",
            25,
            spam_only=True,
        )

        self.assertEqual([email["id"] for email in personal], ["personal"])
        self.assertEqual([email["id"] for email in custom_label], ["personal"])
        self.assertEqual([email["id"] for email in spam], ["spam"])

    def test_gmail_label_mapping_is_account_scoped(self):
        mail_cache.store_cached_gmail_labels(
            "owner@example.com",
            [{"name": "Friends", "id": "Label_friends"}],
        )

        self.assertEqual(
            mail_cache.get_cached_gmail_label_ids(
                "owner@example.com",
                ["Friends"],
            ),
            {"Friends": "Label_friends"},
        )
        self.assertEqual(
            mail_cache.get_cached_gmail_label_ids(
                "other@example.com",
                ["Friends"],
            ),
            {},
        )


if __name__ == "__main__":
    unittest.main()
