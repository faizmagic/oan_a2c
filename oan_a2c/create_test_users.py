import frappe

def create_test_users():
    # Create Dev Agent User
    dev_email = "dev_agent@test.com"
    if not frappe.db.exists("User", dev_email):
        user = frappe.new_doc("User")
        user.email = dev_email
        user.first_name = "Dev"
        user.last_name = "Agent"
        user.send_welcome_email = 0
        user.insert(ignore_permissions=True)
        user.add_roles("A2C Development Agent")
        
        # Set password
        frappe.utils.password.update_password(dev_email, "Test@123")
        print(f"Created user {dev_email}")
    else:
        frappe.utils.password.update_password(dev_email, "Test@123")
        user = frappe.get_doc("User", dev_email)
        user.add_roles("A2C Development Agent")
        print(f"Updated user {dev_email}")

    # Create Bank Agent User
    bank_email = "bank_agent@test.com"
    if not frappe.db.exists("User", bank_email):
        user = frappe.new_doc("User")
        user.email = bank_email
        user.first_name = "Bank"
        user.last_name = "Agent"
        user.send_welcome_email = 0
        user.insert(ignore_permissions=True)
        user.add_roles("A2C Bank Agent", "A2C Administrator")
        
        # Set password
        frappe.utils.password.update_password(bank_email, "Test@123")
        print(f"Created user {bank_email}")
    else:
        frappe.utils.password.update_password(bank_email, "Test@123")
        user = frappe.get_doc("User", bank_email)
        user.add_roles("A2C Bank Agent", "A2C Administrator")
        print(f"Updated user {bank_email}")

    frappe.db.commit()
