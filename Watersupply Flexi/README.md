# WaterCare AI - Intelligent Water Supply Complaint Management Agent

**WaterCare AI** is an **Agentic AI** mini-project developed for municipal water authorities and civic bodies. Unlike traditional static chatbots that merely return text, WaterCare AI executes an autonomous multi-step reasoning cycle: it parses citizen complaints, detects missing parameters, inspects real-time telemetry from a municipal SQLite database, searches for recurring disruptions, assesses public health priorities, invokes backend database tools, registers complaint tickets, and auto-escalates critical emergencies.

The application features a **Dual Portal Architecture**:
1. **Citizen Portal (`/`)**: A clean, welcoming, colorful water-themed public service interface where citizens describe issues naturally, receive automated assistance, and view generated ticket cards without developer clutter or internal logs.
2. **Admin & Developer Dashboard (`/admin`)**: A dedicated executive control center for evaluators and administrators featuring real-time statistics, active complaint management, ward telemetry, direct developer tool testing, demo scenario triggers, and an on-demand **Agent Workflow Modal** (`[ 🤖 View Agent Workflow ]`).

---

## 🌟 Key Architecture & Features

### 1. Dual Portal Interface
- **Citizen Portal (`/`)**:
  - Light, inviting civic design (white/blue/cyan water theme, rounded cards, subtle shadows).
  - Conversational AI Assistant with natural language parsing.
  - Automatic Missing Information Detection (prompts for Ward if missing).
  - Polished **Complaint Ticket Card**: Displays Ticket ID, Category, Location, Priority badge (`HIGH`, `MEDIUM`, `LOW`), Status (`REGISTERED`, `ESCALATED`, `RESOLVED`), and Assigned Officer.
  - **Live Resolution Push**: When an administrator clears or resolves a complaint in the Admin Dashboard, the Citizen Portal conversation immediately receives:
    `"✅ Your complaint TKT-XXXX has been resolved and cleared by the Water Supply Department."`
  - Zero developer clutter, zero raw JSON, zero internal workflow exposure.

- **Admin / Developer Dashboard (`/admin`)**:
  - Sleek dark executive command center.
  - Quick navigation back to Citizen Portal (`← Citizen Portal`).
  - Overview Metric Cards: `[Total Complaints]`, `[Active Cases]`, `[Escalated Alerts]`, `[Resolved / Cleared]`.
  - **Active Complaint Log**:
    - Starts **completely empty** (`"No complaints registered yet."`).
    - Real-time updates as citizens submit complaints.
    - **Clear / Resolve Action**: Prompts confirmation modal (`"Are you sure you want to clear this complaint?"`), clears the complaint from the active ledger, and updates the citizen.
  - **Agent Workflow Modal (`[ 🤖 View Agent Workflow ]`)**:
    - **Hidden by default** to keep the dashboard clean.
    - When clicked, displays the latest multi-step agent reasoning cycle:
      1. Understand & Entity Extraction
      2. Missing Info Check & Plan
      3. Select Tool
      4. Execute Tool
      5. Observe Database Result
      6. Escalate / Resolve
    - Clean visual summary cards with an optional expandable **"Developer Details"** section for raw tool inputs and outputs.
  - **Quick Demo Scenarios Drawer**: Evaluators can trigger standard test queries with one click right from the Admin Dashboard!
  - **Direct Tool Inspector**: Allows manual execution of any of the 5 callable backend tools.
  - **Municipal Ward Status Grid**: Real-time telemetry for 8 municipal wards (operational states, reservoir level meters, maintenance schedules, zonal officers).

### 2. Callable Backend Tools (Connected to SQLite)
- `create_complaint(...)`: Registers formal ticket and writes initial audit log.
- `search_existing_complaints(...)`: Queries active tickets in the ward to detect cluster disruptions.
- `check_area_status(...)`: Queries real-time pipeline status, maintenance schedules, and reservoir levels.
- `update_complaint(...)`: Updates status and writes timestamped audit notes.
- `escalate_complaint(...)`: Elevates priority to `HIGH`, updates status to `ESCALATED`, and alerts emergency engineers.

### 3. Priority Assessment & Auto-Escalation Engine
- **HIGH Priority**: Contamination/foul smell (immediate public health hazard), extended outage duration (> 24 hours), or multiple cluster complaints. Automatically escalated to the *Emergency Response Engineering Cell*.
- **MEDIUM Priority**: Standard service interruption (< 24 hours), localized low water pressure.
- **LOW Priority**: Administrative inquiries, billing, meter reading requests.

---

## 📁 Project Structure

```
Watersupply Flexi/
├── backend/
│   ├── __init__.py
│   ├── main.py                # FastAPI REST API, dual route serving (/ and /admin)
│   ├── config.py              # Environment configuration & API key check
│   ├── database.py            # SQLite schema, connection manager & reference area seeding
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent_core.py      # Agentic AI loop, entity extraction & workflow caching
│   │   └── prompts.py         # System instructions & civic classification rules
│   └── tools/
│       ├── __init__.py
│       └── complaint_tools.py # 5 actual SQLite-connected backend tools
├── frontend/
│   ├── index.html             # Citizen Portal HTML (/)
│   ├── citizen.css            # Bright, friendly civic public service stylesheet
│   ├── citizen.js             # Citizen chat controller & live resolution listener
│   ├── admin.html             # Admin & Developer Dashboard HTML (/admin)
│   ├── admin.css              # Executive dark dashboard stylesheet
│   └── admin.js               # Admin dashboard controller, workflow modal & actions
├── .env.example               # Environment variables template
├── .env                       # Local environment file
├── requirements.txt           # Python dependencies
├── run.bat                    # Windows quick-launch script
├── test_system.py             # Automated unit & system verification test suite
└── README.md                  # Documentation
```

---

## ⚙️ Installation & Running (Windows)

### 1. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### 2. (Optional) Configure Gemini API Key
If you have a Google AI Studio API key, add it to `.env`:
```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```
> **Presentation Safety**: If left blank, WaterCare AI runs in **Local Agentic Engine Mode**, executing the identical multi-step reasoning cycle and SQLite tools locally so the presentation never fails even if offline.

### 3. Start the Server
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
*(Or double-click `run.bat`)*

### 4. Open in Browser
- **Citizen Portal**: **`http://127.0.0.1:8000/`**
- **Admin Dashboard**: **`http://127.0.0.1:8000/admin`**

---

## 🧪 Demonstration Walkthrough for Evaluators

1. **Verify Empty State**:
   - Open **`http://127.0.0.1:8000/admin`**.
   - Notice that the Active Complaint Log shows: `"No complaints registered yet."` with 0 active cases.
2. **Citizen Submits a Complaint**:
   - Open **`http://127.0.0.1:8000/`**.
   - Type: `"There is no water supply in Ward 5 since yesterday."` and click **Submit Complaint**.
   - Notice the friendly AI response and the official green **Complaint Registered Successfully** card with unique Ticket ID (e.g. `TKT-2026-XXXX`), High Priority, and Ward details.
3. **Verify Admin Dashboard Updates**:
   - Switch to **`http://127.0.0.1:8000/admin`**.
   - Exactly **1 complaint** now appears in the Active Complaint Log.
4. **Demonstrate Agentic AI Reasoning**:
   - Click the button: **`[ 🤖 View Agent Workflow ]`**.
   - The modal opens showing the multi-step lifecycle:
     * *Step 1: Understand & Extract (Entities)*
     * *Step 2: Plan (Formulating tool call strategy)*
     * *Step 3: Tool Execution (check_area_status)*
     * *Step 4: Tool Execution (search_existing_complaints)*
     * *Step 5: Priority Assessment (Assessed: HIGH)*
     * *Step 6: Tool Execution (create_complaint & escalate_complaint)*
   - Expand **Developer Details** to view the raw JSON inputs and database responses.
   - Close the modal.
5. **Clear / Resolve the Complaint**:
   - In the Active Complaint Log, click **✓ Clear / Resolve**.
   - A confirmation modal asks: *"Are you sure you want to clear this complaint?"*.
   - Click **Yes, Clear Complaint**.
   - The complaint immediately disappears from the active log, and Resolved count increments by 1.
6. **Verify Live Notification on Citizen Portal**:
   - Switch back to the Citizen Portal tab.
   - Without refreshing the page, a green notification has automatically appeared in the conversation:
     `"✅ Your complaint TKT-XXXX has been resolved and cleared by the Water Supply Department."`
   - The Ticket Card status updates to `RESOLVED`.
7. **Test Missing Information Detection**:
   - On the Citizen Portal, submit: `"There is no water."`
   - The agent detects that the **Ward/Location is missing**, avoids creating an incomplete record in the database, and asks the citizen to specify their Ward.
