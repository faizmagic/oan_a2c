import frappe
import unittest
from unittest.mock import patch, MagicMock
from oan_a2c.api.v1.consent.consent import request_otp, verify_otp_for_lead
from oan_a2c.api.dev import reset_test_data

class TestConsentAPI(unittest.TestCase):
    def setUp(self):
        # Create missing Custom DocTypes if they don't exist in the database
        if not frappe.db.exists("DocType", "Farmer"):
            frappe.get_doc({
                "doctype": "DocType",
                "name": "Farmer",
                "module": "OpenAgriNet Access to Credit",
                "custom": 1,
                "fields": [
                    {"fieldname": "farmer_name", "fieldtype": "Data", "label": "Farmer Name"},
                    {"fieldname": "full_name", "fieldtype": "Data", "label": "Full Name"},
                    {"fieldname": "mobile_no", "fieldtype": "Data", "label": "Mobile No"},
                    {"fieldname": "fayda_id", "fieldtype": "Data", "label": "Fayda ID"}
                ],
                "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}]
            }).insert(ignore_permissions=True)

        if not frappe.db.exists("DocType", "Consent Partner Config"):
            frappe.get_doc({
                "doctype": "DocType",
                "name": "Consent Partner Config",
                "module": "OpenAgriNet Access to Credit",
                "custom": 1,
                "fields": [
                    {"fieldname": "partner_name", "fieldtype": "Data", "label": "Partner Name"}
                ],
                "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}]
            }).insert(ignore_permissions=True)

        # Create necessary partner config placeholder
        if not frappe.db.exists("Consent Partner Config", "Test Partner"):
            frappe.get_doc({
                "doctype": "Consent Partner Config",
                "partner_name": "Test Partner"
            }).insert(ignore_permissions=True)

        # Create necessary farmer placeholder
        if not frappe.db.exists("Farmer", "FAYDA-123"):
            frappe.get_doc({
                "doctype": "Farmer",
                "farmer_name": "Test Farmer",
                "full_name": "Test Farmer",
                "mobile_no": "+251911123456",
                "fayda_id": "FAYDA-123"
            }).insert(ignore_permissions=True)

        # Use the dev.py reset helper to clean and initialize a fresh test lead
        res = reset_test_data()
        self.lead_id = res["lead_id"]

        frappe.conf.secret_key = "test_secret_key"
        frappe.db.commit()

    def _get_consent_values(self, name, *fields):
        """Helper: fetch consent request fields directly from DB to avoid child-table load."""
        result = frappe.db.get_value("A2C Consent Request", name, list(fields), as_dict=True)
        return result or {}

    @patch("oan_a2c.api.v1.consent.consent.OpenG2PConsentClient")
    def test_send_otp_and_create_consent(self, MockClient):
        # Mock the OpenG2P responses
        mock_instance = MockClient.return_value
        
        mock_instance.get_farmer_by_fayda_id.return_value = "DB-FARMER-001"
        mock_instance.get_partner_id.return_value = "DB-PARTNER-001"
        mock_instance.get_partner_allowed_data_field_ids.return_value = [1, 2]
        
        mock_instance.create_consent_request.return_value = {
            "id": "MOCK-G2P-CONS-001",
            "data": {
                "consent_creation_request_id": "MOCK-G2P-CONS-001"
            }
        }
        
        mock_instance.request_otp.return_value = {
            "transaction_id": "MOCK-TXN-999",
            "masked_phone": "091****1111",
            "success": True,
            "data": {
                "transaction_id": "MOCK-TXN-999",
                "masked_mobile": "091****1111"
            }
        }


        response = request_otp(
            fayda_id="FAYDA-123",
            partner="Test Partner",
            lead_id=self.lead_id,
            purpose="Testing Consent API",
            validity_from="2026-06-01 00:00:00",
            validity_to="2027-06-01 00:00:00",
            consent_form_filename="consent.txt",
            consent_form_base64="data:text/plain;base64,dGVzdA=="
        )
        
        self.assertEqual(response.get("status"), "success")
        self.assertEqual(response.get("transaction_id"), "MOCK-TXN-999")
        
        # Verify document was created using direct DB query (no child-table load)
        consent_name = response.get("consent_request")
        vals = self._get_consent_values(consent_name, "farmer_fayda_id", "status", "otp_transaction_id")
        self.assertEqual(vals.get("farmer_fayda_id"), "FAYDA-123")
        self.assertEqual(vals.get("status"), "Pending OTP")
        self.assertEqual(vals.get("otp_transaction_id"), "MOCK-TXN-999")
        
        return consent_name

    @patch("oan_a2c.api.v1.consent.consent.enqueue_websub_delivery")
    @patch("oan_a2c.api.v1.consent.consent.OpenG2PConsentClient")
    def test_verify_otp(self, MockClient, MockEnqueue):
        # Create doc and send OTP first
        consent_name = self.test_send_otp_and_create_consent()
        
        mock_instance = MockClient.return_value
        mock_instance.get_farmer_by_fayda_id.return_value = "DB-FARMER-001"
        mock_instance.get_partner_id.return_value = "DB-PARTNER-001"
        
        mock_instance.verify_otp.return_value = {
            "status": "success"
        }
        mock_instance.upload_consent_attachment.return_value = "MOCK-ATTACH-001"
        mock_instance.create_consent_request.return_value = {
            "id": "MOCK-G2P-CONS-001",
            "data": {
                "consent_creation_request_id": "MOCK-G2P-CONS-001"
            }
        }
        
        response = verify_otp_for_lead(lead_id=self.lead_id, otp_code="123456")
        
        self.assertEqual(response.get("status"), "success")
        self.assertIn("consent_receipt", response)
        
        # Verify via direct DB query to avoid child-table loading
        vals = self._get_consent_values(consent_name, "status", "otp_verified_at")
        self.assertEqual(vals.get("status"), "Approved")
        self.assertIsNotNone(vals.get("otp_verified_at"))
        
        # Verify WebSub was queued
        MockEnqueue.assert_called_once()
