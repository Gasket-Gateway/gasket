# Gasket Gateway

Gasket is an API gateway for OpenAI-compliant inference backends. It provides a portal for users to work with these backends within an organisational context, including enterprise capabilities such as SSO, organisational policy, auditing, monitoring and quotas.

## Architecture

```
                     ┌──────────────────────────────┐
  Browser Users      │             Gasket           │
  ──(OIDC SSO)────►o─│───Portal UI                  │
                     │                              │    ┌─► OpenAI Backend A
  API Clients        │   Gateway API ───────────────┼────┼─► OpenAI Backend B
  ──(API key)─────►o─│───(proxy / agg)              │    └─► OpenAI Backend C
  (Open WebUI,       │                              │
   VSCode, etc.)     └───────────────────┬──────────┘
                                         │
            ┌───────────────┬────────────┼──────────────┐
            │               │            │              │
      PostgreSQL       OpenSearch   Prometheus      OIDC Provider
      (keys, prefs,   (audit logs) (metrics,           (SSO)
    quotas, blocks)                 quota queries)
```

**Components:**

- **Portal UI** — Web interface for users and admins. Supports light/dark mode.
- **Gateway** — Proxies and aggregates requests to configured OpenAI-compliant backends. Enforces access, quotas and audit.
- **PostgreSQL** — Stores API keys, user preferences, policy acceptance records, and per-user quota block status.
- **OpenSearch** — Stores audit records (metadata and optionally full request/response content).
- **Prometheus** — Stores token usage and latency metrics. Used to evaluate quota consumption after each request.
- **OIDC Provider** — Handles SSO login. OIDC groups control user access, admin panel access and backend profile access.

---

> [!NOTE]
> **Open WebUI Integration** — Gasket supports extracting Open WebUI user identity from request headers, enabling
> per-Open-WebUI-user metrics, quotas, and audit records. Because these headers can be spoofed by clients, this
> feature must be explicitly enabled on the backend profile and opted into by the user when creating or editing
> an API key. See [Open WebUI Header Support](#open-webui-header-support) below.

> [!NOTE]
> **VSCode Continue Extension** — Gasket can generate a VSCode Continue plugin config snippet for any API key.
> Users can opt a key into this feature when creating or editing it. See [API Key Management](#api-key-management) below.

---

## Implementation

- Python Flask application
- The app should support multiple instances (high availability) using the same Postgresql, Prometheus and OpenSearch integrations, as well as persisting the user OIDC session
- Dockerfile for containerised deployment
- Docker Compose file for local development, including postgresql
- Their should be a HA version of the docker compose file that has three instances of the portal available on port 5000, 5001, and 5002
- A seperate development environment project will provide, Traefik load balancing, Prometheus, OpenSearch, Authentik, Ollama, Code Server, Open WebUI, and Grafana
- UI built with plain HTML, CSS and JavaScript — no external UI libraries or JavaScript frameworks
- All code should be kept as simple as possible and easily human-readable
- The app should have a healthcheck endpoint at `/health` that returns a 200 OK response
- The app should have a metrics endpoint at `/metrics` that returns a 200 OK response with Prometheus metrics
- The app metrics should work across all instances of the app (high availability) by using the postgresql database for metrics aggregation before presenting to the `/metrics` endpoint

---

## Requirements

### Configuration

- YAML config file for all settings
- Config option to disable TLS verification for the OIDC provider, Prometheus and OpenSearch
- Config option for portal banners (banner content, banner colour)
- Default light/dark mode preference from config YAML

### Authentication & Access

- OIDC login
- OIDC groups for: general user access, admin panel access, and per-backend-profile access
- Logout button URL from config

### Backend Profiles

- Support multiple OpenAI-compliant backends with aggregation of API calls where appropriate (e.g. list models)
- Backend profiles define:
  - Name, description
  - Policy text for users to accept before use
  - Whether metadata audit is enabled
  - Whether full request/response content audit is enabled
  - List of OpenAI backends
  - Default or enforced API key expiry duration
  - Usage quota configurations (see [Quotas](#monitoring--quotas))
  - Maximum number of active API keys per user
  - Whether Open WebUI header support is enabled (see [Open WebUI Header Support](#open-webui-header-support))

### API Key Management

- User can create a new API key with:
  - Key name
  - Backend profile selection
  - Expiry date (default or enforced from backend profile config)
  - Opt-in to VSCode Continue config template generation
  - Opt-in to Open WebUI header support (only shown if enabled on the selected backend profile)
- User can view and edit existing API keys:
  - View API key value
  - Edit VSCode Continue config template opt-in
  - Edit Open WebUI header support opt-in
  - View usage metrics from Prometheus
  - View quota usage from Prometheus
- User can revoke their own API keys
- Template VSCode Continue config for all opted-in API keys

### User Portal

- User can view and accept policies for backend profiles they have access to
- User can view records of policies they have accepted (policy, acceptance timestamp)
- User can see connection status, metrics and quota usage for their available backends and backend profiles
- User interactions with the portal should create log events in the stdout of the flask app
- The user OIDC session should time out after a configurable time in the config (default 8h)

### Monitoring & Quotas

- Prometheus-compatible metrics with the following labels: `user`, `api_key`, `backend_profile`, `openai_backend`, `model`
  - Token usage
  - API call latency
  - API call success/failure
  - Daily active unique API users (Gasket users)
  - Daily active unique API users (Open WebUI users)
  - Daily active unique API users (All users)
- Daily active unique Gasket Portal users
- Token usage quotas configurable per backend profile:
  - Per API key
  - Per Gasket user per backend profile
  - Per Open WebUI user per backend profile
  - Per Gasket user globally
  - Per Open WebUI user globally
  - Quota defined as maximum tokens allowed within a rolling time period (e.g. 10,000 per 24 h)
- After each proxied request completes, query Prometheus to evaluate whether the user has exceeded any quota:
  - If a quota is exceeded, write a block status and expiry timestamp to the database for that user/key/scope
  - On every incoming request, check the database for an active block status before proxying
  - If Prometheus is unavailable, allow the request to proceed provided there is no active block status in the database

### Audit

- Audit records written to OpenSearch
- Audit record contains: request metadata (user, api_key, model, backend, timestamps, token counts)
- Full request/response content audit per backend profile (optional)
- Aggregate related requests (e.g. streaming chunks)

### Open WebUI Header Support

- Backend profiles can opt-in to trusting Open WebUI user identity headers
- When a backend profile has this enabled, users must also opt-in on individual API keys
- If enabled on both the backend profile and the API key, and the headers are present in the request:
  - Include Open WebUI user identity in audit records
  - Use Open WebUI user identity for metrics and quota evaluation (in addition to the Gasket user)
- If headers are absent, fall back to Gasket user identity only

### Admin Panel

- Connection status indicators for: PostgreSQL, OIDC provider, OpenSearch, Prometheus
- List all API keys with usage metrics/quotas from Prometheus, and active block statuses from the database
- Revoke button for any active API key
- Restore button for any revoked API key
- Filter and search API keys
- Fetch and view audit records from OpenSearch:
  - Search and filter (adjusting OpenSearch queries)
  - Metadata view
  - Full content view (where enabled on the backend profile)
  - Aggregate related requests (conversation threads)
  - Request/response histograms to show usage over time
- Usage metrics dashboard from Prometheus
- Usage quotas dashboard including current block statuses from Prometheus and the database
- OpenAI backend dashboard showing connection status and usage metrics
- Backend profile dashboard showing usage metrics and quotas
- Policy acceptance records with search/filter by Gasket user
