# Plane CE - Architecture and Component Overview

## 1. Executive summary

Plane is a self-hosted, full-stack project-management application organized as a
monorepo:

- **Python/Django backend** in `apps/api`.
- **React Router/TypeScript web applications** in `apps/web`, `apps/admin`, and
  `apps/space`.
- **Realtime collaboration server** in `apps/live`.
- **Shared TypeScript packages** under `packages/`.
- **Containerized runtime dependencies** (PostgreSQL, Valkey/Redis, RabbitMQ,
  MinIO and reverse proxy) orchestrated by Docker Compose.

The principal request path is:

```text
Browser
  -> reverse proxy
  -> web/admin/space frontend
  -> Django API
  -> PostgreSQL / Valkey / RabbitMQ / object storage

Browser collaboration traffic
  -> live server
  -> Valkey + persistence/API services
```

The repository is not a single deployable application. It is a coordinated set
of deployable services plus shared libraries.

## 2. Top-level repository structure

| Location | Role |
|---|---|
| [`apps/api/`](../apps/api/) | Django API, authentication, domain logic, ORM models, background tasks |
| [`apps/web/`](../apps/web/) | Main user-facing Plane application |
| [`apps/admin/`](../apps/admin/) | Instance/admin management interface |
| [`apps/space/`](../apps/space/) | Space/public-facing interface and authentication surface |
| [`apps/live/`](../apps/live/) | Realtime collaborative editing server |
| [`apps/proxy/`](../apps/proxy/) | Reverse proxy configuration and container |
| [`packages/`](../packages/) | Shared TypeScript types, constants, UI, services, editor and tooling |
| [`deployments/`](../deployments/) | Community/AIO/Kubernetes deployment assets |
| [`docker-compose.yml`](../docker-compose.yml) | Local/self-hosted service topology |
| [`pnpm-workspace.yaml`](../pnpm-workspace.yaml) | JavaScript/TypeScript workspace definition |

Project classification: **full-stack monorepo with multiple deployable services**.

## 3. Runtime services

The runtime topology is defined in
[`docker-compose.yml`](../docker-compose.yml).

### 3.1 API service

The `api` container runs Django using
[`apps/api/bin/docker-entrypoint-api.sh`](../apps/api/bin/docker-entrypoint-api.sh).
The root URL router is
[`apps/api/plane/urls.py`](../apps/api/plane/urls.py).

Main URL groups:

| Prefix | Function |
|---|---|
| `/api/` | Main application API |
| `/api/public/` | Public/space API |
| `/api/instances/` | Instance and administration API |
| `/api/v1/` | Versioned API surfaces |
| `/auth/` | Credential, magic-link and OAuth authentication |
| `/` | Backend web/health routes |

The API uses Django session authentication and Django REST Framework. Global
middleware, authentication, CORS, storage and database configuration are in
[`apps/api/plane/settings/common.py`](../apps/api/plane/settings/common.py).

### 3.2 Main web application

[`apps/web/`](../apps/web/) is the primary user interface. Its package scripts
use React Router, TypeScript, Vite and shared `@plane/*` packages. Authentication
options are assembled by
[`apps/web/core/hooks/oauth/core.tsx`](../apps/web/core/hooks/oauth/core.tsx).

Responsibilities include:

- Workspace and project navigation.
- Issues/work items, cycles, modules and views.
- User sessions and authentication entry points.
- API calls through shared services and state hooks.
- Rendering shared UI components from `packages/`.

### 3.3 Admin application

[`apps/admin/`](../apps/admin/) is a separate React Router application used for
instance-level administration. It runs on port `3001` in the local configuration
and communicates with the same Django API.

Typical responsibilities:

- Instance setup and configuration.
- Instance administrators.
- Authentication/provider configuration.
- Operational and self-hosted settings.

### 3.4 Space application

[`apps/space/`](../apps/space/) is a separate frontend for public/workspace
space flows. It has its own OAuth configuration hook:
[`apps/space/hooks/oauth/core.tsx`](../apps/space/hooks/oauth/core.tsx).

It shares API contracts and TypeScript packages with the main web application,
but has separate routes, deployment and authentication redirect behavior.

### 3.5 Live collaboration service

[`apps/live/`](../apps/live/) is a Node.js/TypeScript realtime server. Its
package metadata identifies it as the collaboration server and shows usage of
Hocuspocus, WebSockets, Yjs, TipTap and Redis clients.

Responsibilities include:

- Realtime collaborative editor sessions.
- WebSocket connection handling.
- Document synchronization through Yjs protocols.
- Redis-backed coordination/persistence integrations.
- Security headers, CORS and HTTP server concerns.

This service is operationally separate from the Django API and should be treated
as a distinct runtime boundary.

### 3.6 Background workers

The Compose file defines:

- `worker`: asynchronous task execution.
- `beat-worker`: scheduled task dispatch.
- `migrator`: database migration/bootstrap tasks.

The task implementations are under
[`apps/api/plane/bgtasks/`](../apps/api/plane/bgtasks/), including email,
notifications, exports, webhooks, invitations, file handling and workspace
seeding.

### 3.7 Infrastructure services

| Service | Role |
|---|---|
| `plane-db` | PostgreSQL 15 persistence |
| `plane-redis` | Valkey/Redis-compatible cache and shared transient state |
| `plane-mq` | RabbitMQ message broker |
| `plane-minio` | S3-compatible object storage for uploaded assets |
| `proxy` | External HTTP/HTTPS entry point and routing to frontend/API containers |

## 4. Backend architecture

The backend is a Django application split by responsibility rather than strict
layered packages.

### 4.1 Routing layer

The root router delegates to application routers:

- [`apps/api/plane/app/urls.py`](../apps/api/plane/app/urls.py)
- [`apps/api/plane/space/urls.py`](../apps/api/plane/space/urls.py)
- [`apps/api/plane/license/urls.py`](../apps/api/plane/license/urls.py)
- [`apps/api/plane/api/urls.py`](../apps/api/plane/api/urls.py)
- [`apps/api/plane/authentication/urls.py`](../apps/api/plane/authentication/urls.py)

The authentication router contains credential login, magic-link flows and
provider-specific OAuth routes.

### 4.2 API/view layer

Views are grouped by functional area:

- `plane.app`: core application endpoints.
- `plane.space`: public/space endpoints.
- `plane.api`: versioned API endpoints.
- `plane.license`: instance configuration and administration.
- `plane.authentication`: login, signup, session and OAuth flows.

Serializers and REST Framework views define the external JSON API contracts.

### 4.3 Data/model layer

The main user model is
[`apps/api/plane/db/models/user.py`](../apps/api/plane/db/models/user.py).
It defines the `users` table and identity/profile fields such as:

- UUID primary key.
- Email and username.
- First/last/display names.
- Avatar and cover image references.
- Password/session/login metadata.
- Activation, verification and bot flags.
- Timezone and onboarding state.

Other models under
[`apps/api/plane/db/models/`](../apps/api/plane/db/models/) represent
workspaces, projects, issues/work items, cycles, modules, pages, assets,
notifications, integrations and related domain data.

The model layer uses Django ORM migrations under
[`apps/api/plane/db/migrations/`](../apps/api/plane/db/migrations/).

### 4.4 Authentication layer

Authentication is implemented through reusable adapters and endpoint views:

- Credential/password login.
- Magic-link login.
- OAuth providers.
- Session creation and user login.
- Account linking through the existing authentication workflow.

The OAuth adapter is
[`apps/api/plane/authentication/adapter/oauth.py`](../apps/api/plane/authentication/adapter/oauth.py).
Provider implementations live under
[`apps/api/plane/authentication/provider/oauth/`](../apps/api/plane/authentication/provider/oauth/).

The recently added Keycloak implementation follows the same architecture:

1. Provider reads runtime configuration.
2. Provider creates authorization URL.
3. Callback exchanges the code for tokens.
4. UserInfo is mapped to the internal user shape.
5. Existing account linking and session login are reused.

Relevant Keycloak files:

- [`keycloak.py`](../apps/api/plane/authentication/provider/oauth/keycloak.py)
- [`app/keycloak.py`](../apps/api/plane/authentication/views/app/keycloak.py)
- [`space/keycloak.py`](../apps/api/plane/authentication/views/space/keycloak.py)

### 4.5 Background processing

Celery is configured in
[`apps/api/plane/celery.py`](../apps/api/plane/celery.py).
RabbitMQ is used as the broker in the Compose topology; Redis/Valkey is used for
cache and transient coordination. Background tasks avoid blocking API requests
for email, exports, notifications, file operations and webhooks.

### 4.6 Storage and external services

The backend uses:

- PostgreSQL through `psycopg` and Django ORM.
- Redis-compatible storage through `redis`/`django-redis`.
- S3-compatible storage through `boto3`/`django-storages`.
- RabbitMQ through Celery.
- HTTP integrations through `requests`.
- OpenTelemetry and Scout APM integration for observability.

## 5. Frontend architecture

The frontend applications are React/TypeScript applications that share code
through workspace packages.

### 5.1 Shared package responsibilities

The main package categories are:

| Package area | Responsibility |
|---|---|
| `packages/types` | Shared TypeScript domain and API types |
| `packages/constants` | Shared labels, keys and static configuration constants |
| `packages/ui` | Reusable UI primitives and application components |
| `packages/propel` | Design-system components |
| `packages/services` | API/service clients |
| `packages/utils` | Shared utility functions |
| `packages/editor` | Rich-text/editor behavior and styles |
| `packages/i18n` | Localization |
| `packages/hooks` | Reusable React hooks |
| `packages/decorators` | Shared decorators and cross-cutting helpers |

### 5.2 Typical frontend flow

```text
Route/page
  -> feature component
  -> hook/store
  -> shared service/API client
  -> Django endpoint
  -> typed response
  -> state update and UI rendering
```

Authentication provider availability is returned by the instance endpoint and
consumed by frontend hooks. The Keycloak integration adds
`is_keycloak_enabled` to the shared instance configuration type and renders a
`Login with THM SSO` option when enabled.

## 6. Important data and state flows

### 6.1 User authentication

```text
Frontend login option
  -> /auth/<provider>/
  -> provider authorization server
  -> /auth/<provider>/callback/
  -> OauthAdapter
  -> post_user_auth_workflow
  -> User + Account linking
  -> Django session
  -> frontend redirect
```

The OAuth flow carries `state` through the Django session to prevent callback
mix-up. `next_path` is also carried through the session and validated before
redirecting.

### 6.2 Instance configuration

```text
Environment variables / stored instance settings
  -> get_configuration_value(...)
  -> InstanceEndpoint
  -> /api/instances/
  -> frontend useInstance hook
  -> enabled/disabled UI features
```

This mechanism controls whether OAuth buttons are shown and keeps secrets on the
backend.

### 6.3 Uploaded assets

```text
Frontend upload
  -> Django asset endpoint
  -> database metadata
  -> S3/MinIO object
  -> signed/public asset URL
```

### 6.4 Asynchronous work

```text
Django request
  -> Celery task enqueue
  -> RabbitMQ
  -> worker
  -> PostgreSQL/Redis/object storage/external service
```

## 7. Configuration and entry points

Important configuration files:

- [`apps/api/.env.example`](../apps/api/.env.example): API/runtime environment
  variables.
- [`apps/api/plane/settings/common.py`](../apps/api/plane/settings/common.py):
  Django, middleware, REST, security and application configuration.
- [`apps/api/plane/settings/storage.py`](../apps/api/plane/settings/storage.py):
  object-storage configuration.
- [`apps/api/plane/settings/redis.py`](../apps/api/plane/settings/redis.py):
  Redis/Valkey configuration.
- [`docker-compose.yml`](../docker-compose.yml): local service wiring.
- `apps/*/package.json`: frontend/live scripts and dependencies.
- `pnpm-workspace.yaml`: workspace package boundaries.

Primary process entry points:

- API: [`apps/api/plane/asgi.py`](../apps/api/plane/asgi.py)
- Celery: [`apps/api/plane/celery.py`](../apps/api/plane/celery.py)
- Web: `apps/web` package scripts
- Admin: `apps/admin` package scripts
- Space: `apps/space` package scripts
- Live: `apps/live` package scripts

## 8. Architectural boundaries and coupling

### Strong boundaries

- API and frontend are separate deployables communicating over HTTP.
- Live collaboration is a separate Node.js process and WebSocket boundary.
- PostgreSQL, Redis/Valkey, RabbitMQ and object storage are external runtime
  dependencies from the application code's perspective.
- Shared TypeScript packages are consumed by multiple frontend services.

### Shared coupling points

- Shared API URL and data contracts.
- `packages/types` and `packages/constants`.
- Authentication/session behavior between API and all frontend apps.
- Instance configuration flags used by frontend feature rendering.
- Redis/Valkey usage by API background work and live collaboration.
- Object storage metadata in PostgreSQL plus binary objects in MinIO/S3.

### Review caution

Changes to shared types, instance configuration response shape, authentication
routes, session behavior or package exports can affect multiple applications.
Changes to the API model/migration layer can affect workers, admin, web, space
and integrations simultaneously.

## 9. Current Keycloak integration boundary

The Keycloak feature is intentionally bounded to the existing OAuth architecture:

- Provider: [`keycloak.py`](../apps/api/plane/authentication/provider/oauth/keycloak.py)
- App flow: [`app/keycloak.py`](../apps/api/plane/authentication/views/app/keycloak.py)
- Space flow: [`space/keycloak.py`](../apps/api/plane/authentication/views/space/keycloak.py)
- Routes: [`authentication/urls.py`](../apps/api/plane/authentication/urls.py)
- Frontend options:
  - [`apps/web/core/hooks/oauth/core.tsx`](../apps/web/core/hooks/oauth/core.tsx)
  - [`apps/space/hooks/oauth/core.tsx`](../apps/space/hooks/oauth/core.tsx)

It does not introduce a second authentication system, new user/session model or
new account-linking mechanism.

## 10. Validation status

Validation performed after the Keycloak changes:

- Python compile: passed.
- Ruff checks for changed Python files: passed.
- Oxfmt checks for changed TypeScript files: passed.
- Oxlint checks for changed TypeScript files: passed.
- Full frontend type-check: attempted, but the workspace reported unresolved
  internal package declarations such as `@plane/types`, `@plane/constants`,
  `@plane/ui` and `@plane/i18n`. These are workspace build/declaration issues,
  not errors reported from the Keycloak implementation itself.

## 11. Suggested reading order

For understanding the system quickly:

1. [`docker-compose.yml`](../docker-compose.yml) - runtime topology.
2. [`apps/api/plane/urls.py`](../apps/api/plane/urls.py) - API route map.
3. [`apps/api/plane/settings/common.py`](../apps/api/plane/settings/common.py) -
   backend wiring.
4. [`apps/api/plane/db/models/user.py`](../apps/api/plane/db/models/user.py) -
   core identity model.
5. [`apps/api/plane/authentication/adapter/oauth.py`](../apps/api/plane/authentication/adapter/oauth.py) -
   OAuth abstraction.
6. [`apps/web/core/hooks/oauth/core.tsx`](../apps/web/core/hooks/oauth/core.tsx) -
   frontend provider rendering.
7. [`apps/live/package.json`](../apps/live/package.json) - realtime service
   boundary.
8. [`packages/types/`](../packages/types/) and
   [`packages/constants/`](../packages/constants/) - shared frontend contracts.

## 12. Deployment bằng Plane Community CLI

Deployment CLI hiện có nằm trong
[`deployments/cli/community/`](../deployments/cli/community/). Đây là deployment
kiểu **Docker Compose trên một máy Linux/Docker**, không phải Azure CLI và cũng
không phải Kubernetes Helm.

### 12.1 Thành phần CLI triển khai

| File | Vai trò |
|---|---|
| [`install.sh`](../deployments/cli/community/install.sh) | Menu cài đặt, start/stop/restart/upgrade/logs/backup |
| [`docker-compose.yml`](../deployments/cli/community/docker-compose.yml) | Topology runtime dùng image đã build sẵn |
| [`build.yml`](../deployments/cli/community/build.yml) | Override để build image từ source hiện tại |
| `plane-app/plane.env` | Environment runtime được CLI tải/tạo và Compose sử dụng |

CLI mặc định tải các image release từ Docker Hub:

```text
makeplane/plane-frontend
makeplane/plane-space
makeplane/plane-admin
makeplane/plane-live
makeplane/plane-backend
makeplane/plane-proxy
```

### 12.2 Cách triển khai release chuẩn

Trên máy Linux có Docker:

```bash
mkdir plane-selfhost
cd plane-selfhost
curl -fsSL -o setup.sh https://github.com/makeplane/plane/releases/latest/download/setup.sh
chmod +x setup.sh
./setup.sh
```

Chọn các action:

```text
1 Install
2 Start
3 Stop
4 Restart
5 Upgrade
6 View Logs
7 Backup Data
8 Exit
```

Lần đầu, action `1` tạo thư mục `plane-app` và tải:

- `plane-app/docker-compose.yaml`
- `plane-app/plane.env`

Sau đó chỉnh `plane.env` trước khi chọn action `2`.

Các giá trị tối thiểu cần rà soát:

```env
WEB_URL=https://qtda.tanhoangminh.com.vn
CORS_ALLOWED_ORIGINS=https://qtda.tanhoangminh.com.vn
LISTEN_HTTP_PORT=80
LISTEN_HTTPS_PORT=443
SECRET_KEY=<random-secret>
```

### 12.3 Cấu hình Keycloak khi dùng CLI

Trong `plane-app/plane.env`, thêm:

```env
IS_KEYCLOAK_ENABLED=1
KEYCLOAK_CLIENT_ID=plane
KEYCLOAK_CLIENT_SECRET=<keycloak-client-secret>
KEYCLOAK_HOST=https://sso.tanhoangminh.com.vn/realms/cds-tanhoangminh
```

Keycloak client phải cho phép:

```text
https://qtda.tanhoangminh.com.vn/auth/keycloak/callback/
https://qtda.tanhoangminh.com.vn/spaces/keycloak/callback/
```

và Web Origin:

```text
https://qtda.tanhoangminh.com.vn
```

### 12.4 Điểm quan trọng: CLI release không tự dùng source local

Đây là điểm cần phân biệt:

- `setup.sh` mặc định kéo image `makeplane/*` từ Docker Hub.
- Code Keycloak mới trong workspace **không xuất hiện trong image release
  chính thức** cho đến khi source này được build và publish thành image.
- Chỉ thêm biến `KEYCLOAK_*` vào `plane.env` là chưa đủ nếu image backend/frontend
  đang chạy không chứa các thay đổi Keycloak.

Có hai hướng:

#### Hướng A - build image custom từ source

[`build.yml`](../deployments/cli/community/build.yml) định nghĩa việc build các
image local từ source:

```bash
cd deployments/cli/community
docker compose -f build.yml build
```

Sau đó cần tag/push các image tới registry mà máy triển khai truy cập được,
đồng thời cấu hình trong `plane.env`:

```env
DOCKERHUB_USER=<registry-user-or-namespace>
APP_RELEASE=<custom-tag>
CUSTOM_BUILD=false
```

Tên image và registry phải khớp với các biến mà
[`docker-compose.yml`](../deployments/cli/community/docker-compose.yml) sử dụng.
Không nên dùng `latest` cho production; dùng tag bất biến theo commit/release.

#### Hướng B - chạy Compose trực tiếp từ source

Nếu chỉ cần kiểm thử trên máy triển khai, có thể build bằng Compose root:

```bash
docker compose -f docker-compose.yml build
docker compose -f docker-compose.yml up -d
```

Hướng này dùng Dockerfile trong source và phù hợp để xác nhận Keycloak trước khi
publish image. Tuy nhiên cần tự quản lý `.env`, volume, backup, upgrade và
reverse proxy; nó không đi qua lifecycle menu của `setup.sh`.

### 12.5 Lifecycle vận hành

| Nhu cầu | CLI action | Ghi chú |
|---|---:|---|
| Cài lần đầu | `1` | Tạo `plane-app`, tải Compose/env |
| Khởi động | `2` | Start toàn bộ service |
| Dừng | `3` | Dừng service trước khi đổi env |
| Áp dụng env mới | `4` | Restart service |
| Nâng cấp release | `5` | Tải Compose/env mới; phải review env lại |
| Xem logs | `6` | Chọn API, worker, DB, proxy... |
| Backup | `7` | Backup PostgreSQL, MinIO, RabbitMQ, Redis volumes |

Các service chính cần kiểm tra sau deploy:

```text
web, space, admin, live, api, worker, beat-worker, migrator, proxy,
plane-db, plane-redis, plane-mq, plane-minio
```

### 12.6 Checklist deploy Keycloak

- [ ] Docker Engine/Compose đang chạy.
- [ ] DNS `qtda.tanhoangminh.com.vn` trỏ tới máy deploy.
- [ ] TLS/reverse proxy đã hoạt động.
- [ ] `WEB_URL` và `CORS_ALLOWED_ORIGINS` dùng đúng HTTPS domain.
- [ ] `SECRET_KEY` là giá trị ngẫu nhiên, không dùng giá trị mẫu.
- [ ] Đã set đủ `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`,
      `KEYCLOAK_HOST`.
- [ ] Image custom chứa source Keycloak đã được build/publish hoặc đang chạy
      Compose từ source.
- [ ] Redirect URI trên Keycloak khớp tuyệt đối với route callback.
- [ ] Kiểm tra logs `api` nếu callback/token/UserInfo lỗi.
- [ ] Thử cả app callback và space callback.
- [ ] Xác nhận `email_verified=true` trong Keycloak UserInfo.
