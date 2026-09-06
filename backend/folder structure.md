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
|       __init__.py
|
+---redis_app
|   |   redis_service.py
|   |   __init__.py
|   |
|   ---__pycache__
|           redis_service.cpython-313.pyc
|           __init__.cpython-313.pyc
|
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
