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
    max_idle=300,        # close idle connections after 5 min
    reconnect_timeout=60, # keep trying to reconnect for 60s
    kwargs={"row_factory": dict_row},
)

@contextmanager
def get_conn():
    """Get a connection from the pool. Auto-commits on clean exit, rolls back on error."""
    with pool.connection() as conn:
        yield conn
        conn.commit()
