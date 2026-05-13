// =============================================================================
// AI Agent Demo – Frappe Page (plain JS, no build step needed)
//
// Shows pipeline_log step by step:
//   INPUT → PRE-PROCESS → DETECT → AGENT INIT → MODEL → THINK →
//   TOOL SELECT → TOOL INPUT → TOOL OUTPUT → FINISH
// =============================================================================

frappe.pages["ai-agent-demo"].on_page_load = function (wrapper) {
    _inject_styles();
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "AI Agent Demo",
        single_column: true,
    });
    new AIAgentDemoPage(page);
};

// ---------------------------------------------------------------------------
// Tool metadata
// ---------------------------------------------------------------------------
const TOOL_META = {
    analyze_sales_order:        { icon: "📊", color: "#198754" },
    check_customer_credit_history: { icon: "💳", color: "#dc3545" },
};

// Log event type configuration
const LOG_CFG = {
    input:                    { icon: "📥", color: "#0d6efd",  bg: "#f0f7ff", title: "INPUT" },
    preprocess:               { icon: "⚙️",  color: "#6f42c1",  bg: "#f8f5ff", title: "PRE-PROCESSING" },
    detect:                   { icon: "🔍", color: "#fd7e14",  bg: "#fff8f0", title: "DATA DETECTION" },
    agent_init:               { icon: "🤖", color: "#0dcaf0",  bg: "#f0feff", title: "AGENT INIT" },
    model_req:                { icon: "➡️",  color: "#6c757d",  bg: "#f8f9fa", title: "MODEL REQUEST" },
    think:                    { icon: "💭", color: "#856404",  bg: "#fffbef", title: "THINK (REASON)" },
    tool_select:              { icon: "🎯", color: "#4361ee",  bg: "#f0f4ff", title: "TOOL SELECTION (ACT)" },
    tool_input:               { icon: "↘️",  color: "#4361ee",  bg: "#eef1ff", title: "INPUT PARAMETERS" },

    // ERP Data Fetching
    data_fetch:               { icon: "🗃️",  color: "#0d6efd",  bg: "#f0f7ff", title: "ERP DATA FETCH" },
    sensitive_data_detected:  { icon: "🤖", color: "#6f42c1",  bg: "#f8f5ff", title: "AI AUTOMATED DETECTION" },

    // Pseudonymization Process
    pseudonymize_start:       { icon: "🔒", color: "#dc3545",  bg: "#fff5f5", title: "PSEUDONYMIZATION START" },
    pseudonymize_complete:    { icon: "✅", color: "#dc3545",  bg: "#fff5f5", title: "PSEUDONYMIZATION COMPLETE" },
    ai_input_data:           { icon: "🤖", color: "#28a745",  bg: "#f0fff4", title: "AI INPUT DATA (SAFE)" },

    // AI Processing
    llm_analysis:            { icon: "🧠", color: "#6f42c1",  bg: "#f8f5ff", title: "AI ANALYSIS" },
    llm_response:            { icon: "💬", color: "#6f42c1",  bg: "#f8f5ff", title: "AI RESPONSE" },
    token_check:             { icon: "🔍", color: "#856404",  bg: "#fffbef", title: "TOKEN CHECK" },

    // Depseudonymization
    depseudonymize:          { icon: "🔓", color: "#198754",  bg: "#f0fff4", title: "DEPSEUDONYMIZATION" },
    depseudonymize_changes:  { icon: "🔄", color: "#198754",  bg: "#f0fff4", title: "RESTORE IDENTIFIERS" },
    final_response:          { icon: "📊", color: "#198754",  bg: "#e8f8ee", title: "FINAL BUSINESS ANALYSIS" },

    // Legacy/General
    anon_start:              { icon: "🔎", color: "#dc3545",  bg: "#fff5f5", title: "ANONYMIZATION START" },
    anonymize_change:        { icon: "🔒", color: "#dc3545",  bg: "#fff5f5", title: "CHANGE" },
    anon_done:               { icon: "✔️",  color: "#198754",  bg: "#f0fff4", title: "ANONYMIZATION OK" },
    tool_output:             { icon: "↙️",  color: "#198754",  bg: "#f0fff4", title: "TOOL RESULT (OBSERVE)" },
    complete:                { icon: "✅", color: "#198754",  bg: "#e8f8ee", title: "COMPLETE" },
    finish:                  { icon: "✅", color: "#198754",  bg: "#e8f8ee", title: "FINAL ANSWER" },
};

// ---------------------------------------------------------------------------
// Main page class
// ---------------------------------------------------------------------------
class AIAgentDemoPage {
    constructor(page) {
        this.page = page;
        this.$el = $(page.main);
        this.session = null;
        this._render();
        this._load_status();
    }

    // -----------------------------------------------------------------------
    // HTML
    // -----------------------------------------------------------------------
    _render() {
        this.$el.html(`
<div class="ad-wrap">

  <div class="ad-status-bar">
    <span id="ad-dot" class="ad-dot"></span>
    <span id="ad-status-txt">Checking Ollama&hellip;</span>
    <span id="ad-model-list"></span>
  </div>

  <div class="ad-grid">

    <!-- Sidebar -->
    <aside class="ad-sidebar">
      <div class="ad-card">
        <p class="ad-label">Available Tools</p>
        <div id="ad-tools-list"></div>
      </div>
      <div class="ad-card">
        <p class="ad-label">How does the agent work? (ReAct)</p>
        <div class="ad-react-row"><div class="ad-rnum">1</div><div><b>Think</b> – LLM selects tool</div></div>
        <div class="ad-react-row"><div class="ad-rnum">2</div><div><b>Act</b> – executes tool</div></div>
        <div class="ad-react-row"><div class="ad-rnum">3</div><div><b>Observe</b> – processes result</div></div>
      </div>
    </aside>

    <!-- Main panel -->
    <main class="ad-main">

      <nav class="ad-tabs">
        <button class="ad-tab active" data-tab="agent">🤖 AI Agent</button>
      </nav>

      <!-- Tab: Agent -->
      <div id="ad-tab-agent" class="ad-tab-body">

        <div class="ad-input-row">
          <input id="ad-query" class="ad-input" type="text" placeholder="Ask the agent a question about sales orders..." />
          <button id="ad-run-btn" class="ad-btn">
            <span id="ad-btn-label">▶ Run</span>
          </button>
        </div>

        <div class="ad-chips">
          <span class="ad-chip" data-q="Analyze sales order SAL-ORD-2026-00006 for risks">📊 Analyze SAL-ORD-2026-00006</span>
          <span class="ad-chip" data-q="Check credit history for MicroDevices Partners">💳 Credit: MicroDevices Partners</span>
          <span class="ad-chip" data-q="Analyze sales order SAL-ORD-2026-00005 for commercial and credit risks">🔍 Risk analysis SAL-ORD-2026-00005</span>
          <span class="ad-chip" data-q="Check customer credit history for TechnoServices Corp">⚠️ Credit: TechnoServices Corp</span>
        </div>

        <!-- Pipeline log -->
        <div id="ad-log-wrap" style="display:none">
          <div class="ad-log-hdr">
            <span class="ad-label" style="margin:0">Pipeline Log – step by step</span>
            <span id="ad-log-cnt" class="ad-log-cnt">0 events</span>
          </div>
          <div id="ad-log" class="ad-log"></div>
        </div>

      </div>


    </main>
  </div>
</div>`);
        this._bind();
    }

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------
    _bind() {
        this.$el.on("click", ".ad-tab", (e) => {
            const tab = $(e.currentTarget).data("tab");
            this.$el.find(".ad-tab").removeClass("active");
            $(e.currentTarget).addClass("active");
            this.$el.find(".ad-tab-body").hide();
            this.$el.find(`#ad-tab-${tab}`).show();
        });

        this.$el.find("#ad-run-btn").on("click", () => this._run());
        this.$el.find("#ad-query").on("keydown", (e) => { if (e.key === "Enter") this._run(); });

        this.$el.on("click", ".ad-chip", (e) => {
            this.$el.find("#ad-query").val($(e.currentTarget).data("q")).focus();
        });
    }

    // -----------------------------------------------------------------------
    // Status Ollamy
    // -----------------------------------------------------------------------
    _load_status() {
        frappe.call({
            method: "ai_agent_demo.ai_agent_demo.api.get_agent_status",
            callback: (r) => {
                const s = r.message || {};
                if (s.ollama_available) {
                    this.$el.find("#ad-dot").addClass("online");
                    this.$el.find("#ad-status-txt").text("Ollama: connected");
                    this.$el.find("#ad-model-list").text(`Modele: ${(s.models || []).slice(0, 3).join(", ")}`);
                } else {
                    this.$el.find("#ad-dot").addClass("offline");
                    this.$el.find("#ad-status-txt").html("Ollama offline – <code>ollama serve</code> + <code>ollama pull llama3.2</code>");
                }
                this._load_tools();
            },
        });
    }

    _load_tools() {
        frappe.call({
            method: "ai_agent_demo.ai_agent_demo.api.get_available_tools",
            callback: (r) => {
                const $list = this.$el.find("#ad-tools-list").empty();
                (r.message || []).forEach((t) => {
                    const m = TOOL_META[t.name] || { icon: "🔧", color: "#6c757d" };
                    $list.append(`<div class="ad-tool" id="adt-${t.name.replace(/_/g,"-")}">
  <span class="ad-tool-icon">${m.icon}</span>
  <div><div class="ad-tool-name">${t.name}</div><div class="ad-tool-desc">${t.description}</div></div>
</div>`);
                });
            },
        });
    }

    _hi_tool(name) {
        this.$el.find(".ad-tool").removeClass("active");
        this.$el.find(`#adt-${name.replace(/_/g, "-")}`).addClass("active");
        setTimeout(() => this.$el.find(".ad-tool").removeClass("active"), 2500);
    }

    // -----------------------------------------------------------------------
    // Uruchomienie agenta
    // -----------------------------------------------------------------------
    _run() {
        const query = this.$el.find("#ad-query").val().trim();
        if (!query) return;

        const $btn = this.$el.find("#ad-run-btn").prop("disabled", true);
        this.$el.find("#ad-btn-label").html('<span class="ad-spin"></span> Thinking…');

        const $log = this.$el.find("#ad-log").empty();
        this.$el.find("#ad-log-wrap").show();
        this.$el.find("#ad-log-cnt").text("0 events");

        $log.append(`<div class="ad-entry ad-thinking">
  <span class="ad-spin" style="border-color:rgba(0,0,0,.1);border-top-color:#4361ee"></span>
  <span>Agent przetwarza zapytanie…</span>
</div>`);

        frappe.call({
            method: "ai_agent_demo.ai_agent_demo.api.run_agent",
            args: { query, session_name: this.session },
            callback: (r) => {
                $btn.prop("disabled", false);
                this.$el.find("#ad-btn-label").html("▶ Uruchom");
                $log.empty();
                if (r.message) {
                    this._render_log(r.message.pipeline_log || []);
                }
            },
            error: () => {
                $btn.prop("disabled", false);
                this.$el.find("#ad-btn-label").html("▶ Uruchom");
                $log.html(`<div class="ad-entry" style="background:#fff5f5;border-left:3px solid #dc3545">
  <div class="ad-e-icon">❌</div>
  <div><div class="ad-e-type" style="color:#dc3545">BŁĄD</div>
  <div class="ad-e-label">Connection error with agent</div></div>
</div>`);
            },
        });
    }

    // -----------------------------------------------------------------------
    // Log rendering - entries appear one by one
    // -----------------------------------------------------------------------
    _render_log(entries) {
        const $log = this.$el.find("#ad-log");
        const $cnt = this.$el.find("#ad-log-cnt");

        entries.forEach((entry, i) => {
            setTimeout(() => {
                $log.append(this._make_entry(entry));
                $cnt.text(`${i + 1} events`);
                $log[0].scrollTop = $log[0].scrollHeight;

                if (entry.type === "tool_select" && typeof entry.data === "string") {
                    this._hi_tool(entry.data);
                }
            }, i * 130);
        });
    }

    // -----------------------------------------------------------------------
    // Building a single log entry
    // -----------------------------------------------------------------------
    _make_entry(e) {
        const cfg = LOG_CFG[e.type] || { icon: "▸", color: "#495057", bg: "#fff", title: e.type.toUpperCase() };
        const dataHtml = this._fmt(e.data, e.type);
        return `
<div class="ad-entry" style="background:${cfg.bg};border-left:3px solid ${cfg.color}">
  <div class="ad-e-icon">${cfg.icon}</div>
  <div class="ad-e-body">
    <div class="ad-e-type" style="color:${cfg.color}">${cfg.title}</div>
    <div class="ad-e-label">${frappe.utils.escape_html(e.label)}</div>
    ${dataHtml ? `<div class="ad-e-data">${dataHtml}</div>` : ""}
  </div>
</div>`;
    }

    // -----------------------------------------------------------------------
    // Formatting data according to event type
    // -----------------------------------------------------------------------
    _fmt(data, type) {
        if (data === null || data === undefined || data === "") return "";

        // Anonymization - show before → after for each sample
        if (type === "anonymize_change") {
            if (typeof data === "object" && Array.isArray(data.samples)) {
                const rows = data.samples.map(s =>
                    `<div class="ad-diff">`
                    + `<span class="ad-before">${frappe.utils.escape_html(s.original)}</span>`
                    + ` <span class="ad-arrow">→</span> `
                    + `<span class="ad-after">${frappe.utils.escape_html(s.anonymized)}</span>`
                    + `</div>`
                ).join("");
                return `<div class="ad-diffs">${rows}</div>`;
            }
        }

        // Enhanced sensitive data detection with method information
        if (type === "sensitive_data_detected" && typeof data === "object" && data.detection_method) {
            let html = `<div style="margin-bottom:8px;">`;

            // Detection method badge - highlight automation
            const methodColor = data.detection_method.includes('Automated') ? '#6f42c1' : '#fd7e14';
            html += `<span class="ad-badge" style="background:${methodColor}20;color:${methodColor};border:1px solid ${methodColor}50">
                🤖 ${data.detection_method}
            </span>`;

            // NLP framework if available
            if (data.nlp_framework) {
                html += ` <span class="ad-badge" style="background:#6f42c120;color:#6f42c1;border:1px solid #6f42c150">
                    🧠 Framework: ${data.nlp_framework}
                </span>`;
            }

            html += `</div>`;

            // Sensitive fields
            if (data.sensitive_fields && Object.keys(data.sensitive_fields).length > 0) {
                html += `<div style="margin-bottom:6px;"><strong>Sensitive fields found:</strong></div>`;
                const COLORS = {
                    customer_name: "#dc3545", customer_email: "#0d6efd", customer_phone: "#198754",
                    customer_address: "#fd7e14", sales_rep_name: "#6f42c1", sales_rep_email: "#20c997"
                };
                html += Object.entries(data.sensitive_fields).map(([k, v]) => {
                    const c = COLORS[k] || "#6c757d";
                    const label = k.replace('customer_', '').replace('sales_rep_', 'rep_').replace('_', ' ');
                    return `<span class="ad-badge" style="background:${c}20;color:${c};border:1px solid ${c}50">
                        ${label}: ${frappe.utils.escape_html(String(v))}
                    </span>`;
                }).join(" ");
            }

            // Entity types and patterns if available
            if (data.entity_types_supported || data.custom_patterns) {
                html += `<div style="margin-top:8px;font-size:11px;color:#6c757d;">`;
                if (data.entity_types_supported && data.entity_types_supported.length > 0) {
                    html += `<div>🎯 Entity types: ${data.entity_types_supported.join(', ')}</div>`;
                }
                if (data.custom_patterns && data.custom_patterns.length > 0) {
                    html += `<div>🛠️ Custom patterns: ${data.custom_patterns.join(', ')}</div>`;
                }
                html += `</div>`;
            }

            return html;
        }

        // Wykryte dane – kolorowe badges (legacy)
        if (type === "detect" && typeof data === "object" && !Array.isArray(data)) {
            if (!Object.keys(data).length) return `<span class="ad-muted">no personal data</span>`;
            const COLORS = { email: "#0d6efd", phone: "#198754", ssn: "#dc3545", name: "#fd7e14" };
            return Object.entries(data).map(([k, v]) => {
                const c = COLORS[k] || "#6c757d";
                return `<span class="ad-badge" style="background:${c}20;color:${c};border:1px solid ${c}50">${k}: ${v}</span>`;
            }).join(" ");
        }

        // Enhanced pseudonymization complete with methods used
        if (type === "pseudonymize_complete" && typeof data === "object" && data.methods_used) {
            let html = `<div style="margin-bottom:8px;">`;

            // Methods used badges
            if (data.methods_used && data.methods_used.length > 0) {
                html += `<div style="margin-bottom:6px;"><strong>Methods used:</strong></div>`;
                data.methods_used.forEach(method => {
                    const color = method.includes('spaCy') ? '#6f42c1' :
                                  method.includes('Manual') ? '#0d6efd' : '#198754';
                    html += `<span class="ad-badge" style="background:${color}20;color:${color};border:1px solid ${color}50">
                        ${method}
                    </span> `;
                });
            }

            html += `</div>`;

            // Summary stats if available
            if (data.summary) {
                const s = data.summary;
                html += `<div style="font-size:11px;color:#6c757d;">`;
                html += `📊 ${s.total_replacements} replacements in ${Object.keys(s.categories || {}).length} categories`;
                if (s.ner_enabled) {
                    html += ` • NER: ${s.ner_model || 'enabled'}`;
                }
                html += `</div>`;
            }

            // Examples if available
            if (data.examples && data.examples.length > 0) {
                html += `<div style="margin-top:6px;">`;
                html += `<div style="font-size:11px;color:#6c757d;margin-bottom:4px;">Examples:</div>`;
                const firstFew = data.examples.slice(0, 3);
                firstFew.forEach(example => {
                    const [original, token] = example.split(' → ');
                    html += `<div class="ad-diff">`;
                    html += `<span class="ad-before">${frappe.utils.escape_html(original)}</span>`;
                    html += ` <span class="ad-arrow">→</span> `;
                    html += `<span class="ad-after">${frappe.utils.escape_html(token)}</span>`;
                    html += `</div>`;
                });
                if (data.examples.length > 3) {
                    html += `<div style="font-size:10px;color:#6c757d;margin-top:2px;">...and ${data.examples.length - 3} more</div>`;
                }
                html += `</div>`;
            }

            return html;
        }

        // Tool list at agent_init
        if (type === "agent_init" && Array.isArray(data)) {
            return data.map(n => {
                const m = TOOL_META[n] || { icon: "🔧", color: "#6c757d" };
                return `<span class="ad-tool-tag" style="color:${m.color}">${m.icon} ${n}</span>`;
            }).join(" ");
        }

        // Object/array - as expandable, pretty JSON
        if (typeof data === "object") {
            return this._formatExpandableJson(data);
        }

        // Regular string
        return `<span class="ad-mono">${frappe.utils.escape_html(String(data))}</span>`;
    }

    // -----------------------------------------------------------------------
    // Expandable JSON formatting
    // -----------------------------------------------------------------------
    _formatExpandableJson(data) {
        const jsonStr = JSON.stringify(data, null, 2);
        const escaped = frappe.utils.escape_html(jsonStr);
        const id = `json-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;

        // Check if JSON is large enough to warrant collapsing
        if (jsonStr.length > 200 || jsonStr.split('\n').length > 8) {
            const preview = jsonStr.split('\n').slice(0, 3).join('\n') + '\n  ...';
            const escapedPreview = frappe.utils.escape_html(preview);

            return `
                <div class="ad-json-container">
                    <div class="ad-json-header" onclick="this.parentElement.classList.toggle('expanded')">
                        <span class="ad-json-toggle">▶</span>
                        <span class="ad-json-label">{...} JSON Object (${Object.keys(data).length} keys)</span>
                    </div>
                    <div class="ad-json-preview">
                        <pre class="ad-json-content">${escapedPreview}</pre>
                    </div>
                    <div class="ad-json-full">
                        <pre class="ad-json-content">${escaped}</pre>
                    </div>
                </div>
            `;
        } else {
            // Small JSON - show directly with syntax highlighting
            const highlighted = this._highlightJson(escaped);
            return `<pre class="ad-json-content ad-json-small">${highlighted}</pre>`;
        }
    }

    _highlightJson(jsonStr) {
        return jsonStr
            .replace(/"([^"]+)"(\s*:)/g, '<span class="json-key">"$1"</span>$2')
            .replace(/:\s*"([^"]*)"/g, ': <span class="json-string">"$1"</span>')
            .replace(/:\s*(\d+)/g, ': <span class="json-number">$1</span>')
            .replace(/:\s*(true|false)/g, ': <span class="json-boolean">$1</span>')
            .replace(/:\s*(null)/g, ': <span class="json-null">$1</span>');
    }

}

// =============================================================================
// CSS - injected once, without separate file (no build step)
// =============================================================================
function _inject_styles() {
    if (document.getElementById("ad-css")) return;
    const s = document.createElement("style");
    s.id = "ad-css";
    s.textContent = `
.ad-wrap{max-width:1160px;margin:0 auto;padding:20px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.ad-grid{display:grid;grid-template-columns:260px 1fr;gap:18px;margin-top:14px}

/* status bar */
.ad-status-bar{display:flex;align-items:center;gap:10px;padding:10px 16px;background:#f8f9fa;border:1px solid #e9ecef;border-radius:8px;font-size:13px}
.ad-dot{width:10px;height:10px;border-radius:50%;background:#ffc107;flex-shrink:0;animation:ad-pulse 1.4s ease-in-out infinite}
.ad-dot.online{background:#28a745;animation:none}
.ad-dot.offline{background:#dc3545;animation:none}
@keyframes ad-pulse{0%,100%{opacity:1}50%{opacity:.3}}
#ad-model-list{margin-left:auto;color:#6c757d;font-size:11px}

/* karty */
.ad-card{background:#fff;border:1px solid #e9ecef;border-radius:8px;padding:14px;margin-bottom:12px}
.ad-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#6c757d;margin-bottom:10px;display:block}

/* sidebar */
.ad-sidebar{display:flex;flex-direction:column}
.ad-tool{display:flex;align-items:flex-start;gap:9px;padding:8px 9px;border:1px solid #e9ecef;border-radius:6px;margin-bottom:6px;transition:all .2s}
.ad-tool.active{border-color:#4361ee;background:#f0f4ff;box-shadow:0 2px 8px rgba(67,97,238,.15)}
.ad-tool-icon{font-size:18px;flex-shrink:0;margin-top:1px}
.ad-tool-name{font-weight:600;font-size:12px}
.ad-tool-desc{font-size:11px;color:#6c757d;line-height:1.4;margin-top:2px}
.ad-react-row{display:flex;gap:8px;align-items:flex-start;margin-bottom:9px;font-size:12px;color:#495057}
.ad-rnum{width:20px;height:20px;background:#4361ee;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;flex-shrink:0}

/* main panel */
.ad-main{background:#fff;border:1px solid #e9ecef;border-radius:8px;overflow:hidden}
.ad-tabs{display:flex;border-bottom:1px solid #e9ecef;background:#f8f9fa}
.ad-tab{padding:10px 18px;font-size:13px;font-weight:500;border:none;background:none;cursor:pointer;color:#6c757d;border-bottom:2px solid transparent;transition:all .2s}
.ad-tab.active{color:#4361ee;border-bottom-color:#4361ee;background:#fff}
.ad-tab-body{padding:16px 18px}

/* input */
.ad-input-row{display:flex;gap:10px;margin-bottom:10px}
.ad-input{flex:1;padding:9px 14px;border:1px solid #dee2e6;border-radius:6px;font-size:14px;outline:none;transition:border-color .2s}
.ad-input:focus{border-color:#4361ee;box-shadow:0 0 0 3px rgba(67,97,238,.1)}
.ad-btn{padding:9px 18px;background:#4361ee;color:#fff;border:none;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer;display:flex;align-items:center;gap:7px;transition:background .2s;white-space:nowrap}
.ad-btn:hover{background:#3451d1}
.ad-btn:disabled{background:#a0aec0;cursor:not-allowed}

/* chips */
.ad-chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.ad-chip{padding:4px 10px;background:#f0f4ff;color:#4361ee;border:1px solid #c7d2fe;border-radius:20px;font-size:12px;cursor:pointer;transition:all .15s}
.ad-chip:hover{background:#4361ee;color:#fff}

/* no tools message */
.ad-no-tools{display:flex;align-items:center;gap:12px;padding:16px 20px;background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;width:100%}
.ad-no-tools-icon{font-size:24px;flex-shrink:0}
.ad-no-tools-text{flex:1}

/* spinner */
.ad-spin{display:inline-block;width:13px;height:13px;border:2px solid rgba(255,255,255,.4);border-top-color:#fff;border-radius:50%;animation:ad-spin .7s linear infinite}
@keyframes ad-spin{to{transform:rotate(360deg)}}

/* ===== PIPELINE LOG ===== */
.ad-log-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.ad-log-cnt{font-size:11px;color:#6c757d;background:#f8f9fa;padding:2px 8px;border-radius:10px;border:1px solid #e9ecef}
.ad-log{height:440px;overflow-y:auto;border:1px solid #e9ecef;border-radius:8px;background:#fafafa;padding:6px;display:flex;flex-direction:column;gap:4px;scroll-behavior:smooth}

.ad-entry{display:flex;gap:10px;align-items:flex-start;padding:8px 10px;border-radius:6px;animation:ad-slide .25s ease both;flex-shrink:0}
.ad-thinking{border:1px dashed #dee2e6 !important;background:#fff !important;color:#6c757d;font-size:13px;gap:10px;border-left:3px solid #dee2e6 !important}
@keyframes ad-slide{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:translateX(0)}}

.ad-e-icon{font-size:15px;line-height:1.7;flex-shrink:0}
.ad-e-body{flex:1;min-width:0}
.ad-e-type{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:1px}
.ad-e-label{font-size:12px;font-weight:500;color:#212529;margin-bottom:3px}
.ad-e-data{margin-top:4px;font-size:12px;color:#495057}

/* diff before → after */
.ad-diffs{display:flex;flex-direction:column;gap:4px}
.ad-diff{font-size:12px;font-family:monospace}
.ad-before{background:#ffe4e4;color:#b91c1c;padding:1px 6px;border-radius:3px}
.ad-after{background:#dcfce7;color:#15803d;padding:1px 6px;border-radius:3px;font-weight:600}
.ad-arrow{color:#6c757d;margin:0 2px}

/* badges */
.ad-badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;margin-right:4px}
.ad-tool-tag{display:inline-block;font-size:11px;font-weight:600;margin-right:6px}
.ad-mono{font-family:monospace;background:rgba(0,0,0,.04);padding:2px 5px;border-radius:3px;word-break:break-all;font-size:11px}
.ad-json{font-family:monospace;font-size:11px;background:rgba(0,0,0,.04);padding:2px 5px;border-radius:3px;word-break:break-all}
.ad-muted{color:#6c757d;font-style:italic;font-size:11px}

/* expandable json */
.ad-json-container{margin-top:4px;border:1px solid #e9ecef;border-radius:4px;overflow:hidden}
.ad-json-header{padding:6px 10px;background:#f8f9fa;cursor:pointer;display:flex;align-items:center;gap:6px;font-size:11px;font-weight:600;color:#495057;border-bottom:1px solid #e9ecef}
.ad-json-header:hover{background:#e9ecef}
.ad-json-toggle{transition:transform .2s;font-size:10px}
.ad-json-container.expanded .ad-json-toggle{transform:rotate(90deg)}
.ad-json-preview{display:block}
.ad-json-full{display:none}
.ad-json-container.expanded .ad-json-preview{display:none}
.ad-json-container.expanded .ad-json-full{display:block}
.ad-json-content{font-family:monospace;font-size:11px;line-height:1.4;margin:0;padding:8px;background:#fafafa;color:#333;white-space:pre-wrap;word-break:break-all}
.ad-json-small{border:1px solid #e9ecef;border-radius:4px;background:#fafafa}

/* json syntax highlighting */
.json-key{color:#0066cc;font-weight:600}
.json-string{color:#d14}
.json-number{color:#099}
.json-boolean{color:#0086b3}
.json-null{color:#999;font-style:italic}

@media(max-width:768px){.ad-grid{grid-template-columns:1fr}}
`;
    document.head.appendChild(s);
}
