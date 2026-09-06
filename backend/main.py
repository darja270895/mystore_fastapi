import os
from pathlib import Path
import asyncio
import time

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

import backend.models as models
from backend.database import engine, get_db
from backend.redis_app.redis_service import create_lifespan
from backend.users.user_router import router as user_router
from backend.products.products_router import router as product_router

# cmd //c "tasklist | findstr /I python"

# Create the application instance

from pathlib import Path

app = FastAPI(lifespan=create_lifespan)
app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],

)
#подключение статических страниц - вынести отдельно
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"

app.mount("/frontend", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(user_router) #подключение роутов юзера
app.include_router(product_router) #роуты продукта

print(f"BASE_DIR: {BASE_DIR}")
print(f" STATIC_DIR: {STATIC_DIR}")
print(f" INDEX_FILE: {INDEX_FILE}")
print(f" File exists: {INDEX_FILE.exists()}")



# import logging
# logger = logging.getLogger("uvicorn.error")


#syncronous method create_all
# models.Base.metadata.create_all(bind=engine)

# async Hook into FastAPI startup lifecycle to safely create database tables asynchronously
@app.router.on_startup.append
async def init_tables():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

async def slow_cpu_task() -> int:
    s=0
    for i in range(1_000_000):
        s+=i
    return s

@app.get("/")
async def read_root():
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE, media_type="text/html")
    return {"message": "Index file not found"}

@app.get("/get_purchases/")
async def get_purchases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Purchase))
    return result.scalars().all()


# @app.get("/async-test/{request_id}")
# async def async_test(request_id: int, delay: int = 5):
#     start_time = time.time()
#     print(f"🚀 Start Request {request_id} at {time.strftime('%X')}")
#
#     # Simulate non-blocking async wait
#     await asyncio.sleep(delay)
#
#     duration = time.time() - start_time
#     print(f"✅ Finish Request {request_id} after {duration:.2f}s")
#     return {"request_id": request_id, "duration_seconds": duration}

@app.post("/buy")
async def buy(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    try:
        user_id=int(body['user_id'])
        product_id=int(body['product_id'])
        amount=int(body.get('amount', 10))
    except Exception:
        raise HTTPException(400, 'invalid payload')
    new_purchase = models.Purchase(
        user_id=user_id,
        product_id=product_id,
        amount=amount
    )
    db.add(new_purchase)
    await db.commit()
    await db.refresh(new_purchase)
    return new_purchase

# THIS GUARD IS CRITICAL ON WINDOWS FOR MULTI-WORKERS
if __name__ == "__main__":
    import uvicorn
    # Make sure to pass the application as an import string ("main:app")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=4)