import os
import logging
from contextlib import contextmanager
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

log = logging.getLogger("db")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://focusos:focusos@localhost:5432/focusos")

pool = ConnectionPool(
    DATABASE_URL,
    min_size=2,
    max_size=10,
    max_idle=60,          # close idle connections after 1 min
    max_lifetime=300,     # recycle every connection after 5 min — prevents cloud infra from killing them silently
    reconnect_timeout=5,  # fail fast on broken connections instead of blocking the pool
    timeout=10,           # wait max 10s for a connection (fail fast, don't queue for 30s)
    check=ConnectionPool.check_connection,  # ping before handing out — detects dead connections
    kwargs={"row_factory": dict_row},
)

@contextmanager
def get_conn():
    """Get a connection from the pool. Auto-commits on clean exit, rolls back on error."""
    with pool.connection() as conn:
        yield conn
        conn.commit()
