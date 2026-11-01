import unittest
from unittest.mock import patch

from pydantic import SecretStr

from app.services.email_classifier import (
    EmailClassificationBatchInput,
    EmailClassificationInput,
    classify_email,
    classify_emails,
)


class ClassifyEmailLocalRulesTests(unittest.TestCase):
    @patch("app.services.email_classifier._get_provider_factories")
    def test_classifies_subject_snippet_and_body_without_provider_calls(
        self,
        providers_mock,
    ):
        from app.services import email_classifier

        result = classify_email(
            EmailClassificationInput(
                subject="Project approval required",
                sender="manager@example.com",
                snippet="Please approve this by tomorrow.",
                body="The project team needs your approval.",
            )
        )

        self.assertEqual(result.provider, "rules")
        self.assertEqual(result.category.value, "work")
        self.assertEqual(result.priority.value, "urgent")
        self.assertEqual(result.deadline, "by tomorrow")
        providers_mock.assert_called_once()

    def test_classifies_casual_personal_correspondence(self):
        from app.services import email_classifier

        with patch.object(email_classifier, "_get_provider_factories", return_value=[]):
            result = classify_email(
                EmailClassificationInput(
                    subject="nothing...",
                    sender="Arul Xavier <arulx503@gmail.com>",
                    body="hi bro , how are you?",
                )
            )

        self.assertEqual(result.category.value, "personal")

    @patch("app.services.email_classifier.ChatGroq")
    @patch("app.services.email_classifier.ChatOpenAI")
    @patch("app.services.email_classifier.ChatGoogleGenerativeAI")
    def test_registers_groq_after_existing_providers(
        self,
        gemini_mock,
        openai_mock,
        groq_mock,
    ):
        from app.services import email_classifier

        with (
            patch.object(email_classifier.settings, "gemini_api_key", SecretStr("gemini-test")),
            patch.object(email_classifier.settings, "openai_api_key", SecretStr("openai-test")),
            patch.object(email_classifier.settings, "groq_api_key", SecretStr("groq-test")),
        ):
            providers = email_classifier._get_provider_factories()
            for _, factory in providers:
                factory()

        self.assertEqual(
            [provider for provider, _ in providers],
            ["gemini", "openai", "groq"],
        )
        gemini_mock.assert_called_once()
        openai_mock.assert_called_once()
        groq_mock.assert_called_once_with(
            model=email_classifier.settings.groq_model,
            api_key="groq-test",
            temperature=0,
        )


class ClassifyEmailsTests(unittest.TestCase):
    @patch("app.services.email_classifier._get_provider_factories")
    def test_classifies_all_emails_locally_in_one_batch(self, providers_mock):
        request = EmailClassificationBatchInput(
            emails=[
                {
                    "id": "email-1",
                    "sender": "Manager <manager@example.com>",
                    "subject": "Project meeting",
                    "snippet": "Please join the team meeting tomorrow at 10 AM.",
                },
                {
                    "id": "invoice-1",
                    "subject": "Monthly invoice",
                    "body": "Please pay this invoice.",
                }
            ]
        )

        result = classify_emails(request)

        self.assertEqual(result.provider, "rules")
        self.assertEqual(
            [(item.category.value, item.priority.value) for item in result.classifications],
            [("work", "urgent"), ("finance", "normal")],
        )
        providers_mock.assert_called_once()

    def test_local_fallback_covers_each_category(self):
        from app.services import email_classifier

        examples = [
            ("work", "Q3 planning", "Please join the project meeting."),
            ("personal", "Hello", "Hi bro, how are you?"),
            ("finance", "Payment due", "Your credit card payment is due today."),
            ("promotions", "Special offer", "Get 20% off. Unsubscribe here."),
            ("other", "Security alert", "A new sign-in was detected."),
        ]
        request = EmailClassificationBatchInput(
            emails=[
                {
                    "id": str(index),
                    "subject": subject,
                    "body": body,
                }
                for index, (_, subject, body) in enumerate(examples)
            ]
        )

        with patch.object(email_classifier, "_get_provider_factories", return_value=[]):
            result = classify_emails(request)

        self.assertEqual(
            [item.category.value for item in result.classifications],
            [category for category, _, _ in examples],
        )
        self.assertEqual(result.provider, "rules")
        self.assertTrue(result.warnings)

    def test_local_fallback_does_not_infer_a_deadline_from_date_mentions(self):
        from app.services import email_classifier

        request = EmailClassificationBatchInput(
            emails=[
                {
                    "id": "mention",
                    "subject": "A nice day",
                    "body": "I went for a walk today and enjoyed the weather.",
                },
                {
                    "id": "no-action",
                    "subject": "No action needed",
                    "body": "No action is required; this is just an update.",
                },
                {
                    "id": "deadline",
                    "subject": "Please respond",
                    "body": "Please respond by tomorrow.",
                },
            ]
        )

        with patch.object(email_classifier, "_get_provider_factories", return_value=[]):
            result = classify_emails(request)

        self.assertFalse(result.classifications[0].time_sensitive)
        self.assertEqual(result.classifications[0].priority.value, "low")
        self.assertEqual(result.classifications[1].priority.value, "low")
        self.assertTrue(result.classifications[2].time_sensitive)
        self.assertEqual(result.classifications[2].deadline, "by tomorrow")

    def test_uses_structured_ai_results_when_a_provider_is_available(self):
        from app.services import email_classifier

        batch_item = EmailClassificationBatchInput(
            emails=[{"id": "email-1", "subject": "Hello", "body": "How are you?"}]
        )
        provider_response = email_classifier._EmailClassificationBatchProviderResponse(
            classifications=[
                {
                    "id": "email-1",
                    "category": "personal",
                    "priority": "normal",
                    "time_sensitive": False,
                    "deadline": None,
                    "confidence": 0.94,
                    "reason": "A friendly personal message.",
                    "priority_reason": "A conversational reply is appropriate.",
                }
            ]
        )
        model = unittest.mock.Mock()
        model.with_structured_output.return_value.invoke.return_value = provider_response
        provider_factory = unittest.mock.Mock(return_value=model)

        with patch.object(
            email_classifier,
            "_get_provider_factories",
            return_value=[("openai", provider_factory)],
        ):
            result = classify_emails(batch_item)

        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.classifications[0].category.value, "personal")
        self.assertFalse(result.warnings)

    def test_invalid_provider_response_falls_back_with_warning(self):
        from app.services import email_classifier

        batch_item = EmailClassificationBatchInput(
            emails=[{"id": "email-1", "subject": "Hello"}]
        )
        model = unittest.mock.Mock()
        model.with_structured_output.return_value.invoke.return_value = (
            email_classifier._EmailClassificationBatchProviderResponse(
                classifications=[
                    {
                        "id": "unexpected-id",
                        "category": "personal",
                        "priority": "low",
                        "time_sensitive": False,
                        "deadline": None,
                        "confidence": 0.9,
                        "reason": "A personal message.",
                        "priority_reason": "No response is needed.",
                    }
                ]
            )
        )

        with patch.object(
            email_classifier,
            "_get_provider_factories",
            return_value=[("openai", lambda: model)],
        ):
            result = classify_emails(batch_item)

        self.assertEqual(result.provider, "rules")
        self.assertTrue(result.warnings)
        self.assertEqual(result.classifications[0].id, "email-1")

    def test_rejects_duplicate_email_ids(self):
        with self.assertRaisesRegex(ValueError, "Email IDs must be unique"):
            EmailClassificationBatchInput(
                emails=[
                    {"id": "same", "subject": "First"},
                    {"id": "same", "subject": "Second"},
                ]
            )


if __name__ == "__main__":
    unittest.main()
