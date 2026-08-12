"""
Postman-style end-to-end test script for the Loan Application Audit Event flow.

This script simulates the exact API calls that the Postman collection makes:
1. Setup: Create test lead, farmer profile, credit info, and loan application
2. Step 7: Send for Review (Draft -> Processing) — calls update_loan_status
3. Step 15: Update Loan Status (Processing -> Approved with reason) — calls update_loan_status
4. Verify: Check that A2C Loan Application Audit Event records were created

Run with: bench --site development.localhost execute oan_a2c.scripts.test_audit_flow
"""

import frappe

from oan_a2c.api.v1.loan_applications import update_loan_status


def execute():
	frappe.set_user("Administrator")

	print("=" * 70)
	print("POSTMAN-STYLE AUDIT EVENT FLOW TEST")
	print("=" * 70)

	# ---------- SETUP: Create dummy data ----------
	print("\n[SETUP] Creating test data...")

	# Cleanup any previous test run
	frappe.db.sql(
		"DELETE FROM `tabA2C Loan Application Audit Event` WHERE loan_application IN "
		"(SELECT name FROM `tabA2C Loan Application` WHERE lead_id='POSTMAN_TEST_LEAD')"  # bank-scope-exempt: setup test
	)
	frappe.db.sql(
		"DELETE FROM `tabA2C Loan Application` WHERE lead_id='POSTMAN_TEST_LEAD'"  # bank-scope-exempt: setup test
	)
	frappe.db.sql("DELETE FROM `tabA2C Farmer Profile` WHERE lead_id='POSTMAN_TEST_LEAD'")
	frappe.db.sql("DELETE FROM `tabA2C Lead` WHERE name='POSTMAN_TEST_LEAD'")
	frappe.db.commit()

	# Create Lead
	lead = frappe.get_doc(
		{
			"doctype": "A2C Lead",
			"phone_number": "+251911222333",
			"lead_source": "Agent Entry",
			"status": "Verified",
		}
	)
	lead.insert(ignore_permissions=True)
	frappe.db.sql("UPDATE `tabA2C Lead` SET name='POSTMAN_TEST_LEAD' WHERE name=%s", lead.name)
	frappe.db.commit()
	print("  ✔ Created Lead: POSTMAN_TEST_LEAD")

	# Create Farmer Profile
	farmer = frappe.get_doc(
		{
			"doctype": "A2C Farmer Profile",
			"first_name": "Postman",
			"last_name": "TestFarmer",
			"phone_number": "+251911222333",
			"location": "Addis Ababa",
			"lead_id": "POSTMAN_TEST_LEAD",
		}
	)
	farmer.insert(ignore_permissions=True)
	frappe.db.set_value("A2C Lead", "POSTMAN_TEST_LEAD", "farmer_profile", farmer.name)
	frappe.db.commit()
	print(f"  ✔ Created Farmer Profile: {farmer.name}")

	# Create Loan Application
	loan_app = frappe.get_doc(
		{
			"doctype": "A2C Loan Application",
			"first_name": "Postman",
			"last_name": "TestFarmer",
			"phone_number": "+251911222333",
			"loan_amount": 10000,
			"requested_amount": 10000,
			"bank": "Test Bank",
			"loan_type": "Input Loan",
			"status": "Draft",
			"location": "Addis Ababa",
			"lead_id": "POSTMAN_TEST_LEAD",
			"farmer_profile": farmer.name,
		}
	)
	loan_app.insert(ignore_permissions=True)
	frappe.db.commit()
	app_id = loan_app.name
	print(f"  ✔ Created Loan Application: {app_id} (status: Draft)")

	# ---------- STEP 7: Send for Review (Draft -> Processing) ----------
	print("\n[STEP 7] POST update_loan_status — Draft → Processing")
	print(f"  Request body: {{'application_id': '{app_id}', 'status': 'Processing'}}")

	res1 = update_loan_status(application_id=app_id, status="Processing")
	print(f"  Response: status={res1['status']}, message={res1.get('message')}")
	assert res1["status"] == "success", f"Expected success, got {res1['status']}"
	print("  ✔ PASS — Loan status updated to Processing")

	# ---------- STEP 15: Update Loan Status (Processing -> Approved with reason) ----------
	print("\n[STEP 15] POST update_loan_status — Processing → Approved (with reason)")
	reason = "Farmer meets all credit criteria. Land ownership verified."
	print(f"  Request body: {{'application_id': '{app_id}', 'status': 'Approved', 'reason': '{reason}'}}")

	res2 = update_loan_status(application_id=app_id, status="Approved", reason=reason)
	print(f"  Response: status={res2['status']}, message={res2.get('message')}")
	assert res2["status"] == "success", f"Expected success, got {res2['status']}"
	print("  ✔ PASS — Loan status updated to Approved")

	# ---------- VERIFY: Check Audit Events ----------
	print("\n[VERIFY] Querying A2C Loan Application Audit Event records...")

	audit_events = frappe.get_all(
		"A2C Loan Application Audit Event",
		filters={"loan_application": app_id},
		fields=["name", "loan_application", "event_type", "event_title", "event_description", "creation"],
		order_by="creation asc",
	)

	print(f"  Found {len(audit_events)} audit event(s):\n")
	for i, evt in enumerate(audit_events, 1):
		print(f"  --- Audit Event #{i} ---")
		print(f"  Name:        {evt['name']}")
		print(f"  Application: {evt['loan_application']}")
		print(f"  Event Type:  {evt['event_type']}")
		print(f"  Event Title: {evt['event_title']}")
		print(f"  Description: {evt['event_description']}")
		print(f"  Created:     {evt['creation']}")
		print()

	# Assertions
	assert len(audit_events) == 2, f"Expected 2 audit events, got {len(audit_events)}"

	# Event 1: Draft -> Processing
	assert audit_events[0]["event_type"] == "Status Changed"
	assert "Changed to Processing" in audit_events[0]["event_description"]
	assert "Administrator" in audit_events[0]["event_description"]
	print("  ✔ Event #1 verified: Draft → Processing, logged by Administrator")

	# Event 2: Processing -> Approved (with reason)
	assert audit_events[1]["event_type"] == "Status Changed"
	assert "Changed to Approved" in audit_events[1]["event_description"]
	assert reason in audit_events[1]["event_description"]
	assert "Administrator" in audit_events[1]["event_description"]
	print("  ✔ Event #2 verified: Processing → Approved with reason, logged by Administrator")

	# ---------- NEGATIVE TEST: Illegal transition should NOT create audit ----------
	print("\n[NEGATIVE TEST] POST update_loan_status — Approved → Draft (illegal)")
	res3 = update_loan_status(application_id=app_id, status="Draft")
	print(f"  Response: status={res3['status']}")
	assert res3["status"] == "error", f"Expected error, got {res3['status']}"

	audit_count = frappe.db.count("A2C Loan Application Audit Event", {"loan_application": app_id})
	assert audit_count == 2, f"Expected still 2 audit events, got {audit_count}"
	print("  ✔ PASS — No audit event created for failed transition (still 2 events)")

	# ---------- CLEANUP ----------
	print("\n[CLEANUP] Removing test data...")
	# These raw SQL queries bypass bank-scope checks.
	# The `# bank-scope-exempt:` directive ensures the custom bank scope enforcement linter doesn't fail here.
	frappe.db.sql(
		"DELETE FROM `tabA2C Loan Application Audit Event` WHERE loan_application=%s",  # bank-scope-exempt: test cleanup
		app_id,
	)
	frappe.db.sql(
		"UPDATE `tabA2C Loan Application` SET docstatus=0 WHERE name=%s",
		app_id,  # bank-scope-exempt: test cleanup
	)
	frappe.delete_doc("A2C Loan Application", app_id, ignore_permissions=True, force=True)
	frappe.delete_doc("A2C Farmer Profile", farmer.name, ignore_permissions=True, force=True)
	frappe.delete_doc("A2C Lead", "POSTMAN_TEST_LEAD", ignore_permissions=True, force=True)
	frappe.db.commit()
	print("  ✔ Cleanup complete")

	print("\n" + "=" * 70)
	print("ALL TESTS PASSED ✔")
	print("=" * 70)
