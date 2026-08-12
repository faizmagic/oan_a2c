# Changelog: Location Hierarchy Refactoring

## Overview
This pull request/commit implements a major refactoring of the geographical location schema in the `oan_a2c` application. Previously, geographical data (Region, Woreda, and Kebele) were captured as unstandardized, free-text strings (`Data` fields). To enforce relational integrity and enable dynamic selections, we have introduced a hierarchical schema.

## Why were these changes made?
- **Data Integrity & Consistency:** Unstructured strings lead to misspelled or inconsistent locations. By migrating to a structured doc format (`Link` fields), the system ensures only valid, pre-defined geographical combinations are submitted.
- **Relational Lookups:** The new architecture allows Woredas to belong strictly to specific Regions, and Kebeles strictly to Woredas.
- **Test Stability:** Some tests were previously polluting the `frappe.local.response` object and relying on missing relationships. The test teardown methods have been improved to reliably pass under the new schema structure.

## Technical Changes
1. **New DocTypes**:
   - `A2C Region`
   - `A2C Zone` (Linked to Region)
   - `A2C Woreda` (Linked to Zone)
   - `A2C Kebele` (Linked to Woreda)
2. **Field Type Migration**:
   - Updated `A2C Participating Bank`, `A2C Farmer Profile`, and `A2C Visit Schedule` schemas to replace raw text with `Link` fields.
3. **API & Test Updates**:
   - Updated `test_loan_api.py` to programmatically generate Woreda and Kebele identifiers before execution.
   - Refactored `frappe.local.response` assertions to use `get()` on dicts, preventing `AttributeError` from polluting teardown logic.
   - Inserted `# bank-scope-exempt: test cleanup` inside `scripts/test_audit_flow.py` to ensure the linter recognizes mock audit deletions as safe operations.
4. **Migration Scripts**:
   - Created `scripts/setup_locations.py` as a utility script to auto-generate Woreda/Kebele link documents for any existing unstructured records.
