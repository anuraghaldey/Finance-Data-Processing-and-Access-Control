# Finance Data Processing and Access Control Backend

A production-grade backend for a finance dashboard system with hierarchical RBAC, financial record management, analytics APIs, and custom DSA implementations.

## Tech Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.12+ |
| Framework | Flask + Flask-RESTful |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Auth | JWT (access + refresh tokens) |
| Validation | Marshmallow |
| API Docs | Swagger (Flasgger) |
| Server | Gunicorn + gevent |
| Container | Docker + docker-compose |

## Quick Start

### With Docker (Recommended)

```bash
# Clone and enter the project
git clone https://github.com/anuraghaldey/Finance-Data-Processing-and-Access-Control.git
cd Finance-Data-Processing-and-Access-Control

# Start all services (App + PostgreSQL + Redis)
docker-compose up --build -d

# Run database migrations
docker-compose exec app flask db upgrade

# Seed roles, permissions, and Super Admin
docker-compose exec app python seeds/seed.py

# API is live at http://localhost:5000
# Swagger docs at http://localhost:5000/apidocs
```

### Without Docker (Local Development)

```bash
# Prerequisites: Python 3.12+, PostgreSQL, Redis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database/redis URLs

# Run migrations
flask db upgrade

# Seed database
python seeds/seed.py

# Start development server
python run.py
```

## User Roles

| Role | Level | Capabilities |
|------|-------|-------------|
| Viewer | 1 | View dashboard summaries, own profile |
| Analyst | 2 | + View all records, access analytics/trends |
| Manager | 3 | + Create, update, soft-delete records |
| Admin | 4 | + Manage users, assign roles, hard-delete, audit logs |
| Super Admin | 5 | + Manage admins, cannot be deleted |

## API Endpoints

### Authentication
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| POST | `/api/v1/auth/register` | Public | Register user |
| POST | `/api/v1/auth/login` | Public | Login, get tokens |
| POST | `/api/v1/auth/refresh` | Authenticated | Rotate tokens |
| POST | `/api/v1/auth/logout` | Authenticated | Revoke tokens |

### Users
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/api/v1/users` | Admin+ | List users (paginated) |
| GET | `/api/v1/users/<id>` | Self/Admin+ | Get profile |
| PUT | `/api/v1/users/<id>` | Self/Admin+ | Update profile |
| PATCH | `/api/v1/users/<id>/role` | Admin+ | Change role |
| PATCH | `/api/v1/users/<id>/status` | Admin+ | Activate/deactivate |
| DELETE | `/api/v1/users/<id>` | Admin+ | Soft delete |

### Financial Records
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| POST | `/api/v1/records` | Manager+ | Create record |
| GET | `/api/v1/records` | Analyst+ | List with filters/pagination |
| GET | `/api/v1/records/<id>` | Analyst+ | Get record |
| PUT | `/api/v1/records/<id>` | Manager+ | Update record |
| DELETE | `/api/v1/records/<id>` | Manager+/Admin | Soft/hard delete |
| GET | `/api/v1/records/search?q=sal` | Analyst+ | Trie autocomplete |

### Dashboard Analytics
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/api/v1/dashboard/summary` | Viewer+ | Income, expenses, net balance |
| GET | `/api/v1/dashboard/categories` | Viewer+ | Category breakdown + top-K |
| GET | `/api/v1/dashboard/trends` | Analyst+ | Monthly/weekly trends |
| GET | `/api/v1/dashboard/recent` | Viewer+ | Recent activity |

### System
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/api/v1/health` | Public | Health check |
| GET | `/api/v1/audit-logs` | Admin+ | Audit trail |

## Data Structures & Algorithms

Each DSA solves a specific problem the database alone cannot handle efficiently:

| DSA | Use Case | Why Not Just DB? |
|-----|----------|-----------------|
| **Segment Tree + Lazy Propagation** | Range analytics (sum/min/max/count) | O(log n) incremental updates vs full GROUP BY recomputation |
| **Trie (Prefix Tree)** | Search autocomplete | O(k) in-memory prefix match vs ILIKE index scans + network roundtrips |
| **LRU Cache (DLL + HashMap)** | L1 in-process cache | ~50ns memory read vs ~0.5ms Redis network roundtrip |
| **Sliding Window Counter** | Per-role rate limiting | Role-aware granularity not available in off-the-shelf limiters |
| **Min-Heap (Priority Queue)** | Top-K dashboard queries | O(log K) incremental update vs full aggregation recomputation |

## Security

- JWT access tokens (15 min) + refresh tokens (7 day, rotated)
- bcrypt password hashing (12 rounds)
- Redis token blocklist with DB fallback
- Atomic token refresh lock (prevents race condition)
- Input validation via Marshmallow schemas
- SQL injection prevention via SQLAlchemy ORM
- UUID v4 for all public IDs (prevents enumeration)
- Per-role rate limiting
- Complete audit trail on all write operations
- CORS whitelisting

## Architecture

```
Client -> Rate Limiter -> JWT Auth -> RBAC -> Service Layer -> DB
                                                |
                                          DSA Layer (in-memory)
                                          - Segment Tree
                                          - Trie, Min-Heap
                                          - LRU Cache (L1)
                                                |
                                          Redis (L2 Cache)
                                                |
                                          PostgreSQL
```

### Multi-Worker Consistency

Gunicorn runs 4 workers, each with its own in-memory DSA structures and L1 cache. Writes on any one worker are broadcast to the others via Redis Pub/Sub (`dsa:update` channel) — `app/utils/dsa_sync.py`:

1. On write: the handling worker updates its local DSA, invalidates its local L1 + Redis L2 cache, then publishes a `{action, record}` event.
2. Subscriber threads on the other workers apply the same DSA delta and clear their local L1 cache so subsequent reads recompute from the fresh tree.
3. Safety net: every 30s each worker re-warms its DSA directly from PostgreSQL in case a Pub/Sub message was dropped.

DB is the source of truth; in-memory state is eventually consistent (~1ms propagation).

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/
```

## Live Demo

- **Backend API + Swagger Docs:** https://finance-backend-api.onrender.com/apidocs
- **Frontend Dashboard:** https://anuraghaldey.github.io/Finance-Data-Processing-and-Access-Control/Frontend-For-Testing/

> Note: The Render free tier spins down after 15 minutes of inactivity. The first request may take 30-60 seconds to cold-start.

### How to Test the Live Demo

1. Open the **Frontend Dashboard** link above.
2. Click **Super Admin** quick-login button (credentials: `superadmin@finance.local` / `SuperAdmin@123`).
3. Explore:
   - **Dashboard** — summary cards, category breakdown, monthly trends with visual bars.
   - **Records** — create income/expense records, filter by type/category/date, use search autocomplete.
   - **Users** — manage users, change roles, activate/deactivate accounts.
   - **Audit Logs** — view all system activity filtered by action/resource type.
   - **Health** — check backend + database + Redis status.
4. To test role-based access: register a new user (gets Viewer role by default), login, and notice restricted features.
5. To test the API directly: open the **Swagger Docs** link and use the Authorize button with a JWT token.

## Assumptions

1. Single-tenant system (one org per deployment)
2. Default role for registration is Viewer
3. Financial amounts are always positive; type field determines direction
4. All timestamps stored in UTC
5. Super Admin created via DB seed, not registration API
6. Categories are free-form strings (not fixed enum)

## Trade-offs

| Decision | Rationale |
|----------|-----------|
| PostgreSQL over MongoDB | ACID compliance critical for financial data |
| JWT over sessions | Stateless horizontal scaling |
| Custom DSA over libraries | Demonstrate algorithmic depth; each solves a real problem |
| Monolith over microservices | Simpler for assessment scope; layered architecture allows future split |
| Soft delete by default | Prevents accidental data loss; hard delete available to Admins |
