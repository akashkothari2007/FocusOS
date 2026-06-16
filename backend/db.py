import os
import logging
from contextlib import contextmanager
from psycopg import connect
from psycopg.rows import dict_row

log = logging.getLogger("db")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://focusos:focusos@localhost:5432/focusos")


@contextmanager
def get_conn():
    """Fresh connection each call — no local pool.
    Supabase port 6543 is already pgbouncer; double-pooling causes PoolTimeout.

    prepare_threshold=None disables server-side prepared statements, which is
    REQUIRED for Supavisor transaction mode — transactions can land on
    different backends, so a statement prepared in one is missing in the next.
    """
    conn = connect(
        DATABASE_URL,
        row_factory=dict_row,
        prepare_threshold=None,
        connect_timeout=5,
    )
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
