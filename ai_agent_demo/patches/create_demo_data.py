"""
Patch to create demo data for AI Agent Demo tools.

Creates realistic test data with SENSITIVE INFORMATION for:
- analyze_sales_orders: Sales Orders with customers
- check_inventory: Electronic parts inventory
- business_analytics: Aggregated business data
- check_customer_credit_history: Sales Invoices and Payment Entries with a
  differentiated payment profile per customer (on-time, late, overdue, partial)

PURPOSE: Demonstrates AI data anonymization capabilities
- Contains real-looking addresses, phone numbers, emails
- Includes personal contact information and tax IDs
- Shows how sensitive data gets anonymized before AI processing
- Test data for GDPR compliance demonstration

Scenario: TechParts Inc. - electronics distributor with customer data
"""
from __future__ import annotations

import frappe
from frappe.utils import add_days, flt, today, nowdate


def execute():
    """Execute the patch to create demo data."""
    try:
        # Check prerequisites first
        if not _check_prerequisites():
            print("❌ Prerequisites not met. Skipping patch.")
            return

        # Create customers with proper Address and Contact relationships
        customers = _create_demo_customers()

        # Create electronic parts inventory
        items = _create_demo_items()

        # Create sales orders using customers and items
        _create_demo_sales_orders(customers, items)

        # Create the payment history that the credit analysis tool reads
        invoices = _create_demo_sales_invoices(customers)

        frappe.db.commit()
        print("✅ AI Agent Demo data created successfully!")
        print(f"Created {len(customers)} customers with addresses and contacts")
        print(f"Created {len(items)} electronic parts items")
        print(f"Created {invoices} sales invoices with payment history")

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Failed to create demo data: {str(e)}")
        print(f"❌ Error creating demo data: {str(e)}")


def _create_demo_customers() -> list[str]:
    """Create demo customer companies with SENSITIVE DATA for anonymization testing.

    Contains realistic sensitive information to demonstrate AI data anonymization:
    - Real-looking addresses, phone numbers, emails
    - Contact persons with names
    - Tax IDs and business details

    This sensitive data will be anonymized by the agent before AI processing.
    """
    customers_data = [
        {
            "customer_name": "ElectroTech Solutions",
            "customer_type": "Company",
            "customer_group": "Commercial",
            "territory": "All Territories",
            "tax_id": "12-3456789",
            "credit_limit": 75000,
            "address_data": {
                "address_title": "ElectroTech Solutions - Head Office",
                "address_type": "Office",
                "address_line1": "1425 Madison Avenue",
                "city": "New York",
                "state": "NY",
                "pincode": "10029",
                "country": "United States",
                "phone": "+1-555-0123",
                "email_id": "orders@electrotech-solutions.com"
            },
            "contact_data": {
                "first_name": "John",
                "last_name": "Mitchell",
                "email_id": "john.mitchell@electrotech-solutions.com",
                "phone": "+1-555-0123",
                "mobile_no": "+1-555-0124",
                "designation": "Procurement Manager",
                "company_name": "ElectroTech Solutions"
            }
        },
        {
            "customer_name": "AutoParts Manufacturing",
            "customer_type": "Company",
            "customer_group": "Commercial",
            "territory": "All Territories",
            "tax_id": "98-7654321",
            "credit_limit": 120000,
            "address_data": {
                "address_title": "AutoParts Manufacturing - Main Plant",
                "address_type": "Warehouse",
                "address_line1": "3847 Industrial Blvd",
                "city": "Detroit",
                "state": "MI",
                "pincode": "48201",
                "country": "United States",
                "phone": "+1-555-0156",
                "email_id": "procurement@autoparts-mfg.com"
            },
            "contact_data": {
                "first_name": "Sarah",
                "last_name": "Johnson",
                "email_id": "sarah.johnson@autoparts-mfg.com",
                "phone": "+1-555-0156",
                "mobile_no": "+1-555-0157",
                "designation": "Supply Chain Manager",
                "company_name": "AutoParts Manufacturing"
            }
        },
        {
            "customer_name": "TechnoServices Corp",
            "customer_type": "Company",
            "customer_group": "Commercial",
            "territory": "All Territories",
            "tax_id": "55-9988776",
            "credit_limit": 85000,
            "address_data": {
                "address_title": "TechnoServices Corp - HQ",
                "address_type": "Office",
                "address_line1": "789 Innovation Drive",
                "city": "Austin",
                "state": "TX",
                "pincode": "73301",
                "country": "United States",
                "phone": "+1-555-0189",
                "email_id": "buying@technoservices.net"
            },
            "contact_data": {
                "first_name": "Michael",
                "last_name": "Rodriguez",
                "email_id": "michael.rodriguez@technoservices.net",
                "phone": "+1-555-0189",
                "mobile_no": "+1-555-0190",
                "designation": "Technical Director",
                "company_name": "TechnoServices Corp"
            }
        },
        {
            "customer_name": "InnovateLab Inc",
            "customer_type": "Company",
            "customer_group": "Commercial",
            "territory": "All Territories",
            "tax_id": "77-1122334",
            "credit_limit": 95000,
            "address_data": {
                "address_title": "InnovateLab Inc - Research Center",
                "address_type": "Office",
                "address_line1": "2156 Research Park Way",
                "city": "San Jose",
                "state": "CA",
                "pincode": "95134",
                "country": "United States",
                "phone": "+1-555-0167",
                "email_id": "supplies@innovatelab.org"
            },
            "contact_data": {
                "first_name": "Lisa",
                "last_name": "Chen",
                "email_id": "lisa.chen@innovatelab.org",
                "phone": "+1-555-0167",
                "mobile_no": "+1-555-0168",
                "designation": "Research Manager",
                "company_name": "InnovateLab Inc"
            }
        },
        {
            "customer_name": "CircuitSystems LLC",
            "customer_type": "Company",
            "customer_group": "Commercial",
            "territory": "All Territories",
            "tax_id": "44-5566778",
            "credit_limit": 110000,
            "address_data": {
                "address_title": "CircuitSystems LLC - Production Facility",
                "address_type": "Warehouse",
                "address_line1": "4523 Electronics Parkway",
                "city": "Phoenix",
                "state": "AZ",
                "pincode": "85008",
                "country": "United States",
                "phone": "+1-555-0134",
                "email_id": "orders@circuitsystems.biz"
            },
            "contact_data": {
                "first_name": "Robert",
                "last_name": "Davis",
                "email_id": "robert.davis@circuitsystems.biz",
                "phone": "+1-555-0134",
                "mobile_no": "+1-555-0135",
                "designation": "Production Manager",
                "company_name": "CircuitSystems LLC"
            }
        },
        {
            "customer_name": "MicroDevices Partners",
            "customer_type": "Company",
            "customer_group": "Commercial",
            "territory": "All Territories",
            "tax_id": "33-4455667",
            "credit_limit": 60000,
            "address_data": {
                "address_title": "MicroDevices Partners - Tech Hub",
                "address_type": "Office",
                "address_line1": "1678 Technology Center",
                "city": "Seattle",
                "state": "WA",
                "pincode": "98109",
                "country": "United States",
                "phone": "+1-555-0198",
                "email_id": "purchasing@microdevices.co"
            },
            "contact_data": {
                "first_name": "Amanda",
                "last_name": "Wilson",
                "email_id": "amanda.wilson@microdevices.co",
                "phone": "+1-555-0198",
                "mobile_no": "+1-555-0199",
                "designation": "Purchasing Director",
                "company_name": "MicroDevices Partners"
            }
        }
    ]

    created_customers = []

    for customer_data in customers_data:
        customer_name = customer_data["customer_name"]

        # Check if customer exists and needs address/contact setup
        if frappe.db.exists("Customer", customer_name):
            customer_doc = frappe.get_doc("Customer", customer_name)

            # If customer already has proper address, contact, and credit limits, skip
            has_credit_limits = len(customer_doc.credit_limits) > 0
            if (customer_doc.customer_primary_address and
                customer_doc.customer_primary_contact and
                has_credit_limits):
                created_customers.append(customer_name)
                continue
            else:
                # Customer exists but needs address/contact/credit setup - will update below
                pass

        try:
            # Step 1: Create Address
            address_doc = frappe.get_doc({
                "doctype": "Address",
                **customer_data["address_data"]
            })
            address_doc.insert(ignore_permissions=True)
            print(f"Created address: {address_doc.name}")

            # Step 2: Create Contact with proper email and phone child tables
            contact_data = customer_data["contact_data"]

            contact_doc = frappe.new_doc("Contact")
            contact_doc.first_name = contact_data["first_name"]
            contact_doc.last_name = contact_data["last_name"]
            contact_doc.designation = contact_data.get("designation", "")
            contact_doc.company_name = contact_data.get("company_name", "")
            contact_doc.address = address_doc.name

            # Add email using child table
            if contact_data.get("email_id"):
                contact_doc.append("email_ids", {
                    "email_id": contact_data["email_id"],
                    "is_primary": 1
                })

            # Add phone using child table
            if contact_data.get("phone"):
                contact_doc.append("phone_nos", {
                    "phone": contact_data["phone"],
                    "is_primary_phone": 1
                })

            # Add mobile using child table
            if contact_data.get("mobile_no"):
                contact_doc.append("phone_nos", {
                    "phone": contact_data["mobile_no"],
                    "is_primary_mobile_no": 1
                })

            contact_doc.insert(ignore_permissions=True)
            print(f"Created contact: {contact_doc.name}")

            # Step 3: Create or update Customer with references to Address and Contact
            if frappe.db.exists("Customer", customer_name):
                customer_doc = frappe.get_doc("Customer", customer_name)
                customer_doc.customer_primary_address = address_doc.name
                customer_doc.customer_primary_contact = contact_doc.name
                # Add credit limit
                customer_doc.append("credit_limits", {
                    "company": frappe.defaults.get_global_default("company") or "demo",
                    "credit_limit": customer_data["credit_limit"]
                })
                customer_doc.save(ignore_permissions=True)
                print(f"Updated customer: {customer_doc.name}")
            else:
                customer_doc = frappe.get_doc({
                    "doctype": "Customer",
                    "customer_name": customer_name,
                    "customer_type": customer_data["customer_type"],
                    "customer_group": customer_data["customer_group"],
                    "territory": customer_data["territory"],
                    "tax_id": customer_data["tax_id"],
                    "customer_primary_address": address_doc.name,
                    "customer_primary_contact": contact_doc.name
                })
                # Add credit limit
                customer_doc.append("credit_limits", {
                    "company": frappe.defaults.get_global_default("company") or "demo",
                    "credit_limit": customer_data["credit_limit"]
                })
                customer_doc.insert(ignore_permissions=True)
                print(f"Created customer: {customer_doc.name}")

            # Step 4: Add Dynamic Links from Address to Customer
            address_doc.append("links", {
                "link_doctype": "Customer",
                "link_name": customer_doc.name,
                "link_title": customer_name
            })
            address_doc.save(ignore_permissions=True)

            # Step 5: Add Dynamic Links from Contact to Customer
            contact_doc.append("links", {
                "link_doctype": "Customer",
                "link_name": customer_doc.name,
                "link_title": customer_name
            })
            contact_doc.save(ignore_permissions=True)

            created_customers.append(customer_name)

        except Exception as e:
            frappe.db.rollback()
            print(f"Warning: Could not create customer {customer_name}: {e}")

    return created_customers


def _create_demo_items() -> list[str]:
    """Create demo electronic parts inventory."""
    items_data = [
        {
            "item_code": "ATMEGA328P",
            "item_name": "ATmega328P Microcontroller",
            "item_group": "Products",
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "standard_rate": 15.00,
            "valuation_rate": 9.75,
            "description": "8-bit AVR microcontroller with 32KB flash memory"
        },
        {
            "item_code": "CAP-100UF",
            "item_name": "100µF Electrolytic Capacitor",
            "item_group": "Products",
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "standard_rate": 2.50,
            "valuation_rate": 2.10,
            "description": "100µF 25V electrolytic capacitor"
        },
        {
            "item_code": "LED-5MM-RED",
            "item_name": "5mm Red LED",
            "item_group": "Products",
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "standard_rate": 1.20,
            "valuation_rate": 0.66,
            "description": "5mm red LED diode, 20mA forward current"
        },
        {
            "item_code": "RES-10K",
            "item_name": "10kΩ Carbon Resistor",
            "item_group": "Products",
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "standard_rate": 0.50,
            "valuation_rate": 0.30,
            "description": "10kΩ ±5% carbon film resistor, 1/4W"
        },
        {
            "item_code": "ESP32-DEV",
            "item_name": "ESP32 Development Board",
            "item_group": "Products",
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "standard_rate": 25.00,
            "valuation_rate": 19.50,
            "description": "ESP32 WiFi + Bluetooth development board"
        },
        {
            "item_code": "LCD-16X2",
            "item_name": "16x2 Character LCD Display",
            "item_group": "Products",
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "standard_rate": 12.50,
            "valuation_rate": 7.00,
            "description": "16x2 character LCD display with HD44780 controller"
        },
        {
            "item_code": "SERVO-SG90",
            "item_name": "SG90 Micro Servo Motor",
            "item_group": "Products",
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "standard_rate": 8.00,
            "valuation_rate": 6.80,
            "description": "SG90 9g micro servo motor, 180° rotation"
        },
        {
            "item_code": "SENSOR-DHT22",
            "item_name": "DHT22 Temperature Humidity Sensor",
            "item_group": "Products",
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "standard_rate": 18.00,
            "valuation_rate": 10.80,
            "description": "DHT22 digital temperature and humidity sensor"
        },
        {
            "item_code": "BREADBOARD-400",
            "item_name": "400-point Breadboard",
            "item_group": "Products",
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "standard_rate": 5.00,
            "valuation_rate": 3.25,
            "description": "400-point solderless breadboard for prototyping"
        },
        {
            "item_code": "JUMPER-MM",
            "item_name": "Male-to-Male Jumper Wires (40pcs)",
            "item_group": "Products",
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "standard_rate": 4.50,
            "valuation_rate": 2.70,
            "description": "40-piece set of male-to-male jumper wires, 20cm"
        }
    ]

    created_items = []

    for item_data in items_data:
        if not frappe.db.exists("Item", item_data["item_code"]):
            try:
                item = frappe.get_doc({
                    "doctype": "Item",
                    **item_data
                })
                item.insert(ignore_permissions=True)
                created_items.append(item.name)
                print(f"Created item: {item.item_code} - {item.item_name}")
            except Exception as e:
                print(f"Warning: Could not create item {item_data['item_code']}: {e}")
        else:
            _backfill_item_valuation_rate(item_data)
            created_items.append(item_data["item_code"])

    return created_items


def _backfill_item_valuation_rate(item_data: dict) -> None:
    """Set the cost on an item that predates the valuation_rate in this patch.

    Margin analysis compares selling price against valuation_rate. Items created
    by an earlier run have no cost, which makes every margin read as zero.
    """
    item_code = item_data["item_code"]
    valuation_rate = item_data.get("valuation_rate")

    if not valuation_rate or frappe.db.get_value("Item", item_code, "valuation_rate"):
        return

    frappe.db.set_value("Item", item_code, "valuation_rate", valuation_rate)
    print(f"Backfilled valuation rate for {item_code}: {valuation_rate}")


def _create_demo_sales_orders(customers: list[str], items: list[str]) -> None:
    """Create demo sales orders from recent dates.

    All documents use the company's default currency so that sales orders,
    invoices and credit limits stay directly comparable in the analysis.
    """
    if not customers or not items:
        print("Warning: No customers or items available for sales orders")
        return

    company = _get_demo_company()
    if not company:
        print("Warning: No company found - skipping sales orders")
        return

    currency = _get_demo_currency(company)

    # Sample sales orders data (recent dates). Order values are kept in the same
    # range as each customer's invoiced amounts, so recent orders read as a
    # continuation of the payment history rather than as a collapse in volume.
    sales_orders = [
        {
            "transaction_date": add_days(today(), -5),
            "customer": customers[0],  # ElectroTech Solutions - ~5 050
            "items": [
                {"item_code": "ATMEGA328P", "qty": 250, "rate": 15.00},
                {"item_code": "CAP-100UF", "qty": 400, "rate": 2.50},
                {"item_code": "RES-10K", "qty": 600, "rate": 0.50},
            ],
            "delivery_date": add_days(today(), 7)
        },
        {
            "transaction_date": add_days(today(), -3),
            "customer": customers[1],  # AutoParts Manufacturing - ~8 950
            "items": [
                {"item_code": "ESP32-DEV", "qty": 250, "rate": 25.00},
                {"item_code": "SENSOR-DHT22", "qty": 150, "rate": 18.00},
            ],
            "delivery_date": add_days(today(), 5)
        },
        {
            "transaction_date": add_days(today(), -7),
            "customer": customers[2],  # TechnoServices Corp - ~15 900
            "items": [
                {"item_code": "LCD-16X2", "qty": 600, "rate": 12.50},
                {"item_code": "SERVO-SG90", "qty": 800, "rate": 8.00},
                {"item_code": "BREADBOARD-400", "qty": 400, "rate": 5.00},
            ],
            "delivery_date": add_days(today(), 3)
        },
        {
            "transaction_date": add_days(today(), -10),
            "customer": customers[3],  # InnovateLab Inc - ~6 525
            "items": [
                {"item_code": "LED-5MM-RED", "qty": 3000, "rate": 1.20},
                {"item_code": "JUMPER-MM", "qty": 650, "rate": 4.50},
            ],
            "delivery_date": add_days(today(), 2)
        },
        {
            "transaction_date": add_days(today(), -2),
            "customer": customers[4],  # CircuitSystems LLC - ~15 000
            "items": [
                {"item_code": "ATMEGA328P", "qty": 600, "rate": 15.00},
                {"item_code": "ESP32-DEV", "qty": 240, "rate": 25.00},
            ],
            "delivery_date": add_days(today(), 8)
        },
        {
            "transaction_date": add_days(today(), -12),
            "customer": customers[5],  # MicroDevices Partners - ~13 100
            "items": [
                {"item_code": "SENSOR-DHT22", "qty": 450, "rate": 18.00},
                {"item_code": "LCD-16X2", "qty": 300, "rate": 12.50},
                {"item_code": "CAP-100UF", "qty": 500, "rate": 2.50},
            ],
            "delivery_date": today()  # Already delivered
        }
    ]

    for order_data in sales_orders:
        try:
            # Idempotency: a rerun must not stack duplicate orders onto a customer
            if frappe.db.exists("Sales Order", {"customer": order_data["customer"], "docstatus": 1}):
                print(f"Skipping sales order for {order_data['customer']} - order already present")
                continue

            # Create sales order
            sales_order = frappe.get_doc({
                "doctype": "Sales Order",
                "customer": order_data["customer"],
                "company": company,
                "transaction_date": order_data["transaction_date"],
                "delivery_date": order_data["delivery_date"],
                "currency": currency,
                "conversion_rate": 1.0,
                "items": []
            })

            # Add items to sales order
            total = 0
            for item in order_data["items"]:
                # Check if item exists
                if frappe.db.exists("Item", item["item_code"]):
                    amount = item["qty"] * item["rate"]
                    total += amount

                    sales_order.append("items", {
                        "item_code": item["item_code"],
                        "qty": item["qty"],
                        "rate": item["rate"],
                        "amount": amount
                    })

            # Set totals
            sales_order.total = total
            sales_order.grand_total = total

            sales_order.insert(ignore_permissions=True)

            # Submit the order (status = 1)
            sales_order.submit()

            print(f"Created Sales Order: {sales_order.name} for {order_data['customer']} ({total:.2f} {currency})")

        except Exception as e:
            print(f"Warning: Could not create sales order for {order_data['customer']}: {e}")


# Payment profile per customer index, driving the credit history demo.
# Each invoice: days_ago (posting date offset), credit_days (posting -> due date),
# items, and settlement: paid_after_due in days (negative = early), None = unpaid,
# paid_fraction < 1.0 = partially settled.
INVOICE_PLANS = {
    # ElectroTech Solutions - exemplary payer, always settles on or before due date
    0: [
        {"days_ago": 170, "credit_days": 30, "items": [("ATMEGA328P", 400, 15.00)], "paid_after_due": -3},
        {"days_ago": 120, "credit_days": 30, "items": [("ESP32-DEV", 200, 25.00)], "paid_after_due": 0},
        {"days_ago": 70, "credit_days": 30, "items": [("SENSOR-DHT22", 250, 18.00)], "paid_after_due": -6},
        {"days_ago": 45, "credit_days": 30, "items": [("LCD-16X2", 300, 12.50)], "paid_after_due": -2},
    ],
    # AutoParts Manufacturing - reliable but consistently ~10 days late
    1: [
        {"days_ago": 160, "credit_days": 45, "items": [("ESP32-DEV", 400, 25.00)], "paid_after_due": 10},
        {"days_ago": 110, "credit_days": 45, "items": [("SENSOR-DHT22", 500, 18.00)], "paid_after_due": 14},
        {"days_ago": 60, "credit_days": 45, "items": [("ATMEGA328P", 600, 15.00)], "paid_after_due": 9},
        {"days_ago": 20, "credit_days": 45, "items": [("SERVO-SG90", 800, 8.00)], "paid_after_due": None},
    ],
    # TechnoServices Corp - HIGH RISK: heavy overdue exposure against the limit
    2: [
        {"days_ago": 190, "credit_days": 30, "items": [("LCD-16X2", 800, 12.50)], "paid_after_due": 55},
        {"days_ago": 150, "credit_days": 30, "items": [("SERVO-SG90", 1200, 8.00)], "paid_after_due": 48},
        {"days_ago": 130, "credit_days": 30, "items": [("ESP32-DEV", 900, 25.00)], "paid_after_due": None},
        {"days_ago": 80, "credit_days": 30, "items": [("ATMEGA328P", 1500, 15.00)], "paid_after_due": None},
        {"days_ago": 35, "credit_days": 30, "items": [("SENSOR-DHT22", 900, 18.00)], "paid_after_due": None},
    ],
    # InnovateLab Inc - mixed record, current exposure not yet due
    3: [
        {"days_ago": 140, "credit_days": 30, "items": [("LED-5MM-RED", 4000, 1.20)], "paid_after_due": 2},
        {"days_ago": 90, "credit_days": 30, "items": [("JUMPER-MM", 1000, 4.50)], "paid_after_due": 25},
        {"days_ago": 30, "credit_days": 60, "items": [("BREADBOARD-400", 2000, 5.00)], "paid_after_due": None},
    ],
    # CircuitSystems LLC - one partially settled invoice left hanging
    4: [
        {"days_ago": 175, "credit_days": 30, "items": [("ATMEGA328P", 1000, 15.00)], "paid_after_due": 20},
        {
            "days_ago": 100,
            "credit_days": 30,
            "items": [("ESP32-DEV", 800, 25.00)],
            "paid_after_due": 35,
            "paid_fraction": 0.5,
        },
        {"days_ago": 45, "credit_days": 30, "items": [("CAP-100UF", 4000, 2.50)], "paid_after_due": None},
    ],
    # MicroDevices Partners - MEDIUM RISK: chronic delays + high limit utilisation
    5: [
        {"days_ago": 165, "credit_days": 30, "items": [("SENSOR-DHT22", 500, 18.00)], "paid_after_due": 22},
        {"days_ago": 115, "credit_days": 30, "items": [("LCD-16X2", 600, 12.50)], "paid_after_due": 28},
        {"days_ago": 65, "credit_days": 30, "items": [("CAP-100UF", 6000, 2.50)], "paid_after_due": None},
        {"days_ago": 18, "credit_days": 45, "items": [("ESP32-DEV", 800, 25.00)], "paid_after_due": None},
    ],
}


def _get_demo_company() -> str | None:
    """Return the company used for demo accounting documents."""
    company = frappe.defaults.get_global_default("company")
    if company and frappe.db.exists("Company", company):
        return company

    companies = frappe.get_all("Company", pluck="name", limit_page_length=1)
    return companies[0] if companies else None


def _get_demo_currency(company: str) -> str:
    """Return the company default currency used by every demo document."""
    return frappe.db.get_value("Company", company, "default_currency") or "USD"


def _get_cash_account(company: str) -> str | None:
    """Return a non-group Cash or Bank account for the given company."""
    accounts = frappe.get_all(
        "Account",
        filters={"company": company, "is_group": 0, "account_type": ["in", ["Cash", "Bank"]]},
        pluck="name",
        order_by="account_type asc",
        limit_page_length=1,
    )
    return accounts[0] if accounts else None


def _get_income_account(company: str) -> str | None:
    """Return a non-group income account for the given company."""
    accounts = frappe.get_all(
        "Account",
        filters={"company": company, "is_group": 0, "root_type": "Income"},
        pluck="name",
        limit_page_length=1,
    )
    return accounts[0] if accounts else None


def _create_demo_sales_invoices(customers: list[str]) -> int:
    """Create sales invoices and matching payment entries for each demo customer.

    The credit analysis tool derives payment behaviour from Sales Invoice and
    Payment Entry records. Without them every customer looks debt free, so the
    demo plan below gives each customer a distinct, verifiable payment profile.

    Args:
        customers: Ordered list of customer names as returned by _create_demo_customers.

    Returns:
        Number of sales invoices created by this run.
    """
    company = _get_demo_company()
    if not company:
        print("Warning: No company found - skipping sales invoices")
        return 0

    income_account = _get_income_account(company)
    cost_center = frappe.db.get_value("Company", company, "cost_center")
    currency = _get_demo_currency(company)
    created = 0

    for index, plan in INVOICE_PLANS.items():
        if index >= len(customers):
            continue

        customer = customers[index]

        # Idempotency: never stack a second payment history onto the same customer
        if frappe.db.exists("Sales Invoice", {"customer": customer, "docstatus": 1}):
            print(f"Skipping invoices for {customer} - history already present")
            continue

        for invoice_plan in plan:
            invoice = _create_single_invoice(
                customer, invoice_plan, company, currency, income_account, cost_center
            )
            if not invoice:
                continue

            created += 1
            if invoice_plan.get("paid_after_due") is not None:
                _create_payment_for_invoice(invoice, invoice_plan, company)

    return created


def _create_single_invoice(
    customer: str,
    invoice_plan: dict,
    company: str,
    currency: str,
    income_account: str | None,
    cost_center: str | None,
):
    """Create and submit one backdated sales invoice. Returns the document or None."""
    try:
        posting_date = add_days(today(), -invoice_plan["days_ago"])

        invoice = frappe.new_doc("Sales Invoice")
        invoice.customer = customer
        invoice.company = company
        invoice.currency = currency
        invoice.conversion_rate = 1.0
        invoice.set_posting_time = 1
        invoice.posting_date = posting_date
        invoice.due_date = add_days(posting_date, invoice_plan["credit_days"])
        invoice.update_stock = 0

        for item_code, qty, rate in invoice_plan["items"]:
            if not frappe.db.exists("Item", item_code):
                continue

            row = {"item_code": item_code, "qty": qty, "rate": rate}
            if income_account:
                row["income_account"] = income_account
            if cost_center:
                row["cost_center"] = cost_center
            invoice.append("items", row)

        if not invoice.items:
            print(f"Warning: No valid items for invoice of {customer}")
            return None

        invoice.insert(ignore_permissions=True)
        invoice.submit()

        print(f"Created Sales Invoice: {invoice.name} for {customer} ({invoice.grand_total:.2f})")
        return invoice

    except Exception as e:
        print(f"Warning: Could not create sales invoice for {customer}: {e}")
        return None


def _create_payment_for_invoice(invoice, invoice_plan: dict, company: str) -> None:
    """Settle an invoice with a backdated payment entry.

    The payment posting date is derived from the invoice due date plus the
    configured delay, so avg_payment_delay_days becomes a real measurement
    instead of a side effect of record modification timestamps.
    """
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    try:
        cash_account = _get_cash_account(company)
        if not cash_account:
            print(f"Warning: No cash/bank account for {company} - invoice {invoice.name} left unpaid")
            return

        paid_fraction = invoice_plan.get("paid_fraction", 1.0)
        allocated = flt(invoice.grand_total) * paid_fraction

        payment = get_payment_entry("Sales Invoice", invoice.name, party_amount=allocated)
        payment.paid_to = cash_account
        payment.posting_date = add_days(invoice.due_date, invoice_plan["paid_after_due"])
        payment.reference_no = f"DEMO-{invoice.name}"
        payment.reference_date = payment.posting_date

        payment.insert(ignore_permissions=True)
        payment.submit()

        print(f"  Payment {payment.name}: {allocated:.2f} on {payment.posting_date}")

    except Exception as e:
        print(f"Warning: Could not create payment for {invoice.name}: {e}")


def _check_prerequisites() -> bool:
    """Check if required DocTypes exist."""
    required_doctypes = [
        "Customer",
        "Item",
        "Sales Order",
        "Sales Invoice",
        "Payment Entry",
        "Address",
        "Contact",
    ]

    for doctype in required_doctypes:
        if not frappe.db.exists("DocType", doctype):
            print(f"❌ Required DocType '{doctype}' not found")
            return False

    print("✅ All required DocTypes found")
    return True