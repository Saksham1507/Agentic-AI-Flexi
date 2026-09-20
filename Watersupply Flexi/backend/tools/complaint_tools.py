import sqlite3
import random
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.database import get_db_connection, dict_from_row, dicts_from_rows

def generate_ticket_id() -> str:
    """Generates a unique complaint ticket ID like TKT-2026-7842."""
    year = datetime.now().year
    suffix = random.randint(1000, 9999)
    return f"TKT-{year}-{suffix}"

def check_area_status(location: str) -> Dict[str, Any]:
    """
    Checks the municipal jurisdiction, ward identity, and designated zonal
    water officer for the complaint location.

    Parameters:
        location (str): Name or ward identifier (e.g. 'Ward 5', 'Ward 2', 'Green Park').

    Returns:
        dict: Jurisdiction confirmation and assigned zonal officer details.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    import re
    digit_match = re.search(r'\b(?:ward\s*)?(\d+)\b', location, re.IGNORECASE)
    
    if digit_match:
        ward_num = int(digit_match.group(1))
        cursor.execute("SELECT * FROM areas WHERE ward_number = ?", (ward_num,))
        row = cursor.fetchone()
    else:
        cursor.execute("SELECT * FROM areas WHERE name LIKE ?", (f"%{location}%",))
        row = cursor.fetchone()

    conn.close()

    if row:
        area_data = dict_from_row(row)
        return {
            "valid_jurisdiction": True,
            "ward_number": area_data["ward_number"],
            "area_name": area_data["name"],
            "contact_officer": area_data["contact_officer"],
            "contact_phone": area_data["contact_phone"],
            "details": f"{area_data['name']} is within municipal jurisdiction. Designated Zonal Officer: {area_data['contact_officer']}."
        }
    else:
        return {
            "valid_jurisdiction": True,
            "location": location,
            "details": f"Location '{location}' accepted under Central Municipal Jurisdiction. Assigned to General Zonal Officer."
        }

def search_existing_complaints(location: str, category: Optional[str] = None) -> Dict[str, Any]:
    """
    Searches the database for existing active complaints in the same location
    to identify recurring issues, duplicate submissions, or area-wide outages.

    Parameters:
        location (str): The ward or locality (e.g. 'Ward 5').
        category (str, optional): Complaint category (e.g. 'No Water Supply').

    Returns:
        dict: Count and summary of existing active complaints.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM complaints WHERE location LIKE ? AND status != 'RESOLVED'"
    params = [f"%{location}%"]

    if category:
        query += " AND category LIKE ?"
        params.append(f"%{category}%")

    query += " ORDER BY id DESC LIMIT 5"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    complaints_list = dicts_from_rows(rows)
    return {
        "location": location,
        "category_filter": category,
        "existing_count": len(complaints_list),
        "is_recurring_issue": len(complaints_list) >= 2,
        "existing_complaints": [
            {
                "ticket_id": c["ticket_id"],
                "category": c["category"],
                "priority": c["priority"],
                "status": c["status"],
                "duration": c["duration"],
                "created_at": c["created_at"],
                "description": c["description"]
            }
            for c in complaints_list
        ]
    }

def create_complaint(
    description: str,
    location: str,
    category: str,
    priority: str = "MEDIUM",
    duration: Optional[str] = "Unknown",
    citizen_name: str = "Anonymous Citizen",
    citizen_phone: str = "N/A"
) -> Dict[str, Any]:
    """
    Creates a new formal water supply complaint ticket in the municipal database.

    Parameters:
        description (str): Full text of the problem.
        location (str): Standardized location/ward (e.g. 'Ward 5').
        category (str): Category (e.g. 'No Water Supply', 'Contaminated Water', 'Low Pressure', 'Pipeline Leakage').
        priority (str): 'LOW', 'MEDIUM', or 'HIGH'.
        duration (str, optional): How long the issue has persisted.
        citizen_name (str, optional): Citizen name if available.
        citizen_phone (str, optional): Citizen phone number.

    Returns:
        dict: The newly created ticket details with unique ticket_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    while True:
        ticket_id = generate_ticket_id()
        cursor.execute("SELECT id FROM complaints WHERE ticket_id = ?", (ticket_id,))
        if not cursor.fetchone():
            break

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    priority_clean = priority.upper() if priority.upper() in ("LOW", "MEDIUM", "HIGH") else "MEDIUM"
    status = "REGISTERED"

    cursor.execute("""
    INSERT INTO complaints (
        ticket_id, description, location, category, priority,
        status, duration, citizen_name, citizen_phone, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticket_id, description, location, category, priority_clean,
        status, duration or "Unknown", citizen_name, citizen_phone, now_str, now_str
    ))

    cursor.execute("""
    INSERT INTO complaint_updates (ticket_id, action, notes, performed_by, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """, (
        ticket_id,
        "TICKET_CREATED",
        f"Complaint registered via AI Agent for {location} [{category}] with {priority_clean} priority.",
        "AI Agent",
        now_str
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "ticket_id": ticket_id,
        "description": description,
        "location": location,
        "category": category,
        "priority": priority_clean,
        "status": status,
        "duration": duration,
        "created_at": now_str,
        "message": f"Complaint successfully registered with Ticket ID {ticket_id}."
    }

def update_complaint(ticket_id: str, status: str, notes: str, performed_by: str = "AI Agent") -> Dict[str, Any]:
    """
    Updates the status and records an audit progress update for an existing complaint.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints WHERE ticket_id = ?", (ticket_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"success": False, "message": f"Complaint with Ticket ID '{ticket_id}' not found."}

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    UPDATE complaints SET status = ?, updated_at = ? WHERE ticket_id = ?
    """, (status.upper(), now_str, ticket_id))

    cursor.execute("""
    INSERT INTO complaint_updates (ticket_id, action, notes, performed_by, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """, (ticket_id, "STATUS_UPDATED", notes, performed_by, now_str))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "ticket_id": ticket_id,
        "new_status": status.upper(),
        "notes": notes,
        "updated_at": now_str,
        "message": f"Ticket {ticket_id} updated to {status.upper()}."
    }

def escalate_complaint(ticket_id: str, reason: str, target_department: str = "Water Emergency Response Team") -> Dict[str, Any]:
    """
    Escalates an urgent or high-priority complaint directly to the water response team.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints WHERE ticket_id = ?", (ticket_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"success": False, "message": f"Complaint with Ticket ID '{ticket_id}' not found."}

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    UPDATE complaints SET priority = 'HIGH', status = 'ESCALATED', updated_at = ? WHERE ticket_id = ?
    """, (now_str, ticket_id))

    note_text = f"ESCALATED to {target_department}. Reason: {reason}"
    cursor.execute("""
    INSERT INTO complaint_updates (ticket_id, action, notes, performed_by, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """, (ticket_id, "ESCALATED", note_text, "AI Agent (Auto-Escalation Engine)", now_str))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "ticket_id": ticket_id,
        "status": "ESCALATED",
        "priority": "HIGH",
        "reason": reason,
        "target_department": target_department,
        "escalated_at": now_str,
        "message": f"Ticket {ticket_id} has been escalated to {target_department}."
    }
