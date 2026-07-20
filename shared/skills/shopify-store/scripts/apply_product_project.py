#!/usr/bin/env python3
"""
Apply a storefront product content project from a local (gitignored) folder.

Project dir layout (default under outputs/shopify/projects/<name>/):
  project.json       — handle, titles, SEO, flags
  description.html   — proposed PDP body

Modes:
  --dry-run       Print mutations only
  --apply-draft   Create DRAFT duplicate for Admin review (live URL unchanged)
  --apply-live    Update LIVE product title/body/SEO/metafields/template (handle never changes)

Usage:
  python apply_product_project.py --project outputs/shopify/projects/neck-fan --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from dotenv import load_dotenv

load_dotenv(SCRIPT_DIR / "../../../../.env")
load_dotenv(SCRIPT_DIR / "../../../.env")
load_dotenv()

from lib import shopify_api as api  # noqa: E402


def load_project(project_dir: Path) -> tuple[dict, str]:
    cfg_path = project_dir / "project.json"
    if not cfg_path.exists():
        raise RuntimeError(f"Missing {cfg_path}")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    for key in ("handle", "proposed_title"):
        if not cfg.get(key):
            raise RuntimeError(f"project.json missing required key: {key}")
    desc_name = cfg.get("description_file", "description.html")
    desc_path = project_dir / desc_name
    if not desc_path.exists():
        raise RuntimeError(f"Missing description file: {desc_path}")
    return cfg, desc_path.read_text(encoding="utf-8")


def create_draft_duplicate(cfg: dict, description_html: str, *, dry_run: bool) -> dict:
    handle = cfg["handle"]
    draft_handle = f"{handle}-draft-review"
    q = """
    mutation productCreate($input: ProductInput!) {
      productCreate(input: $input) {
        product { id title handle status }
        userErrors { field message }
      }
    }
    """
    variables = {
        "input": {
            "title": f"[DRAFT REVIEW] {cfg['proposed_title']}",
            "handle": draft_handle,
            "descriptionHtml": description_html,
            "status": "DRAFT",
            "seo": {
                "title": cfg.get("seo_title") or cfg["proposed_title"],
                "description": cfg.get("seo_description") or "",
            },
        }
    }
    return api.graphql(q, variables, dry_run=dry_run)


def media_inputs_from_product(detail: dict) -> list[dict]:
    inputs: list[dict] = []
    for node in (detail.get("media") or {}).get("nodes") or []:
        image = node.get("image") or {}
        url = image.get("url")
        if not url:
            continue
        alt = node.get("alt") or image.get("altText") or ""
        inputs.append(
            {
                "originalSource": url.split("?")[0],
                "mediaContentType": "IMAGE",
                "alt": alt or "Product image",
            }
        )
    return inputs


def _image_stem(url: str) -> str:
    if not url:
        return ""
    name = url.split("?")[0].rsplit("/", 1)[-1]
    # Shopify re-uploads append _{uuid} before the extension
    return re.sub(r"_[0-9a-f-]{36}(?=\.)", "", name, flags=re.I).lower()


def link_variant_media_from_live(
    draft_id: str,
    live_detail: dict,
    *,
    dry_run: bool,
) -> dict:
    """
    Attach each draft variant to the gallery image that matches the live
    variant's featured media, so the theme swaps images when options change.

    Prefers the live mediaId when the draft shares the same file (referencesToAdd);
    otherwise matches by filename stem after a re-upload.
    """
    if dry_run:
        return {"dry_run": True}

    live_media_by_title: dict[str, str] = {}
    live_stem_by_title: dict[str, str] = {}
    for v in (live_detail.get("variants") or {}).get("nodes") or []:
        title = v.get("title") or ""
        nodes = (v.get("media") or {}).get("nodes") or []
        if nodes and nodes[0].get("id"):
            live_media_by_title[title] = nodes[0]["id"]
        url = ""
        if nodes:
            url = ((nodes[0].get("image") or {}).get("url") or "")
        if not url:
            url = ((v.get("image") or {}).get("url") or "")
        if url:
            live_stem_by_title[title] = _image_stem(url)

    draft = api.get_product_detail(draft_id)
    draft_media_ids = {
        m["id"]
        for m in (draft.get("media") or {}).get("nodes") or []
        if m and m.get("id")
    }
    draft_media_by_stem: dict[str, str] = {}
    for m in (draft.get("media") or {}).get("nodes") or []:
        if not m or not m.get("id"):
            continue
        url = ((m.get("image") or {}).get("url") or "")
        if url:
            draft_media_by_stem[_image_stem(url)] = m["id"]

    updates = []
    mapping = []
    for dv in (draft.get("variants") or {}).get("nodes") or []:
        title = dv.get("title") or ""
        media_id = live_media_by_title.get(title)
        if media_id and media_id not in draft_media_ids:
            media_id = None
        if not media_id:
            stem = live_stem_by_title.get(title)
            media_id = draft_media_by_stem.get(stem) if stem else None
        if media_id:
            updates.append({"id": dv["id"], "mediaId": media_id})
            mapping.append({"title": title, "mediaId": media_id})

    if not updates:
        return {"linked": 0, "mapping": mapping}

    result = api.product_variants_bulk_update(draft_id, updates, dry_run=False)
    return {
        "linked": len(updates),
        "mapping": mapping,
        "result": result,
    }


def attach_live_media_by_reference(
    draft_id: str,
    live_detail: dict,
    *,
    dry_run: bool,
) -> dict:
    """
    Share the live product's media files with the draft (no re-upload).

    Re-uploading via productCreateMedia + CDN URLs re-encodes JPEGs and can
    softens images; fileUpdate.referencesToAdd keeps bit-identical masters
    (including VIDEO).
    """
    if dry_run:
        return {"dry_run": True}

    # Prefer a fresh query that includes VIDEO nodes
    q = """
    query($id: ID!) {
      product(id: $id) {
        media(first: 50) {
          nodes {
            ... on MediaImage { id }
            ... on Video { id }
            ... on ExternalVideo { id }
            ... on Model3d { id }
          }
        }
      }
    }
    """
    live_id = live_detail.get("id")
    if not live_id:
        return {"error": "live product id missing"}
    nodes = (
        api.graphql(q, {"id": live_id})["data"]["product"]["media"]["nodes"] or []
    )
    media_ids = [n["id"] for n in nodes if n and n.get("id")]
    if not media_ids:
        # Fallback: image-only from detail payload
        media_ids = [
            n["id"]
            for n in (live_detail.get("media") or {}).get("nodes") or []
            if n and n.get("id")
        ]

    mut = """
    mutation fileUpdate($files: [FileUpdateInput!]!) {
      fileUpdate(files: $files) {
        files {
          ... on MediaImage { id }
          ... on Video { id }
        }
        userErrors { field message code }
      }
    }
    """
    results = []
    for i in range(0, len(media_ids), 10):
        chunk = [
            {"id": mid, "referencesToAdd": [draft_id]} for mid in media_ids[i : i + 10]
        ]
        results.append(api.graphql(mut, {"files": chunk}))

    # Match live gallery order
    moves = [{"id": mid, "newPosition": str(pos)} for pos, mid in enumerate(media_ids)]
    reorder = None
    if moves:
        reorder_mut = """
        mutation productReorderMedia($id: ID!, $moves: [MoveInput!]!) {
          productReorderMedia(id: $id, moves: $moves) {
            job { id }
            mediaUserErrors { field message code }
          }
        }
        """
        reorder = api.graphql(reorder_mut, {"id": draft_id, "moves": moves})

    return {"count": len(media_ids), "fileUpdate": results, "reorder": reorder}


def enrich_draft_from_live(
    draft_id: str,
    live_detail: dict,
    *,
    dry_run: bool,
) -> dict:
    """Copy gallery + Color options/prices onto a draft so Admin preview looks real."""
    report: dict = {"media": None, "options": None, "variants": None}
    report["media"] = attach_live_media_by_reference(
        draft_id, live_detail, dry_run=dry_run
    )

    options = live_detail.get("options") or []
    # Skip Shopify's default "Title" / Default Title-only products
    real_options = [o for o in options if o.get("name") and o.get("name") != "Title"]
    live_variants = (live_detail.get("variants") or {}).get("nodes") or []
    if real_options and live_variants:
        # Seed first option value set (creates Color etc.); remaining variants via bulkCreate
        first_values = []
        for o in real_options:
            vals = o.get("values") or []
            if vals:
                first_values.append({"name": o["name"], "values": [{"name": vals[0]}]})
        if first_values:
            report["options"] = api.product_options_create(
                draft_id, first_values, dry_run=dry_run
            )

        # Build bulk variants for every live variant (creates missing option values)
        bulk_inputs = []
        for v in live_variants:
            option_values = [
                {"optionName": so["name"], "name": so["value"]}
                for so in (v.get("selectedOptions") or [])
                if so.get("name") != "Title"
            ]
            if not option_values:
                continue
            item: dict = {
                "optionValues": option_values,
                "price": str(v.get("price") or "0"),
            }
            if v.get("sku"):
                item["inventoryItem"] = {"sku": v["sku"]}
            bulk_inputs.append(item)

        if bulk_inputs and not dry_run:
            # First live variant often already exists as the seed — skip titles that exist
            draft_after = api.get_product_detail(draft_id)
            existing_titles = {
                dv.get("title")
                for dv in (draft_after.get("variants") or {}).get("nodes") or []
            }
            to_create = [
                b
                for b, lv in zip(bulk_inputs, live_variants)
                if lv.get("title") not in existing_titles
            ]
            # Sync price on seed variant
            seed_updates = []
            for dv in (draft_after.get("variants") or {}).get("nodes") or []:
                for lv in live_variants:
                    if lv.get("title") == dv.get("title") and lv.get("price") is not None:
                        seed_updates.append(
                            {"id": dv["id"], "price": str(lv["price"])}
                        )
            if seed_updates:
                api.product_variants_bulk_update(
                    draft_id, seed_updates, dry_run=False
                )
            if to_create:
                q = """
                mutation productVariantsBulkCreate(
                  $productId: ID!,
                  $variants: [ProductVariantsBulkInput!]!
                ) {
                  productVariantsBulkCreate(productId: $productId, variants: $variants) {
                    productVariants { id title price }
                    userErrors { field message code }
                  }
                }
                """
                report["variants"] = api.graphql(
                    q, {"productId": draft_id, "variants": to_create}, dry_run=False
                )
        elif bulk_inputs and dry_run:
            report["variants"] = {"dry_run": True, "would_create": len(bulk_inputs)}

    report["variant_media"] = link_variant_media_from_live(
        draft_id, live_detail, dry_run=dry_run
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        required=True,
        help="Path to local project dir (e.g. outputs/shopify/projects/neck-fan)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply-draft", action="store_true")
    mode.add_argument("--apply-live", action="store_true")
    args = parser.parse_args()

    project_dir = Path(args.project).resolve()
    if not project_dir.is_dir():
        print(f"ERROR: project dir not found: {project_dir}", file=sys.stderr)
        return 1

    cfg, description_html = load_project(project_dir)
    handle = cfg["handle"]
    dry_run = bool(args.dry_run)

    slug = f"{date.today().isoformat()}-{cfg.get('name') or project_dir.name}"
    out_dir = api.resolve_output_dir(slug)

    print(f"Project: {project_dir}")
    print(f"Session output: {out_dir}")
    print(f"Handle: {handle}" + (" (LOCKED)" if cfg.get("live_url_locked") else ""))

    prod = api.get_product_by_handle(handle)
    if not prod:
        print(f"ERROR: product not found for handle {handle!r}", file=sys.stderr)
        return 1

    product_id = prod["id"]
    detail = api.get_product_detail(product_id)
    api.dump_json(out_dir / "product-before.json", detail)
    print(f"Backed up live product → {out_dir / 'product-before.json'}")

    if args.apply_live or dry_run:
        actually_live = bool(args.apply_live) and not dry_run
        defs = api.ensure_product_metafield_definitions(dry_run=not actually_live)
        api.dump_json(out_dir / "metafield-definitions.json", defs)
        print(
            "Metafield definitions:",
            "DRY-RUN" if not actually_live else f"created={len(defs.get('created') or [])} skipped={len(defs.get('skipped') or [])}",
        )

        live_result = api.update_product(
            product_id,
            title=cfg["proposed_title"],
            description_html=description_html,
            seo_title=cfg.get("seo_title"),
            seo_description=cfg.get("seo_description"),
            template_suffix=cfg.get("template_suffix"),
            dry_run=not actually_live,
        )
        api.dump_json(out_dir / "live-update-result.json", live_result)
        print(
            "Live product update:",
            "DRY-RUN" if not actually_live else "APPLIED (handle unchanged)",
        )

        if cfg.get("metafields"):
            mf_result = api.set_product_metafields(
                product_id,
                cfg["metafields"],
                dry_run=not actually_live,
            )
            api.dump_json(out_dir / "metafields-set-result.json", mf_result)
            errs = ((mf_result.get("data") or {}).get("metafieldsSet") or {}).get(
                "userErrors"
            )
            print(
                "Metafields:",
                "DRY-RUN" if not actually_live else ("OK" if not errs else f"errors={errs}"),
            )

    if args.apply_draft or dry_run:
        actually_apply = bool(args.apply_draft) and not dry_run
        draft_result = create_draft_duplicate(
            cfg,
            description_html,
            dry_run=not actually_apply,
        )
        api.dump_json(out_dir / "draft-duplicate-result.json", draft_result)
        print(
            "Draft duplicate:",
            "DRY-RUN" if not actually_apply else "CREATED (live URL untouched)",
        )
        draft_id = (
            ((draft_result.get("data") or {}).get("productCreate") or {})
            .get("product")
            or {}
        ).get("id")
        if draft_id or not actually_apply:
            enrich = enrich_draft_from_live(
                draft_id or "gid://shopify/Product/DRY_RUN",
                detail,
                dry_run=not actually_apply,
            )
            api.dump_json(out_dir / "draft-enrich-result.json", enrich)
            media_count = (enrich.get("media") or {}).get("count", 0)
            print(
                "Draft enrich:",
                "DRY-RUN" if not actually_apply else f"media×{media_count} + options/prices",
            )
            if cfg.get("metafields") and draft_id and actually_apply:
                mf_draft = api.set_product_metafields(
                    draft_id, cfg["metafields"], dry_run=False
                )
                api.dump_json(out_dir / "draft-metafields-set-result.json", mf_draft)
                print("Draft metafields: set")

    plan = {
        "project": str(project_dir),
        "handle": handle,
        "live_url_locked": bool(cfg.get("live_url_locked")),
        "mode": "dry-run" if dry_run else ("apply-draft" if args.apply_draft else "apply-live"),
        "images": cfg.get("images", "reuse_existing_gallery"),
        "template_suffix": cfg.get("template_suffix"),
        "metafield_keys": list((cfg.get("metafields") or {}).keys()),
        "never_set_live_product_status_to_draft": True,
        "draft_media_strategy": "fileUpdate.referencesToAdd",
    }
    api.dump_json(out_dir / "plan.json", plan)
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
