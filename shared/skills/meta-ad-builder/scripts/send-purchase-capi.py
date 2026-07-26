#!/usr/bin/env python3
"""Send (or dry-run) a Meta Conversions API Purchase for one Shopify order.

Default is dry-run. Pass --send to call Meta. Never prints raw email/phone.

Usage:
  python send-purchase-capi.py --order-name '#1002'
  python send-purchase-capi.py --order-name '#1002' --send
  python send-purchase-capi.py --order-id 5678901234567 --send --test-event-code TEST12345
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(ROOT / "shared/skills/shopify-store/scripts"))

import meta_api  # noqa: E402
import requests  # noqa: E402
from lib import shopify_api as shopify  # noqa: E402


def _load_env() -> None:
    for candidate in (ROOT / ".env", Path.cwd() / ".env"):
        if candidate.is_file():
            load_dotenv(candidate)
            return
    load_dotenv()


def _parse_shopify_time(value: str | None) -> int:
    if not value:
        return int(datetime.now(timezone.utc).timestamp())
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _enrich_from_rest(order: dict) -> dict:
    """Attach user_agent / landing_site from REST (not on GraphQL Order).

    Only boolean presence flags are ever printed by callers; raw UA is kept
    in-memory for CAPI only.
    """
    gid = order.get("id") or ""
    numeric = meta_api.normalize_order_event_id(gid)
    shop = shopify.get_shop()
    version = shopify.get_api_version()
    token = shopify.fetch_access_token()
    url = f"https://{shop}/admin/api/{version}/orders/{numeric}.json"
    # Prefer a REST version that still returns client_details
    for ver in (version, "2026-01", "2025-10"):
        url = f"https://{shop}/admin/api/{ver}/orders/{numeric}.json"
        resp = requests.get(
            url,
            headers={"X-Shopify-Access-Token": token},
            timeout=60,
        )
        if resp.status_code == 200:
            break
    else:
        return order
    rest = (resp.json() or {}).get("order") or {}
    cd = rest.get("client_details") or {}
    if cd.get("user_agent"):
        order["_user_agent"] = cd["user_agent"]
    if rest.get("browser_ip") and not order.get("clientIp"):
        order["clientIp"] = rest["browser_ip"]
    if rest.get("landing_site"):
        order["_landing_site"] = rest["landing_site"]
    if rest.get("referring_site"):
        order["_referring_site"] = rest["referring_site"]
    return order


def _fetch_order(*, order_name: str | None, order_id: str | None) -> dict:
    if order_id:
        gid = (
            order_id
            if str(order_id).startswith("gid://")
            else f"gid://shopify/Order/{order_id}"
        )
        q = """
        query Order($id: ID!) {
          order(id: $id) {
            id
            name
            createdAt
            processedAt
            displayFinancialStatus
            test
            email
            phone
            clientIp
            customer { id email phone }
            billingAddress {
              firstName lastName city provinceCode zip countryCodeV2 phone
            }
            shippingAddress {
              firstName lastName city provinceCode zip countryCodeV2 phone
            }
            totalPriceSet { shopMoney { amount currencyCode } }
            lineItems(first: 50) {
              nodes {
                quantity
                variant { id sku }
                product { id }
              }
            }
            customerJourneySummary {
              ready
              firstVisit { landingPage }
              lastVisit { landingPage }
            }
          }
        }
        """
        data = shopify.graphql(q, {"id": gid})["data"]["order"]
        if not data:
            raise RuntimeError(f"Order not found: {gid}")
        return data

    if not order_name:
        raise RuntimeError("Provide --order-name or --order-id")

    name = order_name if order_name.startswith("#") else f"#{order_name}"
    q = """
    query Orders($q: String!) {
      orders(first: 5, query: $q, sortKey: CREATED_AT, reverse: true) {
        nodes {
          id
          name
          createdAt
          processedAt
          displayFinancialStatus
          test
          email
          phone
          clientIp
          customer { id email phone }
          billingAddress {
            firstName lastName city provinceCode zip countryCodeV2 phone
          }
          shippingAddress {
            firstName lastName city provinceCode zip countryCodeV2 phone
          }
          totalPriceSet { shopMoney { amount currencyCode } }
          lineItems(first: 50) {
            nodes {
              quantity
              variant { id sku }
              product { id }
            }
          }
          customerJourneySummary {
            ready
            firstVisit { landingPage }
            lastVisit { landingPage }
          }
        }
      }
    }
    """
    # name: query supports "#1002" / "name:#1002"
    nodes = shopify.graphql(q, {"q": f"name:{name}"})["data"]["orders"]["nodes"]
    for node in nodes:
        if node.get("name") == name:
            return node
    if nodes:
        return nodes[0]
    raise RuntimeError(f"Order not found for name={name}")


def _content_ids(order: dict) -> list[str]:
    ids: list[str] = []
    for li in (order.get("lineItems") or {}).get("nodes") or []:
        variant = li.get("variant") or {}
        product = li.get("product") or {}
        raw = variant.get("id") or product.get("id") or variant.get("sku")
        if not raw:
            continue
        text = str(raw)
        if text.startswith("gid://"):
            text = text.rsplit("/", 1)[-1]
        ids.append(text)
    return ids


def build_purchase_event(order: dict) -> dict:
    money = ((order.get("totalPriceSet") or {}).get("shopMoney")) or {}
    amount = money.get("amount")
    currency = money.get("currencyCode") or "GBP"
    if amount is None:
        raise RuntimeError("Order has no totalPriceSet.shopMoney.amount")

    event_id = meta_api.normalize_order_event_id(order["id"])
    event_time = _parse_shopify_time(order.get("processedAt") or order.get("createdAt"))

    bill = order.get("billingAddress") or {}
    ship = order.get("shippingAddress") or {}
    customer = order.get("customer") or {}

    email = order.get("email") or customer.get("email")
    phone_raw = (
        order.get("phone")
        or customer.get("phone")
        or bill.get("phone")
        or ship.get("phone")
    )
    phone = meta_api.normalize_phone(phone_raw)

    fn = bill.get("firstName") or ship.get("firstName")
    ln = bill.get("lastName") or ship.get("lastName")
    city = bill.get("city") or ship.get("city")
    st = bill.get("provinceCode") or ship.get("provinceCode")
    zp = bill.get("zip") or ship.get("zip")
    country = bill.get("countryCodeV2") or ship.get("countryCodeV2") or "GB"

    journey = order.get("customerJourneySummary") or {}
    last_visit = journey.get("lastVisit") or {}
    first_visit = journey.get("firstVisit") or {}
    landing = (
        order.get("_landing_site")
        or last_visit.get("landingPage")
        or first_visit.get("landingPage")
    )
    # Prefer primary domain over .myshopify.com for event_source_url
    default_url = os.getenv("STORE_PRIMARY_URL") or "https://ourtechaccessories.com/"
    event_source_url = landing if landing and landing.startswith("http") else default_url
    if event_source_url.startswith("/"):
        event_source_url = default_url.rstrip("/") + event_source_url

    user_data: dict = {}
    em = meta_api.sha256_norm(email)
    if em:
        user_data["em"] = [em]
    ph = meta_api.sha256_norm(phone)
    if ph:
        user_data["ph"] = [ph]
    if fn:
        hashed = meta_api.sha256_norm(fn)
        if hashed:
            user_data["fn"] = [hashed]
    if ln:
        hashed = meta_api.sha256_norm(ln)
        if hashed:
            user_data["ln"] = [hashed]
    if city:
        hashed = meta_api.sha256_norm(city)
        if hashed:
            user_data["ct"] = [hashed]
    if st:
        hashed = meta_api.sha256_norm(st)
        if hashed:
            user_data["st"] = [hashed]
    if zp:
        hashed = meta_api.sha256_norm(zp)
        if hashed:
            user_data["zp"] = [hashed]
    if country:
        hashed = meta_api.sha256_norm(country)
        if hashed:
            user_data["country"] = [hashed]

    external = customer.get("id") or order.get("id")
    if external:
        ext = (
            meta_api.normalize_order_event_id(external)
            if "Order" in str(external)
            else str(external).rsplit("/", 1)[-1]
        )
        user_data["external_id"] = [meta_api.sha256_norm(ext) or ext]

    if order.get("clientIp"):
        user_data["client_ip_address"] = order["clientIp"]

    # Required for website action_source events
    ua = order.get("_user_agent")
    if ua:
        user_data["client_user_agent"] = ua
    else:
        # Safe generic fallback so Meta accepts website events; match quality lower
        user_data["client_user_agent"] = (
            "Mozilla/5.0 (compatible; OurTechAccessoriesCAPI/1.0)"
        )

    fbclid = meta_api.extract_fbclid(landing) or meta_api.extract_fbclid(
        order.get("_referring_site")
    )
    if fbclid:
        user_data["fbc"] = meta_api.build_fbc_from_fbclid(
            fbclid, creation_time_ms=event_time * 1000
        )

    contents = []
    for li in (order.get("lineItems") or {}).get("nodes") or []:
        variant = li.get("variant") or {}
        product = li.get("product") or {}
        raw = variant.get("id") or product.get("id")
        if not raw:
            continue
        cid = str(raw).rsplit("/", 1)[-1]
        contents.append(
            {
                "id": cid,
                "quantity": int(li.get("quantity") or 1),
                "item_price": float(amount) / max(1, sum(
                    int(x.get("quantity") or 1)
                    for x in ((order.get("lineItems") or {}).get("nodes") or [])
                )),
            }
        )

    custom_data = {
        "value": float(amount),
        "currency": currency,
        "content_type": "product",
        "order_id": event_id,
        "content_ids": _content_ids(order),
    }
    if contents:
        custom_data["contents"] = contents
        custom_data["num_items"] = sum(c["quantity"] for c in contents)

    return {
        "event_name": "Purchase",
        "event_time": event_time,
        "event_id": event_id,
        "action_source": "website",
        "event_source_url": event_source_url,
        "user_data": user_data,
        "custom_data": custom_data,
    }


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--order-name", help="Shopify order name, e.g. #1002")
    parser.add_argument("--order-id", help="Shopify numeric order id or gid")
    parser.add_argument(
        "--send",
        action="store_true",
        help="Actually POST to Meta CAPI (default is dry-run)",
    )
    parser.add_argument(
        "--test-event-code",
        default=os.getenv("META_TEST_EVENT_CODE"),
        help="Optional Events Manager test_event_code",
    )
    parser.add_argument(
        "--allow-unpaid",
        action="store_true",
        help="Allow non-PAID financial status (debug only)",
    )
    parser.add_argument(
        "--skip-purchase-check",
        action="store_true",
        help="Do not re-check Meta Purchase totals before send",
    )
    args = parser.parse_args()

    if not args.order_name and not args.order_id:
        parser.error("Provide --order-name or --order-id")

    order = _enrich_from_rest(
        _fetch_order(order_name=args.order_name, order_id=args.order_id)
    )
    status = (order.get("displayFinancialStatus") or "").upper()
    summary = {
        "order_name": order.get("name"),
        "order_gid": order.get("id"),
        "financial_status": status,
        "test": bool(order.get("test")),
        "created_at": order.get("createdAt"),
        "value": ((order.get("totalPriceSet") or {}).get("shopMoney") or {}).get("amount"),
        "currency": ((order.get("totalPriceSet") or {}).get("shopMoney") or {}).get(
            "currencyCode"
        ),
        "has_email": bool(order.get("email") or (order.get("customer") or {}).get("email")),
        "has_phone": bool(
            order.get("phone")
            or (order.get("customer") or {}).get("phone")
            or (order.get("billingAddress") or {}).get("phone")
        ),
        "has_client_ip": bool(order.get("clientIp")),
        "has_user_agent": bool(order.get("_user_agent")),
        "has_landing_site": bool(order.get("_landing_site")),
        "journey_ready": (order.get("customerJourneySummary") or {}).get("ready"),
    }
    print(json.dumps({"order_summary": summary}, indent=2))

    if order.get("test"):
        print("ERROR: refusing test order", file=sys.stderr)
        return 2
    if status not in ("PAID", "PARTIALLY_PAID") and not args.allow_unpaid:
        print(f"ERROR: order financial status is {status!r}; use --allow-unpaid to override", file=sys.stderr)
        return 2

    event = build_purchase_event(order)
    age_days = (int(datetime.now(timezone.utc).timestamp()) - int(event["event_time"])) / 86400
    if age_days > 7:
        print(
            f"ERROR: event_time is {age_days:.1f} days old; Meta rejects CAPI events > 7 days",
            file=sys.stderr,
        )
        return 2

    if args.send and not args.skip_purchase_check:
        totals = meta_api.pixel_event_totals(days=7)
        print(json.dumps({"pre_send_meta_totals": {
            "purchase": totals.get("purchase"),
            "counts_sample": {
                k: totals["counts"].get(k)
                for k in ("PageView", "ViewContent", "InitiateCheckout", "AddToCart", "Purchase")
                if k in totals.get("counts", {})
            },
        }}, indent=2))

    result = meta_api.send_capi_events(
        [event],
        test_event_code=args.test_event_code,
        dry_run=not args.send,
    )
    print(json.dumps({"capi_result": result}, indent=2))

    if not args.send:
        print("Dry-run only. Re-run with --send to POST to Meta.")
        return 0

    # Post-send aggregate check (propagation can lag)
    try:
        after = meta_api.pixel_event_totals(days=7)
        print(json.dumps({"post_send_meta_purchase_count": after.get("purchase")}, indent=2))
    except Exception as exc:
        print(f"WARN: could not re-read pixel stats: {exc}", file=sys.stderr)

    print("Sent. Confirm in Events Manager → Test Events / Overview.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
