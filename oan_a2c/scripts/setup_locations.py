import json
import os

import frappe


def execute():
	data_path = frappe.get_app_path("oan_a2c", "data")
	print(f"Loading data from {data_path}")

	# 1. Regions
	regions_file = os.path.join(data_path, "regions.json")
	if os.path.exists(regions_file):
		print("Processing Regions...")
		with open(regions_file, encoding="utf-8") as f:
			regions = json.load(f)
			for r in regions:
				if not frappe.db.exists("A2C Region", {"region_name": r["region_name"]}):
					frappe.get_doc({"doctype": "A2C Region", "region_name": r["region_name"]}).insert(
						ignore_permissions=True
					)

	# 2. Zones
	zones_file = os.path.join(data_path, "zones.json")
	if os.path.exists(zones_file):
		print("Processing Zones...")
		with open(zones_file, encoding="utf-8") as f:
			zones = json.load(f)
			for z in zones:
				# ensure region exists
				if not frappe.db.exists("A2C Region", {"region_name": z["region_name"]}):
					frappe.get_doc({"doctype": "A2C Region", "region_name": z["region_name"]}).insert(
						ignore_permissions=True
					)

				if not frappe.db.exists(
					"A2C Zone", {"zone_name": z["zone_name"], "region": z["region_name"]}
				):
					try:
						frappe.get_doc(
							{"doctype": "A2C Zone", "zone_name": z["zone_name"], "region": z["region_name"]}
						).insert(ignore_permissions=True)
					except Exception as e:
						print(f"Failed to insert zone {z['zone_name']}: {e}")

	# 3. Woredas
	woredas_file = os.path.join(data_path, "woredas.json")
	if os.path.exists(woredas_file):
		print("Processing Woredas...")
		with open(woredas_file, encoding="utf-8") as f:
			woredas = json.load(f)
			for w in woredas:
				# ensure zone exists
				if not frappe.db.exists("A2C Zone", {"zone_name": w["zone_name"]}):
					try:
						frappe.get_doc(
							{"doctype": "A2C Zone", "zone_name": w["zone_name"], "region": w["region_name"]}
						).insert(ignore_permissions=True)
					except Exception:
						pass

				if not frappe.db.exists(
					"A2C Woreda", {"woreda_name": w["woreda_name"], "zone": w["zone_name"]}
				):
					try:
						frappe.get_doc(
							{"doctype": "A2C Woreda", "woreda_name": w["woreda_name"], "zone": w["zone_name"]}
						).insert(ignore_permissions=True)
					except Exception:
						pass

	frappe.db.commit()
	print("Locations setup successfully.")
