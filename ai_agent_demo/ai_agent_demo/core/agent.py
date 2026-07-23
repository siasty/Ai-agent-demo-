"""
Simple AI Agent for business data analysis.

Coordinates between tools and LLM for structured business workflows.
"""
from __future__ import annotations

import json
import re
from typing import Dict, Any

import frappe

from .llm_client import LLMClient, LLMError
from .pseudonymizer import BusinessPseudonymizer
from .tools import get_available_tools, get_tool_by_name


SALES_ORDER_ID_PATTERN = re.compile(r'\bSAL-ORD-\d{4}-\d{5}\b')
MAX_TOOL_SELECTION_QUERY_CHARS = 2000
MAX_FINAL_REVERSE_MAPPINGS = 200
INTERNAL_TOOL_RESULT_KEYS = ("analysis_for_llm", "pseudonym_reverse_mapping")
CREDIT_KEYWORDS = ("credit", "payment history", "credit history")
CREDIT_CUSTOMER_PATTERNS = (
    r'credit.{0,30}for\s+([A-Za-z][A-Za-z\s&.]+)',
    r'check.{0,30}([A-Za-z][A-Za-z\s&.]+).{0,30}credit',
    r'([A-Za-z][A-Za-z\s&.]+).{0,30}payment.{0,30}history',
    r'history.{0,30}for\s+([A-Za-z][A-Za-z\s&.]+)',
)


class BusinessAgent:
    """AI Agent for business data analysis with privacy protection."""

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client or LLMClient()
        self.model_name = self.llm_client.config.model
        self.available_tools = get_available_tools()

    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM with the given prompt."""
        try:
            return self.llm_client.generate(prompt)
        except LLMError as exc:
            return f"Error calling LLM: {exc}"

    def _resolve_customer_name(self, candidate: str) -> str | None:
        """Resolve a name extracted from the query to an actual Customer record.

        Regex extraction produces approximate names, so the candidate is verified
        against the database instead of being passed to the tool unchecked.

        Args:
            candidate: Customer name as extracted from the user query.

        Returns:
            The canonical Customer name, or None when nothing matches.
        """
        if not candidate:
            return None

        if frappe.db.exists("Customer", candidate):
            return candidate

        matches = frappe.get_all(
            "Customer",
            filters={"customer_name": ["like", f"%{candidate}%"]},
            pluck="name",
            limit_page_length=2,
        )

        # Only accept an unambiguous match - two candidates means we guessed wrong
        return matches[0] if len(matches) == 1 else None

    def _parse_tool_selection(self, user_query: str, llm_response: str) -> Dict[str, Any] | None:
        """Parse tool selection, preferring evidence from the user query.

        Identifiers are extracted from the user query, never from the model's
        reply. Reading them out of the reply only worked while the model happened
        to echo the question back.

        Args:
            user_query: The original question asked by the user.
            llm_response: The model's tool selection reply.

        Returns:
            Dict with 'tool_name' and 'parameters', or None when nothing matched.
        """

        # Priority 1: Direct sales order patterns in the query
        so_match = SALES_ORDER_ID_PATTERN.search(user_query)
        if so_match:
            return {
                "tool_name": "analyze_sales_order",
                "parameters": {"sales_order_id": so_match.group(0)}
            }

        # Priority 2: Customer credit mentions in the query
        _, resolved_customer = self._extract_credit_customer(user_query)
        if resolved_customer:
            return {
                "tool_name": "check_customer_credit_history",
                "parameters": {"customer_name": resolved_customer}
            }

        # Priority 3: Look for structured tool calls in the model reply
        tool_match = re.search(r'TOOL:\s*(\w+)', llm_response, re.IGNORECASE)
        params_match = re.search(r'PARAMS:\s*({[^}]*})', llm_response, re.IGNORECASE)

        if tool_match:
            tool_name = tool_match.group(1)
            params = {}

            if params_match:
                try:
                    params_text = params_match.group(1)
                    # Clean up the JSON
                    params_text = re.sub(r'([{,]\s*)([a-zA-Z_]+)\s*:', r'\1"\2":', params_text)
                    params = json.loads(params_text)

                    # Validate parameters for known tools
                    if tool_name == "analyze_sales_order" and "sales_order_id" in params:
                        sales_order_id = params["sales_order_id"]
                        if SALES_ORDER_ID_PATTERN.fullmatch(str(sales_order_id)):
                            params = {"sales_order_id": sales_order_id}
                        else:
                            params = {}
                    elif tool_name == "check_customer_credit_history" and "customer_name" in params:
                        resolved = self._resolve_customer_name(str(params["customer_name"]))
                        params = {"customer_name": resolved} if resolved else {}

                except Exception:
                    # Simple fallback extraction
                    if tool_name == "analyze_sales_order":
                        so_match = SALES_ORDER_ID_PATTERN.search(params_match.group(1))
                        if so_match:
                            params = {"sales_order_id": so_match.group(0)}
                    elif tool_name == "check_customer_credit_history":
                        name_match = re.search(r'["\']([^"\']+)["\']', params_match.group(1))
                        if name_match:
                            resolved = self._resolve_customer_name(name_match.group(1))
                            params = {"customer_name": resolved} if resolved else {}

            if tool_name in {"analyze_sales_order", "check_customer_credit_history"} and not params:
                return None

            return {
                "tool_name": tool_name,
                "parameters": params
            }

        return None

    def _extract_credit_customer(self, user_query: str) -> tuple[str | None, str | None]:
        """Extract and resolve a customer mentioned in a credit-history query."""
        if not user_query:
            return None, None

        query_lower = user_query.lower()
        if not any(keyword in query_lower for keyword in CREDIT_KEYWORDS):
            return None, None

        for pattern in CREDIT_CUSTOMER_PATTERNS:
            match = re.search(pattern, user_query, re.IGNORECASE)
            if not match:
                continue

            candidate = re.sub(r'\s+', ' ', match.group(1).strip())
            if not candidate:
                continue

            resolved = self._resolve_customer_name(candidate)
            if resolved:
                return candidate, resolved

        return None, None

    def _replace_literal_for_prompt(self, text: str, value: str | None, token: str) -> tuple[str, bool]:
        """Replace one literal value before data is put in a model prompt."""
        if not text or not value:
            return text, False

        updated = re.sub(re.escape(value), token, text, flags=re.IGNORECASE)
        return updated, updated != text

    def _replace_sales_order_ids_for_prompt(self, text: str) -> tuple[str, int]:
        """Replace ERP sales-order identifiers before tool-selection prompting."""
        if not text:
            return text, 0

        matches = SALES_ORDER_ID_PATTERN.findall(text)
        updated = SALES_ORDER_ID_PATTERN.sub("SALES_ORDER_ID", text)
        return updated, len(matches)

    def _create_safe_tool_selection_query(self, user_query: str) -> tuple[str, Dict[str, Any]]:
        """Create an LLM-safe version of the user query for tool selection only."""
        if not user_query:
            return "", {"raw_query_sent_to_llm": False, "changed": False}

        bounded_query = user_query[:MAX_TOOL_SELECTION_QUERY_CHARS]
        safe_query, sales_order_count = self._replace_sales_order_ids_for_prompt(bounded_query)
        candidate, resolved = self._extract_credit_customer(bounded_query)

        customer_replaced = False
        safe_query, changed = self._replace_literal_for_prompt(safe_query, candidate, "CUSTOMER_NAME")
        customer_replaced = customer_replaced or changed
        if resolved != candidate:
            safe_query, changed = self._replace_literal_for_prompt(safe_query, resolved, "CUSTOMER_NAME")
            customer_replaced = customer_replaced or changed

        pseudonymizer = BusinessPseudonymizer(use_ner=True)
        safe_query = pseudonymizer.pseudonymize_text_auto(safe_query)

        privacy_info = {
            "raw_query_sent_to_llm": False,
            "safe_query": safe_query,
            "changed": safe_query != bounded_query,
            "truncated": len(user_query) > MAX_TOOL_SELECTION_QUERY_CHARS,
            "sales_order_ids_replaced": sales_order_count,
            "customer_name_replaced": customer_replaced,
            "ner_replacements": len(pseudonymizer.mapping),
            "ner_enabled": pseudonymizer.use_ner,
        }
        return safe_query, privacy_info

    def _create_tool_selection_prompt(self, user_query: str) -> str:
        """Create prompt for tool selection."""
        tools_desc = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in self.available_tools
        ])

        return f"""You are a business AI assistant with access to the following tools:

{tools_desc}

User query (privacy filtered): "{user_query}"

Select the most appropriate tool. The query may contain placeholders such as
SALES_ORDER_ID, CUSTOMER_NAME, PERSON_01, ORGANIZATION_01, EMAIL_01, or PHONE_01.
Actual identifiers are resolved locally by application code and are not available
to you. Use placeholders in PARAMS when needed.

Respond with:

TOOL: tool_name
PARAMS: {{"param1": "value1", "param2": "value2"}}
REASONING: Brief explanation of why this tool was selected

If analyzing sales orders, look for sales order references like SALES_ORDER_ID.
For credit history questions, use check_customer_credit_history.
For sales risk analysis questions, use analyze_sales_order."""

    # Shared grounding block: the formatting step must not introduce new facts.
    _FORMATTING_RULES = """GROUNDING RULES - these override the formatting requirements:
- Reformat ONLY what the analysis results contain. Never add findings, numbers,
  ratings or reassurances that are not present above.
- Every bullet must cite a concrete figure from the analysis results.
- If the analysis reports unknown risk or missing data, say so plainly and do not
  fill the section with generic positive statements.
- If a section has no supporting data, write "Not assessable - no data available"
  instead of inventing content."""

    def _create_sales_order_answer_prompt(self, analysis: str, metrics: Dict[str, Any] | None = None) -> str:
        """Create the final answer prompt for a sales order risk analysis.

        Args:
            analysis: Risk verdict JSON produced by the sales order analysis tool.
            metrics: Numeric figures behind that verdict, passed separately because
                the verdict JSON does not carry the order value.
        """
        figures = json.dumps(metrics, indent=2, ensure_ascii=False) if metrics else "Not provided."
        currency = (metrics or {}).get("currency") or "the reporting currency"

        return f"""You are a business AI assistant presenting a sales order risk review.

TECHNICAL ANALYSIS RESULTS:
{analysis}

VERIFIED FIGURES (authoritative - quote these, never contradict them):
{figures}

{self._FORMATTING_RULES}
- All amounts are in {currency}. Write the amount followed by "{currency}".
  Never use a currency symbol such as $ and never convert values.

STRUCTURE YOUR RESPONSE EXACTLY LIKE THIS:

## Executive Summary
[2-3 sentences: what was ordered, for what value, and the headline risk]

## Order Profile
• Order value: [order_total_net with currency]
• Margin and discount: [discount_percent vs historical average, lowest item margin]
• Customer exposure: [current exposure against credit limit]

## Risk Assessment
• Risk Level: [High/Medium/Low]
• Main Risk Factors: [one bullet per factor, each with its supporting figure]

## Recommendations
• Action 1: [specific recommendation]
• Action 2: [specific recommendation]
• Manual review required: [Yes/No, per the analysis]

Use markdown headers and bullet points exactly as shown."""

    def _create_credit_answer_prompt(self, analysis: str, metrics: Dict[str, Any] | None = None) -> str:
        """Create the final answer prompt for a customer credit history analysis.

        Args:
            analysis: Risk verdict JSON produced by the credit analysis tool.
            metrics: Numeric figures behind that verdict. Passed separately because
                the verdict JSON does not carry them, which previously forced the
                model to report available data as missing.
        """
        figures = json.dumps(metrics, indent=2, ensure_ascii=False) if metrics else "Not provided."

        return f"""You are a business AI assistant presenting a customer credit review.

TECHNICAL ANALYSIS RESULTS:
{analysis}

VERIFIED FIGURES (authoritative - quote these, never contradict them):
{figures}

{self._FORMATTING_RULES}
- The risk level must match "rule_based_risk_level" from the verified figures
  exactly. It was decided by a rule engine and is not open to reinterpretation.
- Never state that a customer pays on time, has no debt or has a good credit score
  unless the analysis results explicitly support it with figures.

STRUCTURE YOUR RESPONSE EXACTLY LIKE THIS:

## Executive Summary
[2-3 sentences: the customer's payment standing and the headline credit risk]

## Payment Behaviour
• Invoices settled: [paid vs total, with percentage]
• Average payment delay: [days, or "not measurable"]
• Overdue exposure: [overdue amount and maximum days overdue]

## Credit Exposure
• Outstanding balance vs credit limit: [amounts and utilization percentage]
• Outstanding vs 12-month revenue: [both figures]

## Risk Assessment
• Risk Level: [High/Medium/Low/Unknown]
• Main Risk Factors: [one bullet per factor, each with its supporting figure]

## Recommendations
• Credit limit: [increase/maintain/decrease/suspend, or "insufficient data"]
• Action 1: [specific recommendation]
• Action 2: [specific recommendation]

Use markdown headers and bullet points exactly as shown."""

    def _create_final_answer_prompt(self, user_query: str, analysis: str, context_info: str) -> str:
        """Create prompt for final answer formatting for an unrecognised tool."""
        return f"""You are a business AI assistant providing final analysis results to a business user.

TASK: Create a professional, well-formatted final answer based on the analysis results.

ANALYSIS TYPE: {context_info}

TECHNICAL ANALYSIS RESULTS:
{analysis}

{self._FORMATTING_RULES}

STRUCTURE YOUR RESPONSE EXACTLY LIKE THIS:

## Executive Summary
[Brief overview in 2-3 sentences]

## Key Findings
• Finding 1: [specific detail with its supporting figure]
• Finding 2: [specific detail with its supporting figure]

## Recommendations
• Action 1: [specific recommendation]
• Action 2: [specific recommendation]

Use markdown headers and bullet points exactly as shown."""

    def _restore_identifiers(self, text: str, reverse_mapping: Dict[str, str]) -> str:
        """Restore pseudonym tokens after the final model response is produced."""
        if not text or not reverse_mapping:
            return text

        result = text
        for token, original in list(reverse_mapping.items())[:MAX_FINAL_REVERSE_MAPPINGS]:
            if token and original and token in result:
                result = result.replace(token, str(original))
        return result

    def _public_tool_result(self, tool_result: Dict[str, Any]) -> Dict[str, Any]:
        """Remove internal privacy fields before returning or persisting steps."""
        public_result = dict(tool_result)
        for key in INTERNAL_TOOL_RESULT_KEYS:
            public_result.pop(key, None)
        return public_result

    def run(self, user_query: str) -> Dict[str, Any]:
        """Execute user query through agent workflow."""
        pipeline_log = []
        steps = []

        def log_step(step_type: str, message: str, data=None):
            entry = {
                "type": step_type,
                "message": message,
                "data": data
            }
            pipeline_log.append(entry)

        try:
            # Step 1: Analyze query and select tool
            log_step("input", "Analyzing user query", user_query)

            safe_user_query, privacy_info = self._create_safe_tool_selection_query(user_query)
            log_step("query_privacy_filter", "User query sanitized before tool-selection prompt", privacy_info)

            tool_prompt = self._create_tool_selection_prompt(safe_user_query)
            log_step("think", "AI reasoning about tool selection")
            log_step("ai_prompt", "Prompt sent to AI for tool selection", tool_prompt)

            llm_response = self._call_llm(tool_prompt)

            tool_selection = self._parse_tool_selection(user_query, llm_response)

            if not tool_selection:
                log_step("no_tool", "No suitable tool found for query")
                return {
                    "answer": (
                        "I couldn't find an appropriate tool for your query. "
                        "Please try asking about sales order analysis or current date/time."
                    ),
                    "steps": [],
                    "pipeline_log": pipeline_log
                }

            log_step(
                "tool_select",
                f"Selected tool: {tool_selection['tool_name']}",
                tool_selection['tool_name'],
            )
            log_step("tool_input", "Tool parameters", tool_selection['parameters'])

            # Step 2: Execute tool
            tool = get_tool_by_name(
                tool_selection['tool_name'],
                llm_client=self.llm_client,
            )
            if not tool:
                log_step("tool_error", f"Tool {tool_selection['tool_name']} not found")
                return {
                    "answer": f"Tool {tool_selection['tool_name']} is not available.",
                    "steps": [],
                    "pipeline_log": pipeline_log
                }

            try:
                tool_result = tool.execute(**tool_selection['parameters'])

                # Always add tool's pipeline log to main log (even on error)
                if 'pipeline_log' in tool_result:
                    pipeline_log.extend(tool_result['pipeline_log'])

                log_step("tool_output", "Tool execution completed", {
                    "success": "error" not in tool_result,
                    "has_analysis": "analysis" in tool_result
                })

            except Exception as e:
                log_step("tool_error", f"Tool execution failed: {str(e)}")
                tool_result = {"error": f"Tool execution failed: {str(e)}"}

            steps.append({
                "tool_name": tool_selection['tool_name'],
                "tool_input": tool_selection['parameters'],
                "tool_output": self._public_tool_result(tool_result),
                "step_number": 1
            })

            # Step 3: Generate final AI-formatted response
            if "error" in tool_result:
                answer = f"Error: {tool_result['error']}"
            else:
                reverse_mapping = tool_result.get("pseudonym_reverse_mapping", {})
                if not isinstance(reverse_mapping, dict):
                    reverse_mapping = {}

                # Generate final answer using AI (without exposing sensitive identifiers).
                # Each tool gets a prompt whose sections match the data it actually
                # produces, so the model is never forced to fill an unsupported section.
                if tool_selection['tool_name'] == "analyze_sales_order":
                    analysis = (
                        tool_result.get('analysis_for_llm')
                        or tool_result.get('analysis', 'No analysis available')
                    )
                    final_answer_prompt = self._create_sales_order_answer_prompt(
                        analysis, tool_result.get('metrics')
                    )
                elif tool_selection['tool_name'] == "check_customer_credit_history":
                    analysis = (
                        tool_result.get('analysis_for_llm')
                        or tool_result.get('analysis', 'No analysis available')
                    )
                    final_answer_prompt = self._create_credit_answer_prompt(
                        analysis, tool_result.get('metrics')
                    )
                else:
                    analysis = str(self._public_tool_result(tool_result))
                    context_info = f"Analysis using tool: {tool_selection['tool_name']}"
                    final_answer_prompt = self._create_final_answer_prompt(user_query, analysis, context_info)

                log_step("ai_prompt", "Final answer formatting prompt sent to AI", final_answer_prompt)

                safe_answer = self._call_llm(final_answer_prompt)
                answer = self._restore_identifiers(safe_answer, reverse_mapping)
                if answer != safe_answer:
                    log_step("depseudonymize", "Restored identifiers after final answer formatting")

            log_step("finish", "Analysis completed", answer)

            return {
                "answer": answer,
                "steps": steps,
                "pipeline_log": pipeline_log
            }

        except Exception as e:
            log_step("error", f"Agent execution failed: {str(e)}")
            return {
                "answer": f"Agent error: {str(e)}",
                "steps": [],
                "pipeline_log": pipeline_log
            }
