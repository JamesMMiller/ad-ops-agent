"""Minimal Hashnode GraphQL client (stdlib only)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

# Production playground host often returns HTML; the GraphQL API is on gql-beta.
DEFAULT_GQL_URL = "https://gql-beta.hashnode.com"


class HashnodeError(RuntimeError):
    pass


def gql_url() -> str:
    return (os.environ.get("HASHNODE_GQL_URL") or DEFAULT_GQL_URL).rstrip("/")


def pat() -> str:
    token = (os.environ.get("HASHNODE_PAT") or "").strip()
    if not token:
        raise HashnodeError("HASHNODE_PAT is not set (see .env.example)")
    return token


def publication_id() -> str:
    pub = (os.environ.get("HASHNODE_PUBLICATION_ID") or "").strip()
    if not pub:
        raise HashnodeError("HASHNODE_PUBLICATION_ID is not set (see .env.example)")
    return pub


def _request(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"query": query, "variables": variables or {}}
    data = json.dumps(payload).encode("utf-8")
    # Cloudflare on gql.hashnode.com bans the default Python-urllib user-agent.
    req = urllib.request.Request(
        gql_url(),
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {pat()}",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Origin": "https://hashnode.com",
            "Referer": "https://hashnode.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise HashnodeError(f"HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise HashnodeError(f"Network error: {e}") from e

    if not raw.strip():
        raise HashnodeError("Empty response from Hashnode GraphQL")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HashnodeError(f"Non-JSON response: {raw[:240]!r}") from e

    if body.get("errors"):
        msgs = "; ".join(
            (err.get("message") or json.dumps(err)) for err in body["errors"]
        )
        raise HashnodeError(msgs)
    if "data" not in body:
        raise HashnodeError(f"Unexpected response: {body!r}")
    return body["data"]


def me_publications() -> dict[str, Any]:
    query = """
    query MePubs {
      me {
        id
        username
        name
        publications(first: 20) {
          edges {
            node {
              id
              title
              url
            }
          }
        }
      }
    }
    """
    return _request(query)


def create_draft(input_data: dict[str, Any]) -> dict[str, Any]:
    query = """
    mutation CreateDraft($input: CreateDraftInput!) {
      createDraft(input: $input) {
        draft { id title slug }
      }
    }
    """
    data = _request(query, {"input": input_data})
    return data["createDraft"]["draft"]


def update_draft(input_data: dict[str, Any]) -> dict[str, Any]:
    query = """
    mutation UpdateDraft($input: UpdateDraftInput!) {
      updateDraft(input: $input) {
        draft { id title slug }
      }
    }
    """
    data = _request(query, {"input": input_data})
    return data["updateDraft"]["draft"]


def publish_draft(draft_id: str) -> dict[str, Any]:
    query = """
    mutation PublishDraft($input: PublishDraftInput!) {
      publishDraft(input: $input) {
        post { id title slug url publishedAt }
      }
    }
    """
    data = _request(query, {"input": {"draftId": draft_id}})
    return data["publishDraft"]["post"]


def publish_post(input_data: dict[str, Any]) -> dict[str, Any]:
    query = """
    mutation PublishPost($input: PublishPostInput!) {
      publishPost(input: $input) {
        post { id title slug url publishedAt }
      }
    }
    """
    data = _request(query, {"input": input_data})
    return data["publishPost"]["post"]


def update_post(input_data: dict[str, Any]) -> dict[str, Any]:
    query = """
    mutation UpdatePost($input: UpdatePostInput!) {
      updatePost(input: $input) {
        post { id title slug url publishedAt }
      }
    }
    """
    data = _request(query, {"input": input_data})
    return data["updatePost"]["post"]


def create_image_upload_url(content_type: str) -> dict[str, Any]:
    query = """
    mutation CreateImageUploadURL($input: CreateImageUploadInput!) {
      createImageUploadURL(input: $input) {
        presignedPost { url fields }
      }
    }
    """
    data = _request(query, {"input": {"contentType": content_type}})
    return data["createImageUploadURL"]["presignedPost"]


def upload_image(path: str, content_type: str = "image/png") -> str:
    """Upload a local image via Hashnode presigned POST; return public object URL."""
    import mimetypes
    from pathlib import Path
    import urllib.parse

    p = Path(path)
    if not p.is_file():
        raise HashnodeError(f"Image not found: {path}")
    ctype = content_type or mimetypes.guess_type(p.name)[0] or "image/png"
    presigned = create_image_upload_url(ctype)
    url = presigned["url"]
    fields = dict(presigned.get("fields") or {})
    # multipart encode: fields first, file last
    boundary = "----AdOpsHashnodeBoundary7MA4YWxkTrZu0gW"
    body = bytearray()
    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        body.extend(str(value).encode())
        body.extend(b"\r\n")
    file_bytes = p.read_bytes()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{p.name}"\r\n'.encode()
    )
    body.extend(f"Content-Type: {ctype}\r\n\r\n".encode())
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        url,
        data=bytes(body),
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise HashnodeError(f"Image upload HTTP {e.code}: {detail}") from e

    key = fields.get("key") or fields.get("Key")
    if not key:
        raise HashnodeError("Presigned post missing key field")
    # Public CDN URL is typically upload host + key
    base = url.rstrip("/")
    if "amazonaws.com" in base or "s3" in base:
        # Hashnode CDN usually looks like https://cdn.hashnode.com/res/hashnode/image/upload/...
        # Prefer constructing from key if it already includes full path style.
        if str(key).startswith("http"):
            return str(key)
        return urllib.parse.urljoin(base + "/", str(key))
    return urllib.parse.urljoin(base + "/", str(key))
