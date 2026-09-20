import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from backend.config import DB_PATH

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes SQLite database tables (starts with zero complaints)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table 1: Complaints
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL,
        location TEXT NOT NULL,
        category TEXT NOT NULL,
        priority TEXT NOT NULL,
        status TEXT NOT NULL,
        duration TEXT,
        citizen_name TEXT DEFAULT 'Anonymous Citizen',
        citizen_phone TEXT DEFAULT 'N/A',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # Table 2: Areas (Reference ward directories for location validation)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS areas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ward_number INTEGER UNIQUE NOT NULL,
        name TEXT NOT NULL,
        contact_officer TEXT NOT NULL,
        contact_phone TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # Table 3: Complaint Updates / Audit Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaint_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT NOT NULL,
        action TEXT NOT NULL,
        notes TEXT NOT NULL,
        performed_by TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)

    conn.commit()

    # Seed baseline ward officer directories if empty
    cursor.execute("SELECT COUNT(*) FROM areas")
    if cursor.fetchone()[0] == 0:
        seed_reference_areas(conn)

    conn.close()

def seed_reference_areas(conn: sqlite3.Connection):
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 8 municipal wards and designated zonal officers
    sample_areas = [
        (1, "Ward 1 - North Ridge", "Er. Sunil Mehta (Junior Engineer)", "+91-98765-01001", now_str),
        (2, "Ward 2 - Market Square", "Er. Priya Nair (Assistant Engineer)", "+91-98765-01002", now_str),
        (3, "Ward 3 - Riverside Colony", "Er. Rajesh Gupta (Executive Engineer)", "+91-98765-01003", now_str),
        (4, "Ward 4 - Metro Heights", "Er. Neha Verma (Junior Engineer)", "+91-98765-01004", now_str),
        (5, "Ward 5 - Green Park", "Er. Vikram Singh (Assistant Engineer)", "+91-98765-01005", now_str),
        (6, "Ward 6 - Industrial Sector", "Er. Amit Patil (Junior Engineer)", "+91-98765-01006", now_str),
        (7, "Ward 7 - Old Cantonment", "Er. S. Sengupta (Junior Engineer)", "+91-98765-01007", now_str),
        (8, "Ward 8 - South Extension", "Er. Farooq Khan (Assistant Engineer)", "+91-98765-01008", now_str),
    ]

    cursor.executemany("""
    INSERT INTO areas (ward_number, name, contact_officer, contact_phone, updated_at)
    VALUES (?, ?, ?, ?, ?)
    """, sample_areas)

    conn.commit()

def reset_complaints():
    """Wipes all complaints and complaint updates so the system starts with zero records."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM complaints")
    cursor.execute("DELETE FROM complaint_updates")
    conn.commit()
    conn.close()

def dict_from_row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)

def dicts_from_rows(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]
