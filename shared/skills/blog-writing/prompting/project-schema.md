# Post project schema

Each post lives in:

```
blog/posts/<YYYY-MM-DD>-<slug>/
  post.md
  post.json
  images/          # storefront screenshots (see screenshots.md)
```

## `post.md`

- Markdown body only (no YAML frontmatter required; metadata lives in `post.json`).
- Start with prose, not a duplicate H1 if Hashnode will show `title` separately. An optional leading `#` matching the title is OK for local reading.
- Use `##` / `###` for sections.
- Links: prefer full HTTPS URLs for public pages.
- Images: relative paths like `![Homepage](images/homepage-desktop.png)` placed beside the relevant section.

## `post.json`

```json
{
  "title": "Can a Lead Developer Build a Dropshipping Store Without Building a Dropshipping Store?",
  "subtitle": "Evenings, curiosity, and trying not to build another carnival of fake urgency.",
  "slug": "lead-dev-dropshipping-calm-store",
  "tags": [
    { "slug": "dropshipping", "name": "Dropshipping" },
    { "slug": "shopify", "name": "Shopify" },
    { "slug": "side-project", "name": "Side Project" }
  ],
  "coverImageURL": "",
  "seo": {
    "title": "",
    "description": "A UK lead developer documents building a calm tech store and an IDE ad-ops agent — without the classic dropshipping mess."
  },
  "originalArticleURL": "",
  "enableToc": true,
  "status": "draft",
  "hashnode": {
    "draftId": "",
    "postId": "",
    "url": "",
    "publishedAt": ""
  },
  "notes": "Optional agent/human notes; not published."
}
```

### Field notes

| Field | Rules |
|-------|--------|
| `title` | Required. Human, specific. |
| `subtitle` | Optional; used as Hashnode subtitle when set. |
| `slug` | Required. kebab-case; stable once published. |
| `tags` | 1–8 objects with `slug` (required) and optional `name`. |
| `coverImageURL` | Public HTTPS image, or empty. |
| `seo.title` | Optional override; empty → use `title`. |
| `seo.description` | Strongly preferred; ≤ ~160 chars. |
| `status` | `draft` \| `published` \| `local` (local = not pushed yet). |
| `hashnode.*` | Filled by CLI after remote sync; do not invent IDs. |

## Directory naming

`YYYY-MM-DD` = intended publish or first-draft date.  
`<slug>` should match `post.json` `slug` (or be a close prefix if the folder needs a longer label).
