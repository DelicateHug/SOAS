# SOC on a Stick - Claude Code Project Guide

## Project Overview
SOC on a Stick (SOAS) is a full-stack Security Operations Center platform with visual automation building, incident management, case management, wiki documentation, and real-time collaboration.

## Tech Stack
- **Frontend**: React 19 + TypeScript + Vite 6 + Zustand 5 + React Flow (@xyflow/react 12) + TanStack React Query 5 + Tailwind CSS 4
- **Backend**: FastAPI + Python 3.12+ + SQLAlchemy 2 (async) + Alembic + PostgreSQL 16
- **Workers**: Celery 5.4 + Redis 7
- **Auth**: JWT (RS256) + WebAuthn + TOTP MFA + bcrypt passwords
- **Compiler**: VisualPython2 - custom graph-to-Python compiler

## Directory Structure
```
├── backend/                    # FastAPI API server
│   ├── alembic/versions/       # DB migrations (001-029, sequential numeric prefix)
│   └── src/soas_backend/
│       ├── api/v1/             # Route handlers (36 files)
│       ├── api/deps.py         # FastAPI dependencies (auth, DB, Redis)
│       ├── auth/               # JWT, password, TOTP, WebAuthn
│       ├── models/             # SQLAlchemy 2 ORM models (26 files)
│       ├── services/           # Business logic layer (30+ files)
│       ├── middleware/          # Monitoring middleware
│       ├── config.py           # pydantic_settings config
│       ├── database.py         # async engine + session factory
│       ├── crypto.py           # Fernet encryption for user secrets
│       ├── seed.py             # Default data seeding (wiki, vars, automations)
│       └── main.py             # App factory + lifespan
├── frontend/                   # React SPA
│   └── src/
│       ├── components/
│       │   ├── graph-editor/   # Visual automation editor
│       │   │   ├── stores/     # graphEditorStore.ts (Zustand)
│       │   │   ├── hooks/      # useCollaboration, useGraphSave, useNodeCatalog, etc.
│       │   │   ├── nodes/      # CustomNodeComponent.tsx
│       │   │   ├── edges/      # FlowEdge.tsx, DataEdge.tsx
│       │   │   ├── types/      # graph.ts (VP2 types)
│       │   │   └── utils/      # graphConversion.ts (format converters)
│       │   ├── layout/         # DashboardLayout.tsx
│       │   └── ui/             # Shared UI components
│       ├── stores/             # authStore.ts (Zustand)
│       ├── pages/              # Route pages (lazy-loaded)
│       ├── lib/                # api.ts (ApiClient), queryClient.ts, utils.ts
│       └── types/              # api.ts (all API response types)
├── workers/                    # Celery workers
│   └── src/soas_workers/
│       ├── tasks/              # compile_graph, run_automation, test_run_graph, etc.
│       ├── celery_app.py       # Celery config
│       └── db.py               # Sync DB access (psycopg2)
├── shared/                     # Shared Pydantic schemas (backend + workers)
│   └── src/soas_shared/schemas/
├── VisualPython2/              # Graph compiler (current)
│   └── src/visualpython2/
│       ├── compiler/           # code_generator.py + emitters/
│       ├── graph/              # graph_model.py
│       ├── schema/             # node_catalog.py
│       └── serialization/      # graph_serializer.py
├── docker-compose.yml          # 6 services: postgres, redis, backend, worker, worker-beat, frontend
├── docker-compose.dev.yml      # Dev overrides (hot reload)
├── start.ps1                   # Bootstrap script (-Dev, -Build, -Down, -Rebuild, -Reset)
├── secrets/                    # JWT PEM keys (auto-generated)
└── .env / .env.example         # Environment config
```

## Architecture Patterns

### Backend: Route → Service → Model

**Routes** (`api/v1/*.py`):
```python
router = APIRouter(prefix="/things", tags=["things"])

@router.get("", response_model=PaginatedResponse[ThingItem])
async def list_things(
    page: int = Query(1, ge=1),
    _: dict = Depends(require_permission("thing", "read")),  # RBAC (JWT-only, no DB)
    db: AsyncSession = Depends(get_db),                       # auto-commit on success
):
    svc = ThingService(db)  # services instantiated inline, NOT as dependencies
    items, total = await svc.list(page=page)
    return PaginatedResponse(data=[...], meta=PaginationMeta(...))
```

**Services** (`services/*.py`):
```python
class ThingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, ...) -> Thing:
        obj = Thing(...)
        self.db.add(obj)
        await self.db.flush()  # ALWAYS flush(), NEVER commit() - get_db() handles commit
        return obj
```

**Models** (`models/*.py`): SQLAlchemy 2 `Mapped[]` + `mapped_column()`. All PKs are UUIDs. Timestamps use `timezone=True` + `server_default=func.now()`.

### Frontend: API Client → React Query → Zustand

**API calls**: `api.get/post/patch/put/delete()` via singleton `ApiClient` in `lib/api.ts`. Auto-refreshes JWT on 401.

**Server state**: TanStack React Query `useQuery` / `useMutation` with invalidation on success.

**Client state**: Two Zustand stores - `authStore` (global auth) and `graphEditorStore` (graph editor).

**Pages**: Lazy-loaded via `React.lazy()`, wrapped in `ProtectedRoute`, nested under `DashboardLayout`.

**Styling**: Tailwind CSS v4 (CSS-configured, no JS config file). CSS custom properties on `:root` for theming. `cn()` helper for conditional classes.

### Graph Editor Data Flow
1. Backend stores `graph_data` as JSONB in `automations` table
2. Frontend loads → `fromBackendFormat()` → `VP2GraphData` → `vp2ToReactFlow()` → React Flow nodes/edges
3. Frontend saves → `reactFlowToVP2()` → `toBackendFormat()` → PUT to backend
4. Compile: backend enqueues Celery task → `GraphSerializer.deserialize()` → `CodeGenerator.generate()` → `.py` file
5. Execute: worker prepends bridge code (SOAS vars, secrets, incident vars) → `subprocess.Popen` → streams output via Redis pubsub → WebSocket to frontend

### Auth & RBAC
- **`get_current_user`**: DB query, returns full `User` ORM object
- **`require_permission("resource", "action")`**: JWT-only check (no DB), returns payload dict. Admin role bypasses all.
- **`require_role("admin")`**: JWT-only role check
- Routes use `_: dict = Depends(require_permission(...))` when return value is not needed
- Permissions format: `"resource:action"` strings embedded in JWT

### WebSocket Endpoints (registered directly on app, NOT via v1_router)
- `/api/v1/ws/executions/{execution_id}` - execution output streaming
- `/api/v1/ws/collaboration/{automation_id}` - real-time co-editing
- `/api/v1/ws/monitoring` - system metrics
- Auth via `?token=` query param. DB access uses `async_session()` directly (not `get_db()`).

### Collaboration
- Redis pubsub for broadcasting ops between WebSocket connections
- `_isRemoteUpdate` flag in store prevents re-broadcast loops
- Edit lock: Redis key `collab:{id}:lock` + DB columns `locked_by`/`locked_at`
- Presence: Redis hash `collab:{id}:presence`

## Key Conventions

### Database
- Session factory is `async_session` (not `async_session_factory`) from `soas_backend.database`
- Migrations: `backend/alembic/versions/NNN_description.py`, linear chain, `revision = "NNN"`, `down_revision = "NNN-1"`
- Workers use sync `psycopg2` (not async) for DB access

### Frontend
- Path alias: `@/` → `frontend/src/`
- Zustand selectors: `useStore((s) => s.field)` for fine-grained subscriptions
- Tab state stored in URL via `useSearchParams()`
- No component library - raw HTML + Tailwind classes
- Graph editor uses hardcoded dark colors, not CSS vars

### Shared Schemas
- Pydantic v2 schemas in `shared/src/soas_shared/schemas/`
- Used by both backend (API responses) and workers (DB queries)
- Inline schemas (like `GraphSaveRequest`) defined in route files when simple enough

### Seeding
- `backend/src/soas_backend/seed.py` runs idempotently on startup via `seed_defaults()`
- Uses `app_settings.seed_version` as idempotency marker
- Defers if no users exist (needs `created_by` FK)
- Non-fatal: app starts even if seeding fails

## How to Add Things

### New API Endpoint
1. Create `backend/src/soas_backend/api/v1/my_thing.py` with `router = APIRouter(prefix="/my-things")`
2. Create service `backend/src/soas_backend/services/my_thing_service.py`
3. Create model `backend/src/soas_backend/models/my_thing.py` (import in `models/__init__.py`)
4. Create schema `shared/src/soas_shared/schemas/my_thing.py`
5. Add migration `backend/alembic/versions/NNN_description.py`
6. Register router in `backend/src/soas_backend/api/v1/router.py`
7. Add frontend types in `frontend/src/types/api.ts`

### New Graph Node Type
1. Add to `VisualPython2/src/visualpython2/schema/node_catalog.py`
2. Add emitter in appropriate `VisualPython2/src/visualpython2/compiler/emitters/*.py`
3. Register emitter in `code_generator.py` if new emitter file
4. Add wiki page entry in `seed.py` with `linked_node_type`

### New Migration
- Next number: check highest in `backend/alembic/versions/` and increment
- Pattern: `revision = "030"`, `down_revision = "029"`
- Run via: `alembic upgrade head` (happens automatically on backend container start)

## Docker Services
| Service | Port | Purpose |
|---------|------|---------|
| postgres | 5432 | PostgreSQL 16 database |
| redis | 6379 | Celery broker + pubsub + cache |
| backend | 8000 | FastAPI API server |
| worker | - | Celery worker (queues: celery, compile, execute) |
| worker-beat | - | Celery Beat scheduler |
| frontend | 3000 (prod) / 5173 (dev) | React SPA |

## Startup
```powershell
.\start.ps1            # Production-like start
.\start.ps1 -Dev       # Dev mode with hot reload
.\start.ps1 -Build     # Force rebuild all images
.\start.ps1 -Down      # Stop everything
.\start.ps1 -Rebuild   # Down + rebuild + start
.\start.ps1 -Reset     # Factory reset (destroy volumes, rebuild, create admin/adminadmin user)
```

## Important Gotchas
- WebSocket routers are on `app` directly, NOT under `v1_router`
- Services `flush()` but never `commit()` - the `get_db()` dependency handles commits
- `require_permission()` returns a dict (JWT payload), not a User object
- Graph editor has 3 data formats: Backend JSON, VP2GraphData, React Flow nodes/edges
- Tailwind v4 uses CSS config (`index.css`), not `tailwind.config.js`
- The `VisualPython` (v1) directory is legacy fallback; `VisualPython2` is current
