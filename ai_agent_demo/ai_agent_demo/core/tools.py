"""
AI Agent Tools for Business Risk Analysis.

This module contains tools for analyzing business data with privacy protection.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import frappe
from frappe.utils import flt, cint, getdate

from .llm_client import LLMClient, LLMError
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

    def __init__(
        self,
        name: str,
        description: str,
        llm_client: LLMClient | None = None,
    ):
        self.name = name
        self.description = description
        self.llm_client = llm_client or LLMClient()

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

    def __init__(self, llm_client: LLMClient | None = None):
        super().__init__(
            name="analyze_sales_order",
            description="Analyze sales order for commercial, credit, margin, and delivery risks",
            llm_client=llm_client,
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

    def _get_item_cost(self, item_code: str) -> float | None:
        """Get item cost for margin analysis.

        Reads valuation_rate, the item's cost. The previous implementation read
        standard_rate, which is the selling price, so every margin came out as
        exactly zero and margin risk could never be detected.

        Args:
            item_code: The item to price.

        Returns:
            Unit cost, or None when no cost is recorded for the item.
        """
        cost = frappe.db.get_value("Item", item_code, "valuation_rate")
        if cost:
            return flt(cost)

        cost = frappe.db.get_value("Item", item_code, "last_purchase_rate")
        return flt(cost) if cost else None

    def _calculate_margin(self, price: float, cost: float | None) -> float | None:
        """Calculate margin percentage.

        Returns None when the margin cannot be computed. Returning 0 would be
        indistinguishable from a genuine zero-margin sale.
        """
        if not price or cost is None:
            return None
        return round(((price - cost) / price) * 100, 1)

    def _create_analysis_prompt(self, pseudonymized_data: dict) -> str:
        """Create analysis prompt for LLM."""
        currency = pseudonymized_data.get("order", {}).get("currency") or "the reporting currency"

        return f"""Analyze the following sales order for commercial, credit, margin, and delivery risk.

GROUNDING RULES - these override everything else:
- Use ONLY the values present in the sales order data below. Do not invent numbers,
  ratings or history that are not in the data.
- All monetary amounts are in {currency}. Always write the amount followed by
  "{currency}". Never use a currency symbol such as $ and never convert values.
- A null or missing value means "not measurable", not zero and not a good result.
- Cite the concrete figure behind every risk factor you report.

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
            return self.llm_client.generate(prompt)
        except LLMError as exc:
            return f"Error calling LLM: {exc}"

    def _analyze_with_llm(self, pseudonymized_data: dict) -> str:
        """Send pseudonymized data to LLM for analysis (legacy method)."""
        prompt = self._create_analysis_prompt(pseudonymized_data)
        return self._analyze_with_llm_prompt(prompt)

    def execute(self, sales_order_id: str) -> dict:
        """Execute sales order analysis with pseudonymization."""
        pipeline_log = []

        def log_step(step_type: str, message: str, data=None):
            entry = {
                "type": step_type,
                "message": message,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            pipeline_log.append(entry)

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

            # Step 3: Build the complete prompt before the single LLM request.
            analysis_prompt = self._create_analysis_prompt(pseudonymized_data)
            log_step("ai_prompt", "Analysis prompt sent to AI", analysis_prompt)

            llm_response = self._analyze_with_llm_prompt(analysis_prompt)

            # Show AI raw response
            log_step(
                "llm_response",
                "AI analysis completed - raw response from model",
                llm_response,
            )

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
                "analysis_for_llm": llm_response,
                "pseudonym_reverse_mapping": dict(pseudonymizer.reverse_mapping),
                # Numeric-only figures for the answer formatting step, mirroring the
                # credit tool. Without them the formatter has no order value to quote
                # and invents one. Nothing here identifies the customer.
                "metrics": {
                    "currency": raw_data["order"]["currency"],
                    "order_total_net": raw_data["order"]["total_net"],
                    "discount_percent": raw_data["order"]["discount_percent"],
                    "historical_avg_discount_percent": raw_data["order"]["historical_avg_discount_percent"],
                    "customer_credit_limit": raw_data["customer"]["credit_limit"],
                    "customer_current_exposure": raw_data["customer"]["current_exposure"],
                    "requested_delivery_date": raw_data["order"]["requested_delivery_date"],
                    "item_count": len(raw_data["items"]),
                    "min_item_margin_percent": min(
                        (
                            item["margin_percent"]
                            for item in raw_data["items"]
                            if item["margin_percent"] is not None
                        ),
                        default=None,
                    ),
                },
                "pipeline_log": pipeline_log,
                "data_protection": {
                    "sensitive_data_count": len(pseudonymizer.mapping),
                    "pseudonymization_successful": True
                }
            }

        except Exception as e:
            log_step("error", f"Analysis failed: {str(e)}")
            return {"error": str(e), "pipeline_log": pipeline_log}


# Credit risk thresholds. Any single breach promotes the customer to that level.
HIGH_RISK_MAX_DAYS_OVERDUE = 60
HIGH_RISK_UTILIZATION_PERCENT = 70
HIGH_RISK_AVG_DELAY_DAYS = 30
HIGH_RISK_PAYMENT_RATIO_PERCENT = 50

MEDIUM_RISK_UTILIZATION_PERCENT = 40
MEDIUM_RISK_AVG_DELAY_DAYS = 10

# A low settled ratio is only meaningful once enough invoices have come due.
# Below this count a new customer with one not-yet-due invoice would otherwise
# be flagged high risk purely for not having paid something that is not owed yet.
MIN_INVOICES_FOR_RATIO_RULE = 3


class CustomerCreditAnalyzer(BaseTool):
    """Check customer credit history and risk indicators with pseudonymization."""

    def __init__(self, llm_client: LLMClient | None = None):
        super().__init__(
            name="check_customer_credit_history",
            description="Check customer payment history and credit risk with data protection",
            llm_client=llm_client,
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
                AND docstatus = 1
                AND outstanding_amount > 0
                ORDER BY due_date
                LIMIT 20
            """, [customer_name], as_dict=True)

            credit_limit = flt(customer.credit_limits[0].credit_limit if customer.credit_limits else 0)
            payment_history = self._calculate_payment_history(customer_name, outstanding_invoices, credit_limit)

            # Build structured data. Every monetary value below - credit limit,
            # payment history, orders and invoices - is expressed in this currency.
            return {
                "currency": self._get_company_currency(customer.name),
                "customer": {
                    "name": customer.customer_name,
                    "tax_id": customer.tax_id if customer.tax_id else "N/A",
                    "email": primary_contact.email_id if primary_contact and primary_contact.email_id else "N/A",
                    "phone": primary_contact.mobile_no if primary_contact and primary_contact.mobile_no else "N/A",
                    "address": self._format_address(primary_address) if primary_address else "N/A",
                    "credit_limit": credit_limit,
                    "customer_group": customer.customer_group,
                    "territory": customer.territory
                },
                "payment_history": payment_history,
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

    def _classify_risk_level(self, payment_history: dict) -> str:
        """Classify credit risk from payment metrics using fixed thresholds.

        Risk classification drives a credit decision, so it is computed in code
        rather than delegated to the language model. The model narrates this
        verdict; it does not produce it.

        Args:
            payment_history: Metrics dict from _calculate_payment_history.

        Returns:
            One of: unknown, high, medium, low.
        """
        if not payment_history.get("has_payment_history"):
            return "unknown"

        max_overdue = payment_history.get("max_days_overdue") or 0
        utilization = payment_history.get("credit_utilization_percent")
        avg_delay = payment_history.get("avg_payment_delay_days")
        payment_ratio = payment_history.get("payment_ratio_percent")
        total_invoices = payment_history.get("total_invoices_12m") or 0

        # An unpaid invoice that is not yet due is not evidence of poor payment
        ratio_is_meaningful = (
            payment_ratio is not None and total_invoices >= MIN_INVOICES_FOR_RATIO_RULE
        )

        high_risk = (
            max_overdue > HIGH_RISK_MAX_DAYS_OVERDUE
            or (utilization is not None and utilization > HIGH_RISK_UTILIZATION_PERCENT)
            or (avg_delay is not None and avg_delay > HIGH_RISK_AVG_DELAY_DAYS)
            or (ratio_is_meaningful and payment_ratio < HIGH_RISK_PAYMENT_RATIO_PERCENT)
        )
        if high_risk:
            return "high"

        medium_risk = (
            max_overdue > 0
            or (utilization is not None and utilization > MEDIUM_RISK_UTILIZATION_PERCENT)
            or (avg_delay is not None and avg_delay > MEDIUM_RISK_AVG_DELAY_DAYS)
        )
        if medium_risk:
            return "medium"

        return "low"

    def _get_company_currency(self, customer_name: str) -> str:
        """Return the reporting currency for the customer's transactions.

        Demo documents are all issued in the company default currency, so a
        single currency describes every amount in the analysis payload.

        Args:
            customer_name: Name (primary key) of the Customer document.

        Returns:
            Currency code, falling back to the company default.
        """
        currency = frappe.db.get_value(
            "Sales Invoice",
            {"customer": customer_name, "docstatus": 1},
            "currency",
        )
        if currency:
            return currency

        company = frappe.defaults.get_global_default("company")
        return frappe.db.get_value("Company", company, "default_currency") if company else "N/A"

    def _calculate_payment_history(
        self,
        customer_name: str,
        outstanding_invoices: list,
        credit_limit: float,
    ) -> dict:
        """Calculate payment behaviour metrics over the last 12 months.

        Payment delay is measured against actual Payment Entry posting dates, not
        record modification timestamps. When a customer has no invoice history the
        metrics are returned as None rather than as flattering defaults, so the
        downstream analysis can distinguish "pays on time" from "never invoiced".

        Args:
            customer_name: Name (primary key) of the Customer document.
            outstanding_invoices: Already fetched submitted invoices with a balance.
            credit_limit: Approved credit limit, used for utilisation.

        Returns:
            Dict of payment metrics, including a has_payment_history flag.
        """
        invoice_stats = frappe.db.sql("""
            SELECT
                COUNT(*) as total_invoices,
                SUM(CASE WHEN outstanding_amount = 0 THEN 1 ELSE 0 END) as paid_invoices,
                SUM(outstanding_amount) as total_outstanding,
                SUM(grand_total) as total_12m_revenue
            FROM `tabSales Invoice`
            WHERE customer = %s
            AND docstatus = 1
            AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
        """, [customer_name], as_dict=True)[0]

        total_invoices = int(invoice_stats.total_invoices or 0)

        if not total_invoices:
            return {
                "has_payment_history": False,
                "data_note": "No submitted sales invoices in the last 12 months - payment behaviour is unknown.",
                "total_invoices_12m": 0,
                "paid_invoices_12m": 0,
                "payment_ratio_percent": None,
                "avg_payment_delay_days": None,
                "max_days_overdue": 0,
                "total_outstanding": 0.0,
                "overdue_amount": 0.0,
                "total_12m_revenue": 0.0,
                "credit_utilization_percent": None,
            }

        # Real payment delay: settlement date from Payment Entry vs invoice due date
        delay_stats = frappe.db.sql("""
            SELECT
                COUNT(*) as settled_allocations,
                AVG(DATEDIFF(pe.posting_date, si.due_date)) as avg_payment_delay_days
            FROM `tabPayment Entry Reference` per
            INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent AND pe.docstatus = 1
            INNER JOIN `tabSales Invoice` si ON si.name = per.reference_name AND si.docstatus = 1
            WHERE per.reference_doctype = 'Sales Invoice'
            AND per.docstatus = 1
            AND si.customer = %s
            AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
        """, [customer_name], as_dict=True)[0]

        settled = int(delay_stats.settled_allocations or 0)
        avg_delay = round(delay_stats.avg_payment_delay_days, 1) if settled else None

        overdue = [inv for inv in outstanding_invoices if inv.days_overdue and inv.days_overdue > 0]
        overdue_amount = sum(flt(inv.outstanding_amount) for inv in overdue)
        max_days_overdue = max((int(inv.days_overdue) for inv in overdue), default=0)

        total_outstanding = flt(invoice_stats.total_outstanding or 0)
        paid_invoices = int(invoice_stats.paid_invoices or 0)

        return {
            "has_payment_history": True,
            "total_invoices_12m": total_invoices,
            "paid_invoices_12m": paid_invoices,
            "payment_ratio_percent": round(paid_invoices / total_invoices * 100, 1),
            "avg_payment_delay_days": avg_delay,
            "settled_invoice_count": settled,
            "max_days_overdue": max_days_overdue,
            "total_outstanding": total_outstanding,
            "overdue_amount": flt(overdue_amount),
            "total_12m_revenue": flt(invoice_stats.total_12m_revenue or 0),
            "credit_utilization_percent": round(total_outstanding / credit_limit * 100, 1) if credit_limit else None,
        }

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
        """Create credit analysis prompt for LLM.

        The prompt is grounded: it forbids inventing facts that are absent from
        the payload and handles the "no invoices at all" case explicitly, so an
        empty history is reported as unknown risk instead of excellent standing.
        The risk level itself comes from _classify_risk_level, not from the model.
        """
        currency = pseudonymized_data.get("currency") or "the reporting currency"
        risk_level = self._classify_risk_level(pseudonymized_data.get("payment_history", {}))

        return f"""Analyze the following customer's credit and payment history for financial risk assessment.

GROUNDING RULES - these override everything else:
- Use ONLY the values present in the customer data below. Do not invent numbers,
  credit scores, ratings, or trends that are not in the data.
- All monetary amounts are in {currency}. Never convert or relabel them.
- If "has_payment_history" is false, the customer has NO invoice history. In that
  case you MUST return "credit_risk_level": "unknown", state that payment behaviour
  cannot be assessed, and recommend obtaining a payment history before extending
  credit. Do NOT describe such a customer as reliable, debt free or low risk.
- A null value means "not measurable", not zero and not a good result.
- Never claim a positive trend from a single data point.

RISK CLASSIFICATION - already decided, do not recompute:
The rule engine classified this customer as "{risk_level}". Copy this value into
"credit_risk_level" verbatim. Your task is to explain and support that verdict with
the figures below, never to argue for a different level.

Return ONLY a JSON response with this exact structure:
{{
    "credit_risk_level": "{risk_level}",
    "main_risk_factors": ["risk factor 1", "risk factor 2", ...],
    "recommended_actions": ["action 1", "action 2", ...],
    "credit_limit_recommendation": "increase|maintain|decrease|suspend|insufficient_data",
    "analysis_summary": "brief summary of key findings, citing concrete numbers"
}}

Customer data:
{json.dumps(pseudonymized_data, indent=2, ensure_ascii=False)}

Assess, citing the concrete figures behind each point:
1. Payment behavior - avg_payment_delay_days, payment_ratio_percent
2. Overdue exposure - overdue_amount, max_days_overdue
3. Credit utilization - credit_utilization_percent against credit_limit
4. Outstanding debt vs revenue - total_outstanding vs total_12m_revenue
5. Recent order patterns and overall financial stability"""

    def execute(self, customer_name: str) -> dict:
        """Execute customer credit analysis with pseudonymization."""
        pipeline_log = []

        def log_step(step_type: str, message: str, data=None):
            entry = {
                "type": step_type,
                "message": message,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            pipeline_log.append(entry)

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

            # Step 3: Build the complete prompt before the single LLM request.
            analysis_prompt = self._create_credit_analysis_prompt(pseudonymized_data)
            log_step("ai_prompt", "Credit analysis prompt sent to AI", analysis_prompt)

            llm_response = self._analyze_with_llm_prompt(analysis_prompt)

            # Show AI response
            log_step(
                "llm_response",
                "AI credit analysis completed - raw response from model",
                llm_response,
            )

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
                "analysis_for_llm": llm_response,
                "pseudonym_reverse_mapping": dict(pseudonymizer.reverse_mapping),
                # Numeric-only metrics for the answer formatting step. The LLM JSON
                # above carries a verdict but drops the underlying figures, which
                # left the final answer unable to fill its sections. Nothing here
                # identifies the customer, so the privacy guarantee is preserved.
                "metrics": {
                    "currency": raw_data.get("currency"),
                    "credit_limit": raw_data["customer"]["credit_limit"],
                    "rule_based_risk_level": self._classify_risk_level(raw_data["payment_history"]),
                    "payment_history": raw_data["payment_history"],
                    "outstanding_invoice_count": len(raw_data["outstanding_invoices"]),
                    "recent_order_count": len(raw_data["recent_orders"]),
                },
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
            return self.llm_client.generate(prompt)
        except LLMError as exc:
            return f"Error calling LLM: {exc}"


def get_tool_by_name(
    name: str,
    llm_client: LLMClient | None = None,
) -> BaseTool | None:
    """Create a tool with the same LLM client used by the agent."""
    if name == "analyze_sales_order":
        return SalesOrderAnalyzer(llm_client=llm_client)
    if name == "check_customer_credit_history":
        return CustomerCreditAnalyzer(llm_client=llm_client)
    return None
