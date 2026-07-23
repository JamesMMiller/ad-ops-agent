# Journey blog

Version-controlled source for James Miller's public build log: evenings after a lead-developer day job, trying to make a bit of money online with **Our Tech Accessories** (`ourtechaccessories.com`), and documenting whether a calm, Apple/Samsung-style store can work without the classic dropshipping circus.

**Why this lives in ad-ops-agent:** so the same IDE agent that ships creatives and storefront updates can also write and publish the diary. The bet is **organic traffic** to the store from honest build posts. The expectation is that almost no blog reader will buy anything. That is fine: this is an SEO / storytelling experiment, not a soft sell.

**Point of view:** James's lived experience. Agent session details stay out of the prose unless he asks for them.

## Voice

- First person, UK English
- Light-spirited with a little humour
- Honest about ups and downs; no fake certainty
- Evidence from this repo and real decisions; never invent results
- No revenue / ROAS / profit figures unless James supplies them
- Supplier criticism = policy fit only (returns, freight, reliability), not accusations

## Local layout (committed)

```
blog/
  README.md
  posts/
    <YYYY-MM-DD>-<slug>/
      post.md      # canonical markdown body
      post.json    # title, slug, tags, SEO, Hashnode IDs after sync
      images/      # storefront screenshots (homepage, PDPs, etc.)
```

Store-focused posts should include real screenshots of `ourtechaccessories.com` (see `shared/skills/blog-writing/prompting/screenshots.md`).

Working scratch (optional, gitignored) can also live under `outputs/blog/` if an agent needs throwaway drafts. Prefer committing finished posts under `blog/posts/`.

## Hosting: Hashnode Pro

Publishing target is **Evening Ops** on Hashnode:

| | |
|---|---|
| **Publication** | Evening Ops |
| **Subdomain** | [eveningops.hashnode.dev](https://eveningops.hashnode.dev) |
| **Branding** | [`blog/branding/`](branding/) — EO squircle + amber; upload logo/favicon/OG in Hashnode Appearance |
| **API** | GraphQL `https://gql-beta.hashnode.com` (writes need **Hashnode Pro**) |

### Signup checklist

1. Publication created: **Evening Ops** / `eveningops.hashnode.dev`.
2. Upgrade to [Hashnode Pro](https://hashnode.com/pro) (required for API writes).
3. Generate a Personal Access Token: Account Settings → Developer → API tokens.
4. Find the publication ObjectId (dashboard / GraphQL `me { publications { edges { node { id title } } } }`).
5. Add to repo `.env` (never commit):

```bash
HASHNODE_PAT=your_personal_access_token
HASHNODE_PUBLICATION_ID=your_publication_object_id
HASHNODE_HOST=eveningops.hashnode.dev
# Optional:
# HASHNODE_GQL_URL=https://gql-beta.hashnode.com
```

6. Verify:

```bash
bash shared/skills/blog-writing/scripts/check-hashnode-env.sh
```

## Agent workflow

Use the **`blog-writing`** skill (`shared/skills/blog-writing/SKILL.md`).

Default path:

1. Draft / edit `blog/posts/<date>-<slug>/post.md` + `post.json` locally.
2. Hit the quality bar in the skill.
3. Dry-run payload → create/update **Hashnode draft**.
4. Explicit user yes before `publish`.

```bash
# Preview what would be sent
python3 shared/skills/blog-writing/scripts/hashnode_cli.py preview \
  --project blog/posts/2026-07-23-lead-dev-dropshipping-calm-store

# Upsert a Hashnode draft (default; never live)
python3 shared/skills/blog-writing/scripts/hashnode_cli.py upsert-draft \
  --project blog/posts/2026-07-23-lead-dev-dropshipping-calm-store

# Publish only after explicit approval
python3 shared/skills/blog-writing/scripts/hashnode_cli.py publish \
  --project blog/posts/2026-07-23-lead-dev-dropshipping-calm-store
```

## First post

See [`posts/2026-07-23-lead-dev-dropshipping-calm-store/`](posts/2026-07-23-lead-dev-dropshipping-calm-store/).
