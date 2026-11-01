import unittest
from unittest.mock import Mock, patch

from app.api.labels import (
    GmailLabelRequest,
    _list_all_message_ids,
    create_gmail_label,
    sync_gmail_label,
)


def configure_message_batch(service, details_by_id):
    messages = service.users.return_value.messages.return_value

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


class GmailLabelsApiTests(unittest.TestCase):
    @patch("app.api.labels.get_gmail_service")
    def test_creates_label_in_gmail(self, service_factory):
        service = service_factory.return_value
        labels = service.users.return_value.labels.return_value
        labels.list.return_value.execute.return_value = {"labels": []}
        labels.create.return_value.execute.return_value = {
            "id": "Label_123",
            "name": "LinkedIn",
        }

        result = create_gmail_label(
            GmailLabelRequest(name=" LinkedIn "),
            credentials=object(),
        )

        self.assertEqual(result.model_dump(), {"id": "Label_123", "name": "LinkedIn"})
        labels.create.assert_called_once_with(
            userId="me",
            body={
                "name": "LinkedIn",
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )

    @patch("app.api.labels.get_gmail_service")
    def test_reuses_existing_gmail_label(self, service_factory):
        service = service_factory.return_value
        labels = service.users.return_value.labels.return_value
        labels.list.return_value.execute.return_value = {
            "labels": [{"id": "Label_123", "name": "LinkedIn"}]
        }

        result = create_gmail_label(
            GmailLabelRequest(name="LinkedIn"),
            credentials=object(),
        )

        self.assertEqual(result.model_dump(), {"id": "Label_123", "name": "LinkedIn"})
        labels.create.assert_not_called()

    @patch("app.api.labels.invalidate_cached_emails")
    @patch("app.api.labels.get_gmail_service")
    @patch("app.api.labels._list_all_message_ids")
    @patch("app.api.labels.find_emails_relevant_to_label")
    @patch("app.api.labels.has_configured_provider", return_value=False)
    def test_sync_matches_delivery_and_removes_incidental_order_match(
        self,
        _provider_mock,
        match_mock,
        list_ids_mock,
        service_factory,
        _invalidate_cache,
    ):
        service = service_factory.return_value
        service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": [{"id": "Label_123", "name": "Orders"}]
        }
        messages = service.users.return_value.messages.return_value
        list_ids_mock.side_effect = [
            ["job-alert", "shoe-delivery"],
            ["job-alert"],
        ]
        configure_message_batch(
            service,
            {
                "job-alert": {
                    "id": "job-alert",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "LinkedIn"},
                            {
                                "name": "Subject",
                                "value": "Intern: hiring trends",
                            },
                        ]
                    },
                    "snippet": "Orders and resolve Team Member. Hiring trends.",
                    "labelIds": ["Label_123"],
                },
                "shoe-delivery": {
                    "id": "shoe-delivery",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Shoe Store"},
                            {
                                "name": "Subject",
                                "value": "Your shoes have been delivered",
                            },
                        ]
                    },
                    "snippet": "Your order has arrived.",
                    "labelIds": ["INBOX"],
                },
            },
        )
        result = sync_gmail_label(
            GmailLabelRequest(name="Orders"),
            session=type(
                "Session",
                (),
                {
                    "credentials": object(),
                    "profile": {"email": "test@example.com"},
                },
            )(),
        )

        self.assertEqual(result.label_name, "Orders")
        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.removed_count, 1)
        query = list_ids_mock.call_args_list[0].kwargs["q"]
        self.assertIn("-in:drafts", query)
        self.assertIn('"delivered"', query)
        self.assertIn('"shipping"', query)
        match_mock.assert_not_called()
        self.assertEqual(
            messages.batchModify.call_args_list[0].kwargs["body"],
            {
                "ids": ["shoe-delivery"],
                "addLabelIds": ["Label_123"],
            },
        )
        self.assertEqual(
            messages.batchModify.call_args_list[1].kwargs["body"],
            {
                "ids": ["job-alert"],
                "removeLabelIds": ["Label_123"],
            },
        )

    def test_lists_all_gmail_search_pages(self):
        messages = Mock()
        messages.list.return_value.execute.side_effect = [
            {
                "messages": [{"id": "message-1"}],
                "nextPageToken": "next-page",
            },
            {"messages": [{"id": "message-2"}]},
        ]

        result = _list_all_message_ids(messages, q='"orders"')

        self.assertEqual(result, ["message-1", "message-2"])
        self.assertEqual(messages.list.call_count, 2)
        self.assertEqual(
            messages.list.call_args_list[1].kwargs["pageToken"],
            "next-page",
        )


if __name__ == "__main__":
    unittest.main()
