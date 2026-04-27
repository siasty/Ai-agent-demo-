// =============================================================================
// AI Agent Demo – Frappe Page (plain JS, no build step needed)
//
// Pokazuje pipeline_log krok po kroku:
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
// Metadane narzędzi
// ---------------------------------------------------------------------------
const TOOL_META = {
    anonymize_data:       { icon: "🔒", color: "#dc3545" },
    search_database:      { icon: "🔍", color: "#0d6efd" },
    analyze_data:         { icon: "📊", color: "#198754" },
    get_datetime:         { icon: "🕐", color: "#6f42c1" },
    search_customers:     { icon: "🏢", color: "#0d6efd" },
    analyze_sales_orders: { icon: "📈", color: "#198754" },
    check_inventory:      { icon: "📦", color: "#fd7e14" },
    business_analytics:   { icon: "💼", color: "#6f42c1" },
};

// Konfiguracja każdego typu zdarzenia w logu
const LOG_CFG = {
    input:            { icon: "📥", color: "#0d6efd",  bg: "#f0f7ff", title: "WEJŚCIE" },
    preprocess:       { icon: "⚙️",  color: "#6f42c1",  bg: "#f8f5ff", title: "PRE-PROCESSING" },
    detect:           { icon: "🔍", color: "#fd7e14",  bg: "#fff8f0", title: "WYKRYWANIE DANYCH" },
    agent_init:       { icon: "🤖", color: "#0dcaf0",  bg: "#f0feff", title: "AGENT INIT" },
    model_req:        { icon: "➡️",  color: "#6c757d",  bg: "#f8f9fa", title: "MODEL REQUEST" },
    think:            { icon: "💭", color: "#856404",  bg: "#fffbef", title: "MYŚL (REASON)" },
    tool_select:      { icon: "🎯", color: "#4361ee",  bg: "#f0f4ff", title: "WYBÓR NARZĘDZIA (ACT)" },
    tool_input:       { icon: "↘️",  color: "#4361ee",  bg: "#eef1ff", title: "PARAMETRY WEJŚCIOWE" },
    anon_start:       { icon: "🔎", color: "#dc3545",  bg: "#fff5f5", title: "ANONIMIZACJA START" },
    anonymize_change: { icon: "🔒", color: "#dc3545",  bg: "#fff5f5", title: "ZMIANA" },
    anon_done:        { icon: "✔️",  color: "#198754",  bg: "#f0fff4", title: "ANONIMIZACJA OK" },
    tool_output:      { icon: "↙️",  color: "#198754",  bg: "#f0fff4", title: "WYNIK NARZĘDZIA (OBSERVE)" },
    finish:           { icon: "✅", color: "#198754",  bg: "#e8f8ee", title: "ODPOWIEDŹ KOŃCOWA" },
};

// ---------------------------------------------------------------------------
// Główna klasa strony
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
    <span id="ad-status-txt">Sprawdzanie Ollama&hellip;</span>
    <span id="ad-model-list"></span>
  </div>

  <div class="ad-grid">

    <!-- Sidebar -->
    <aside class="ad-sidebar">
      <div class="ad-card">
        <p class="ad-label">Dostępne narzędzia</p>
        <div id="ad-tools-list"></div>
      </div>
      <div class="ad-card">
        <p class="ad-label">Jak działa agent? (ReAct)</p>
        <div class="ad-react-row"><div class="ad-rnum">1</div><div><b>Myśl</b> – LLM wybiera narzędzie</div></div>
        <div class="ad-react-row"><div class="ad-rnum">2</div><div><b>Działaj</b> – wywołuje narzędzie</div></div>
        <div class="ad-react-row"><div class="ad-rnum">3</div><div><b>Obserwuj</b> – przetwarza wynik</div></div>
      </div>
    </aside>

    <!-- Panel główny -->
    <main class="ad-main">

      <nav class="ad-tabs">
        <button class="ad-tab active" data-tab="agent">🤖 Agent AI</button>
      </nav>

      <!-- Tab: Agent -->
      <div id="ad-tab-agent" class="ad-tab-body">

        <div class="ad-input-row">
          <input id="ad-query" class="ad-input" type="text" placeholder="Zadaj pytanie agentowi…" />
          <button id="ad-run-btn" class="ad-btn">
            <span id="ad-btn-label">▶ Uruchom</span>
          </button>
        </div>

        <div class="ad-chips">
          <span class="ad-chip" data-q="Podaj aktualną datę i godzinę">🕐 Podaj aktualną datę i godzinę</span>
          <span class="ad-chip" data-q="Wyszukaj klientów z Warszawy">🏢 Klienci z Warszawy (z anonimizacją PII)</span>
          <span class="ad-chip" data-q="Pokaż analizę zamówień z ostatnich 30 dni">📈 Analiza zamówień sprzedaży</span>
          <span class="ad-chip" data-q="Sprawdź stan magazynu dla produktów LED">📦 Stan magazynu LED</span>
          <span class="ad-chip" data-q="Wykonaj analizę biznesową sprzedaży">💼 Analiza biznesowa</span>
        </div>

        <!-- Pipeline log -->
        <div id="ad-log-wrap" style="display:none">
          <div class="ad-log-hdr">
            <span class="ad-label" style="margin:0">Pipeline Log – krok po kroku</span>
            <span id="ad-log-cnt" class="ad-log-cnt">0 zdarzeń</span>
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
    // Zdarzenia
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
                    this.$el.find("#ad-status-txt").text("Ollama: połączono");
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
        this.$el.find("#ad-btn-label").html('<span class="ad-spin"></span> Myślę…');

        const $log = this.$el.find("#ad-log").empty();
        this.$el.find("#ad-log-wrap").show();
        this.$el.find("#ad-log-cnt").text("0 zdarzeń");

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
  <div class="ad-e-label">Błąd połączenia z agentem</div></div>
</div>`);
            },
        });
    }

    // -----------------------------------------------------------------------
    // Renderowanie logu – wpisy pojawiają się jeden po drugim
    // -----------------------------------------------------------------------
    _render_log(entries) {
        const $log = this.$el.find("#ad-log");
        const $cnt = this.$el.find("#ad-log-cnt");

        entries.forEach((entry, i) => {
            setTimeout(() => {
                $log.append(this._make_entry(entry));
                $cnt.text(`${i + 1} zdarzeń`);
                $log[0].scrollTop = $log[0].scrollHeight;

                if (entry.type === "tool_select" && typeof entry.data === "string") {
                    this._hi_tool(entry.data);
                }
            }, i * 130);
        });
    }

    // -----------------------------------------------------------------------
    // Budowanie pojedynczego wpisu logu
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
    // Formatowanie danych według typu zdarzenia
    // -----------------------------------------------------------------------
    _fmt(data, type) {
        if (data === null || data === undefined || data === "") return "";

        // Anonimizacja – pokazuj before → after dla każdego sample
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

        // Wykryte dane – kolorowe badges
        if (type === "detect" && typeof data === "object" && !Array.isArray(data)) {
            if (!Object.keys(data).length) return `<span class="ad-muted">brak danych osobowych</span>`;
            const COLORS = { email: "#0d6efd", phone: "#198754", pesel: "#dc3545", name: "#fd7e14" };
            return Object.entries(data).map(([k, v]) => {
                const c = COLORS[k] || "#6c757d";
                return `<span class="ad-badge" style="background:${c}20;color:${c};border:1px solid ${c}50">${k}: ${v}</span>`;
            }).join(" ");
        }

        // Lista narzędzi przy agent_init
        if (type === "agent_init" && Array.isArray(data)) {
            return data.map(n => {
                const m = TOOL_META[n] || { icon: "🔧", color: "#6c757d" };
                return `<span class="ad-tool-tag" style="color:${m.color}">${m.icon} ${n}</span>`;
            }).join(" ");
        }

        // Obiekt / tablica – jako zwięzły JSON
        if (typeof data === "object") {
            return `<code class="ad-json">${frappe.utils.escape_html(JSON.stringify(data))}</code>`;
        }

        // Zwykły string
        return `<span class="ad-mono">${frappe.utils.escape_html(String(data))}</span>`;
    }

}

// =============================================================================
// CSS – wstrzykiwany raz, bez osobnego pliku (brak build step)
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

@media(max-width:768px){.ad-grid{grid-template-columns:1fr}}
`;
    document.head.appendChild(s);
}
