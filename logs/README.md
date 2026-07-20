# API generation logs

Append-only logs of every generative API call. They power smarter credit-cost estimation over time.

## Primary: KIE.ai

- **`kie-api.jsonl`** — one JSON object per line for every KIE generation (`POST /api/v1/veo/generate`, `POST /api/v1/jobs/createTask`).

### Entry schema (illustrative)

```json
{
  "timestamp": "2026-07-19T21:54:29.470780Z",
  "endpoint": "POST /api/v1/jobs/createTask",
  "model": "bytedance/seedance-2-fast",
  "taskId": "…",
  "request": {
    "duration": 12,
    "resolution": "720p",
    "aspect_ratio": "1:1",
    "promptWordCount": 220
  },
  "response": {
    "state": "success",
    "creditsCharged": 396,
    "resultUrls": ["https://…"]
  },
  "session": {
    "folder": "outputs/2026-07-19-example"
  }
}
```

### How the agent uses this file

- **Before any new generation:** grep for the same `model` + similar config and use recorded `creditsCharged` for the estimate.
- **After each generation:** append request metadata and the final polled response.
- **When pricing rules emerge:** document per-second rates in `MASTER_CONTEXT.md`.

Dashboard: https://kie.ai/logs

## Rules

- Do **not** log API keys, Authorization headers, or full prompt text (store a word count instead).
- Historical cost data is useful across sessions; keep entries lean.
