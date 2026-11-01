import json
import logging
import base64
import time
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import parseaddr
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

from app.api.auth import (
    GMAIL_COMPOSE_SCOPE,
    UserSession,
    get_current_credentials,
    get_current_session,
)
from app.services.gmail_service import (
    extract_message_body,
    get_gmail_service,
    has_unreadable_tracking_url,
    redact_sensitive_tokens,
)
from app.services.email_classifier import (
    EmailClassificationBatchItem,
    EmailLabelMatch,
    EmailLabelMatchRequest,
    EmailLabelMatchResult,
    EmailClassificationResult,
    EmailClassificationInput,
    EmailClassificationBatchInput,
    EmailClassificationBatchResponse,
    classify_email,
    classify_emails,
    is_security_related_content,
    generate_email_reply_draft,
    find_emails_relevant_to_label,
    find_emails_relevant_to_label_locally,
    has_configured_provider,
    is_ecommerce_email,
    is_ecommerce_label,
)
from app.services.draft_tracker import (
    claim_message,
    complete_message,
    release_message,
)
from app.services.mail_cache import (
    CACHE_REVALIDATION_SECONDS,
    get_cached_gmail_label_ids,
    get_cached_emails,
    get_latest_cached_emails,
    store_cached_gmail_labels,
    store_cached_emails,
    update_cached_email_labels,
)


router = APIRouter(
    prefix="/api/emails",
    tags=["Emails"],
)


def _is_ai_quota_exhausted(error: BaseException | None) -> bool:
    while error is not None:
        provider_code = getattr(error, "code", None)
        message = str(error).lower()
        if provider_code in {"insufficient_quota", "credit_balance_exhausted"}:
            return True
        if "no credits remaining" in message:
            return True
        error = error.__cause__ or error.__context__
    return False


def _is_gmail_rate_limit_error(error: BaseException | None) -> bool:
    while error is not None:
        if getattr(getattr(error, "resp", None), "status", None) == 429:
            return True

        content = getattr(error, "content", None)
        if isinstance(content, bytes):
            try:
                response_body = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                response_body = {}
            error_details = response_body.get("error", {})
            reasons = {
                item.get("reason")
                for item in error_details.get("errors", [])
                if isinstance(item, dict)
            }
            if reasons.intersection(
                {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"}
            ):
                return True

        error = error.__cause__ or error.__context__
    return False


def _gmail_header(payload: dict[str, Any], name: str) -> str:
    return next(
        (
            header.get("value", "")
            for header in payload.get("headers", [])
            if header.get("name", "").lower() == name.lower()
        ),
        "",
    )


def _make_reply_raw(
    *,
    recipient: str,
    subject: str,
    body: str,
    message_id: str,
    references: str,
) -> str:
    reply = EmailMessage()
    reply["To"] = recipient
    reply["Subject"] = (
        subject if subject.lower().startswith("re:") else f"Re: {subject}"
    )
    if message_id:
        reply["In-Reply-To"] = message_id
        reply["References"] = " ".join(
            part for part in (references, message_id) if part
        )
    reply.set_content(body)
    return base64.urlsafe_b64encode(
        reply.as_bytes(policy=SMTP)
    ).decode("ascii")


@router.post("/drafts/process")
def process_reply_drafts(
    session: UserSession = Depends(get_current_session),
):
    if GMAIL_COMPOSE_SCOPE not in (session.credentials.scopes or []):
        raise HTTPException(
            status_code=403,
            detail="Reconnect Gmail in Settings to allow creating reply drafts.",
        )

    if not has_configured_provider():
        raise HTTPException(
            status_code=503,
            detail=(
                "Set OPENAI_API_KEY, GEMINI_API_KEY, or GROQ_API_KEY "
                "in backend/.env "
                "to enable reply-draft generation."
            ),
        )

    account_email = session.profile.get("email", "").lower()
    if not account_email:
        raise HTTPException(
            status_code=401,
            detail="The connected Gmail account has no profile email.",
        )

    service = get_gmail_service(session.credentials)
    claimed_candidates = []
    page_token = None
    try:
        while len(claimed_candidates) < 10:
            message_page = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    q="in:inbox -from:me -in:drafts newer_than:7d",
                    maxResults=25,
                    pageToken=page_token,
                )
                .execute()
            )
            for candidate in message_page.get("messages", []):
                if claim_message(account_email, candidate["id"]):
                    claimed_candidates.append(candidate)
                if len(claimed_candidates) >= 10:
                    break
            page_token = message_page.get("nextPageToken")
            if not page_token:
                break
    except HttpError as exc:
        for candidate in claimed_candidates:
            release_message(account_email, candidate["id"])
        logger.error(
            "Gmail reply-draft scan failed with HTTP %s",
            getattr(exc.resp, "status", "unknown"),
        )
        if _is_gmail_rate_limit_error(exc):
            raise HTTPException(
                status_code=503,
                detail="Gmail temporarily rate-limited draft scanning. Try again shortly.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="Gmail could not scan unread messages for reply drafts.",
        ) from exc

    if not claimed_candidates:
        return {
            "reviewed_count": 0,
            "created_count": 0,
            "skipped_count": 0,
            "warnings": [],
        }

    reviewed_count = 0
    created_count = 0
    skipped_count = 0
    warnings: list[str] = []
    messages = service.users().messages()
    try:
        existing_drafts = []
        page_token = None
        while True:
            draft_page = (
                service.users()
                .drafts()
                .list(
                    userId="me",
                    maxResults=100,
                    pageToken=page_token,
                )
                .execute()
            )
            existing_drafts.extend(draft_page.get("drafts", []))
            page_token = draft_page.get("nextPageToken")
            if not page_token:
                break
    except HttpError as exc:
        logger.error(
            "Gmail draft lookup failed with HTTP %s",
            getattr(exc.resp, "status", "unknown"),
        )
        if _is_gmail_rate_limit_error(exc):
            raise HTTPException(
                status_code=503,
                detail="Gmail temporarily rate-limited draft scanning. Try again shortly.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="Gmail could not check existing drafts.",
        ) from exc
    draft_threads = {
        draft.get("message", {}).get("threadId")
        for draft in existing_drafts
        if draft.get("message", {}).get("threadId")
    }

    for candidate in claimed_candidates:
        message_id = candidate["id"]
        try:
            message = (
                messages.get(
                    userId="me",
                    id=message_id,
                    format="full",
                )
                .execute()
            )
            payload = message.get("payload", {})
            sender_header = _gmail_header(payload, "From")
            sender_email = parseaddr(sender_header)[1].lower()
            if (
                not sender_email
                or sender_email == account_email
                or any(
                    label in message.get("labelIds", [])
                    for label in ("SENT", "DRAFT", "SPAM", "TRASH")
                )
            ):
                complete_message(account_email, message_id)
                skipped_count += 1
                continue

            thread_id = message.get("threadId")
            if not thread_id:
                raise ValueError("Gmail message did not include a thread ID.")
            if thread_id in draft_threads:
                complete_message(account_email, message_id)
                skipped_count += 1
                continue

            thread = (
                service.users()
                .threads()
                .get(userId="me", id=thread_id, format="full")
                .execute()
            )
            incoming_time = int(message.get("internalDate", "0"))
            has_newer_sent_message = any(
                "SENT" in thread_message.get("labelIds", [])
                and int(thread_message.get("internalDate", "0")) > incoming_time
                for thread_message in thread.get("messages", [])
            )
            if has_newer_sent_message:
                complete_message(account_email, message_id)
                skipped_count += 1
                continue

            sender = EmailClassificationInput(
                subject=_gmail_header(payload, "Subject"),
                sender=sender_header,
                snippet=message.get("snippet", ""),
                body=extract_message_body(payload)[:12_000],
            )
            draft = generate_email_reply_draft(sender)
            reviewed_count += 1
            if not draft.needs_reply:
                complete_message(account_email, message_id)
                skipped_count += 1
                continue

            raw_message = _make_reply_raw(
                recipient=sender_email,
                subject=draft.subject or sender.subject,
                body=draft.body,
                message_id=_gmail_header(payload, "Message-ID"),
                references=_gmail_header(payload, "References"),
            )
            service.users().drafts().create(
                userId="me",
                body={
                    "message": {
                        "raw": raw_message,
                        "threadId": thread_id,
                    }
                },
            ).execute()
            complete_message(account_email, message_id)
            draft_threads.add(thread_id)
            created_count += 1
        except Exception as exc:
            release_message(account_email, message_id)
            logger.warning(
                "Reply-draft processing failed for one message (%s)",
                type(exc).__name__,
            )
            if _is_ai_quota_exhausted(exc):
                warnings.append(
                    "The configured AI provider has no API credits remaining. "
                    "Add credits or configure another AI provider."
                )
            else:
                warnings.append(
                    "Some Inbox messages could not be checked for reply drafts."
                )

    return {
        "reviewed_count": reviewed_count,
        "created_count": created_count,
        "skipped_count": skipped_count,
        "warnings": list(dict.fromkeys(warnings)),
    }


@router.post("/classify", response_model=EmailClassificationResult)
def classify_email_route(email: EmailClassificationInput):
    try:
        return classify_email(email)
    except Exception as exc:
        logger.exception("Local email classification failed")
        raise HTTPException(
            status_code=502,
            detail="The email classification request failed.",
        ) from exc


@router.post(
    "/classify/batch",
    response_model=EmailClassificationBatchResponse,
)
def classify_emails_route(
    request: EmailClassificationBatchInput,
    _credentials: Credentials = Depends(get_current_credentials),
):
    try:
        return classify_emails(request)
    except Exception as exc:
        logger.exception("Local email batch classification failed")
        raise HTTPException(
            status_code=502,
            detail="The email batch classification request failed.",
        ) from exc


@router.post("/match-label", response_model=EmailLabelMatchResult)
def match_emails_to_label(
    request: EmailLabelMatchRequest,
    _credentials: Credentials = Depends(get_current_credentials),
):
    if not has_configured_provider():
        raise HTTPException(
            status_code=503,
            detail=(
                "Set OPENAI_API_KEY, GEMINI_API_KEY, or GROQ_API_KEY "
                "in backend/.env "
                "to enable AI label matching."
            ),
        )

    try:
        return find_emails_relevant_to_label(request)
    except Exception as exc:
        logger.exception("Email label matching provider request failed")
        if _is_ai_quota_exhausted(exc):
            raise HTTPException(
                status_code=503,
                detail=(
                    "The configured AI provider has no API credits remaining. "
                    "Add credits to its account or configure another AI provider."
                ),
            ) from exc

        raise HTTPException(
            status_code=502,
            detail="The email label matching provider request failed.",
        ) from exc



@router.get("")
def get_emails(
    max_results: int = 10,
    folder: Literal["all", "spam"] = "all",
    label: str | None = None,
    category_label: str | None = None,
    custom_labels: list[str] | None = None,
    refresh: bool = False,
    session: UserSession = Depends(get_current_session),
):
    if not 1 <= max_results <= 100:
        raise HTTPException(
            status_code=400,
            detail="max_results must be between 1 and 100.",
        )
    if label is not None and (not label.strip() or len(label) > 225):
        raise HTTPException(
            status_code=400,
            detail="label must contain 1 to 225 non-whitespace characters.",
        )
    for requested_label in (label, category_label):
        if requested_label is not None and (
            not requested_label.strip() or len(requested_label) > 225
        ):
            raise HTTPException(
                status_code=400,
                detail="Labels must contain 1 to 225 non-whitespace characters.",
            )
    custom_labels = custom_labels or []
    if any(not name.strip() or len(name) > 225 for name in custom_labels):
        raise HTTPException(
            status_code=400,
            detail="Custom labels must contain 1 to 225 non-whitespace characters.",
        )

    try:
        account_email = session.profile.get("email", "").strip().casefold()
        if not account_email:
            raise HTTPException(
                status_code=401,
                detail="The connected Gmail account has no profile email.",
            )

        filter_labels = [
            name.strip()
            for name in (label, category_label)
            if name is not None
        ]
        requested_labels = list(
            dict.fromkeys(
                [*(name.strip() for name in custom_labels), *filter_labels]
            )
        )
        label_ids_by_name = get_cached_gmail_label_ids(
            account_email,
            requested_labels,
        )

        service = None
        if requested_labels and len(label_ids_by_name) != len(set(requested_labels)):
            service = get_gmail_service(session.credentials)
            gmail_labels = (
                service.users()
                .labels()
                .list(userId="me")
                .execute()
                .get("labels", [])
            )
            store_cached_gmail_labels(account_email, gmail_labels)
            label_ids_by_name.update(
                {
                    item["name"]: item["id"]
                    for item in gmail_labels
                    if item.get("name") and item.get("id")
                }
            )

        label_ids: list[str] = []
        for label_name in filter_labels:
            label_id = label_ids_by_name.get(label_name)
            if label_id is None:
                raise HTTPException(
                    status_code=404,
                    detail=f'Gmail label "{label_name}" was not found.',
                )
            if label_id not in label_ids:
                label_ids.append(label_id)

        custom_category_labels = [
            (name.strip(), label_ids_by_name[name.strip()])
            for name in custom_labels
            if name.strip() in label_ids_by_name
        ]

        def add_custom_category(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
            categorized_emails = []
            for email in emails:
                categorized_email = dict(email)
                categorized_email.pop("category_label", None)
                email_label_ids = set(email.get("labels", []))
                matched_labels = [
                    name
                    for name, label_id in custom_category_labels
                    if label_id in email_label_ids
                ]
                if matched_labels:
                    categorized_email["category_label"] = matched_labels[0]
                    categorized_email["category_labels"] = matched_labels
                categorized_emails.append(categorized_email)
            return categorized_emails

        has_filter = bool(
            label_ids
            or folder == "spam"
        )
        if has_filter and not refresh:
            cached_matches = get_latest_cached_emails(
                account_email,
                max_results,
                label_ids=label_ids,
                spam_only=folder == "spam",
                exclude_spam=folder == "all",
            )
            # The cache keeps only the newest 50 messages. Use it when it can
            # fill this request; otherwise ask Gmail so older matching labels
            # are not incorrectly hidden by an incomplete cache.
            if len(cached_matches) >= max_results:
                categorized_matches = add_custom_category(cached_matches)
                return {
                    "count": len(categorized_matches),
                    "emails": categorized_matches,
                }

        if service is None:
            service = get_gmail_service(session.credentials)

        # Get recent message IDs from Gmail.
        list_arguments = {
            "userId": "me",
            "maxResults": max_results,
            "q": "-in:drafts",
        }
        if folder == "spam":
            label_ids.append("SPAM")
        if label_ids:
            list_arguments["labelIds"] = label_ids

        response = service.users().messages().list(**list_arguments).execute()

        messages = response.get("messages", [])
        message_details: dict[str, dict[str, Any]] = {}
        message_ids = [message["id"] for message in messages]
        cached_emails = get_cached_emails(account_email, message_ids)
        stale_before = time.time() - CACHE_REVALIDATION_SECONDS
        message_ids_to_fetch = [
            message_id
            for message_id in message_ids
            if (
                refresh
                or message_id not in cached_emails
                or cached_emails[message_id]["email"]
                .get("classification", {})
                .get("provider") == "rules"
                and cached_emails[message_id]["email"]
                .get("classification", {})
                .get("category") == "other"
                and is_security_related_content(
                    cached_emails[message_id]["email"].get("sender", ""),
                    cached_emails[message_id]["email"].get("subject", ""),
                    cached_emails[message_id]["email"].get("snippet", ""),
                    cached_emails[message_id]["email"].get("body", ""),
                )
                or has_unreadable_tracking_url(
                    cached_emails[message_id]["email"].get("body", "")
                )
                or cached_emails[message_id]["checked_at"] < stale_before
            )
        ]
        failed_message_ids: list[str] = []
        failed_message_errors: list[Exception] = []

        def collect_message_details(
            request_id: str,
            details: dict[str, Any] | None,
            error: Exception | None,
        ) -> None:
            if error is not None or details is None:
                failed_message_ids.append(request_id)
                if error is not None:
                    failed_message_errors.append(error)
                return
            message_details[request_id] = details

        if message_ids_to_fetch:
            batch = service.new_batch_http_request(
                callback=collect_message_details
            )
            for message_id in message_ids_to_fetch:
                batch.add(
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=message_id,
                        format="full",
                    ),
                    request_id=message_id,
                )
            batch.execute()

        if failed_message_ids:
            logger.warning(
                "Gmail batch failed to load %d of %d messages",
                len(failed_message_ids),
                len(messages),
            )
            if not message_details:
                if any(
                    _is_gmail_rate_limit_error(error)
                    for error in failed_message_errors
                ):
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Gmail temporarily rate-limited this request. "
                            "Wait a minute, then refresh your inbox."
                        ),
                    )
                raise RuntimeError("Gmail did not return any requested messages.")

        emails: list[dict[str, Any]] = []
        emails_to_cache: list[tuple[dict[str, Any], int]] = []
        emails_to_classify: list[dict[str, Any]] = []

        # Preserve Gmail's list order after the batch requests complete.
        for message, message_id in zip(messages, message_ids):
            cached_entry = cached_emails.get(message_id)
            details = message_details.get(message["id"])
            if details is None:
                if cached_entry is not None:
                    emails.append(cached_entry["email"])
                continue
            if "DRAFT" in details.get("labelIds", []):
                continue

            headers = details.get("payload", {}).get("headers", [])

            header_map = {
                header["name"].lower(): header["value"]
                for header in headers
            }

            email = {
                "id": details["id"],
                "thread_id": details.get("threadId"),
                "sender": redact_sensitive_tokens(
                    header_map.get("from", "Unknown")
                ),
                "to": redact_sensitive_tokens(header_map.get("to", "")),
                "subject": redact_sensitive_tokens(
                    header_map.get("subject", "(No subject)")
                ),
                "date": header_map.get("date", ""),
                "snippet": redact_sensitive_tokens(details.get("snippet", "")),
                "body": redact_sensitive_tokens(
                    extract_message_body(details.get("payload", {}))
                ),
                "labels": details.get("labelIds", []),
                "is_unread": "UNREAD" in details.get("labelIds", []),
            }
            previous_email = (
                cached_entry["email"] if cached_entry is not None else None
            )
            content_fields = ("sender", "subject", "snippet", "body", "date")
            content_changed = previous_email is None or any(
                email[field] != previous_email.get(field) for field in content_fields
            )
            if not content_changed and previous_email is not None:
                email["classification"] = previous_email["classification"]
            emails.append(email)
            emails_to_cache.append(
                (email, int(details.get("internalDate", "0")))
            )
            if content_changed or (
                previous_email is not None
                and previous_email.get("classification", {}).get("provider") == "rules"
                and previous_email.get("classification", {}).get("category") == "other"
                and is_security_related_content(
                    email["sender"], email["subject"], email["snippet"], email["body"]
                )
            ):
                emails_to_classify.append(email)

        classification_warnings: list[str] = []
        if emails_to_classify:
            classifications_by_id = {}
            for start in range(0, len(emails_to_classify), 10):
                email_batch = emails_to_classify[start : start + 10]
                # Incoming Gmail messages should use the configured AI provider
                # first; classify_emails falls back to local rules when needed.
                classification_response = classify_emails(
                    EmailClassificationBatchInput(
                        emails=[
                            EmailClassificationBatchItem(
                                id=email["id"],
                                sender=email["sender"][:500],
                                subject=email["subject"][:500],
                                snippet=email["snippet"][:2_000],
                                body=email["body"][:4_000],
                                received_at=email["date"][:100],
                            )
                            for email in email_batch
                        ]
                    )
                )
                classifications_by_id.update(
                    {
                        classification.id: (
                            classification,
                            classification_response.provider,
                        )
                        for classification in classification_response.classifications
                    }
                )
                classification_warnings.extend(
                    classification_response.warnings
                )

                for email in email_batch:
                    classification, provider = classifications_by_id[email["id"]]
                    email["classification"] = {
                        **classification.model_dump(mode="json", exclude={"id"}),
                        "provider": provider,
                    }

        # Apply the user's saved Gmail labels to every message in this result,
        # including cached messages that predate label setup.
        for label_name, label_id in custom_category_labels:
            candidates = [
                email
                for email in emails
                if label_id not in email.get("labels", [])
            ]
            if not candidates:
                continue
            try:
                if is_ecommerce_label(label_name):
                    matched_ids = {
                        email["id"]
                        for email in candidates
                        if is_ecommerce_email(
                            EmailLabelMatch(
                                id=email["id"],
                                sender=email["sender"][:500],
                                subject=email["subject"][:500],
                                snippet=email["snippet"][:2_000],
                                body=email["body"][:2_000],
                            )
                        )
                    }
                else:
                    matched_ids = set(
                        find_emails_relevant_to_label_locally(
                            label_name,
                            [
                                EmailLabelMatch(
                                    id=email["id"],
                                    sender=email["sender"][:500],
                                    subject=email["subject"][:500],
                                    snippet=email["snippet"][:2_000],
                                    body=email["body"][:2_000],
                                )
                                for email in candidates
                            ],
                        )
                    )

                if matched_ids:
                    service.users().messages().batchModify(
                        userId="me",
                        body={
                            "ids": sorted(matched_ids),
                            "addLabelIds": [label_id],
                        },
                    ).execute()
                    for email in candidates:
                        if email["id"] in matched_ids:
                            email["labels"] = list(
                                dict.fromkeys([*email.get("labels", []), label_id])
                            )
                            update_cached_email_labels(
                                account_email,
                                email["id"],
                                email["labels"],
                            )
            except Exception as exc:
                logger.warning(
                    "Automatic Gmail label matching failed for %s (%s)",
                    label_name,
                    type(exc).__name__,
                )

        store_cached_emails(account_email, emails_to_cache)

        result = {
            "count": len(emails),
            "emails": add_custom_category(emails),
        }
        if failed_message_ids:
            result["warnings"] = [
                f"{len(failed_message_ids)} of {len(messages)} emails could not "
                "be loaded. Showing the messages Gmail returned."
            ]
        if classification_warnings:
            result["warnings"] = list(
                dict.fromkeys(
                    result.get("warnings", []) + classification_warnings
                )
            )
        return result

    except HTTPException:
        raise
    except HttpError as exc:
        logger.error(
            "Gmail email fetch failed with HTTP %s",
            getattr(exc.resp, "status", "unknown"),
        )
        if _is_gmail_rate_limit_error(exc):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Gmail temporarily rate-limited this request. "
                    "Wait a minute, then refresh your inbox."
                ),
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="Gmail could not fetch emails. Please try again.",
        ) from exc
    except Exception as exc:
        logger.error(
            "Failed to fetch messages for authenticated Gmail user (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch Gmail messages. Please try again.",
        ) from exc
