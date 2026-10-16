+---alembic

|   |   env.py
|   |   README
|   |   script.py.mako
|   |
|   ---versions
|           9819a1639e00_change_product_table_id_type.py
|           de248fa018c5_initial.py
|
+---products
|   |   products_router.py (отвечает за HTTP)
|   |   product_cache.py
|   |   product_db_interface.py (отвечает за работу с БД)
|   |   product_schemas.py (отвечают за форма входных и выходных данных)
|   |   product_service.py (бизнес логика, изолирована от внешних систем)
|   |   README
|   |   __init__.py
|   |
|   ---__pycache__
|           products_router.cpython-313.pyc
|           product_db_interface.cpython-313.pyc
|           product_schemas.cpython-313.pyc
|           product_service.cpython-313.pyc
|           __init__.cpython-313.pyc
|
+---purchases
|   |   purchases_router.py
|   |   purchase_service.py
|   |   purchase_db_interface.py
|   |   purchase_schemas.py
|   |   __init__.py
|
+---async_lab
|   |   router.py          # AsyncIO playground endpoints
|   |   __init__.py
|
+---redis_app
|   |   redis_service.py   # pool, cache, lock, rate-limit, streams, pubsub, zset
|   |   stream_consumer.py # background asyncio.Task consumer
|   |   events.py          # PurchaseEvent payload
|   |   keys.py            # Redis key helpers
|   |   __init__.py
|
REDIS_ASYNCIO_LEARNING.md  # study guide

+---static
|       index.html
|       styles.css
|       __init__.py
|
+---tests
|       test_concurrency_unittest.py
|       test_redis_connection_pool_integration.py
|       __init__.py
|
+---untitled
|       mystore_fastapi.iml
|
+---users
|   |   db_interface.py
|   |   README
|   |   schemas.py
|   |   service.py
|   |   user_router.py
|   |   __init__.py
|   |

├── init.py
├── .env

├──  alembic.ini

├──  config.py

├── database.py //connection to SQAlchemy DB

├── main.py // main executable file

├── models.py // ORM models using SQAlhemy

* Разделение запроса на 4 слоя

HTTP
│
▼
Router
│
▼
Service
│
▼
Repository
│
▼
AsyncSession → SQLite

Слой	Ответственность
router.py	HTTP, status codes, request/response
schemas.py	Pydantic-модели
service.py	бизнес-логика
repository.py	SQLAlchemy / БД
models.py	структура таблиц
database.py	engine, session


|  |  |  |
| - | - | - |

```
                  ┌──────────────┐
                  │   FastAPI    │
                  └──────┬───────┘
                         │
              ┌──────────┴──────────┐
              │                     │
          PostgreSQL/SQLite       Redis
              │                     │
              │              ┌──────┴──────┐
              │              │             │
            data           cache       rate limit
              │
              │
           purchase
```
