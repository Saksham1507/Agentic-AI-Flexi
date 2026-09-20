import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.config import BASE_DIR, GEMINI_MODEL, has_gemini_key
from backend.database import init_db, get_db_connection, dict_from_row, dicts_from_rows
from backend.agent.agent_core import WaterCareAgent, get_latest_workflow

# Initialize database on startup (starts with zero complaints)
init_db()

# Initialize AI Agent
agent = WaterCareAgent()

app = FastAPI(
    title="WaterCare AI - Complaint Management Agent",
    description="AI-Based Water Supply Complaint Management Agent",
    version="2.0.0"
)

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []

# API Endpoints
@app.get("/api/health")
def get_health():
    return {
        "status": "online",
        "service": "WaterCare AI Agent",
        "gemini_api_configured": has_gemini_key(),
        "model": GEMINI_MODEL,
        "mode": "Gemini Live LLM" if has_gemini_key() else "Agentic Engine (Local)"
    }

@app.get("/api/stats")
def get_stats():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM complaints")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM complaints WHERE status != 'RESOLVED'")
    active = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM complaints WHERE status = 'ESCALATED'")
    escalated = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM complaints WHERE status = 'RESOLVED'")
    resolved = c.fetchone()[0]

    conn.close()

    return {
        "total_complaints": total,
        "active_complaints": active,
        "escalated_complaints": escalated,
        "resolved_complaints": resolved
    }

@app.post("/api/chat")
def chat_with_agent(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Complaint message cannot be empty.")
    
    result = agent.process_complaint(
        user_message=req.message.strip(),
        conversation_history=req.history
    )
    return result

@app.get("/api/agent/latest-workflow")
def get_agent_latest_workflow():
    """Returns the most recent multi-step reasoning workflow for the Admin modal."""
    return get_latest_workflow()

@app.get("/api/complaints/active")
def list_active_complaints():
    """Returns only active complaints (excluding resolved ones)."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM complaints WHERE status != 'RESOLVED' ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return {"complaints": dicts_from_rows(rows)}

@app.get("/api/complaints")
def list_complaints(
    ward: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None)
):
    conn = get_db_connection()
    c = conn.cursor()

    query = "SELECT * FROM complaints WHERE 1=1"
    params = []

    if ward:
        query += " AND location LIKE ?"
        params.append(f"%{ward}%")
    if status:
        query += " AND status = ?"
        params.append(status.upper())
    if priority:
        query += " AND priority = ?"
        params.append(priority.upper())

    query += " ORDER BY id DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    return {"complaints": dicts_from_rows(rows)}

@app.get("/api/complaints/{ticket_id}")
def get_complaint(ticket_id: str):
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM complaints WHERE ticket_id = ?", (ticket_id,))
    comp_row = c.fetchone()

    if not comp_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint ticket not found.")

    c.execute("SELECT * FROM complaint_updates WHERE ticket_id = ? ORDER BY id ASC", (ticket_id,))
    updates_rows = c.fetchall()
    conn.close()

    return {
        "complaint": dict_from_row(comp_row),
        "updates": dicts_from_rows(updates_rows)
    }

@app.get("/api/complaints/{ticket_id}/status-check")
def check_complaint_status(ticket_id: str):
    """Used by Citizen Portal to detect when their ticket is resolved."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT ticket_id, status, priority, updated_at FROM complaints WHERE ticket_id = ?", (ticket_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return {"exists": False}

    return {
        "exists": True,
        "ticket_id": row["ticket_id"],
        "status": row["status"],
        "is_resolved": row["status"] == "RESOLVED",
        "updated_at": row["updated_at"]
    }

@app.post("/api/complaints/{ticket_id}/resolve")
def resolve_complaint(ticket_id: str):
    """Admin action: resolves and clears a complaint from the active ledger."""
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM complaints WHERE ticket_id = ?", (ticket_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found.")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
    UPDATE complaints SET status = 'RESOLVED', updated_at = ? WHERE ticket_id = ?
    """, (now_str, ticket_id))

    c.execute("""
    INSERT INTO complaint_updates (ticket_id, action, notes, performed_by, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """, (
        ticket_id,
        "STATUS_RESOLVED",
        "Complaint resolved and cleared by Water Supply Department.",
        "Department Admin",
        now_str
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "ticket_id": ticket_id,
        "status": "RESOLVED",
        "message": f"Complaint {ticket_id} marked as RESOLVED and cleared from active ledger."
    }

# Frontend Static Routes
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
def serve_citizen_portal():
    """Citizen public interface."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "WaterCare AI Backend is running. Frontend index.html not found."}

@app.get("/admin")
def serve_admin_dashboard():
    """Admin & Evaluator complaint management dashboard."""
    admin_path = FRONTEND_DIR / "admin.html"
    if admin_path.exists():
        return FileResponse(admin_path)
    return {"message": "Admin Dashboard file (admin.html) not found."}
