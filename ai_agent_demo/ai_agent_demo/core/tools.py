"""
AI Agent Tools for Business Risk Analysis.

This module contains tools for analyzing business data with privacy protection.
"""
from __future__ import annotations

import json
import requests
from datetime import datetime, timedelta

import frappe
from frappe.utils import flt, cint, getdate

from .pseudonymizer import BusinessPseudonymizer


def get_available_tools() -> list[dict]:
    """
    Get list of available tools for the AI agent.

    Returns:
        List of tool metadata dictionaries
    """
    return [
        {
            "name": "analyze_sales_order",
            "description": "Analyze sales order for commercial, credit, margin, and delivery risks with data pseudonymization",
            "schema": {
                "type": "object",
                "properties": {
                    "sales_order_id": {
                        "type": "string",
                        "description": "Sales Order ID to analyze (e.g., 'SAL-ORD-2026-00025')"
                    }
                },
                "required": ["sales_order_id"]
            }
        },
        {
            "name": "check_customer_credit_history",
            "description": "Check customer's payment history, outstanding invoices, and credit risk indicators",
            "schema": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name to check credit history for"
                    }
                },
                "required": ["customer_name"]
            }
        }
    ]


class BaseTool:
    """Base class for AI agent tools."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def execute(self, **kwargs) -> dict:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool parameters

        Returns:
            Tool execution result
        """
        raise NotImplementedError("Tool execution must be implemented")

    def get_schema(self) -> dict:
        """
        Get tool parameter schema.

        Returns:
            JSON schema for tool parameters
        """
        return {
            "type": "object",
            "properties": {},
            "required": []
        }


class SalesOrderAnalyzer(BaseTool):
    """Analyze sales orders for business risks with data protection."""

    def __init__(self):
        super().__init__(
            name="analyze_sales_order",
            description="Analyze sales order for commercial, credit, margin, and delivery risks"
        )

    def _fetch_sales_order_data(self, sales_order_id: str) -> dict:
        """Fetch sales order data from Frappe/ERPNext."""
        try:
            if not frappe.db.exists("Sales Order", sales_order_id):
                return {"error": f"Sales Order {sales_order_id} not found"}

            # Get sales order document
            sales_order = frappe.get_doc("Sales Order", sales_order_id)

            # Get customer data
            customer_doc = frappe.get_doc("Customer", sales_order.customer) if sales_order.customer else None

            # Get customer's primary contact and address
            primary_contact = None
            primary_address = None

            if customer_doc:
                if customer_doc.customer_primary_contact:
                    primary_contact = frappe.get_doc("Contact", customer_doc.customer_primary_contact)
                if customer_doc.customer_primary_address:
                    primary_address = frappe.get_doc("Address", customer_doc.customer_primary_address)

            # Calculate customer exposure (sum of outstanding invoices)
            current_exposure = frappe.db.sql("""
                SELECT SUM(outstanding_amount)
                FROM `tabSales Invoice`
                WHERE customer = %s AND outstanding_amount > 0
            """, [sales_order.customer])[0][0] or 0

            # Get historical discount average for customer
            historical_discount = frappe.db.sql("""
                SELECT AVG(additional_discount_percentage) as avg_discount
                FROM `tabSales Order`
                WHERE customer = %s AND name != %s AND docstatus = 1
                LIMIT 10
            """, [sales_order.customer, sales_order_id])
            avg_discount = historical_discount[0][0] if historical_discount and historical_discount[0][0] else 0

            # Build structured data
            return {
                "sales_order_id": sales_order.name,
                "customer": {
                    "name": customer_doc.customer_name if customer_doc else sales_order.customer,
                    "tax_id": customer_doc.tax_id if customer_doc else "N/A",
                    "email": primary_contact.email_id if primary_contact else "N/A",
                    "phone": primary_contact.mobile_no if primary_contact else "N/A",
                    "address": self._format_address(primary_address) if primary_address else "N/A",
                    "credit_limit": flt(customer_doc.credit_limits[0].credit_limit if customer_doc and customer_doc.credit_limits else 0),
                    "current_exposure": flt(current_exposure),
                    "payment_terms": sales_order.payment_terms_template or "N/A"
                },
                "sales_rep": {
                    "name": frappe.db.get_value("User", sales_order.owner, "full_name") or sales_order.owner,
                    "email": sales_order.owner
                },
                "order": {
                    "currency": sales_order.currency,
                    "total_net": flt(sales_order.net_total),
                    "requested_delivery_date": str(sales_order.delivery_date) if sales_order.delivery_date else "N/A",
                    "shipping_address": self._get_shipping_address(sales_order),
                    "discount_percent": flt(sales_order.additional_discount_percentage),
                    "historical_avg_discount_percent": flt(avg_discount)
                },
                "items": [
                    {
                        "sku": item.item_code,
                        "description": item.item_name or item.description,
                        "quantity": flt(item.qty),
                        "unit_price": flt(item.rate),
                        "unit_cost": self._get_item_cost(item.item_code),
                        "margin_percent": self._calculate_margin(item.rate, self._get_item_cost(item.item_code))
                    }
                    for item in sales_order.items
                ],
                "notes": (sales_order.terms or "") + " " + (getattr(sales_order, 'remarks', '') or "")
            }

        except Exception as e:
            return {"error": f"Error fetching sales order data: {str(e)}"}

    def _format_address(self, address_doc) -> str:
        """Format address document to string."""
        if not address_doc:
            return "N/A"

        parts = []
        if address_doc.address_line1:
            parts.append(address_doc.address_line1)
        if address_doc.city and address_doc.pincode:
            parts.append(f"{address_doc.pincode} {address_doc.city}")

        return ", ".join(parts)

    def _get_shipping_address(self, sales_order) -> str:
        """Get shipping address for sales order."""
        if sales_order.shipping_address_name:
            shipping_doc = frappe.get_doc("Address", sales_order.shipping_address_name)
            return self._format_address(shipping_doc)
        return "Same as billing"

    def _get_item_cost(self, item_code: str) -> float:
        """Get item standard cost."""
        cost = frappe.db.get_value("Item", item_code, "standard_rate")
        return flt(cost) if cost else 0

    def _calculate_margin(self, price: float, cost: float) -> float:
        """Calculate margin percentage."""
        if not price or not cost:
            return 0
        return ((price - cost) / price) * 100

    def _create_analysis_prompt(self, pseudonymized_data: dict) -> str:
        """Create analysis prompt for LLM."""
        return f"""Analyze the following sales order for commercial, credit, margin, and delivery risk.

Return ONLY a JSON response with this exact structure:
{{
    "risk_level": "low|medium|high",
    "main_risk_factors": ["risk factor 1", "risk factor 2", ...],
    "recommended_actions": ["action 1", "action 2", ...],
    "manual_review_required": true|false,
    "analysis_summary": "brief summary of key findings"
}}

Sales order data:
{json.dumps(pseudonymized_data, indent=2, ensure_ascii=False)}

Focus on:
1. Credit risk (exposure vs limits)
2. Margin risk (unusual discounts/margins)
3. Commercial risk (order patterns, amounts)
4. Delivery/logistics risk (timing, addresses)"""

    def _analyze_with_llm_prompt(self, prompt: str) -> str:
        """Send prompt to LLM for analysis."""
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9
                    }
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "No response from LLM")
            else:
                return f"LLM API error: {response.status_code}"

        except Exception as e:
            return f"Error calling LLM: {str(e)}"

    def _analyze_with_llm(self, pseudonymized_data: dict) -> str:
        """Send pseudonymized data to LLM for analysis (legacy method)."""
        prompt = self._create_analysis_prompt(pseudonymized_data)
        return self._analyze_with_llm_prompt(prompt)

    def execute(self, sales_order_id: str) -> dict:
        """Execute sales order analysis with pseudonymization."""
        pipeline_log = []

        def log_step(step_type: str, message: str, data=None):
            pipeline_log.append({
                "type": step_type,
                "message": message,
                "data": data,
                "timestamp": datetime.now().isoformat()
            })

        try:
            # Step 1: Fetch raw data from ERP
            log_step("input", f"Fetching sales order data for {sales_order_id}")
            raw_data = self._fetch_sales_order_data(sales_order_id)

            if "error" in raw_data:
                return {"error": raw_data["error"], "pipeline_log": pipeline_log}

            # Show detailed raw data
            log_step("data_fetch", "Raw sales order data retrieved from ERP", raw_data)

            # Show sensitive data that will be pseudonymized
            # Create pseudonymizer early to get detection method info
            pseudonymizer = BusinessPseudonymizer(use_ner=True)
            tools_info = pseudonymizer._get_tools_used()

            sensitive_items = {
                "customer_name": raw_data["customer"]["name"],
                "customer_email": raw_data["customer"]["email"],
                "customer_phone": raw_data["customer"]["phone"],
                "customer_address": raw_data["customer"]["address"],
                "sales_rep_name": raw_data["sales_rep"]["name"],
                "sales_rep_email": raw_data["sales_rep"]["email"]
            }

            detection_info = {
                "sensitive_fields": sensitive_items,
                "detection_method": tools_info["primary_method"],
                "nlp_framework": tools_info["nlp_framework"],
                "language_model": tools_info["language_model"],
                "entity_types_supported": tools_info["entity_types"][:10] if tools_info["entity_types"] else [],  # Show first 10
                "custom_patterns": tools_info["custom_patterns"]
            }

            log_step("sensitive_data_detected",
                    f"SENSITIVE DATA DETECTED using {tools_info['primary_method']}",
                    detection_info)

            # Step 2: Pseudonymize sensitive data
            log_step("pseudonymize_start", "Starting data pseudonymization with NER detection for privacy protection")

            # pseudonymizer already created above for detection method info
            pseudonymized_data = pseudonymizer.pseudonymize_sales_order(raw_data)

            # Debug: Show what was actually detected and mapped
            detection_details = []
            for original, token in list(pseudonymizer.mapping.items()):
                detection_details.append(f"'{original}' → {token}")

            log_step("debug_detection", "🔍 DEBUG: What spaCy/patterns detected and mapped", {
                "total_mappings": len(pseudonymizer.mapping),
                "all_mappings": detection_details,
                "spacy_used": getattr(pseudonymizer, '_used_spacy_ner', False),
                "manual_used": getattr(pseudonymizer, '_used_manual_patterns', False)
            })

            # Show examples of pseudonymization
            examples = []
            for original, token in list(pseudonymizer.mapping.items()):
                examples.append(f"{original} → {token}")

            summary = pseudonymizer.get_pseudonymization_summary()
            log_step("pseudonymize_complete",
                    f"Data pseudonymized using {', '.join(summary['detection_methods'])} - sensitive information replaced with tokens",
                    {
                        "summary": summary,
                        "examples": examples,
                        "methods_used": summary['detection_methods'],
                        "tools_used": summary['tools_used']
                    })

            # Show what data is being sent to AI
            log_step("ai_input_data", "Pseudonymized data being sent to AI (safe for processing)", pseudonymized_data)

            # Step 3: LLM Analysis
            log_step("llm_analysis", "Sending pseudonymized data to AI for risk analysis")

            # Create and log the analysis prompt
            analysis_prompt = self._create_analysis_prompt(pseudonymized_data)
            log_step("ai_prompt", "Analysis prompt sent to AI", analysis_prompt)

            llm_response = self._analyze_with_llm_prompt(analysis_prompt)

            # Show AI raw response
            log_step("llm_response", "AI analysis completed - raw response from model", llm_response)

            # Check if response contains tokens
            tokens_in_response = [token for token in pseudonymizer.reverse_mapping.keys() if token in llm_response]
            log_step("token_check", "Checking AI response for pseudonym tokens", {
                "tokens_found": tokens_in_response,
                "needs_depseudonymization": len(tokens_in_response) > 0
            })

            # Step 4: Depseudonymize response
            log_step("depseudonymize", "Restoring original identifiers in analysis results")

            final_response = pseudonymizer.depseudonymize_text(llm_response)

            # Show before/after depseudonymization if changes were made
            if final_response != llm_response:
                changes_made = []
                for token, original in pseudonymizer.reverse_mapping.items():
                    if token in llm_response and token not in final_response:
                        changes_made.append(f"{token} → {original}")

                log_step("depseudonymize_changes", "Token replacements made in final response", {
                    "changes": changes_made[:5],  # Show first 5 changes
                    "total_changes": len(changes_made)
                })

            log_step("final_response", "Final business analysis with original identifiers restored", final_response)
            log_step("complete", "Analysis completed with data protection maintained throughout process")

            return {
                "sales_order_id": sales_order_id,
                "analysis": final_response,
                "pipeline_log": pipeline_log,
                "data_protection": {
                    "sensitive_data_count": len(pseudonymizer.mapping),
                    "pseudonymization_successful": True
                }
            }

        except Exception as e:
            log_step("error", f"Analysis failed: {str(e)}")
            return {"error": str(e), "pipeline_log": pipeline_log}


class CustomerCreditAnalyzer(BaseTool):
    """Check customer credit history and risk indicators with pseudonymization."""

    def __init__(self):
        super().__init__(
            name="check_customer_credit_history",
            description="Check customer payment history and credit risk with data protection"
        )

    def _fetch_customer_data(self, customer_name: str) -> dict:
        """Fetch comprehensive customer data from Frappe/ERPNext."""
        try:
            if not frappe.db.exists("Customer", customer_name):
                return {"error": f"Customer {customer_name} not found"}

            # Get customer document
            customer = frappe.get_doc("Customer", customer_name)

            # Get customer's primary contact and address
            primary_contact = None
            primary_address = None

            if customer.customer_primary_contact:
                primary_contact = frappe.get_doc("Contact", customer.customer_primary_contact)
            if customer.customer_primary_address:
                primary_address = frappe.get_doc("Address", customer.customer_primary_address)

            # Get recent sales orders (last 12 months)
            recent_orders = frappe.db.sql("""
                SELECT
                    name,
                    transaction_date,
                    delivery_date,
                    grand_total,
                    currency,
                    additional_discount_percentage,
                    payment_terms_template,
                    owner
                FROM `tabSales Order`
                WHERE customer = %s
                AND transaction_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                AND docstatus = 1
                ORDER BY transaction_date DESC
                LIMIT 10
            """, [customer_name], as_dict=True)

            # Get outstanding invoices
            outstanding_invoices = frappe.db.sql("""
                SELECT
                    name,
                    posting_date,
                    due_date,
                    grand_total,
                    outstanding_amount,
                    DATEDIFF(CURDATE(), due_date) as days_overdue,
                    currency
                FROM `tabSales Invoice`
                WHERE customer = %s
                AND outstanding_amount > 0
                ORDER BY due_date
                LIMIT 20
            """, [customer_name], as_dict=True)

            # Calculate payment statistics
            payment_stats = frappe.db.sql("""
                SELECT
                    COUNT(*) as total_invoices,
                    SUM(CASE WHEN outstanding_amount = 0 THEN 1 ELSE 0 END) as paid_invoices,
                    AVG(DATEDIFF(modified, due_date)) as avg_payment_delay_days,
                    SUM(outstanding_amount) as total_outstanding,
                    SUM(grand_total) as total_12m_revenue
                FROM `tabSales Invoice`
                WHERE customer = %s
                AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            """, [customer_name], as_dict=True)[0]

            # Build structured data
            return {
                "customer": {
                    "name": customer.customer_name,
                    "tax_id": customer.tax_id if customer.tax_id else "N/A",
                    "email": primary_contact.email_id if primary_contact and primary_contact.email_id else "N/A",
                    "phone": primary_contact.mobile_no if primary_contact and primary_contact.mobile_no else "N/A",
                    "address": self._format_address(primary_address) if primary_address else "N/A",
                    "credit_limit": flt(customer.credit_limits[0].credit_limit if customer.credit_limits else 0),
                    "customer_group": customer.customer_group,
                    "territory": customer.territory
                },
                "payment_history": {
                    "total_invoices_12m": int(payment_stats.total_invoices or 0),
                    "paid_invoices_12m": int(payment_stats.paid_invoices or 0),
                    "payment_ratio_percent": round((payment_stats.paid_invoices / payment_stats.total_invoices * 100) if payment_stats.total_invoices > 0 else 100, 1),
                    "avg_payment_delay_days": round(payment_stats.avg_payment_delay_days or 0, 1),
                    "total_outstanding": flt(payment_stats.total_outstanding or 0),
                    "total_12m_revenue": flt(payment_stats.total_12m_revenue or 0)
                },
                "recent_orders": [
                    {
                        "sales_order_id": order.name,
                        "date": str(order.transaction_date),
                        "amount": flt(order.grand_total),
                        "currency": order.currency,
                        "discount_percent": flt(order.additional_discount_percentage),
                        "payment_terms": order.payment_terms_template or "N/A",
                        "sales_rep": frappe.db.get_value("User", order.owner, "full_name") or order.owner
                    }
                    for order in recent_orders
                ],
                "outstanding_invoices": [
                    {
                        "invoice_id": inv.name,
                        "issue_date": str(inv.posting_date),
                        "due_date": str(inv.due_date),
                        "amount": flt(inv.grand_total),
                        "outstanding": flt(inv.outstanding_amount),
                        "days_overdue": int(inv.days_overdue) if inv.days_overdue and inv.days_overdue > 0 else 0,
                        "currency": inv.currency
                    }
                    for inv in outstanding_invoices
                ]
            }

        except Exception as e:
            return {"error": f"Error fetching customer data: {str(e)}"}

    def _format_address(self, address_doc) -> str:
        """Format address document to string."""
        if not address_doc:
            return "N/A"

        parts = []
        if address_doc.address_line1:
            parts.append(address_doc.address_line1)
        if address_doc.city and address_doc.pincode:
            parts.append(f"{address_doc.pincode} {address_doc.city}")

        return ", ".join(parts)

    def _create_credit_analysis_prompt(self, pseudonymized_data: dict) -> str:
        """Create credit analysis prompt for LLM."""
        return f"""Analyze the following customer's credit and payment history for financial risk assessment.

Return ONLY a JSON response with this exact structure:
{{
    "credit_risk_level": "low|medium|high",
    "main_risk_factors": ["risk factor 1", "risk factor 2", ...],
    "recommended_actions": ["action 1", "action 2", ...],
    "credit_limit_recommendation": "increase|maintain|decrease|suspend",
    "analysis_summary": "brief summary of key findings"
}}

Customer data:
{json.dumps(pseudonymized_data, indent=2, ensure_ascii=False)}

Focus on:
1. Payment behavior and delays
2. Outstanding debt levels vs revenue
3. Credit utilization vs limits
4. Recent order patterns and trends
5. Overall financial stability indicators"""

    def execute(self, customer_name: str) -> dict:
        """Execute customer credit analysis with pseudonymization."""
        pipeline_log = []

        def log_step(step_type: str, message: str, data=None):
            pipeline_log.append({
                "type": step_type,
                "message": message,
                "data": data,
                "timestamp": datetime.now().isoformat()
            })

        try:
            # Step 1: Fetch customer data from ERP
            log_step("input", f"Fetching credit history data for customer: {customer_name}")
            raw_data = self._fetch_customer_data(customer_name)

            if "error" in raw_data:
                return {"error": raw_data["error"], "pipeline_log": pipeline_log}

            # Show detailed raw data
            log_step("data_fetch", "Customer credit and order history retrieved from ERP", raw_data)

            # Show sensitive data that will be pseudonymized
            pseudonymizer = BusinessPseudonymizer(use_ner=True)
            tools_info = pseudonymizer._get_tools_used()

            sensitive_items = {
                "customer_name": raw_data["customer"]["name"],
                "customer_email": raw_data["customer"]["email"],
                "customer_phone": raw_data["customer"]["phone"],
                "customer_address": raw_data["customer"]["address"]
            }

            # Add sales rep names from recent orders
            for i, order in enumerate(raw_data.get("recent_orders", [])):
                if order.get("sales_rep"):
                    sensitive_items[f"sales_rep_{i}"] = order["sales_rep"]

            detection_info = {
                "sensitive_fields": sensitive_items,
                "detection_method": tools_info["primary_method"],
                "nlp_framework": tools_info["nlp_framework"],
                "entity_types_supported": tools_info["entity_types"][:10] if tools_info["entity_types"] else [],
                "custom_patterns": tools_info["custom_patterns"]
            }

            log_step("sensitive_data_detected",
                    f"SENSITIVE DATA DETECTED using {tools_info['primary_method']}",
                    detection_info)

            # Step 2: Pseudonymize sensitive data
            log_step("pseudonymize_start", "Starting data pseudonymization for customer credit analysis")

            pseudonymized_data = pseudonymizer.pseudonymize_customer_data(raw_data)

            # Debug: Show what was detected and mapped
            detection_details = []
            for original, token in list(pseudonymizer.mapping.items()):
                detection_details.append(f"'{original}' → {token}")

            log_step("debug_detection", "🔍 DEBUG: What spaCy/patterns detected and mapped", {
                "total_mappings": len(pseudonymizer.mapping),
                "all_mappings": detection_details,
                "spacy_used": getattr(pseudonymizer, '_used_spacy_ner', False),
                "manual_used": getattr(pseudonymizer, '_used_manual_patterns', False)
            })

            # Show pseudonymization results
            examples = []
            for original, token in list(pseudonymizer.mapping.items()):
                examples.append(f"{original} → {token}")

            summary = pseudonymizer.get_pseudonymization_summary()
            log_step("pseudonymize_complete",
                    f"Customer data pseudonymized using {', '.join(summary['detection_methods'])}",
                    {
                        "summary": summary,
                        "examples": examples,
                        "methods_used": summary['detection_methods']
                    })

            # Show what data is being sent to AI
            log_step("ai_input_data", "Pseudonymized customer data being sent to AI (safe for processing)", pseudonymized_data)

            # Step 3: LLM Analysis
            log_step("llm_analysis", "Sending pseudonymized customer data to AI for credit analysis")

            # Create and log the analysis prompt
            analysis_prompt = self._create_credit_analysis_prompt(pseudonymized_data)
            log_step("ai_prompt", "Credit analysis prompt sent to AI", analysis_prompt)

            llm_response = self._analyze_with_llm_prompt(analysis_prompt)

            # Show AI response
            log_step("llm_response", "AI credit analysis completed - raw response from model", llm_response)

            # Check if response contains tokens
            tokens_in_response = [token for token in pseudonymizer.reverse_mapping.keys() if token in llm_response]
            log_step("token_check", "Checking AI response for pseudonym tokens", {
                "tokens_found": tokens_in_response,
                "needs_depseudonymization": len(tokens_in_response) > 0
            })

            # Step 4: Depseudonymize response
            log_step("depseudonymize", "Restoring original customer identifiers in credit analysis")

            final_response = pseudonymizer.depseudonymize_text(llm_response)

            # Show before/after depseudonymization if changes were made
            if final_response != llm_response:
                changes_made = []
                for token, original in pseudonymizer.reverse_mapping.items():
                    if token in llm_response and token not in final_response:
                        changes_made.append(f"{token} → {original}")

                log_step("depseudonymize_changes", "Token replacements made in final response", {
                    "changes": changes_made[:5],
                    "total_changes": len(changes_made)
                })

            log_step("final_response", "Final credit analysis with original identifiers restored", final_response)
            log_step("complete", "Customer credit analysis completed with data protection maintained")

            return {
                "customer_name": customer_name,
                "analysis": final_response,
                "pipeline_log": pipeline_log,
                "data_protection": {
                    "sensitive_data_count": len(pseudonymizer.mapping),
                    "pseudonymization_successful": True
                }
            }

        except Exception as e:
            log_step("error", f"Credit analysis failed: {str(e)}")
            return {"error": str(e), "pipeline_log": pipeline_log}

    def _analyze_with_llm_prompt(self, prompt: str) -> str:
        """Send prompt to LLM for credit analysis."""
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9
                    }
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "No response from LLM")
            else:
                return f"LLM API error: {response.status_code}"

        except Exception as e:
            return f"Error calling LLM: {str(e)}"


# Tool registry
AVAILABLE_TOOLS = [
    SalesOrderAnalyzer(),
    CustomerCreditAnalyzer()
]


def get_tool_by_name(name: str) -> BaseTool | None:
    """Get tool instance by name."""
    for tool in AVAILABLE_TOOLS:
        if tool.name == name:
            return tool
    return None