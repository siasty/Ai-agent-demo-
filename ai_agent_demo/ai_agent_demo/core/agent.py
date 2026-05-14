"""
Simple AI Agent for business data analysis.

Coordinates between tools and LLM for structured business workflows.
"""
from __future__ import annotations

import json
import re
import requests
from typing import Dict, Any, List

from .tools import get_available_tools, get_tool_by_name


class BusinessAgent:
    """AI Agent for business data analysis with privacy protection."""

    def __init__(self, model_name: str = "llama3.2"):
        self.model_name = model_name
        self.available_tools = get_available_tools()

    def _call_llm(self, prompt: str) -> str:
        """Call Ollama LLM with given prompt."""
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model_name,
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

    def _parse_tool_selection(self, llm_response: str) -> Dict[str, Any] | None:
        """Parse tool selection from LLM response with better error handling."""

        # Priority 1: Direct sales order patterns in query
        so_match = re.search(r'(SAL-ORD-\d{4}-\d{5})', llm_response)
        if so_match:
            return {
                "tool_name": "analyze_sales_order",
                "parameters": {"sales_order_id": so_match.group(1)}
            }

        # Priority 2: Customer credit mentions
        credit_keywords = ["credit", "payment history", "credit history"]
        if any(keyword in llm_response.lower() for keyword in credit_keywords):
            # Extract customer name patterns
            credit_patterns = [
                r'credit.{0,30}for\s+([A-Za-z][A-Za-z\s&.]+)',
                r'check.{0,30}([A-Za-z][A-Za-z\s&.]+).{0,30}credit',
                r'([A-Za-z][A-Za-z\s&.]+).{0,30}payment.{0,30}history',
                r'history.{0,30}for\s+([A-Za-z][A-Za-z\s&.]+)'
            ]

            for pattern in credit_patterns:
                match = re.search(pattern, llm_response, re.IGNORECASE)
                if match:
                    customer_name = match.group(1).strip()
                    # Clean up customer name
                    customer_name = re.sub(r'\s+', ' ', customer_name)
                    if 5 <= len(customer_name) <= 50:  # Reasonable length
                        return {
                            "tool_name": "check_customer_credit_history",
                            "parameters": {"customer_name": customer_name}
                        }

        # Priority 3: Look for structured tool calls
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
                        # Keep only valid parameters
                        params = {"sales_order_id": params["sales_order_id"]}
                    elif tool_name == "check_customer_credit_history" and "customer_name" in params:
                        params = {"customer_name": params["customer_name"]}

                except Exception:
                    # Simple fallback extraction
                    if tool_name == "analyze_sales_order":
                        so_match = re.search(r'(SAL-ORD-\d{4}-\d{5})', params_match.group(1))
                        if so_match:
                            params = {"sales_order_id": so_match.group(1)}
                    elif tool_name == "check_customer_credit_history":
                        name_match = re.search(r'["\']([^"\']+)["\']', params_match.group(1))
                        if name_match:
                            params = {"customer_name": name_match.group(1)}

            return {
                "tool_name": tool_name,
                "parameters": params
            }

        return None

    def _create_tool_selection_prompt(self, user_query: str) -> str:
        """Create prompt for tool selection."""
        tools_desc = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in self.available_tools
        ])

        return f"""You are a business AI assistant with access to the following tools:

{tools_desc}

User query: "{user_query}"

Select the most appropriate tool and provide parameters. Respond with:

TOOL: tool_name
PARAMS: {{"param1": "value1", "param2": "value2"}}
REASONING: Brief explanation of why this tool was selected

If analyzing sales orders, look for sales order IDs like "SAL-ORD-2026-00025" in the query.
For credit history questions, use check_customer_credit_history with customer name.
For sales risk analysis questions, use analyze_sales_order."""

    def run(self, user_query: str) -> Dict[str, Any]:
        """Execute user query through agent workflow."""
        pipeline_log = []
        steps = []

        def log_step(step_type: str, message: str, data=None):
            pipeline_log.append({
                "type": step_type,
                "message": message,
                "data": data
            })

        try:
            # Step 1: Analyze query and select tool
            log_step("input", "Analyzing user query", user_query)

            tool_prompt = self._create_tool_selection_prompt(user_query)
            log_step("think", "AI reasoning about tool selection")
            log_step("ai_prompt", "Prompt sent to AI for tool selection", tool_prompt)

            llm_response = self._call_llm(tool_prompt)

            tool_selection = self._parse_tool_selection(llm_response)

            if not tool_selection:
                log_step("no_tool", "No suitable tool found for query")
                return {
                    "answer": "I couldn't find an appropriate tool for your query. Please try asking about sales order analysis or current date/time.",
                    "steps": [],
                    "pipeline_log": pipeline_log
                }

            log_step("tool_select", f"Selected tool: {tool_selection['tool_name']}", tool_selection['tool_name'])
            log_step("tool_input", "Tool parameters", tool_selection['parameters'])

            # Step 2: Execute tool
            tool = get_tool_by_name(tool_selection['tool_name'])
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
                "tool_output": tool_result,
                "step_number": 1
            })

            # Step 3: Format final response
            if "error" in tool_result:
                answer = f"Error: {tool_result['error']}"
            elif tool_selection['tool_name'] == "analyze_sales_order":
                # Parse and format the analysis
                analysis = tool_result.get('analysis', 'No analysis available')
                answer = f"Sales Order Analysis Results:\n\n{analysis}"
            elif tool_selection['tool_name'] == "check_customer_credit_history":
                # Format credit analysis
                customer = tool_result.get('customer_name', 'Unknown')
                risk_level = tool_result.get('credit_risk_level', 'unknown')
                risk_factors = tool_result.get('risk_factors', [])

                answer = f"Credit Analysis for {customer}:\n\n"
                answer += f"Risk Level: {risk_level.upper()}\n\n"
                answer += "Risk Factors:\n" + "\n".join(f"• {factor}" for factor in risk_factors)

                if 'payment_statistics' in tool_result:
                    stats = tool_result['payment_statistics']
                    answer += f"\n\nPayment Statistics:\n"
                    answer += f"• Payment ratio: {stats.get('payment_ratio_percent', 0)}%\n"
                    answer += f"• Average delay: {stats.get('average_delay_days', 0)} days\n"
                    answer += f"• Total outstanding: ${stats.get('total_outstanding', 0):,.2f}"
            else:
                answer = str(tool_result)

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