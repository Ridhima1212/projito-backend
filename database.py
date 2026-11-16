# backend/database.py
import json
import os
import sqlite3

# Try PostgreSQL first if DATABASE_URL or POSTGRES_URL is provided, else fallback to SQLite
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")

SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.db")

def is_postgres():
    return bool(DATABASE_URL)

def get_db_connection():
    """Returns a database connection (PostgreSQL if DATABASE_URL configured, otherwise SQLite)."""
    if is_postgres():
        # pyrefly: ignore[missing-import]
        import psycopg2  # type: ignore
        # pyrefly: ignore[missing-import]
        import psycopg2.extras  # type: ignore
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """Creates users, contacts, and evaluations tables in PostgreSQL or SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if is_postgres():
        # PostgreSQL syntax
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                subject VARCHAR(255),
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                github_url TEXT NOT NULL,
                repo_name VARCHAR(255),
                description TEXT,
                score INTEGER,
                quality VARCHAR(100),
                result_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
        print("🐘 PostgreSQL Database tables initialized successfully.")
    else:
        # SQLite syntax
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                subject TEXT,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                github_url TEXT NOT NULL,
                repo_name TEXT,
                description TEXT,
                score INTEGER,
                quality TEXT,
                result_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
        print("📁 SQLite Database tables initialized successfully (PostgreSQL URL not provided).")

def save_evaluation(user_id: int, github_url: str, repo_name: str, description: str, score: int, quality: str, result_dict: dict) -> int:
    """Saves an evaluation result to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    result_json = json.dumps(result_dict)

    if is_postgres():
        cursor.execute(
            """
            INSERT INTO evaluations (user_id, github_url, repo_name, description, score, quality, result_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (user_id, github_url, repo_name, description, score, quality, result_json)
        )
        row = cursor.fetchone()
        eval_id = row['id'] if isinstance(row, dict) else (row[0] if row else 0)
    else:
        cursor.execute(
            """
            INSERT INTO evaluations (user_id, github_url, repo_name, description, score, quality, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (user_id, github_url, repo_name, description, score, quality, result_json)
        )
        eval_id = cursor.lastrowid or 0

    conn.commit()
    conn.close()
    return eval_id

def get_user_evaluations(user_id: int) -> list:
    """Retrieves all evaluations for a specific user, sorted from newest to oldest."""
    conn = get_db_connection()
    cursor = conn.cursor()
    placeholder = "%s" if is_postgres() else "?"

    cursor.execute(
        f"""
        SELECT id, user_id, github_url, repo_name, description, score, quality, result_json, created_at
        FROM evaluations
        WHERE user_id = {placeholder}
        ORDER BY id DESC;
        """,
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    evaluations = []
    for row in rows:
        item = dict(row)
        if isinstance(item.get('result_json'), str):
            try:
                item['result'] = json.loads(item['result_json'])
            except Exception:
                item['result'] = None
        else:
            item['result'] = item.get('result_json')
        evaluations.append(item)

    return evaluations

def delete_evaluation(eval_id: int, user_id: int | None = None) -> bool:
    """Deletes an evaluation item, optionally verifying user_id ownership."""
    conn = get_db_connection()
    cursor = conn.cursor()
    placeholder = "%s" if is_postgres() else "?"

    if user_id:
        cursor.execute(
            f"DELETE FROM evaluations WHERE id = {placeholder} AND user_id = {placeholder};",
            (eval_id, user_id)
        )
    else:
        cursor.execute(
            f"DELETE FROM evaluations WHERE id = {placeholder};",
            (eval_id,)
        )

    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

if __name__ == "__main__":
    init_db()
