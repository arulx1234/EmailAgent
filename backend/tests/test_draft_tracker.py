from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.services import draft_tracker


class DraftTrackerTests(unittest.TestCase):
    def test_claim_is_idempotent_until_released_or_expired(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "drafts.sqlite3"
            with patch.object(draft_tracker, "AUTH_DB_FILE", database_path):
                self.assertTrue(
                    draft_tracker.claim_message("owner@example.com", "message-1")
                )
                self.assertFalse(
                    draft_tracker.claim_message("owner@example.com", "message-1")
                )

                draft_tracker.release_message("owner@example.com", "message-1")
                self.assertTrue(
                    draft_tracker.claim_message("owner@example.com", "message-1")
                )

                draft_tracker.complete_message("owner@example.com", "message-1")
                self.assertFalse(
                    draft_tracker.claim_message("owner@example.com", "message-1")
                )


if __name__ == "__main__":
    unittest.main()
