# Redis + AsyncIO Learning Guide (Python 3.13)

This project is a hands-on lab. Read code in this order.

## Mental model

```
HTTP request
    │
    ▼
Router  (purchases_router / async_lab)
    │
    ▼
Service (business rules + orchestration)
    │
    ├── AsyncSession  → SQLite (source of truth)
    └── RedisService  → cache / lock / rate-limit / stream / pubsub / zset
                              │
                              ▼
                    Background consumer (asyncio.Task)
                              │
                              ▼
                         Notification rows
```

## Redis patterns in this repo

| Pattern | Where | Why |
|--------|--------|-----|
| Connection pool | `redis_app/redis_service.py` lifespan | Reuse TCP connections across requests |
| Cache-aside | `products/product_service.py` | Fast reads; invalidate on purchase |
| Distributed lock | `purchases/purchase_service.py` | Serialize stock updates across workers |
| Rate limit | `check_rate_limit` | Protect `/purchases` from bursts |
| Streams (simple) | `stream_add` + `PurchaseStreamConsumer` | Producer `XADD`, consumer `XREAD` |
| Pub/Sub + SSE | `GET /purchases/events/live` | Live push without polling |
| Sorted set | `GET /purchases/recent` | Time-ordered recent feed |

**Streams vs Pub/Sub:** Stream messages stay in Redis; a consumer reads them with `XREAD`. Pub/Sub is fire-and-forget — if nobody is listening, the message is gone.

**Not used yet (later step):** consumer groups (`XREADGROUP` / `XACK`).

## AsyncIO patterns in this repo

| Pattern | Endpoint / code | Lesson |
|--------|-----------------|--------|
| `asyncio.gather` | purchase side-effects + `/async-lab/sleep-gather` | Concurrent awaits finish in max(delay), not sum |
| `asyncio.TaskGroup` | user+product load + `/async-lab/taskgroup` | Structured concurrency (preferred in 3.11+) |
| `asyncio.to_thread` | `/async-lab/to-thread` | Offload CPU so the event loop stays free |
| Blocking CPU (anti-pattern) | `/async-lab/blocking-cpu` | Feel how one heavy handler freezes siblings |
| `asyncio.wait_for` | `/async-lab/wait-for` | Timeouts cancel slow work |
| Background `create_task` | stream consumer in lifespan | Long-running work outside request scope |
| SSE + Pub/Sub loop | `/purchases/events/live` | Async generator streaming to the client |

### Golden rules (Python 3.13)

1. Never call blocking I/O or heavy CPU directly inside `async def` — use `await`, or `asyncio.to_thread`.
2. Do not share one `AsyncSession` across concurrent tasks — open separate sessions (see `PurchaseService._load_user_and_product`).
3. Prefer `TaskGroup` over bare `gather` when tasks are a single unit of work that should fail together.
4. Use app `lifespan` for pool/consumer startup; avoid deprecated `@app.on_event`.
5. Keep Redis optional (`RedisService | None`) so the API degrades if Redis is down.

## Try it locally

```bash
# 1) Start Redis (Docker)
cd backend
docker compose up -d redis

# 2) Run API (from repo root, Python 3.13 venv)
uv run --env-file backend/.env uvicorn backend.main:app --reload --port 8000
```

### Happy path

```bash
# create user + product
curl -X POST http://localhost:8000/users/ -H "Content-Type: application/json" -d "{\"name\":\"Ada\",\"email\":\"ada@example.com\"}"
curl -X POST http://localhost:8000/products/ -H "Content-Type: application/json" -d "{\"name\":\"Keyboard\",\"stock\":50,\"price\":100}"

# terminal A — live SSE
curl -N http://localhost:8000/purchases/events/live

# terminal B — buy
curl -X POST http://localhost:8000/purchases/ -H "Content-Type: application/json" -d "{\"user_id\":1,\"product_id\":1,\"amount\":2}"

# inspect async results
curl http://localhost:8000/purchases/recent
curl http://localhost:8000/purchases/stock-movements
curl http://localhost:8000/purchases/notifications/1
```

### Feel concurrency

```bash
curl "http://localhost:8000/async-lab/sleep-gather?delay=1&n=5"
curl http://localhost:8000/async-lab/taskgroup
curl "http://localhost:8000/async-lab/to-thread?n=2000000"
curl "http://localhost:8000/async-lab/blocking-cpu?n=2000000"
```

## New DB objects

- `StockMovement` — append-only inventory ledger (`delta`, `reason`, optional `purchase_id`)
- `Notification` — written by the stream consumer after each purchase (async side effect)

Legacy `POST /buy` and `GET /get_purchases/` were replaced by `/purchases/`.
