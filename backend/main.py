import logging
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from db import get_conn, pool
from routers import todo_router, session_router, job_router, doc_router, profile_router, habit_router, email_router, routine_router, plan_router
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scheduler import run_email_scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    stream=sys.stdout,
    force=True,
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default port
    allow_methods=["*"],
    allow_headers=["*"],
)
#-----Load Environment Variables-----
from dotenv import load_dotenv
load_dotenv()

#-----Scheduler-----
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    scheduler.add_job(run_email_scan, "cron", hour=8, timezone="America/New_York")
    scheduler.add_job(run_email_scan, "cron", hour=18, timezone="America/New_York")
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_pool():
    pool.close()

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



#-----Rate Limiting-----
import os
import time
from collections import defaultdict

# Track failed auth attempts per IP: {ip: [(timestamp, ...), ...]}
_fail_log: dict[str, list[float]] = defaultdict(list)
# Blocked IPs: {ip: unblock_timestamp}
_blocked_ips: dict[str, float] = {}

MAX_FAILURES = 5        # max failed attempts before block
WINDOW_SECONDS = 60     # rolling window to count failures
BLOCK_SECONDS = 300     # 5-minute block after too many failures

def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _cleanup_old_entries(ip: str, now: float):
    """Remove failure timestamps outside the rolling window."""
    cutoff = now - WINDOW_SECONDS
    _fail_log[ip] = [t for t in _fail_log[ip] if t > cutoff]
    if not _fail_log[ip]:
        del _fail_log[ip]

#-----API Key Middleware-----
@app.middleware("http")
async def api_key_middleware(request: Request, call_next):

    EXEMPT_PATHS = ["/auth/login", "/auth/callback", "/health", "/db"]

    if request.url.path in EXEMPT_PATHS:
        return await call_next(request)

    ip = _client_ip(request)
    now = time.time()

    # Check if IP is currently blocked
    if ip in _blocked_ips:
        if now < _blocked_ips[ip]:
            retry_after = int(_blocked_ips[ip] - now)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many failed attempts. Try again later."},
                headers={"Retry-After": str(retry_after)},
            )
        else:
            # Block expired — clear it
            del _blocked_ips[ip]
            _fail_log.pop(ip, None)

    key = request.headers.get("X-API-Key")
    if key != os.environ.get("FOCUSOS_API_KEY"):
        # Record the failure
        _fail_log[ip].append(now)
        _cleanup_old_entries(ip, now)

        if len(_fail_log.get(ip, [])) >= MAX_FAILURES:
            _blocked_ips[ip] = now + BLOCK_SECONDS
            logging.warning("Blocked IP %s for %ds after %d failed auth attempts", ip, BLOCK_SECONDS, MAX_FAILURES)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many failed attempts. Try again later."},
                headers={"Retry-After": str(BLOCK_SECONDS)},
            )

        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    return await call_next(request)

#-----Routers-----

app.include_router(todo_router.router)
app.include_router(session_router.router)
app.include_router(job_router.router)
app.include_router(doc_router.router)
app.include_router(profile_router.router)
app.include_router(habit_router.router)
app.include_router(email_router.router)
app.include_router(routine_router.router)
app.include_router(plan_router.router)

 
