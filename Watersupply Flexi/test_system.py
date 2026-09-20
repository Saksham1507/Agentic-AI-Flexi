import unittest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import init_db, reset_complaints, get_db_connection
from backend.tools.complaint_tools import (
    check_area_status,
    search_existing_complaints,
    create_complaint,
    update_complaint,
    escalate_complaint
)
from backend.agent.agent_core import WaterCareAgent, get_latest_workflow

class TestWaterCareCleaned(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        reset_complaints()
        cls.client = TestClient(app)
        cls.agent = WaterCareAgent()

    def test_01_initial_complaint_log_empty(self):
        """Active complaint log MUST start empty."""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM complaints")
        count = c.fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

        res = self.client.get("/api/complaints/active")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["complaints"]), 0)

        # Check stats
        res_stats = self.client.get("/api/stats")
        self.assertEqual(res_stats.status_code, 200)
        stats = res_stats.json()
        self.assertEqual(stats["total_complaints"], 0)
        self.assertEqual(stats["active_complaints"], 0)
        self.assertEqual(stats["resolved_complaints"], 0)

    def test_02_routes_serving_and_content_check(self):
        """Citizen portal on / and Admin dashboard on /admin without telemetry or dev tools."""
        # /
        res_citizen = self.client.get("/")
        self.assertEqual(res_citizen.status_code, 200)
        self.assertIn("WaterCare AI", res_citizen.text)
        self.assertIn("Not sure what to write? Try an example", res_citizen.text)
        self.assertNotIn("Municipal Ward Telemetry", res_citizen.text)
        self.assertNotIn("Developer Tools", res_citizen.text)

        # /admin
        res_admin = self.client.get("/admin")
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn("WaterCare AI Admin", res_admin.text)
        self.assertIn("Active Complaint Log", res_admin.text)
        self.assertIn("View Agent Workflow", res_admin.text)
        # Ensure telemetry and dev tools are removed
        self.assertNotIn("Municipal Ward Telemetry", res_admin.text)
        self.assertNotIn("Developer Tools", res_admin.text)
        self.assertNotIn("Quick Demo Scenarios", res_admin.text)

    def test_03_citizen_complaint_and_admin_view(self):
        """Citizen submits complaint -> exactly 1 complaint in active log -> workflow recorded."""
        res_chat = self.client.post("/api/chat", json={
            "message": "There is no water supply in Ward 5 since yesterday."
        })
        self.assertEqual(res_chat.status_code, 200)
        data = res_chat.json()
        self.assertFalse(data["missing_info"])
        self.assertIsNotNone(data["ticket"])
        ticket_id = data["ticket"]["ticket_id"]
        self.assertTrue(ticket_id.startswith("TKT-"))
        self.assertEqual(data["ticket"]["location"], "Ward 5")

        # Check Active Complaints list has exactly 1 ticket
        res_active = self.client.get("/api/complaints/active")
        self.assertEqual(res_active.status_code, 200)
        active_list = res_active.json()["complaints"]
        self.assertEqual(len(active_list), 1)
        self.assertEqual(active_list[0]["ticket_id"], ticket_id)

        # Check Latest Workflow API
        res_wf = self.client.get("/api/agent/latest-workflow")
        self.assertEqual(res_wf.status_code, 200)
        wf_data = res_wf.json()
        self.assertTrue(wf_data["has_run"])
        self.assertGreater(len(wf_data["steps"]), 0)

    def test_04_resolve_and_clear_complaint(self):
        """Admin resolves complaint -> disappears from active log -> resolved count increases."""
        # Get current active complaint
        res_active = self.client.get("/api/complaints/active")
        ticket_id = res_active.json()["complaints"][0]["ticket_id"]

        # Status check should be is_resolved = False
        res_status = self.client.get(f"/api/complaints/{ticket_id}/status-check")
        self.assertFalse(res_status.json()["is_resolved"])

        # Admin resolves
        res_resolve = self.client.post(f"/api/complaints/{ticket_id}/resolve")
        self.assertEqual(res_resolve.status_code, 200)
        self.assertEqual(res_resolve.json()["status"], "RESOLVED")

        # Active log should now be 0
        res_active_after = self.client.get("/api/complaints/active")
        self.assertEqual(len(res_active_after.json()["complaints"]), 0)

        # Status check should now be is_resolved = True
        res_status_after = self.client.get(f"/api/complaints/{ticket_id}/status-check")
        self.assertTrue(res_status_after.json()["is_resolved"])

        # Stats should show 1 resolved
        stats = self.client.get("/api/stats").json()
        self.assertEqual(stats["resolved_complaints"], 1)
        self.assertEqual(stats["active_complaints"], 0)

    def test_05_missing_info_detection(self):
        """Prompting without location pauses ticket creation."""
        res = self.client.post("/api/chat", json={"message": "There is no water."})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["missing_info"])
        self.assertIsNone(data["ticket"])
        self.assertIn("Ward number", data["response"])

if __name__ == "__main__":
    unittest.main()
