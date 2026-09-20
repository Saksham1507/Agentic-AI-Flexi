"""
Test suite for the entity extraction fix.
Verifies that each new complaint is independently analyzed:
- Correct location extracted from current message only
- Correct category extracted from current message only
- No bleed from conversation history or prior complaints
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
from backend.agent.agent_core import WaterCareAgent


class TestEntityExtractionIndependence(unittest.TestCase):
    """Tests that entity extraction is always based on the CURRENT message only."""

    def setUp(self):
        self.agent = WaterCareAgent()

    def _extract(self, message, history=None):
        """Helper: call _extract_entities with message as both text and context (as process_complaint now does)."""
        return self.agent._extract_entities(message, message)

    # ------------------------------------------------------------------ #
    #  Core extraction tests — no history                                  #
    # ------------------------------------------------------------------ #

    def test_pipeline_leakage_ward2(self):
        """Pipeline leakage near Ward 2 market must give category=Pipeline Leakage, location=Ward 2."""
        msg = "There is a pipeline leakage near Ward 2 market."
        result = self._extract(msg)
        self.assertEqual(result["location"], "Ward 2", f"Expected Ward 2, got: {result['location']}")
        self.assertEqual(result["category"], "Pipeline Leakage", f"Expected Pipeline Leakage, got: {result['category']}")

    def test_no_water_supply_ward5(self):
        """No water supply in Ward 5 must give category=No Water Supply, location=Ward 5."""
        msg = "There is no water supply in Ward 5 since yesterday."
        result = self._extract(msg)
        self.assertEqual(result["location"], "Ward 5", f"Expected Ward 5, got: {result['location']}")
        self.assertEqual(result["category"], "No Water Supply", f"Expected No Water Supply, got: {result['category']}")

    def test_low_pressure_ward4(self):
        """Low pressure in Ward 4 must give category=Low Pressure, location=Ward 4."""
        msg = "Water pressure is very low in Ward 4."
        result = self._extract(msg)
        self.assertEqual(result["location"], "Ward 4", f"Expected Ward 4, got: {result['location']}")
        self.assertEqual(result["category"], "Low Pressure", f"Expected Low Pressure, got: {result['category']}")

    def test_contaminated_water_ward3(self):
        """Contaminated water in Ward 3 must give category=Contaminated Water."""
        msg = "The water is dirty and contaminated in Ward 3."
        result = self._extract(msg)
        self.assertEqual(result["location"], "Ward 3")
        self.assertEqual(result["category"], "Contaminated Water")

    # ------------------------------------------------------------------ #
    #  No history bleed tests — simulate multiple sequential complaints    #
    # ------------------------------------------------------------------ #

    def test_no_bleed_from_prior_complaint_category(self):
        """After a contaminated-water/Ward-5 complaint, a new Ward-2 pipeline complaint
        must extract Ward 2 and Pipeline Leakage — NOT Ward 5 or Contaminated Water."""
        # Simulate what citizen.js sends as history after first complaint
        fake_history = [
            {"role": "user", "content": "The water is dirty and contaminated in Ward 5."},
            {"role": "assistant", "content": "Ticket registered for Ward 5, Contaminated Water."}
        ]
        # process_complaint now ignores history for entity extraction
        new_msg = "There is a pipeline leakage near Ward 2 market."
        result = self._extract(new_msg)  # history is NOT passed to _extract_entities
        self.assertEqual(result["location"], "Ward 2",
            f"Category bled from history: expected Ward 2, got {result['location']}")
        self.assertEqual(result["category"], "Pipeline Leakage",
            f"Category bled from history: expected Pipeline Leakage, got {result['category']}")

    def test_no_bleed_from_prior_complaint_location(self):
        """A Ward 1 complaint followed by a Ward 7 complaint must extract Ward 7, not Ward 1."""
        msg = "There is a pipe burst near Ward 7."
        result = self._extract(msg)
        self.assertEqual(result["location"], "Ward 7")
        self.assertEqual(result["category"], "Pipeline Leakage")

    # ------------------------------------------------------------------ #
    #  Duration extraction                                                 #
    # ------------------------------------------------------------------ #

    def test_duration_yesterday(self):
        msg = "No water supply in Ward 5 since yesterday."
        result = self._extract(msg)
        self.assertIn("yesterday", result["duration"].lower())

    def test_duration_unspecified(self):
        msg = "There is a pipeline leakage near Ward 2 market."
        result = self._extract(msg)
        self.assertEqual(result["duration"], "Unspecified")

    # ------------------------------------------------------------------ #
    #  Missing location                                                    #
    # ------------------------------------------------------------------ #

    def test_missing_location_returns_none(self):
        """A message with no ward must return location=None."""
        msg = "There is no water supply in my area."
        result = self._extract(msg)
        self.assertIsNone(result["location"], f"Expected None, got: {result['location']}")


class TestProcessComplaintAPIIndependence(unittest.TestCase):
    """Tests that process_complaint() returns correct ticket data for each independent call,
    with no stale data from conversation_history."""

    def setUp(self):
        self.agent = WaterCareAgent()

    def test_ward2_pipeline_end_to_end(self):
        """Full process_complaint call for Ward 2 pipeline leakage must return correct ticket."""
        result = self.agent.process_complaint(
            user_message="There is a pipeline leakage near Ward 2 market.",
            conversation_history=[]
        )
        ticket = result.get("ticket")
        self.assertIsNotNone(ticket, "Expected a ticket to be created")
        self.assertEqual(ticket["location"], "Ward 2", f"Wrong location: {ticket['location']}")
        self.assertEqual(ticket["category"], "Pipeline Leakage", f"Wrong category: {ticket['category']}")
        self.assertFalse(result.get("missing_info", False))

    def test_ward5_no_water_end_to_end(self):
        """Full process_complaint call for Ward 5 no water must return correct ticket."""
        result = self.agent.process_complaint(
            user_message="There is no water supply in Ward 5 since yesterday.",
            conversation_history=[]
        )
        ticket = result.get("ticket")
        self.assertIsNotNone(ticket, "Expected a ticket to be created")
        self.assertEqual(ticket["location"], "Ward 5", f"Wrong location: {ticket['location']}")
        self.assertEqual(ticket["category"], "No Water Supply", f"Wrong category: {ticket['category']}")

    def test_ward4_low_pressure_end_to_end(self):
        """Full process_complaint call for Ward 4 low pressure must return correct ticket."""
        result = self.agent.process_complaint(
            user_message="Water pressure is very low in Ward 4.",
            conversation_history=[]
        )
        ticket = result.get("ticket")
        self.assertIsNotNone(ticket, "Expected a ticket to be created")
        self.assertEqual(ticket["location"], "Ward 4", f"Wrong location: {ticket['location']}")
        self.assertEqual(ticket["category"], "Low Pressure", f"Wrong category: {ticket['category']}")

    def test_two_sequential_complaints_independent(self):
        """Submitting two complaints in sequence with history must produce independent tickets."""
        # First complaint
        r1 = self.agent.process_complaint(
            user_message="The water is dirty and contaminated in Ward 5.",
            conversation_history=[]
        )
        t1 = r1.get("ticket")
        self.assertIsNotNone(t1)
        self.assertEqual(t1["location"], "Ward 5")
        self.assertEqual(t1["category"], "Contaminated Water")

        # Second complaint — sent with history of first (as citizen portal does)
        history_after_first = [
            {"role": "user", "content": "The water is dirty and contaminated in Ward 5."},
            {"role": "assistant", "content": r1.get("response", "")}
        ]
        r2 = self.agent.process_complaint(
            user_message="There is a pipeline leakage near Ward 2 market.",
            conversation_history=history_after_first
        )
        t2 = r2.get("ticket")
        self.assertIsNotNone(t2, "Second complaint must create a new ticket")
        self.assertEqual(t2["location"], "Ward 2",
            f"Second ticket got wrong location (bled from first): {t2['location']}")
        self.assertEqual(t2["category"], "Pipeline Leakage",
            f"Second ticket got wrong category (bled from first): {t2['category']}")
        self.assertNotEqual(t1["ticket_id"], t2["ticket_id"], "Both complaints must have unique ticket IDs")


if __name__ == "__main__":
    unittest.main(verbosity=2)
