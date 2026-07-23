# AI Agent Demo - privacy and prompt flow map

This file maps where sensitive data is filtered, which prompts exist, and what
each prompt receives. The key rule after the privacy fix is:

> Raw user query and restored identifiers are not sent to Ollama prompts.

## Graphical Flow

```mermaid
flowchart TD
    U[User query in Desk UI] --> API[api.run_agent]
    API --> A[BusinessAgent.run]

    A --> QF[Query privacy filter]
    QF --> SQ[Safe query with placeholders]
    SQ --> P1[Prompt 1: tool selection]
    P1 --> O1[Ollama: choose tool]

    A --> LP[Local parser on raw query]
    O1 --> LP
    LP --> T{Selected tool}

    T -->|analyze_sales_order| SO[Fetch Sales Order from ERPNext]
    T -->|check_customer_credit_history| CR[Fetch customer credit data from ERPNext]

    SO --> PSO[BusinessPseudonymizer.pseudonymize_sales_order]
    CR --> PCR[BusinessPseudonymizer.pseudonymize_customer_data]

    PSO --> SOD[Safe sales-order payload built locally]
    PCR --> CRD[Safe credit payload built locally]

    SOD --> P2[Build complete Prompt 2 locally:<br/>sales-order risk analysis plus safe payload]
    CRD --> P3[Build complete Prompt 3 locally:<br/>credit analysis plus safe payload]

    P2 --> O2[Single Ollama request:<br/>analysis returned with tokens]
    P3 --> O3[Single Ollama request:<br/>analysis returned with tokens]

    O2 --> P4[Prompt 4: final sales-order formatting with tokens]
    O3 --> P5[Prompt 5: final credit formatting with tokens]

    P4 --> FO[Ollama formatted answer with tokens]
    P5 --> FO

    FO --> R[Local depseudonymization]
    R --> UI[Final answer shown in UI]
```

The safe ERP payload is not a separate model request. Application code embeds it
in Prompt 2 or Prompt 3 first, then logs one `ai_prompt` event immediately before
the corresponding Ollama request. The obsolete `ai_input_data` and empty
`llm_analysis` events are no longer emitted.

## Recorded Credit Pipeline Events

The bundled `Check credit history for MicroDevices Partners` recording contains
21 raw backend events. The interactive viewer combines related prompt/response
pairs and hides status-only events, producing 9 presentation steps.

```mermaid
flowchart TD
    E01["1 input<br/>raw user query"] --> E02["2 query_privacy_filter<br/>safe query created"]
    E02 --> E03["3 think<br/>tool-selection status"]
    E03 --> E04["4 ai_prompt<br/>safe tool-selection prompt"]
    E04 --> E05["5 tool_select<br/>selected tool"]
    E05 --> E06["6 tool_input<br/>local customer parameter"]
    E06 --> E07["7 input<br/>ERP fetch status"]
    E07 --> E08["8 data_fetch<br/>ERP result"]
    E08 --> E09["9 sensitive_data_detected"]
    E09 --> E10["10 pseudonymize_start"]
    E10 --> E11["11 debug_detection"]
    E11 --> E12["12 pseudonymize_complete"]
    E12 --> E13["13 ai_prompt<br/>complete credit-analysis prompt"]
    E13 --> E14["14 llm_response<br/>credit analysis"]
    E14 --> E15["15 token_check"]
    E15 --> E16["16 depseudonymize"]
    E16 --> E17["17 final_response<br/>local tool result"]
    E17 --> E18["18 complete"]
    E18 --> E19["19 tool_output"]
    E19 --> E20["20 ai_prompt<br/>final formatting prompt"]
    E20 --> E21["21 finish<br/>final answer"]
```

## Prompt Map

| Prompt | Code location | Data passed to model | Privacy status |
|---|---|---|---|
| Tool selection | `core/agent.py::_create_tool_selection_prompt` | `safe_user_query` from `_create_safe_tool_selection_query` | Raw query is not sent. Sales Order IDs, resolved customer names, and NER-detected entities are replaced with placeholders. |
| Sales-order analysis | `core/tools.py::SalesOrderAnalyzer._create_analysis_prompt` | `pseudonymized_data` from `BusinessPseudonymizer.pseudonymize_sales_order` | Sensitive ERP fields are tokenized before the prompt is created. |
| Customer credit analysis | `core/tools.py::CustomerCreditAnalyzer._create_credit_analysis_prompt` | `pseudonymized_data` from `BusinessPseudonymizer.pseudonymize_customer_data` | Sensitive customer/contact fields are tokenized before the prompt is created. |
| Final sales-order answer | `core/agent.py::_create_sales_order_answer_prompt` | `analysis_for_llm` plus numeric-only `metrics` | The prompt receives tokenized analysis, not restored identifiers. |
| Final credit answer | `core/agent.py::_create_credit_answer_prompt` | `analysis_for_llm` plus numeric-only `metrics` | The prompt receives tokenized analysis, not restored identifiers. |
| Fallback final answer | `core/agent.py::_create_final_answer_prompt` | Generic tool result | Used only for unknown tools; current registered tools use the specific final prompts above. |

## Where The Privacy Filter Runs

`BusinessAgent.run()` calls `_create_safe_tool_selection_query()` before creating
the tool-selection prompt. That function:

1. Bounds the query to `MAX_TOOL_SELECTION_QUERY_CHARS`.
2. Replaces ERP Sales Order IDs with `SALES_ORDER_ID`.
3. Resolves customer names locally for credit-history questions and replaces them
   with `CUSTOMER_NAME`.
4. Runs `BusinessPseudonymizer.pseudonymize_text_auto()` for remaining names,
   emails, phones, organizations, locations, tax IDs, and similar entities.

The raw query is still used locally by `_parse_tool_selection()` so the app can
extract the real `sales_order_id` or `customer_name` without showing those values
to the tool-selection prompt.

## Where Identifiers Are Restored

Tool analysis still restores identifiers for the UI pipeline log, but the final
formatting prompt uses `analysis_for_llm`, which is the tokenized model response.
After the final model response is produced, `BusinessAgent._restore_identifiers()`
replaces tokens locally using `pseudonym_reverse_mapping`.

Internal fields used for this handoff are removed from `steps` by
`BusinessAgent._public_tool_result()` before the API response can persist or show
the technical tool output.
