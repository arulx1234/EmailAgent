import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field, field_validator

from app.api.auth import UserSession, get_current_credentials, get_current_session
from app.services.email_classifier import (
    EmailLabelMatch,
    EmailLabelMatchRequest,
    find_emails_relevant_to_label,
    find_emails_relevant_to_label_locally,
    is_ecommerce_email,
    is_ecommerce_label,
    has_configured_provider,
)
from app.services.gmail_service import (
    extract_message_body,
    get_gmail_service,
    redact_sensitive_tokens,
)
from app.services.mail_cache import (
    delete_cached_gmail_label,
    get_cached_emails,
    invalidate_cached_emails,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/labels",
    tags=["Labels"],
)


class GmailLabelRequest(BaseModel):
    name: str = Field(min_length=1, max_length=225)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Label name cannot be blank.")
        return value


class GmailLabelResponse(BaseModel):
    id: str
    name: str


class GmailLabelSyncResponse(BaseModel):
    label_name: str
    matched_count: int
    removed_count: int = 0


_ORDER_SEARCH_TERMS = (
    "order",
    "orders",
    "purchase",
    "purchased",
    "ordered",
    "shopping",
    "shipment",
    "shipped",
    "shipping",
    "delivery",
    "delivered",
    "arrived",
    "dispatched",
    "dispatch",
    "tracking",
    "package",
    "parcel",
    "shoe",
    "shoes",
    "sneaker",
    "sneakers",
    "receipt",
    "return",
    "refund",
)


def _candidate_search_query(label_name: str) -> str:
    terms = [label_name]
    if is_ecommerce_label(label_name):
        terms.extend(_ORDER_SEARCH_TERMS)

    unique_terms = list(dict.fromkeys(term.casefold() for term in terms))
    escaped_terms = []
    for term in unique_terms:
        escaped_term = term.replace("\\", "\\\\").replace('"', '\\"')
        escaped_terms.append(f'"{escaped_term}"')
    return f'-in:drafts {{{" ".join(escaped_terms)}}}'


def _list_all_message_ids(
    messages: Any,
    **list_arguments: Any,
) -> list[str]:
    message_ids: list[str] = []
    page_token = None
    while True:
        arguments = {
            "userId": "me",
            "maxResults": 100,
            **list_arguments,
        }
        if page_token:
            arguments["pageToken"] = page_token
        result = messages.list(**arguments).execute()
        message_ids.extend(
            message["id"] for message in result.get("messages", [])
        )
        page_token = result.get("nextPageToken")
        if not page_token:
            return message_ids


def _is_gmail_rate_limit_error(error: BaseException | None) -> bool:
    while error is not None:
        status = getattr(getattr(error, "resp", None), "status", None)
        if status == 429:
            return True

        content = getattr(error, "content", None)
        if isinstance(content, bytes):
            try:
                response_body = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                response_body = {}
            reasons = {
                item.get("reason")
                for item in response_body.get("error", {}).get("errors", [])
                if isinstance(item, dict)
            }
            if reasons.intersection(
                {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"}
            ):
                return True

        error = error.__cause__ or error.__context__
    return False


@router.post("", response_model=GmailLabelResponse)
def create_gmail_label(
    request: GmailLabelRequest,
    credentials: Credentials = Depends(get_current_credentials),
) -> GmailLabelResponse:
    try:
        service = get_gmail_service(credentials)
        labels = (
            service.users()
            .labels()
            .list(userId="me")
            .execute()
            .get("labels", [])
        )
        existing_label = next(
            (label for label in labels if label.get("name") == request.name),
            None,
        )
        if existing_label:
            return GmailLabelResponse(
                id=existing_label["id"],
                name=existing_label["name"],
            )

        created_label = (
            service.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": request.name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        return GmailLabelResponse(
            id=created_label["id"],
            name=created_label["name"],
        )
    except HttpError as exc:
        logger.exception("Gmail label request failed")
        if exc.resp.status == 403:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Gmail label access was denied. Disconnect and reconnect "
                    "Gmail to grant label-management access."
                ),
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="Gmail could not create the label. Please try again.",
        ) from exc
    except Exception as exc:
        logger.exception("Gmail label request failed")
        raise HTTPException(
            status_code=502,
            detail="Gmail could not create the label. Please try again.",
        ) from exc


@router.delete("")
def delete_gmail_label(
    name: str = Query(min_length=1, max_length=225),
    session: UserSession = Depends(get_current_session),
) -> dict[str, str]:
    normalized_name = name.strip()
    if not normalized_name:
        raise HTTPException(status_code=422, detail="Label name cannot be blank.")

    account_email = session.profile.get("email", "").strip().casefold()
    if not account_email:
        raise HTTPException(
            status_code=401,
            detail="The connected Gmail account has no profile email.",
        )

    try:
        service = get_gmail_service(session.credentials)
        labels = (
            service.users()
            .labels()
            .list(userId="me")
            .execute()
            .get("labels", [])
        )
        gmail_label = next(
            (label for label in labels if label.get("name") == normalized_name),
            None,
        )
        if gmail_label is None:
            # The label may have been deleted in Gmail already; clear stale app state.
            delete_cached_gmail_label(account_email, normalized_name)
            return {"name": normalized_name, "status": "deleted"}
        if gmail_label.get("type") != "user":
            raise HTTPException(
                status_code=400,
                detail="Built-in Gmail labels cannot be deleted from the app.",
            )

        affected_message_ids = _list_all_message_ids(
            service.users().messages(),
            labelIds=[gmail_label["id"]],
        )
        service.users().labels().delete(
            userId="me", id=gmail_label["id"]
        ).execute()
        delete_cached_gmail_label(account_email, normalized_name)
        invalidate_cached_emails(account_email, affected_message_ids)
        return {"name": normalized_name, "status": "deleted"}
    except HTTPException:
        raise
    except HttpError as exc:
        logger.exception("Gmail label deletion failed")
        if getattr(exc.resp, "status", None) == 403:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Gmail denied label deletion. Disconnect and reconnect "
                    "Gmail to grant label-management access."
                ),
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="Gmail could not delete the label. Please try again.",
        ) from exc
    except Exception as exc:
        logger.exception("Gmail label deletion failed")
        raise HTTPException(
            status_code=502,
            detail="Gmail could not delete the label. Please try again.",
        ) from exc
@router.post("/sync", response_model=GmailLabelSyncResponse)
def sync_gmail_label(
    request: GmailLabelRequest,
    session: UserSession = Depends(get_current_session),
) -> GmailLabelSyncResponse:
    try:
        account_email = session.profile.get("email", "").strip().casefold()
        if not account_email:
            raise HTTPException(
                status_code=401,
                detail="The connected Gmail account has no profile email.",
            )
        service = get_gmail_service(session.credentials)
        labels = (
            service.users()
            .labels()
            .list(userId="me")
            .execute()
            .get("labels", [])
        )
        gmail_label = next(
            (label for label in labels if label.get("name") == request.name),
            None,
        )
        if gmail_label is None:
            raise HTTPException(
                status_code=404,
                detail=f'Gmail label "{request.name}" was not found.',
            )
        messages = service.users().messages()
        candidate_ids = _list_all_message_ids(
            messages,
            q=_candidate_search_query(request.name),
        )
        existing_label_ids = set(
            _list_all_message_ids(
                messages,
                labelIds=[gmail_label["id"]],
            )
        )
        message_ids = list(
            dict.fromkeys([*candidate_ids, *existing_label_ids])
        )
        matched_count = 0
        removed_count = 0

        for start in range(0, len(message_ids), 100):
            message_batch_ids = message_ids[start : start + 100]
            cached_entries = get_cached_emails(
                account_email,
                message_batch_ids,
            )
            ids_to_fetch = [
                message_id
                for message_id in message_batch_ids
                if message_id not in cached_entries
            ]
            message_details: dict[str, dict[str, Any]] = {}
            batch_errors: list[Exception] = []

            def collect_message_details(
                request_id: str,
                details: dict[str, Any] | None,
                error: Exception | None,
            ) -> None:
                if error is not None:
                    batch_errors.append(error)
                elif details is not None:
                    message_details[request_id] = details

            if ids_to_fetch:
                batch = service.new_batch_http_request(
                    callback=collect_message_details
                )
                for message_id in ids_to_fetch:
                    batch.add(
                        messages.get(
                            userId="me",
                            id=message_id,
                            format="full",
                        ),
                        request_id=message_id,
                    )
                batch.execute()
                if batch_errors or len(message_details) != len(ids_to_fetch):
                    failure = batch_errors[0] if batch_errors else None
                    if _is_gmail_rate_limit_error(failure):
                        raise HTTPException(
                            status_code=503,
                            detail=(
                                "Gmail temporarily rate-limited label sync. "
                                "Wait a minute, then retry."
                            ),
                        ) from failure
                    logger.error(
                        "Gmail label sync could not load all %d uncached candidate messages",
                        len(ids_to_fetch),
                    )
                    raise RuntimeError(
                        "Gmail could not load every candidate email for label matching."
                    ) from failure

            emails_to_match = []
            previously_labeled_ids = set(existing_label_ids).intersection(
                message_batch_ids
            )
            for message_id in message_batch_ids:
                cached_entry = cached_entries.get(message_id)
                cached_email = cached_entry["email"] if cached_entry else None
                details = message_details.get(message_id)
                label_ids = (
                    cached_email.get("labels", [])
                    if cached_email is not None
                    else details.get("labelIds", [])
                )
                if "DRAFT" in label_ids:
                    continue
                if cached_email is not None:
                    emails_to_match.append(
                        EmailLabelMatch(
                            id=message_id,
                            sender=cached_email.get("sender", ""),
                            subject=cached_email.get("subject", ""),
                            snippet=cached_email.get("snippet", ""),
                            body=cached_email.get("body", "")[:2_000],
                        )
                    )
                    continue

                payload = details.get("payload", {})
                headers = {
                    header.get("name", "").lower(): header.get("value", "")
                    for header in payload.get("headers", [])
                }
                emails_to_match.append(
                    EmailLabelMatch(
                        id=message_id,
                        sender=redact_sensitive_tokens(headers.get("from", "")),
                        subject=redact_sensitive_tokens(headers.get("subject", "")),
                        snippet=redact_sensitive_tokens(
                            details.get("snippet", "")
                        ),
                        body=redact_sensitive_tokens(
                            extract_message_body(payload)
                        )[:2_000],
                    )
                )

            matching_ids: set[str] = set()
            if emails_to_match:
                if is_ecommerce_label(request.name):
                    matching_ids = {
                        email.id
                        for email in emails_to_match
                        if is_ecommerce_email(email)
                    }
                elif has_configured_provider():
                    try:
                        match_result = find_emails_relevant_to_label(
                            EmailLabelMatchRequest(
                                label=request.name,
                                emails=emails_to_match,
                            )
                        )
                        matching_ids = set(match_result.matching_ids)
                    except Exception as exc:
                        logger.warning(
                            "AI matching failed for Gmail label %s (%s); local matching was used.",
                            request.name,
                            type(exc).__name__,
                        )
                        matching_ids = set(
                            find_emails_relevant_to_label_locally(
                                request.name,
                                emails_to_match,
                            )
                        )
                else:
                    matching_ids = set(
                        find_emails_relevant_to_label_locally(
                            request.name,
                            emails_to_match,
                        )
                    )

            ids_to_add = matching_ids - previously_labeled_ids
            ids_to_remove = previously_labeled_ids - matching_ids
            if ids_to_add:
                messages.batchModify(
                    userId="me",
                    body={
                        "ids": sorted(ids_to_add),
                        "addLabelIds": [gmail_label["id"]],
                    },
                ).execute()
            if ids_to_remove:
                messages.batchModify(
                    userId="me",
                    body={
                        "ids": sorted(ids_to_remove),
                        "removeLabelIds": [gmail_label["id"]],
                    },
                ).execute()

            matched_count += len(matching_ids)
            removed_count += len(ids_to_remove)

        invalidate_cached_emails(account_email, message_ids)

        return GmailLabelSyncResponse(
            label_name=request.name,
            matched_count=matched_count,
            removed_count=removed_count,
        )
    except HTTPException:
        raise
    except HttpError as exc:
        logger.exception("Gmail label sync failed")
        status = getattr(exc.resp, "status", None)
        if _is_gmail_rate_limit_error(exc):
            raise HTTPException(
                status_code=503,
                detail="Gmail temporarily rate-limited label sync. Wait a minute, then retry.",
            ) from exc
        if status == 403:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Gmail could not update message labels. Disconnect and "
                    "reconnect Gmail to grant message-label access."
                ),
            ) from exc
        if status == 429:
            raise HTTPException(
                status_code=503,
                detail="Gmail rate-limited label sync. Wait a minute, then retry.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=(
                f"Gmail rejected label sync (HTTP {status or 'unknown'}). "
                "Check Gmail access and retry."
            ),
        ) from exc
    except RuntimeError as exc:
        logger.exception("Gmail label sync processing failed")
        error_message = str(exc).casefold()
        if "classification provider" in error_message or "configure" in error_message:
            raise HTTPException(
                status_code=503,
                detail=(
                    "AI label matching failed. Check the configured provider key, "
                    "model name, and available quota, then retry."
                ),
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=(
                "Gmail label sync could not load or update all matching emails. "
                "Check the backend log for the failed Gmail request, then retry."
            ),
        ) from exc
    except Exception as exc:
        logger.exception("Gmail label sync failed")
        raise HTTPException(
            status_code=502,
            detail=(
                "Label sync failed due to an unexpected backend error "
                f"({type(exc).__name__}). Check the backend log, then retry."
            ),
        ) from exc
