#!/usr/bin/env python3
"""
Hashnode CLI for the blog-writing skill.

Examples:
  python3 hashnode_cli.py whoami
  python3 hashnode_cli.py preview --project blog/posts/2026-07-23-lead-dev-dropshipping-calm-store
  python3 hashnode_cli.py upsert-draft --project blog/posts/... --dry-run
  python3 hashnode_cli.py upsert-draft --project blog/posts/...
  python3 hashnode_cli.py publish --project blog/posts/...
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import hashnode_api as api  # noqa: E402


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / ".git").exists() or (p / ".env").exists():
            return p
    return here.parents[4]


def _load_dotenv() -> None:
    root = _find_repo_root()
    env_path = root / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val


def _load_project(project: Path) -> tuple[dict[str, Any], str]:
    meta_path = project / "post.json"
    body_path = project / "post.md"
    if not meta_path.is_file():
        raise SystemExit(f"Missing {meta_path}")
    if not body_path.is_file():
        raise SystemExit(f"Missing {body_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    body = body_path.read_text(encoding="utf-8").strip() + "\n"
    if not meta.get("title"):
        raise SystemExit("post.json: title is required")
    if not meta.get("slug"):
        raise SystemExit("post.json: slug is required")
    if not body.strip():
        raise SystemExit("post.md is empty")
    return meta, body


def _save_meta(project: Path, meta: dict[str, Any]) -> None:
    path = project / "post.json"
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _tags(meta: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for t in meta.get("tags") or []:
        if isinstance(t, str):
            slug = t.strip().lower().replace(" ", "-")
            if slug:
                out.append({"slug": slug})
            continue
        slug = (t.get("slug") or "").strip()
        if not slug:
            continue
        item: dict[str, str] = {"slug": slug}
        name = (t.get("name") or "").strip()
        if name:
            item["name"] = name
        out.append(item)
    return out[:15]


def _publication_id(allow_missing: bool = False) -> str:
    pub = (os.environ.get("HASHNODE_PUBLICATION_ID") or "").strip()
    if pub:
        return pub
    if allow_missing:
        return "<HASHNODE_PUBLICATION_ID>"
    raise api.HashnodeError("HASHNODE_PUBLICATION_ID is not set (see .env.example)")


def _draft_input(meta: dict[str, Any], body: str, *, allow_missing_pub: bool = False) -> dict[str, Any]:
    seo = meta.get("seo") or {}
    inp: dict[str, Any] = {
        "publicationId": _publication_id(allow_missing=allow_missing_pub),
        "title": meta["title"],
        "contentMarkdown": body,
        "slug": meta["slug"],
    }
    if meta.get("subtitle"):
        inp["subtitle"] = meta["subtitle"]
    tags = _tags(meta)
    if tags:
        inp["tags"] = tags
    cover = (meta.get("coverImageURL") or "").strip()
    if cover:
        inp["coverImageOptions"] = {"coverImageURL": cover}
    meta_tags: dict[str, str] = {}
    if seo.get("title"):
        meta_tags["title"] = seo["title"]
    if seo.get("description"):
        meta_tags["description"] = seo["description"]
    if seo.get("image"):
        meta_tags["image"] = seo["image"]
    if meta_tags:
        inp["metaTags"] = meta_tags
    if meta.get("originalArticleURL"):
        inp["originalArticleURL"] = meta["originalArticleURL"]
    if meta.get("enableToc") is not None:
        inp["settings"] = {"enableTableOfContent": bool(meta["enableToc"])}
    return inp


def _publish_input(
    meta: dict[str, Any], body: str, *, allow_missing_pub: bool = False
) -> dict[str, Any]:
    """Shape for publishPost / updatePost (slightly different field names)."""
    seo = meta.get("seo") or {}
    inp: dict[str, Any] = {
        "publicationId": _publication_id(allow_missing=allow_missing_pub),
        "title": meta["title"],
        "contentMarkdown": body,
        "slug": meta["slug"],
        "enableToc": bool(meta.get("enableToc", True)),
    }
    if meta.get("subtitle"):
        inp["subtitle"] = meta["subtitle"]
    tags = _tags(meta)
    if tags:
        inp["tags"] = tags
    cover = (meta.get("coverImageURL") or "").strip()
    if cover:
        inp["coverImage"] = cover
    if seo.get("title"):
        inp["metaTitle"] = seo["title"]
    if seo.get("description"):
        inp["metaDescription"] = seo["description"]
    if seo.get("image"):
        inp["ogImage"] = seo["image"]
    if meta.get("originalArticleURL"):
        inp["originalArticleURL"] = meta["originalArticleURL"]
    return inp


def cmd_whoami(_: argparse.Namespace) -> int:
    data = api.me_publications()
    me = data.get("me") or {}
    print("Hashnode auth OK")
    print(f"  id: {me.get('id')}")
    print(f"  username: {me.get('username')}")
    print(f"  name: {me.get('name')}")
    edges = ((me.get("publications") or {}).get("edges")) or []
    if not edges:
        print("  publications: (none)")
        return 0
    print("  publications:")
    want = (os.environ.get("HASHNODE_PUBLICATION_ID") or "").strip()
    for edge in edges:
        node = edge.get("node") or {}
        mark = " ← HASHNODE_PUBLICATION_ID" if node.get("id") == want else ""
        print(f"    - {node.get('id')}  {node.get('title')}  {node.get('url')}{mark}")
    if want and not any((e.get("node") or {}).get("id") == want for e in edges):
        print(
            f"\nWARNING: HASHNODE_PUBLICATION_ID={want} not in your publication list.",
            file=sys.stderr,
        )
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    project = Path(args.project)
    meta, body = _load_project(project)
    draft_inp = _draft_input(meta, body, allow_missing_pub=True)
    print(json.dumps({"createDraft/updateDraft input": draft_inp}, indent=2, ensure_ascii=False))
    hn = meta.get("hashnode") or {}
    print("\nLocal hashnode state:")
    print(json.dumps(hn, indent=2))
    print(f"\nBody chars: {len(body)}  words≈{len(body.split())}")
    return 0


def cmd_upsert_draft(args: argparse.Namespace) -> int:
    project = Path(args.project)
    meta, body = _load_project(project)
    hn = meta.setdefault("hashnode", {})
    draft_id = (hn.get("draftId") or "").strip()

    if args.dry_run:
        inp = _draft_input(meta, body, allow_missing_pub=True)
        action = "updateDraft" if draft_id else "createDraft"
        print(f"[dry-run] would {action}")
        if draft_id:
            print(f"  draftId: {draft_id}")
        print(json.dumps(inp, indent=2, ensure_ascii=False))
        return 0

    inp = _draft_input(meta, body)

    if draft_id:
        update_inp = {"draftId": draft_id, **{k: v for k, v in inp.items() if k != "publicationId"}}
        draft = api.update_draft(update_inp)
        print(f"Updated draft {draft.get('id')}")
    else:
        draft = api.create_draft(inp)
        print(f"Created draft {draft.get('id')}")

    hn["draftId"] = draft.get("id") or draft_id
    meta["status"] = "draft"
    _save_meta(project, meta)
    print(f"  title: {draft.get('title')}")
    print(f"  slug: {draft.get('slug')}")
    print(f"Wrote {project / 'post.json'}")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    project = Path(args.project)
    meta, body = _load_project(project)
    hn = meta.setdefault("hashnode", {})
    draft_id = (hn.get("draftId") or "").strip()
    post_id = (hn.get("postId") or "").strip()

    if args.dry_run:
        if post_id:
            print(f"[dry-run] would updatePost id={post_id}")
            print(json.dumps(_publish_input(meta, body, allow_missing_pub=True), indent=2, ensure_ascii=False))
        elif draft_id:
            print(f"[dry-run] would publishDraft draftId={draft_id}")
        else:
            print("[dry-run] would publishPost (no draftId)")
            print(json.dumps(_publish_input(meta, body, allow_missing_pub=True), indent=2, ensure_ascii=False))
        return 0

    if post_id:
        inp = _publish_input(meta, body)
        inp.pop("publicationId", None)
        inp["id"] = post_id
        post = api.update_post(inp)
        print(f"Updated post {post.get('id')}")
    elif draft_id:
        post = api.publish_draft(draft_id)
        print(f"Published draft → post {post.get('id')}")
        hn["draftId"] = ""  # draft soft-deleted on Hashnode
    else:
        post = api.publish_post(_publish_input(meta, body))
        print(f"Published post {post.get('id')}")

    hn["postId"] = post.get("id") or post_id
    hn["url"] = post.get("url") or hn.get("url") or ""
    hn["publishedAt"] = post.get("publishedAt") or hn.get("publishedAt") or ""
    meta["status"] = "published"
    _save_meta(project, meta)
    print(f"  url: {hn.get('url')}")
    print(f"Wrote {project / 'post.json'}")
    return 0


def cmd_update_post(args: argparse.Namespace) -> int:
    """Force updatePost path (requires hashnode.postId)."""
    project = Path(args.project)
    meta, body = _load_project(project)
    hn = meta.setdefault("hashnode", {})
    post_id = (hn.get("postId") or "").strip()
    if not post_id:
        raise SystemExit("post.json hashnode.postId is empty — publish first")
    inp = _publish_input(meta, body)
    inp.pop("publicationId", None)
    inp["id"] = post_id
    if args.dry_run:
        print("[dry-run] would updatePost")
        print(json.dumps(inp, indent=2, ensure_ascii=False))
        return 0
    post = api.update_post(inp)
    hn["url"] = post.get("url") or hn.get("url") or ""
    hn["publishedAt"] = post.get("publishedAt") or hn.get("publishedAt") or ""
    meta["status"] = "published"
    _save_meta(project, meta)
    print(f"Updated post {post.get('id')}")
    print(f"  url: {hn.get('url')}")
    return 0


def main() -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="Hashnode blog CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_who = sub.add_parser("whoami", help="Validate PAT and list publications")
    p_who.set_defaults(func=cmd_whoami)

    p_prev = sub.add_parser("preview", help="Print draft payload from a project dir")
    p_prev.add_argument("--project", required=True, help="Path to blog/posts/<date>-<slug>")
    p_prev.set_defaults(func=cmd_preview)

    p_up = sub.add_parser("upsert-draft", help="Create or update a Hashnode draft")
    p_up.add_argument("--project", required=True)
    p_up.add_argument("--dry-run", action="store_true")
    p_up.set_defaults(func=cmd_upsert_draft)

    p_pub = sub.add_parser("publish", help="Publish draft (or publishPost if no draft)")
    p_pub.add_argument("--project", required=True)
    p_pub.add_argument("--dry-run", action="store_true")
    p_pub.set_defaults(func=cmd_publish)

    p_upd = sub.add_parser("update-post", help="Update an already-published post")
    p_upd.add_argument("--project", required=True)
    p_upd.add_argument("--dry-run", action="store_true")
    p_upd.set_defaults(func=cmd_update_post)

    args = parser.parse_args()
    try:
        return args.func(args)
    except api.HashnodeError as e:
        print(f"Hashnode error: {e}", file=sys.stderr)
        msg = str(e).lower()
        if "pro plan" in msg or "forbidden" in msg:
            print(
                "Hint: API writes require Hashnode Pro on the publication.",
                file=sys.stderr,
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
