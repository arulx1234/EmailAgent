import base64
import html
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


_TOKEN_ASSIGNMENT = re.compile(
    r"""(?i)\b((?:(?:access|refresh|id|auth|oauth|api)[_-]?\s*)?token)\b"""
    r"""(\s*[:=]\s*)(?:"[^"\r\n]*"|'[^'\r\n]*'|[A-Za-z0-9._~+/=-]+)"""
)
_BEARER_TOKEN = re.compile(
    r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"
)
_JWT = re.compile(
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}\b"
)
_COMMON_API_TOKEN = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,})\b"
)
_GOOGLE_TOKEN = re.compile(
    r"\b(?:ya29\.[A-Za-z0-9_-]{20,}|1//[A-Za-z0-9_-]{20,})\b"
)
_URL = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
_URL_SUFFIX_PUNCTUATION = ".,;:!?)]}>'\""
_TRACKING_PARAMETER = re.compile(
    r"^(?:token|midtoken|trk|eid|lipi|utm_.+|tracking(?:_id)?)$",
    re.IGNORECASE,
)


def has_unreadable_tracking_url(text: str) -> bool:
    for match in _URL.finditer(text):
        raw_url = match.group(0).rstrip(_URL_SUFFIX_PUNCTUATION)
        try:
            parts = urlsplit(raw_url)
        except ValueError:
            continue
        has_tracking = any(
            _TRACKING_PARAMETER.match(parameter.split("=", 1)[0])
            for parameter in parts.query.split("&")
            if parameter
        )
        if len(raw_url) > 180 or has_tracking:
            return True
    return False


def redact_sensitive_tokens(text: str) -> str:
    text = _TOKEN_ASSIGNMENT.sub(r"\1\2[REDACTED]", text)
    text = _BEARER_TOKEN.sub("Bearer [REDACTED]", text)
    text = _JWT.sub("[REDACTED]", text)
    text = _COMMON_API_TOKEN.sub("[REDACTED]", text)
    return _GOOGLE_TOKEN.sub("[REDACTED]", text)


class _HTMLTextParser(HTMLParser):
    _block_tags = {
        "address",
        "article",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "li",
        "p",
        "section",
        "tr",
        "td",
        "table",
        "ul",
        "ol",
        "blockquote",
        "footer",
    }
    _ignored_tags = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        _attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag in self._ignored_tags:
            self.ignored_depth += 1
        elif self.ignored_depth == 0 and tag in self._block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._ignored_tags and self.ignored_depth > 0:
            self.ignored_depth -= 1
        elif self.ignored_depth == 0 and tag in self._block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignored_depth == 0:
            self.parts.append(data)


def _decode_body_data(part: dict[str, Any]) -> str:
    data = part.get("body", {}).get("data")
    if not isinstance(data, str) or not data:
        return ""
    padded_data = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded_data).decode("utf-8", errors="replace")
    except (ValueError, base64.binascii.Error):
        return ""


def _clean_mail_text(text: str) -> str:
    text = html.unescape(text).replace("\r", "")
    # Join quoted-printable soft-wrapped lines before detecting long links.
    text = re.sub(r"=\n", "", text)

    def clean_url(match: re.Match[str]) -> str:
        raw_url = match.group(0)
        trailing = ""
        while raw_url and raw_url[-1] in _URL_SUFFIX_PUNCTUATION:
            trailing = raw_url[-1] + trailing
            raw_url = raw_url[:-1]
        try:
            parts = urlsplit(raw_url)
            query_has_tracking = any(
                _TRACKING_PARAMETER.match(parameter.split("=", 1)[0])
                for parameter in parts.query.split("&")
                if parameter
            )
            if len(raw_url) > 180 or query_has_tracking:
                raw_url = urlunsplit(
                    (parts.scheme, parts.netloc, parts.path, "", "")
                )
        except ValueError:
            pass
        return f"\n{raw_url}{trailing}"

    text = _URL.sub(clean_url, text)
    lines = [re.sub(r"[\t\u00a0 ]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def extract_message_body(payload: dict[str, Any]) -> str:
    plain_text_parts: list[str] = []
    html_parts: list[str] = []

    def collect_parts(part: dict[str, Any]) -> None:
        if part.get("filename"):
            return

        mime_type = part.get("mimeType")
        text = _decode_body_data(part)
        if mime_type == "text/plain" and text.strip():
            plain_text_parts.append(text)
        elif mime_type == "text/html" and text.strip():
            html_parts.append(text)

        for nested_part in part.get("parts", []):
            collect_parts(nested_part)

    collect_parts(payload)

    if plain_text_parts:
        return _clean_mail_text("\n\n".join(plain_text_parts))

    if html_parts:
        parser = _HTMLTextParser()
        parser.feed("\n\n".join(html_parts))
        return _clean_mail_text(
            "\n".join(
                line.strip()
                for line in "".join(parser.parts).splitlines()
                if line.strip()
            )
        )

    return ""


def get_gmail_service(credentials: Credentials):
    # Refresh the access token if it has expired.
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            raise RuntimeError(
                "Gmail credentials are invalid. Please reconnect Gmail."
            )

    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )
