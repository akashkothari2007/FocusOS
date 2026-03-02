import os
from psycopg import connect
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://focusos:focusos@localhost:5432/focusos")

def get_conn():
    return connect(DATABASE_URL, row_factory=dict_row)
