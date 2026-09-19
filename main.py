import os
import socket
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import asyncpg
import redis.asyncio as redis

#Get ID container from hostname
NODE_ID = os.getenv("NODE_ID", "unknown_node")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/appdb")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

#Initializing app
app = FastAPI(title="Scalable Web App")

db_pool: asyncpg.Pool = None
redis_client: redis.Redis = None

#Connection to REDIS
@app.on_event("startup")
async def startup():
    global db_pool, redis_client
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    
    #Visitor Tables
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                id SERIAL PRIMARY KEY,
                node_id TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

@app.on_event("shutdown")
async def shutdown():
    await db_pool.close()
    await redis_client.close()

#WEb APP (main board)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # 1.Visit = Data into PostgreSQL
    async with db_pool.acquire() as conn:
        await conn.execute("INSERT INTO visits (node_id) VALUES ($1)", NODE_ID)
        visit_count = await conn.fetchval("SELECT COUNT(*) FROM visits")
    
    # 2.Visitor counter for this Node (REDIS)
    node_visits = await redis_client.incr(f"node:{NODE_ID}:visits")
    
    # 3. HTML 
    return f"""
    <html>
    <head><title>Node {NODE_ID}</title></head>
    <body style="font-family: Arial, sans-serif; padding: 40px; background: #f4f4f9; color: #333;">
        <h1>Hellow, welcome to the NODE <b>{NODE_ID}</b></h1>
        <p>This answer is correct.</p>
        <hr>
        <h3>Statistics:</h3>
        <ul>
            <li>All visiting sessions (sum of all NODES): <b>{visit_count}</b></li>
            <li>Visiting sessions for this Node (REDIS): <b>{node_visits}</b></li>
        </ul>
        <hr>
        <h3>API endpoints for cheks:</h3>
        <ul>
            <li><a href="/api/node">/api/node</a> — Node info (JSON)</li>
            <li><a href="/api/visits">/api/visits</a> — visitor sessin history PostgreSQL</li>
            <li><a href="/api/session?user=student">/api/session?user=student</a> — tests in Redis</li>
        </ul>
    </body>
    </html>
    """

#Node info (API)
@app.get("/api/node")
async def get_node():
    return {
        "node_id": NODE_ID,
        "status": "running",
        "message": "This response is served by a specific backend node."
    }

#Postgres visits (API)
@app.get("/api/visits")
async def get_visits():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM visits ORDER BY id DESC LIMIT 20")
    return [{"id": r["id"], "node_id": r["node_id"], "created_at": str(r["created_at"])} for r in rows]

#REDIS's session (API)
@app.get("/api/session")
async def get_session(request: Request):
    session_id = request.query_params.get("user", "anonymous")
    
    #Get/create session REDIS
    session_data = await redis_client.hgetall(f"session:{session_id}")
    
    if not session_data:
        await redis_client.hset(f"session:{session_id}", mapping={
            "served_by_node": NODE_ID,
            "visits": "1"
        })
        session_data = await redis_client.hgetall(f"session:{session_id}")
    else:
        await redis_client.hincrby(f"session:{session_id}", "visits")
        session_data = await redis_client.hgetall(f"session:{session_id}")
    
    #Time session - 1h
    await redis_client.expire(f"session:{session_id}", 3600)
    
    return {
        "session_id": session_id,
        "data": session_data,
        "current_node": NODE_ID
    }