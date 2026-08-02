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
        options {
          id
          name
          values
          optionValues { id name }
        }
        media(first: 50) {
          nodes {
            ... on MediaImage {
              id
              alt
              image { url altText }
            }
          }
        }
        variants(first: 250) {
          nodes {
            id
            title
            price
            sku
            availableForSale
            selectedOptions { name value }
            image { url altText }
            media(first: 5) {
              nodes {
                ... on MediaImage {
                  id
                  image { url altText }
                }
              }
            }
          }
        }
      }
    }
    """
    return graphql(q, {"id": product_id})["data"]["product"]


def product_create_media(
    product_id: str,
    media: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Attach media via CreateMediaInput: {originalSource, mediaContentType, alt?}."""
    q = """
    mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
      productCreateMedia(productId: $productId, media: $media) {
        media {
          ... on MediaImage {
            id
            alt
            image { url }
          }
        }
        mediaUserErrors { field message code }
      }
    }
    """
    return graphql(q, {"productId": product_id, "media": media}, dry_run=dry_run)


def product_options_create(
    product_id: str,
    options: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """options: [{name, values: [{name}]}]"""
    q = """
    mutation productOptionsCreate($productId: ID!, $options: [OptionCreateInput!]!) {
      productOptionsCreate(productId: $productId, options: $options) {
        product {
          id
          options { id name values }
          variants(first: 50) { nodes { id title } }
        }
        userErrors { field message code }
      }
    }
    """
    return graphql(q, {"productId": product_id, "options": options}, dry_run=dry_run)


def product_variants_bulk_update(
    product_id: str,
    variants: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    q = """
    mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
      productVariantsBulkUpdate(productId: $productId, variants: $variants) {
        productVariants { id title price }
        userErrors { field message }
      }
    }
    """
    return graphql(q, {"productId": product_id, "variants": variants}, dry_run=dry_run)


def update_product(
    product_id: str,
    *,
    title: str | None = None,
    description_html: str | None = None,
    seo_title: str | None = None,
    seo_description: str | None = None,
    template_suffix: str | None = None,
    product_type: str | None = None,
    vendor: str | None = None,
    tags: list[str] | None = None,
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
    if template_suffix is not None:
        # Empty string clears suffix back to default product.json
        input_obj["templateSuffix"] = template_suffix
    if product_type is not None:
        input_obj["productType"] = product_type
    if vendor is not None:
        input_obj["vendor"] = vendor
    if tags is not None:
        input_obj["tags"] = tags

    q = """
    mutation productUpdate($input: ProductInput!) {
      productUpdate(input: $input) {
        product {
          id title handle descriptionHtml templateSuffix productType vendor tags
        }
        userErrors { field message }
      }
    }
    """
    return graphql(q, {"input": input_obj}, dry_run=dry_run)


def rename_product_options(
    product_id: str,
    option_renames: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    option_renames shape (from project.json):
      {
        "names": {"Applicable Model": "Phone model", "Color": "Colour"},
        "values": {"Applicable Model": {"IPhone16Pro": "iPhone 16 Pro", ...}}
      }
    Or legacy flat colour map: {"Gun Color": "Gunmetal"} applied to values of option named Color.
    """
    detail = get_product_detail(product_id)
    options = detail.get("options") or []
    names_map = dict(option_renames.get("names") or {})
    values_by_option = dict(option_renames.get("values") or {})

    # Legacy flat map (qi2-folding-charger style): treat as Color/Colour value renames
    legacy_keys = [k for k in option_renames.keys() if k not in ("names", "values")]
    if legacy_keys:
        colour_key = next(
            (o["name"] for o in options if o.get("name") in ("Color", "Colour")),
            "Color",
        )
        values_by_option.setdefault(colour_key, {}).update(
            {k: option_renames[k] for k in legacy_keys}
        )

    q = """
    mutation productOptionUpdate(
      $productId: ID!
      $option: OptionUpdateInput!
      $optionValuesToUpdate: [OptionValueUpdateInput!]
    ) {
      productOptionUpdate(
        productId: $productId
        option: $option
        optionValuesToUpdate: $optionValuesToUpdate
      ) {
        product {
          id
          options { id name optionValues { id name } }
        }
        userErrors { field message code }
      }
    }
    """
    results: list[dict[str, Any]] = []
    for opt in options:
        old_name = opt.get("name") or ""
        new_name = names_map.get(old_name, old_name)
        value_map = values_by_option.get(old_name) or values_by_option.get(new_name) or {}
        option_values = opt.get("optionValues") or []
        # Fallback: synthesize from values[] strings if optionValues missing
        if not option_values and opt.get("values"):
            option_values = [{"id": None, "name": v} for v in opt["values"]]

        to_update = []
        for ov in option_values:
            old_val = ov.get("name") or ""
            new_val = value_map.get(old_val)
            if new_val and new_val != old_val and ov.get("id"):
                to_update.append({"id": ov["id"], "name": new_val})

        if new_name == old_name and not to_update:
            continue

        option_input: dict[str, Any] = {"id": opt["id"]}
        if new_name != old_name:
            option_input["name"] = new_name

        results.append(
            graphql(
                q,
                {
                    "productId": product_id,
                    "option": option_input,
                    "optionValuesToUpdate": to_update or None,
                },
                dry_run=dry_run,
            )
        )
    return {"updates": results, "count": len(results)}


def ensure_collection(
    *,
    title: str,
    handle: str,
    description_html: str = "",
    template_suffix: str | None = None,
    product_ids: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create collection if missing, else update products/template/description."""
    q_find = """
    query ($q: String!) {
      collections(first: 5, query: $q) {
        nodes { id handle title templateSuffix }
      }
    }
    """
    found = graphql(q_find, {"q": f"handle:{handle}"})
    nodes = (((found.get("data") or {}).get("collections") or {}).get("nodes")) or []
    existing = next((n for n in nodes if n.get("handle") == handle), None)

    if existing:
        coll_id = existing["id"]
        mut = """
        mutation collectionUpdate($input: CollectionInput!) {
          collectionUpdate(input: $input) {
            collection { id handle title templateSuffix productsCount { count } }
            userErrors { field message }
          }
        }
        """
        inp: dict[str, Any] = {"id": coll_id}
        # Only patch fields the caller explicitly wants to change
        if title and title != existing.get("title"):
            inp["title"] = title
        if description_html:
            inp["descriptionHtml"] = description_html
        if template_suffix is not None and template_suffix != existing.get(
            "templateSuffix"
        ):
            inp["templateSuffix"] = template_suffix
        if product_ids:
            inp["products"] = product_ids
        if len(inp) == 1:
            return {
                "data": {
                    "collectionUpdate": {
                        "collection": existing,
                        "userErrors": [],
                    }
                },
                "skipped": True,
                "reason": "no collection fields to patch",
            }
        return graphql(mut, {"input": inp}, dry_run=dry_run)

    mut = """
    mutation collectionCreate($input: CollectionInput!) {
      collectionCreate(input: $input) {
        collection { id handle title templateSuffix }
        userErrors { field message }
      }
    }
    """
    inp = {
        "title": title,
        "handle": handle,
        "descriptionHtml": description_html,
    }
    if template_suffix is not None:
        inp["templateSuffix"] = template_suffix
    if product_ids:
        inp["products"] = product_ids
    return graphql(mut, {"input": inp}, dry_run=dry_run)


def collection_add_products(
    collection_id: str,
    product_ids: list[str],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    q = """
    mutation collectionAddProducts($id: ID!, $productIds: [ID!]!) {
      collectionAddProducts(id: $id, productIds: $productIds) {
        collection { id handle productsCount { count } }
        userErrors { field message }
      }
    }
    """
    return graphql(
        q, {"id": collection_id, "productIds": product_ids}, dry_run=dry_run
    )


def add_menu_item_if_missing(
    *,
    menu_handle: str = "main-menu",
    title: str,
    url: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Best-effort: append a top-level link to an Online Store menu if not present."""
    q = """
    query {
      menus(first: 20) {
        nodes {
          id
          handle
          title
          items {
            id
            title
            url
            items { id title url }
          }
        }
      }
    }
    """
    data = graphql(q)
    menus = (((data.get("data") or {}).get("menus") or {}).get("nodes")) or []
    menu = next((m for m in menus if m.get("handle") == menu_handle), None)
    if not menu:
        return {"skipped": True, "reason": f"menu {menu_handle!r} not found"}

    def _has(items: list) -> bool:
        for it in items or []:
            if (it.get("url") or "").rstrip("/") == url.rstrip("/"):
                return True
            if (it.get("title") or "").lower() == title.lower():
                return True
            if _has(it.get("items") or []):
                return True
        return False

    if _has(menu.get("items") or []):
        return {"skipped": True, "reason": "already present", "menuId": menu["id"]}

    # Rebuild items + append (MenuUpdateInput uses items nested structure)
    def _map_item(it: dict[str, Any]) -> dict[str, Any]:
        mapped: dict[str, Any] = {
            "title": it.get("title") or "",
            "type": it.get("type") or "HTTP",
        }
        if it.get("url"):
            mapped["url"] = it["url"]
        if it.get("resourceId"):
            mapped["resourceId"] = it["resourceId"]
        kids = it.get("items") or []
        if kids:
            mapped["items"] = [_map_item(k) for k in kids]
        return mapped

    # Need type on existing items — re-query with type fields
    q2 = """
    query ($id: ID!) {
      menu(id: $id) {
        id
        title
        items {
          title
          type
          url
          resourceId
          items {
            title
            type
            url
            resourceId
            items { title type url resourceId }
          }
        }
      }
    }
    """
    menu2 = (((graphql(q2, {"id": menu["id"]}).get("data") or {}).get("menu")) or menu)
    items = [_map_item(it) for it in (menu2.get("items") or [])]
    items.append({"title": title, "type": "HTTP", "url": url})

    mut = """
    mutation menuUpdate($id: ID!, $title: String!, $items: [MenuItemUpdateInput!]!) {
      menuUpdate(id: $id, title: $title, items: $items) {
        menu { id handle }
        userErrors { field message }
      }
    }
    """
    return graphql(
        mut,
        {"id": menu["id"], "title": menu.get("title") or "Main menu", "items": items},
        dry_run=dry_run,
    )


# Standard custom.* PRODUCT metafield pack (see prompting/metafields.md)
PRODUCT_METAFIELD_DEFINITIONS: list[dict[str, str]] = [
    {
        "name": "Tagline",
        "namespace": "custom",
        "key": "tagline",
        "type": "single_line_text_field",
        "description": "One-line value prop under the product title",
    },
    {
        "name": "Key benefits",
        "namespace": "custom",
        "key": "key_benefits",
        "type": "list.single_line_text_field",
        "description": "3-6 short benefit lines for theme blocks",
    },
    {
        "name": "Battery life",
        "namespace": "custom",
        "key": "battery_life",
        "type": "single_line_text_field",
        "description": "Battery / runtime claim",
    },
    {
        "name": "Noise level",
        "namespace": "custom",
        "key": "noise_level",
        "type": "single_line_text_field",
        "description": "Noise / dB claim",
    },
    {
        "name": "Power supply",
        "namespace": "custom",
        "key": "power_supply",
        "type": "single_line_text_field",
        "description": "Power / charging claim",
    },
    {
        "name": "Colours",
        "namespace": "custom",
        "key": "colours",
        "type": "single_line_text_field",
        "description": "Comma-separated live colour option values",
    },
    {
        "name": "What's in the box",
        "namespace": "custom",
        "key": "whats_in_box",
        "type": "multi_line_text_field",
        "description": "Pack contents, one item per line",
    },
    {
        "name": "Fit / use notes",
        "namespace": "custom",
        "key": "fit_notes",
        "type": "multi_line_text_field",
        "description": "Optional fit, wear, or use guidance",
    },
    {
        "name": "Bulk pack enabled",
        "namespace": "custom",
        "key": "bulk_pack_enabled",
        "type": "boolean",
        "description": "Show mix-variant volume pack UI even without bulk-pack template suffix",
    },
    {
        "name": "Bulk pack config",
        "namespace": "custom",
        "key": "bulk_pack",
        "type": "json",
        "description": "Volume pack overrides: tiers, unit labels, colour_css (see prompting/bulk-pack.md)",
    },
]


def ensure_product_metafield_definitions(*, dry_run: bool = False) -> dict[str, Any]:
    """Create standard custom.* PRODUCT definitions if missing (idempotent)."""
    q_list = """
    query {
      metafieldDefinitions(first: 100, ownerType: PRODUCT, namespace: "custom") {
        nodes { namespace key }
      }
    }
    """
    existing = {
        (n["namespace"], n["key"])
        for n in graphql(q_list)["data"]["metafieldDefinitions"]["nodes"]
    }
    created = []
    skipped = []
    errors = []
    mut = """
    mutation metafieldDefinitionCreate($definition: MetafieldDefinitionInput!) {
      metafieldDefinitionCreate(definition: $definition) {
        createdDefinition { id namespace key }
        userErrors { field message code }
      }
    }
    """
    for d in PRODUCT_METAFIELD_DEFINITIONS:
        key = (d["namespace"], d["key"])
        if key in existing:
            skipped.append(f"{d['namespace']}.{d['key']}")
            continue
        definition = {
            "name": d["name"],
            "namespace": d["namespace"],
            "key": d["key"],
            "description": d.get("description") or "",
            "type": d["type"],
            "ownerType": "PRODUCT",
            "access": {"storefront": "PUBLIC_READ"},
        }
        if dry_run:
            created.append({"dry_run": True, "definition": definition})
            continue
        res = graphql(mut, {"definition": definition})
        payload = (res.get("data") or {}).get("metafieldDefinitionCreate") or {}
        if payload.get("userErrors"):
            # TAKEN / already exists → treat as skip
            msgs = [e.get("message") or "" for e in payload["userErrors"]]
            if any("taken" in m.lower() or "already" in m.lower() for m in msgs):
                skipped.append(f"{d['namespace']}.{d['key']}")
            else:
                errors.append({"key": d["key"], "userErrors": payload["userErrors"]})
        else:
            created.append(payload.get("createdDefinition"))
    return {"created": created, "skipped": skipped, "errors": errors}


def set_product_metafields(
    product_id: str,
    metafields: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Set custom.* values from a project.json metafields object.
    list.single_line_text_field values accept a Python list (JSON-encoded).
    """
    type_by_key = {d["key"]: d["type"] for d in PRODUCT_METAFIELD_DEFINITIONS}
    inputs: list[dict[str, Any]] = []
    for key, value in (metafields or {}).items():
        if value is None or value == "":
            continue
        if key not in type_by_key:
            continue
        mf_type = type_by_key[key]
        if mf_type == "boolean":
            serialized = (
                "true"
                if value in (True, "true", "True", "1", 1)
                else "false"
            )
        elif mf_type.startswith("list.") and isinstance(value, list):
            serialized = json.dumps(value, ensure_ascii=False)
        elif mf_type == "json" or isinstance(value, (dict, list)):
            serialized = json.dumps(value, ensure_ascii=False)
        else:
            serialized = str(value)
        inputs.append(
            {
                "ownerId": product_id,
                "namespace": "custom",
                "key": key,
                "type": mf_type,
                "value": serialized,
            }
        )
    if not inputs:
        return {"set": 0, "metafields": []}
    q = """
    mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $metafields) {
        metafields { id namespace key value type }
        userErrors { field message code }
      }
    }
    """
    return graphql(q, {"metafields": inputs}, dry_run=dry_run)


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
    template_suffix: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    page_input: dict[str, Any] = {
        "title": title,
        "handle": handle,
        "body": body_html,
        "isPublished": is_published,
    }
    if template_suffix is not None:
        page_input["templateSuffix"] = template_suffix
    if page_id:
        q = """
        mutation pageUpdate($id: ID!, $page: PageUpdateInput!) {
          pageUpdate(id: $id, page: $page) {
            page { id title handle templateSuffix isPublished }
            userErrors { field message }
          }
        }
        """
        variables = {"id": page_id, "page": page_input}
    else:
        q = """
        mutation pageCreate($page: PageCreateInput!) {
          pageCreate(page: $page) {
            page { id title handle templateSuffix isPublished }
            userErrors { field message }
          }
        }
        """
        variables = {"page": page_input}
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
