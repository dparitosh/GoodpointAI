import os

import psycopg
from dotenv import load_dotenv


def main() -> None:
    # Load backend env (same behavior as runtime).
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is not set")

    conn = psycopg.connect(database_url)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS public.soda_test_table (id int primary key, name text not null)"
        )
        conn.execute(
            "INSERT INTO public.soda_test_table (id, name) VALUES (1, 'a') ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            "INSERT INTO public.soda_test_table (id, name) VALUES (2, 'b') ON CONFLICT (id) DO NOTHING"
        )
        conn.commit()
    finally:
        conn.close()

    print("OK created/seeded public.soda_test_table")


if __name__ == "__main__":
    main()
