import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.api.emails import match_emails_to_label
from app.services.email_classifier import EmailLabelMatchRequest


class ProviderQuotaError(RuntimeError):
    code = "credit_balance_exhausted"
    status_code = 429


class EmailLabelMatchingApiTests(unittest.TestCase):
    @patch("app.api.emails.has_configured_provider", return_value=True)
    @patch("app.api.emails.find_emails_relevant_to_label")
    def test_reports_exhausted_provider_quota(
        self,
        match_mock,
        _provider_mock,
    ):
        provider_error = ProviderQuotaError("Provider has no credits remaining.")
        outer_provider_error = RuntimeError("Provider returned HTTP 429.")
        outer_provider_error.__cause__ = provider_error
        match_error = RuntimeError("All configured providers failed.")
        match_error.__cause__ = outer_provider_error
        match_mock.side_effect = match_error

        with self.assertRaises(HTTPException) as raised:
            match_emails_to_label(
                EmailLabelMatchRequest(
                    label="LinkedIn",
                    emails=[{"id": "email-1", "subject": "Connection request"}],
                )
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("no API credits remaining", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
