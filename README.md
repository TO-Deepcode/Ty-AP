# AWS-WEBse News & Market Aggregator

Production-ready Python microservice for fetching crypto market data, aggregating multi-source news, confirming cross-publisher events, and persisting JSON records to blob storage. Designed for Vercel serverless deployment with GPT Action compatibility.

> **Compliance banner**: This service only accesses publicly available content, respects `robots.txt` and site terms, and falls back to HTML extraction only when RSS is unavailable. No aggressive crawling or access control bypassing is performed. Configure the `USER_AGENT` and contact details before going live.

## Features
- Binance, Bybit, and CoinMarketCap market snapshot ingestion with unified schema and JSON archival.
- RSS-first news gathering across 11 crypto outlets, HTML fallback with site-specific extractors, dedupe, and soft per-host rate limiting.
- Lightweight entity heuristics and multi-source confirmation with scoring and near-duplicate clustering.
- Structured JSON logging, correlation IDs, HMAC-protected POST endpoints, and strict CORS controls.
- Storage abstraction supporting Vercel Blob/S3-style HTTP APIs with TTL-based cleanup jobs.
- Weekly automated cleanup via Vercel Cron; optional daily compaction hooks.
- OpenAPI schema + GPT Action manifest snippet for secure integrations.
- Smoke tests with pytest and modular design for future unit coverage.

## Project Layout

```
api/
  health.py
  market_fetch.py
  news_fetch.py
  analyze_news.py
  store_list.py
  admin_cleanup.py
src/
  api_utils.py
  config.py
  confirm.py
  dedupe.py
  extractors/
    rss.py
    html.py
    sites/
      __init__.py
      coindesk.py
      cointelegraph.py
  http_clients.py
  logging_setup.py
  normalization.py
  rate_limit.py
  schemas.py
  security.py
  storage.py
requirements.txt
.env.example
vercel.json
tests/test_smoke.py
```

## Quick Start
1. **Install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure environment**
   - Copy `.env.example` → `.env` and fill in API keys, blob storage credentials, and `ALLOWED_ORIGINS`.
   - Set `HMAC_SHARED_SECRET` to a strong value shared with trusted clients.
3. **Run smoke tests**
   ```bash
   pytest -q
   ```
4. **Local iteration**
   - Use `vercel dev` or a simple runner such as `python -m http.server` (Vercel loads each file as a handler). For manual testing, import the `api.*` modules and invoke `process_request`, `fetch_news`, or `analyze` helper functions directly.

## Environment Variables
| Name | Description |
| --- | --- |
| `ENV` | `development` or `production` toggles local vs. blob storage. |
| `BYBIT_*`, `BINANCE_*`, `CMC_API_KEY` | API credentials. Binance/Bybit are optional for public data; CMC key required for production use. |
| `BLOB_BASE_URL`, `BLOB_*` | Blob/S3-compatible endpoint configuration. Leave empty to use local `.data` directory. |
| `HMAC_SHARED_SECRET` | Shared secret used to compute `X-Signature` header for POST requests. |
| `ALLOWED_ORIGINS` | Comma-separated list of permitted origins for CORS. |
| `HTTP_PROXY` | Optional proxy passed to outbound HTTP clients. |
| `USER_AGENT` | Public-facing identifier with contact information for crawling compliance. |

## API Overview
All endpoints emit/accept JSON. POST requests **must** include `X-Signature: <hex hmac-sha256(body, HMAC_SHARED_SECRET)>`.

### `GET /api/health`
Response:
```json
{"status": "ok", "time": "2025-09-28T12:34:56Z", "version": "1.0.0"}
```

### `POST /api/market_fetch`
Request:
```json
{
  "exchanges": ["bybit", "binance", "cmc"],
  "symbols": ["BTCUSDT", "SOLUSDT"],
  "granularity": "1h",
  "limit": 200
}
```
Response: `MarketFetchResponse` containing normalized OHLC data, 24h deltas, and storage metadata (see `src/schemas.py`). Snapshots are stored under `market/<exchange>/<symbol>/<yyyymmddHH>/snapshot.json`.

### `POST /api/news_fetch`
Request:
```json
{
  "sources": ["coindesk", "theblock", "blockworks", "cointelegraph", "defiant", "dlnews", "protos", "decrypt", "cryptopanic", "messari", "glassnode"],
  "since": "2025-09-28T00:00:00Z",
  "max_per_source": 50
}
```
Response: `NewsFetchResponse` containing deduped `NewsItem` entries with normalized titles, content, and source scores. Raw records land in `news/raw/<source>/<date>/<uuid>.json`.

### `POST /api/analyze_news`
Clusters submitted `NewsItem`s into cross-source events using RapidFuzz similarity, time windows, and source weighting. Stores results in `news/clustered/<date>/<cluster>.json`.

### `GET /api/store_list`
Debug utility returning stored keys for a prefix: `/api/store_list?prefix=news/&limit=100`.

### `POST /api/admin_cleanup`
Purges stored objects older than their `ttl_days` metadata (default 14). Accepts `{ "dry_run": true }` for non-destructive runs.

## Storage & Logging
- Local development writes JSON files to `.data/` respecting key prefixes.
- Production mode targets Vercel Blob/S3-style APIs using HMAC authorization. Adjust `src/storage.py` if your provider exposes different endpoints.
- Structured logs are emitted via `structlog` with correlation IDs and serialized to stdout. For additional audit trails, store per-request logs using `Storage.put_json` (`logs/<date>/<request_id>.json`).

## Security Notes
- POST HMAC validation is enforced in `src/security.py`; failing signatures yield `401`.
- CORS is restricted to `ALLOWED_ORIGINS`. Preflight requests (`OPTIONS`) return minimal headers.
- Rate limiting (0.5 QPS default) is host-specific to avoid overloading publishers.
- Robots.txt is honored before any HTML fetch; blocked pages are skipped silently.

## Deployment to Vercel
1. Push the repository to GitHub/GitLab.
2. Create a Vercel project, set build command to `pip install -r requirements.txt` and framework to **Other**.
3. Set environment variables in Vercel dashboard (Production + Preview).
4. Deploy; Vercel maps each `api/*.py` file to a serverless function running Python 3.11.
5. Verify the weekly cron (Monday 03:00 UTC) automatically invokes `/api/admin_cleanup` per `vercel.json`. Adjust the schedule as needed.

## GPT Action Manifest Example
Include the following manifest in your custom GPT configuration and point `openapi_schema` to the hosted `/api/openapi` endpoint (see below):
```json
{
  "schema_version": "v1",
  "name_for_human": "AWS-WEBse Crypto Aggregator",
  "name_for_model": "aws_webse",
  "description_for_human": "Fetch crypto market data and vetted news clusters",
  "description_for_model": "Interacts with AWS-WEBse service. Sign all POST requests with HMAC SHA-256 using the shared secret.",
  "auth": {
    "type": "custom",
    "authorization_type": "signature",
    "verification_tokens": {}
  },
  "api": {
    "type": "openapi",
    "url": "https://your-deployment.vercel.app/api/openapi"
  },
  "contact_email": "ops@your-domain",
  "legal_info_url": "https://your-domain/legal"
}
```

The OpenAPI schema exposed at `/api/openapi` documents request/response models with signature requirements.

## OpenAPI Quick Reference
Key components of the generated schema:
- `MarketFetchRequest`, `MarketFetchResponse`
- `NewsFetchRequest`, `NewsFetchResponse`
- `AnalyzeNewsRequest`, `AnalyzeNewsResponse`
- `StorageListResponse`, `CleanupRequest/Response`

Refer to `src/schemas.py` for field-level definitions.

## Testing & CI
- Current smoke tests (`tests/test_smoke.py`) mock external HTTP calls and validate serialization paths.
- Extend with per-source extractor fixtures and signature validation cases.
- Recommended tooling: `ruff` for linting, `black` for formatting, `pytest-cov` for coverage.

## Maintenance Checklist
- Rotate `HMAC_SHARED_SECRET` regularly.
- Monitor API rates for Binance/Bybit/CMC and back-off thresholds.
- Validate robots.txt for each publisher after site redesigns.
- Review `.data` directory or blob bucket for growth; adjust TTL or introduce compaction if required.

## License
Internal project — adopt your organization’s licensing policy before distribution.
