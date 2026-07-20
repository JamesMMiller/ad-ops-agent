"""
Shopify Admin GraphQL helpers for the shopify-store skill.

Auth: Dev Dashboard client credentials grant (2026+).
  POST https://{shop}/admin/oauth/access_token
  grant_type=client_credentials&client_id=...&client_secret=...

Env (load .env with python-dotenv first):
  SHOPIFY_SHOP              — e.g. our-tech-accessories.myshopify.com
  SHOPIFY_CLIENT_ID
  SHOPIFY_CLIENT_SECRET
  SHOPIFY_API_VERSION       — default 2025-10
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

_TOKEN_CACHE: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


def get_shop() -> str:
    shop = (os.getenv("SHOPIFY_SHOP") or "").strip().rstrip("/")
    if shop.startswith("https://"):
        shop = shop[len("https://") :]
    if not shop:
        raise RuntimeError("SHOPIFY_SHOP not set — see .env.example")
    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"
    return shop


def get_api_version() -> str:
    return os.getenv("SHOPIFY_API_VERSION", "2025-10")


def get_client_id() -> str:
    cid = os.getenv("SHOPIFY_CLIENT_ID", "").strip()
    if not cid:
        raise RuntimeError("SHOPIFY_CLIENT_ID not set — see .env.example")
    return cid


def get_client_secret() -> str:
    secret = os.getenv("SHOPIFY_CLIENT_SECRET", "").strip()
    if not secret:
        raise RuntimeError("SHOPIFY_CLIENT_SECRET not set — see .env.example")
    return secret


def _token_url() -> str:
    return f"https://{get_shop()}/admin/oauth/access_token"


def _graphql_url() -> str:
    return f"https://{get_shop()}/admin/api/{get_api_version()}/graphql.json"


def fetch_access_token(force: bool = False) -> str:
    """Exchange client credentials for a short-lived Admin API token (~24h)."""
    now = time.time()
    if (
        not force
        and _TOKEN_CACHE.get("access_token")
        and now < float(_TOKEN_CACHE.get("expires_at", 0)) - 60
    ):
        return _TOKEN_CACHE["access_token"]

    resp = requests.post(
        _token_url(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": get_client_id(),
            "client_secret": get_client_secret(),
        },
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Token exchange failed HTTP {resp.status_code}: {resp.text[:500]}"
        )
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"No access_token in response: {json.dumps(data)[:500]}")
    expires_in = int(data.get("expires_in", 86399))
    _TOKEN_CACHE["access_token"] = token
    _TOKEN_CACHE["expires_at"] = now + expires_in
    return token


def graphql(
    query: str,
    variables: dict[str, Any] | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    if dry_run:
        return {
            "dry_run": True,
            "query": query,
            "variables": variables or {},
        }
    token = fetch_access_token()
    resp = requests.post(
        _graphql_url(),
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token,
        },
        json={"query": query, "variables": variables or {}},
        timeout=120,
    )
    try:
        payload = resp.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response HTTP {resp.status_code}: {resp.text[:500]}") from exc
    if resp.status_code != 200:
        raise RuntimeError(f"GraphQL HTTP {resp.status_code}: {json.dumps(payload)[:800]}")
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL errors: {json.dumps(payload['errors'])[:800]}")
    return payload


def shop_info() -> dict[str, Any]:
    q = """
    query {
      shop {
        name
        myshopifyDomain
        primaryDomain { url host }
        currencyCode
      }
      appInstallation {
        accessScopes { handle }
      }
    }
    """
    return graphql(q)["data"]


def list_products(first: int = 20, query: str | None = None) -> list[dict[str, Any]]:
    q = """
    query Products($first: Int!, $query: String) {
      products(first: $first, query: $query) {
        nodes {
          id
          title
          handle
          status
          onlineStoreUrl
          featuredImage { url altText }
        }
      }
    }
    """
    data = graphql(q, {"first": first, "query": query})["data"]
    return data["products"]["nodes"]


def get_product_by_handle(handle: str) -> dict[str, Any] | None:
    nodes = list_products(first=5, query=f"handle:{handle}")
    for node in nodes:
        if node.get("handle") == handle:
            return node
    return nodes[0] if nodes else None


def get_product_detail(product_id: str) -> dict[str, Any]:
    q = """
    query Product($id: ID!) {
      product(id: $id) {
        id
        title
        handle
        descriptionHtml
        seo { title description }
        featuredImage { url altText }
        media(first: 20) {
          nodes {
            ... on MediaImage {
              id
              image { url altText }
            }
          }
        }
      }
    }
    """
    return graphql(q, {"id": product_id})["data"]["product"]


def update_product(
    product_id: str,
    *,
    title: str | None = None,
    description_html: str | None = None,
    seo_title: str | None = None,
    seo_description: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    input_obj: dict[str, Any] = {"id": product_id}
    if title is not None:
        input_obj["title"] = title
    if description_html is not None:
        input_obj["descriptionHtml"] = description_html
    if seo_title is not None or seo_description is not None:
        input_obj["seo"] = {}
        if seo_title is not None:
            input_obj["seo"]["title"] = seo_title
        if seo_description is not None:
            input_obj["seo"]["description"] = seo_description

    q = """
    mutation productUpdate($input: ProductInput!) {
      productUpdate(input: $input) {
        product { id title handle descriptionHtml }
        userErrors { field message }
      }
    }
    """
    return graphql(q, {"input": input_obj}, dry_run=dry_run)


def list_pages(first: int = 50) -> list[dict[str, Any]]:
    q = """
    query Pages($first: Int!) {
      pages(first: $first) {
        nodes { id title handle bodySummary isPublished }
      }
    }
    """
    return graphql(q, {"first": first})["data"]["pages"]["nodes"]


def get_page_by_handle(handle: str) -> dict[str, Any] | None:
    for page in list_pages():
        if page.get("handle") == handle:
            return page
    return None


def upsert_page(
    *,
    title: str,
    handle: str,
    body_html: str,
    page_id: str | None = None,
    is_published: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    if page_id:
        q = """
        mutation pageUpdate($id: ID!, $page: PageUpdateInput!) {
          pageUpdate(id: $id, page: $page) {
            page { id title handle }
            userErrors { field message }
          }
        }
        """
        variables = {
            "id": page_id,
            "page": {
                "title": title,
                "handle": handle,
                "body": body_html,
                "isPublished": is_published,
            },
        }
    else:
        q = """
        mutation pageCreate($page: PageCreateInput!) {
          pageCreate(page: $page) {
            page { id title handle }
            userErrors { field message }
          }
        }
        """
        variables = {
            "page": {
                "title": title,
                "handle": handle,
                "body": body_html,
                "isPublished": is_published,
            },
        }
    return graphql(q, variables, dry_run=dry_run)


def list_themes() -> list[dict[str, Any]]:
    q = """
    query {
      themes(first: 25) {
        nodes { id name role createdAt updatedAt }
      }
    }
    """
    return graphql(q)["data"]["themes"]["nodes"]


def get_main_theme_id() -> str | None:
    env_id = os.getenv("SHOPIFY_THEME_ID", "").strip()
    if env_id:
        return env_id if env_id.startswith("gid://") else f"gid://shopify/OnlineStoreTheme/{env_id}"
    for theme in list_themes():
        if theme.get("role") == "MAIN":
            return theme["id"]
    return None


def get_theme_file(theme_id: str, filename: str) -> str | None:
    q = """
    query ThemeFile($themeId: ID!, $filenames: [String!]!) {
      theme(id: $themeId) {
        files(filenames: $filenames) {
          nodes {
            filename
            body {
              ... on OnlineStoreThemeFileBodyText { content }
              ... on OnlineStoreThemeFileBodyBase64 { contentBase64 }
            }
          }
        }
      }
    }
    """
    data = graphql(q, {"themeId": theme_id, "filenames": [filename]})["data"]
    nodes = (data.get("theme") or {}).get("files", {}).get("nodes", [])
    if not nodes:
        return None
    body = nodes[0].get("body") or {}
    if "content" in body:
        return body["content"]
    if "contentBase64" in body:
        import base64

        return base64.b64decode(body["contentBase64"]).decode("utf-8", errors="replace")
    return None


def upsert_theme_files(
    theme_id: str,
    files: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """files: [{filename, body: {type: TEXT|BASE64|URL, value}}]"""
    q = """
    mutation themeFilesUpsert($themeId: ID!, $files: [OnlineStoreThemeFilesUpsertFileInput!]!) {
      themeFilesUpsert(themeId: $themeId, files: $files) {
        upsertedThemeFiles { filename }
        job { id }
        userErrors { field message }
      }
    }
    """
    return graphql(q, {"themeId": theme_id, "files": files}, dry_run=dry_run)


def create_file_from_url(url: str, alt: str | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    """Register a remote image URL in Shopify Files."""
    q = """
    mutation fileCreate($files: [FileCreateInput!]!) {
      fileCreate(files: $files) {
        files {
          ... on MediaImage { id image { url altText } }
          ... on GenericFile { id url }
        }
        userErrors { field message }
      }
    }
    """
    file_input: dict[str, Any] = {
        "originalSource": url,
        "contentType": "IMAGE",
    }
    if alt:
        file_input["alt"] = alt
    return graphql(q, {"files": [file_input]}, dry_run=dry_run)


def resolve_output_dir(slug: str) -> Path:
    base = os.getenv("OUTPUT_BASE")
    root = Path(base) if base else Path("outputs/shopify")
    run_dir = root / slug
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def dump_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
