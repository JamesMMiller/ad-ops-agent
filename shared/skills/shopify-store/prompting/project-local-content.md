# Local Shopify projects (gitignored)

Put **store-specific** briefs, HTML, and `project.json` under:

```
outputs/shopify/projects/<project-name>/
  project.json
  description.html
  brief.md          # optional
  landing-page.html # optional
```

These paths are under `outputs/` and are **not** committed to git.

Apply with the generic skill script:

```bash
python shared/skills/shopify-store/scripts/apply_product_project.py \
  --project outputs/shopify/projects/<project-name> \
  --dry-run
```

See `shared/skills/shopify-store/SKILL.md` for draft vs live rules.
