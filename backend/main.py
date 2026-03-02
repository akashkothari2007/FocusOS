from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db import get_conn
from routers import todo_router, session_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default port
    allow_methods=["*"],
    allow_headers=["*"],
)

#-----Health Checks-----

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/db")
def db_check():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS one;")
            row = cur.fetchone()
    return {"db": "connected", "result": row}

#-----Routers-----

app.include_router(todo_router.router)
app.include_router(session_router.router)
