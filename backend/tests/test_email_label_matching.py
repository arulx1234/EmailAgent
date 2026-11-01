import unittest
from unittest.mock import Mock, patch

from app.services.email_classifier import (
    EmailLabelMatch,
    EmailLabelMatchRequest,
    EmailLabelMatchResponse,
    find_emails_relevant_to_label,
    is_ecommerce_email,
    is_ecommerce_label,
)


class EmailLabelMatchingTests(unittest.TestCase):
    def test_recognizes_order_label_variants(self):
        for label in ("Orders", "Ecommerce", "E-commerce", "Shopping"):
            with self.subTest(label=label):
                self.assertTrue(is_ecommerce_label(label))

    def test_matches_delivery_without_the_word_order(self):
        self.assertTrue(
            is_ecommerce_email(
                EmailLabelMatch(
                    id="shoe-delivery",
                    subject="Your shoes got delivered",
                    snippet="Your package has arrived.",
                )
            )
        )

    def test_rejects_linkedin_job_alert_with_incidental_orders_mention(self):
        self.assertFalse(
            is_ecommerce_email(
                EmailLabelMatch(
                    id="linkedin-job-alert",
                    sender="LinkedIn <messages-noreply@linkedin.com>",
                    subject=(
                        "Intern: Secure Network Solutions India Private "
                        "Limited and Rhino Creative Agency are hiring"
                    ),
                    snippet=(
                        "Hiring trends for Intern roles. New job openings. "
                        "Orders and resolve Team Member."
                    ),
                    body=(
                        "Companies with the most job openings in your role. "
                        "People with similar roles applied to these jobs."
                    ),
                )
            )
        )

    def test_rejects_non_commerce_work_email(self):
        self.assertFalse(
            is_ecommerce_email(
                EmailLabelMatch(
                    id="work-return",
                    subject="Return to office next week",
                    snippet="Please confirm your attendance.",
                )
            )
        )

    @patch("app.services.email_classifier._get_provider_factories")
    def test_discards_ids_not_in_the_requested_emails(self, factories_mock):
        model = Mock()
        model.with_structured_output.return_value = model
        model.invoke.return_value = EmailLabelMatchResponse(
            matching_ids=["email-1", "email-1", "not-requested"]
        )
        factories_mock.return_value = [("groq", lambda: model)]

        result = find_emails_relevant_to_label(
            EmailLabelMatchRequest(
                label="Travel",
                emails=[
                    EmailLabelMatch(
                        id="email-1",
                        subject="Flight confirmation",
                    ),
                    EmailLabelMatch(
                        id="email-2",
                        subject="Weekly report",
                    ),
                ],
            )
        )

        self.assertEqual(result.matching_ids, ["email-1"])
        self.assertEqual(result.provider, "groq")
        prompt = model.invoke.call_args.args[0][0].content
        self.assertIn("actual purpose", prompt)
        self.assertIn("Do not match job alerts", prompt)
        self.assertIn("your shoes have been delivered", prompt)


if __name__ == "__main__":
    unittest.main()
