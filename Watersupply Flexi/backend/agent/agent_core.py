import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.config import GEMINI_API_KEY, GEMINI_MODEL, has_gemini_key
from backend.agent.prompts import SYSTEM_INSTRUCTION
from backend.tools.complaint_tools import (
    check_area_status,
    search_existing_complaints,
    create_complaint,
    update_complaint,
    escalate_complaint
)

logger = logging.getLogger("watercare.agent")

# Registry of callable tools
AVAILABLE_TOOLS = {
    "check_area_status": check_area_status,
    "search_existing_complaints": search_existing_complaints,
    "create_complaint": create_complaint,
    "update_complaint": update_complaint,
    "escalate_complaint": escalate_complaint,
}

# In-memory store of the most recent agent workflow (for Admin Dashboard inspection)
LATEST_AGENT_WORKFLOW: Dict[str, Any] = {
    "has_run": False,
    "timestamp": None,
    "user_message": None,
    "steps": [],
    "ticket": None,
    "missing_info": False,
    "agent_mode": None
}

class AgentStep:
    """Represents a single discrete step in the agent's reasoning / execution cycle."""
    def __init__(self, step_type: str, title: str, description: str, data: Optional[Dict[str, Any]] = None):
        self.step_type = step_type  # UNDERSTAND, PLAN, SELECT_TOOL, EXECUTE_TOOL, OBSERVE, DECIDE, ESCALATE, FINAL_RESPONSE
        self.title = title
        self.description = description
        self.data = data or {}
        self.timestamp = datetime.now().strftime("%H:%M:%S")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_type": self.step_type,
            "title": self.title,
            "description": self.description,
            "data": self.data,
            "timestamp": self.timestamp
        }


class WaterCareAgent:
    """
    Intelligent Agent for Municipal Water Supply Complaints.
    Demonstrates true Agentic AI:
    Understand -> Plan -> Select Tool -> Execute Tool -> Observe Result -> Decide Next Action -> Final Response
    """

    def __init__(self):
        self.has_key = has_gemini_key()
        self.gemini_client = None
        if self.has_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI Client: {e}")
                self.has_key = False

    def process_complaint(self, user_message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Main entry point for citizen complaint interaction.
        IMPORTANT: Each complaint is analyzed independently from the CURRENT message only.
        Conversation history is NEVER blended into entity extraction (location, category).
        Blending caused stale Ward numbers and categories from old complaints to appear in new tickets.
        """
        conversation_history = conversation_history or []
        steps: List[AgentStep] = []

        # Entity extraction ALWAYS uses ONLY the current user_message.
        # Do NOT combine previous messages here — that is the root cause of the
        # stale-Ward and wrong-category bug.
        context_description = user_message

        # If Gemini API key is valid and available, try Gemini Agentic Execution first
        if self.has_key and self.gemini_client:
            try:
                result = self._execute_with_gemini(user_message, context_description, conversation_history)
                if result:
                    self._record_latest_workflow(user_message, result)
                    return result
            except Exception as e:
                logger.error(f"Gemini agent execution encountered error: {e}. Falling back to internal Agentic Engine.")
                steps.append(AgentStep(
                    "DECIDE",
                    "Switched to Resilient Agentic Engine",
                    f"Gemini API notice: {str(e)[:120]}. Continuing with deterministic agent tool workflow."
                ))

        # Fallback / Local Deterministic Agentic Engine
        result = self._execute_agentic_loop(user_message, context_description, conversation_history, initial_steps=steps)
        self._record_latest_workflow(user_message, result)
        return result

    def _record_latest_workflow(self, user_message: str, result: Dict[str, Any]):
        global LATEST_AGENT_WORKFLOW
        LATEST_AGENT_WORKFLOW = {
            "has_run": True,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_message": user_message,
            "steps": result.get("steps", []),
            "ticket": result.get("ticket"),
            "missing_info": result.get("missing_info", False),
            "agent_mode": result.get("agent_mode", "Agentic Engine")
        }

    def _execute_agentic_loop(
        self,
        user_message: str,
        context_text: str,
        conversation_history: List[Dict[str, str]],
        initial_steps: Optional[List[AgentStep]] = None
    ) -> Dict[str, Any]:
        """
        Pure Agentic Reasoning Engine.
        Executes discrete, traceable multi-step reasoning with actual SQLite tool invocations.
        """
        steps: List[AgentStep] = list(initial_steps) if initial_steps else []

        # 1. UNDERSTAND & EXTRACT INFORMATION
        extracted = self._extract_entities(user_message, context_text)
        
        steps.append(AgentStep(
            "UNDERSTAND",
            "Analyzing Citizen Complaint & Extracting Entities",
            f"Extracted Category: '{extracted['category']}', Location: '{extracted['location'] or 'NOT FOUND'}', Duration: '{extracted['duration']}'",
            {
                "raw_input": user_message,
                "category": extracted["category"],
                "location": extracted["location"],
                "duration": extracted["duration"],
                "urgency_markers": extracted["urgency_markers"]
            }
        ))

        # 2. DETECT MISSING INFORMATION
        if not extracted["location"]:
            steps.append(AgentStep(
                "VERIFY_INFO",
                "Missing Location Parameter Detected",
                "A specific Ward number or area is required to route the complaint to the designated zonal water officer.",
                {"missing_field": "location", "category_identified": extracted["category"]}
            ))

            clarification_msg = (
                f"I understand that you are experiencing an issue regarding **{extracted['category']}**.\n\n"
                f"To register your complaint and route it to the appropriate zonal engineer, "
                f"**could you please specify your Ward number or area** (for example: *Ward 5*, *Ward 2*, or *Market Square*)?"
            )

            steps.append(AgentStep(
                "FINAL_RESPONSE",
                "Prompting Citizen for Clarification",
                "Complaint registration paused until location is provided. No incomplete ticket was created."
            ))

            return {
                "response": clarification_msg,
                "steps": [s.to_dict() for s in steps],
                "ticket": None,
                "missing_info": True,
                "agent_mode": "Agentic Engine (Local)"
            }

        # 3. PLAN ACTION & SELECT RECONNAISSANCE TOOLS
        location = extracted["location"]
        category = extracted["category"]
        duration = extracted["duration"]

        steps.append(AgentStep(
            "PLAN",
            "Formulating Resolution Plan",
            f"1. Verify municipal jurisdiction for {location}.\n2. Query existing active complaints in {location} to check for recurring issues.\n3. Calculate priority.\n4. Call create_complaint() tool.\n5. Evaluate escalation criteria.",
            {"target_location": location, "target_category": category}
        ))

        # 4. TOOL CALL 1 - check_area_status
        steps.append(AgentStep(
            "SELECT_TOOL",
            "Selecting Tool: check_area_status",
            f"Verifying municipal jurisdiction and designated zonal officer for {location}.",
            {"tool": "check_area_status", "args": {"location": location}}
        ))

        area_status = check_area_status(location)

        steps.append(AgentStep(
            "EXECUTE_TOOL",
            f"Executed check_area_status('{location}')",
            f"Confirmed municipal jurisdiction. Designated Officer: {area_status.get('contact_officer', 'Zonal Engineer')}",
            {"tool_output": area_status}
        ))

        # 5. TOOL CALL 2 - search_existing_complaints
        steps.append(AgentStep(
            "SELECT_TOOL",
            "Selecting Tool: search_existing_complaints",
            f"Checking for existing related active tickets in {location}.",
            {"tool": "search_existing_complaints", "args": {"location": location, "category": category}}
        ))

        existing_info = search_existing_complaints(location, category)

        steps.append(AgentStep(
            "OBSERVE",
            "Observing Database Query Results",
            f"Found {existing_info['existing_count']} active complaint(s) in {location}. Recurring issue: {existing_info['is_recurring_issue']}.",
            {"tool_output": existing_info}
        ))

        # 6. DECIDE & DETERMINE PRIORITY
        priority, priority_reasons = self._calculate_priority(
            category=category,
            duration=duration,
            existing_count=existing_info["existing_count"],
            urgency_markers=extracted["urgency_markers"]
        )

        steps.append(AgentStep(
            "DECIDE",
            f"Priority Assessed: {priority}",
            f"Assessment factors: {'; '.join(priority_reasons)}",
            {"priority": priority, "reasons": priority_reasons}
        ))

        # 7. TOOL CALL 3 - create_complaint
        steps.append(AgentStep(
            "SELECT_TOOL",
            "Selecting Tool: create_complaint",
            f"Registering official municipal ticket for {location} [{category}] with {priority} priority.",
            {
                "tool": "create_complaint",
                "args": {
                    "description": user_message,
                    "location": location,
                    "category": category,
                    "priority": priority,
                    "duration": duration
                }
            }
        ))

        new_ticket = create_complaint(
            description=user_message,
            location=location,
            category=category,
            priority=priority,
            duration=duration
        )

        ticket_id = new_ticket["ticket_id"]

        steps.append(AgentStep(
            "EXECUTE_TOOL",
            f"Executed create_complaint -> Created Ticket #{ticket_id}",
            f"Complaint persisted into SQLite. Status: REGISTERED, Priority: {priority}.",
            {"ticket": new_ticket}
        ))

        # 8. DECIDE NEXT ACTION - Escalation Check
        should_escalate = (
            priority == "HIGH" or
            category == "Contaminated Water" or
            existing_info["is_recurring_issue"]
        )

        if should_escalate:
            escalate_reason = f"Automated Escalation: Priority is {priority}. " + "; ".join(priority_reasons)
            steps.append(AgentStep(
                "SELECT_TOOL",
                "High Urgency Detected: Selecting escalate_complaint Tool",
                f"Escalation conditions met. Dispatching priority alert for Ticket {ticket_id}.",
                {"tool": "escalate_complaint", "args": {"ticket_id": ticket_id, "reason": escalate_reason}}
            ))

            escalation_result = escalate_complaint(
                ticket_id=ticket_id,
                reason=escalate_reason,
                target_department="Water Emergency Response Team"
            )

            steps.append(AgentStep(
                "ESCALATE",
                f"Ticket {ticket_id} Escalated",
                f"High-priority dispatch sent to {escalation_result.get('target_department')}. Status updated to ESCALATED.",
                {"escalation_data": escalation_result}
            ))

            new_ticket["status"] = "ESCALATED"

        # 9. COMPOSE FINAL CITIZEN RESPONSE
        officer = area_status.get("contact_officer", "Zonal Assistant Engineer")
        phone = area_status.get("contact_phone", "1800-WATER-HELP")

        response_lines = [
            f"✅ **Complaint Registered Successfully!**",
            f"- **Ticket ID:** `{ticket_id}`",
            f"- **Category:** {category}",
            f"- **Location:** {location}",
            f"- **Priority:** **{priority}**",
            f"- **Status:** `{new_ticket['status']}`",
            ""
        ]

        if existing_info["existing_count"] > 1:
            response_lines.append(f"🔔 **Multiple Reports Detected:** There are currently {existing_info['existing_count']} active complaints reported in {location}. Our field engineers are already notified.")
            response_lines.append("")

        if should_escalate:
            response_lines.append(f"🚨 **Fast-Track Escalation:** Due to the severity of this issue, your ticket has been prioritized and escalated to the **Water Emergency Response Team**.")
            response_lines.append("")

        response_lines.append(f"👤 **Assigned Officer:** {officer} (📞 {phone})")
        response_lines.append("You can track this complaint anytime using your Ticket ID.")

        final_response_text = "\n".join(response_lines)

        steps.append(AgentStep(
            "FINAL_RESPONSE",
            "Synthesizing Final Response for Citizen",
            f"Generated response briefing including Ticket #{ticket_id} and Zonal Officer contact details."
        ))

        return {
            "response": final_response_text,
            "steps": [s.to_dict() for s in steps],
            "ticket": new_ticket,
            "missing_info": False,
            "agent_mode": "Agentic Engine (Deterministic)"
        }

    def _execute_with_gemini(
        self,
        user_message: str,
        context_text: str,
        conversation_history: List[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        from google.genai import types

        steps: List[AgentStep] = []

        extracted = self._extract_entities(user_message, context_text)
        if not extracted["location"]:
            steps.append(AgentStep(
                "UNDERSTAND",
                "Gemini Agent Analyzing Complaint",
                f"Extracted category: '{extracted['category']}', but no Ward or location was identified.",
                {"user_input": user_message}
            ))
            steps.append(AgentStep(
                "VERIFY_INFO",
                "Missing Location Detected",
                "Ward number is missing. Halting ticket generation to request citizen details."
            ))
            return {
                "response": (
                    f"I have noted your concern regarding **{extracted['category']}**.\n\n"
                    f"To enable our municipal team to investigate, **please specify your Ward number or area** (e.g. *Ward 5*, *Ward 2*, etc.)."
                ),
                "steps": [s.to_dict() for s in steps],
                "ticket": None,
                "missing_info": True,
                "agent_mode": f"Gemini LLM ({GEMINI_MODEL})"
            }

        steps.append(AgentStep(
            "UNDERSTAND",
            "Gemini Agent Initialized with Function Calling",
            f"Query: '{user_message}'. Extracted Ward: '{extracted['location']}'. Sending to Gemini {GEMINI_MODEL} with callable database tools.",
            {"model": GEMINI_MODEL, "location": extracted["location"]}
        ))

        tools = [
            check_area_status,
            search_existing_complaints,
            create_complaint,
            update_complaint,
            escalate_complaint
        ]

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.2,
            tools=tools
        )

        prompt = (
            f"Citizen complaint: \"{user_message}\"\n"
            f"Context: Location={extracted['location']}, Category={extracted['category']}, Duration={extracted['duration']}.\n"
            f"Please follow the required steps: 1. check_area_status, 2. search_existing_complaints, 3. determine priority, 4. create_complaint, 5. escalate if high priority. Then give a polite final response."
        )

        # Snapshot the highest existing complaint ID BEFORE calling Gemini.
        # This lets us identify only the NEW ticket Gemini creates, avoiding stale data.
        from backend.database import get_db_connection, dict_from_row
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT MAX(id) FROM complaints")
        row = c.fetchone()
        max_id_before = row[0] if row[0] is not None else -1
        conn.close()

        response = self.gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config
        )

        # Fetch ONLY a ticket created after the pre-call snapshot (i.e., the NEW ticket).
        # This is the fix for the stale-ticket bug: we never return a previously-created complaint.
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT * FROM complaints WHERE id > ? ORDER BY id DESC LIMIT 1",
            (max_id_before,)
        )
        last_row = c.fetchone()
        conn.close()

        created_ticket = dict_from_row(last_row) if last_row else None

        steps.append(AgentStep(
            "EXECUTE_TOOL",
            "Gemini Function Calling Loop Complete",
            f"Gemini orchestrated tool calling against SQLite database. Ticket: {created_ticket['ticket_id'] if created_ticket else 'None created'}.",
            {"ticket": created_ticket}
        ))

        steps.append(AgentStep(
            "FINAL_RESPONSE",
            "Gemini Synthesized Response",
            "Final response generated by Gemini model."
        ))

        final_text = response.text or (
            f"Your complaint has been successfully processed and registered with Ticket ID `{created_ticket['ticket_id'] if created_ticket else 'TKT-PENDING'}`."
        )

        return {
            "response": final_text,
            "steps": [s.to_dict() for s in steps],
            "ticket": created_ticket,
            "missing_info": False,
            "agent_mode": f"Gemini LLM ({GEMINI_MODEL})"
        }

    def _extract_entities(self, text: str, context_text: str) -> Dict[str, Any]:
        # IMPORTANT: Always extract from ONLY the current message text.
        # context_text is intentionally ignored here — combining it with text
        # caused stale Wards/categories from past complaints to bleed into new tickets.
        full_text = text.lower()

        location = None
        ward_match = re.search(r'\b(ward\s*\d+|ward-\d+)\b', full_text, re.IGNORECASE)
        if ward_match:
            num = re.search(r'\d+', ward_match.group(1))
            if num:
                location = f"Ward {num.group(0)}"
        else:
            landmarks = [
                ("north ridge", "Ward 1"),
                ("market square", "Ward 2"),
                ("riverside colony", "Ward 3"),
                ("metro heights", "Ward 4"),
                ("green park", "Ward 5"),
                ("industrial sector", "Ward 6"),
                ("old cantonment", "Ward 7"),
                ("south extension", "Ward 8"),
            ]
            for landmark, ward in landmarks:
                if landmark in full_text:
                    location = ward
                    break

        category = "No Water Supply"
        if any(w in full_text for w in ["dirty", "muddy", "contaminated", "brown", "smell", "black", "stink", "sewage", "poison", "germ"]):
            category = "Contaminated Water"
        elif any(w in full_text for w in ["leak", "burst", "pipe broken", "pipe cracked", "overflow", "gushing"]):
            category = "Pipeline Leakage"
        elif any(w in full_text for w in ["pressure", "trickle", "slow flow", "very low", "low flow"]):
            category = "Low Pressure"
        elif any(w in full_text for w in ["bill", "meter", "tariff", "charge", "payment", "unit"]):
            category = "Billing & Meter"
        elif any(w in full_text for w in ["timing", "irregular", "late", "schedule", "no schedule"]):
            category = "Irregular Timings"
        elif any(w in full_text for w in ["no water", "not coming", "stopped", "dry", "cut off", "no supply", "outage"]):
            category = "No Water Supply"

        duration = "Unspecified"
        if "yesterday" in full_text:
            duration = "Since yesterday (~24 hours)"
        elif "today" in full_text:
            duration = "Since today morning"
        elif re.search(r'\b(\d+)\s*(days?|hrs?|hours?|weeks?)\b', full_text):
            m = re.search(r'\b(\d+)\s*(days?|hrs?|hours?|weeks?)\b', full_text)
            duration = f"{m.group(1)} {m.group(2)}"
        elif "morning" in full_text:
            duration = "Since morning"

        urgency_markers = []
        for kw in ["urgent", "emergency", "immediately", "hospital", "critical", "children", "sick", "school", "sewage", "foul", "burst"]:
            if kw in full_text:
                urgency_markers.append(kw)

        return {
            "location": location,
            "category": category,
            "duration": duration,
            "urgency_markers": urgency_markers
        }

    def _calculate_priority(
        self,
        category: str,
        duration: str,
        existing_count: int,
        urgency_markers: List[str]
    ) -> tuple[str, List[str]]:
        reasons = []
        is_high = False

        if category == "Contaminated Water":
            is_high = True
            reasons.append("Contaminated water represents immediate public health risk")

        if "yesterday" in duration.lower() or any(d in duration.lower() for d in ["2 day", "3 day", "4 day", "5 day", "week"]):
            is_high = True
            reasons.append(f"Extended outage duration: {duration}")

        if urgency_markers:
            is_high = True
            reasons.append(f"Detected critical indicators: {', '.join(urgency_markers)}")

        if existing_count >= 2:
            is_high = True
            reasons.append(f"Multiple active complaints ({existing_count}) logged in same ward")

        if is_high:
            return "HIGH", reasons

        if category in ("Billing & Meter", "Irregular Timings") and not urgency_markers:
            reasons.append("Administrative complaint category")
            return "LOW", reasons

        reasons.append("Standard service interruption (< 24 hours)")
        return "MEDIUM", reasons

def get_latest_workflow() -> Dict[str, Any]:
    """Returns the most recent agent execution steps and metadata for Admin Dashboard display."""
    return LATEST_AGENT_WORKFLOW
