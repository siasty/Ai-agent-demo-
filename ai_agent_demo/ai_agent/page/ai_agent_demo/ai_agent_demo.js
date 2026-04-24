// =============================================================================
// AI Agent Demo – Frappe Page
//
// Pokazuje:
//   • status Ollamy (lokalny LLM)
//   • listę dostępnych narzędzi agenta
//   • wizualizację pętli ReAct krok po kroku (Myśl / Działaj / Obserwuj)
//   • demo anonimizacji danych osobowych
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
// Ikony narzędzi
// ---------------------------------------------------------------------------
const TOOL_ICONS = {
    anonymize_data: "🔒",
    search_database: "🔍",
    analyze_data: "📊",
    get_datetime: "🕐",
};

const FINDING_COLORS = {
    email: "#0d6efd",
    phone: "#198754",
    pesel: "#dc3545",
    name: "#fd7e14",
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
    // Renderowanie HTML
    // -----------------------------------------------------------------------
    _render() {
        this.$el.html(`
<div class="ad-wrap">

  <!-- ===== PASEK STATUSU ===== -->
  <div class="ad-status-bar">
    <span id="ad-dot" class="ad-dot"></span>
    <span id="ad-status-txt">Sprawdzanie połączenia z Ollama…</span>
    <span id="ad-model-list"></span>
  </div>

  <!-- ===== SIATKA GŁÓWNA ===== -->
  <div class="ad-grid">

    <!-- === PANEL NARZĘDZI === -->
    <aside class="ad-sidebar">
      <div class="ad-card">
        <p class="ad-section-label">Dostępne narzędzia</p>
        <div id="ad-tools-list"></div>
      </div>

      <div class="ad-card ad-how">
        <p class="ad-section-label">Jak działa agent?</p>
        <div class="ad-step-info">
          <div class="ad-step-bubble">1</div>
          <div><strong>Myśl</strong> – LLM analizuje zapytanie i wybiera narzędzie</div>
        </div>
        <div class="ad-step-info">
          <div class="ad-step-bubble">2</div>
          <div><strong>Działaj</strong> – wywołuje narzędzie z parametrami</div>
        </div>
        <div class="ad-step-info">
          <div class="ad-step-bubble">3</div>
          <div><strong>Obserwuj</strong> – przetwarza wynik i kontynuuje lub kończy</div>
        </div>
      </div>
    </aside>

    <!-- === PANEL GŁÓWNY === -->
    <main class="ad-main">

      <!-- TABS -->
      <nav class="ad-tabs">
        <button class="ad-tab active" data-tab="agent">🤖 Agent AI</button>
        <button class="ad-tab" data-tab="anon">🔒 Anonimizacja Danych</button>
      </nav>

      <!-- TAB: AGENT -->
      <div id="ad-tab-agent" class="ad-tab-body">

        <!-- Wejście -->
        <div class="ad-input-row">
          <input id="ad-query" class="ad-input" type="text"
            placeholder="Zadaj pytanie agentowi…" />
          <button id="ad-run-btn" class="ad-btn-primary">
            <span id="ad-btn-label">▶ Uruchom</span>
          </button>
        </div>

        <!-- Przykłady -->
        <div class="ad-chips">
          <span class="ad-chip">🕐 Podaj aktualną datę i godzinę</span>
          <span class="ad-chip">🔒 Zanonimizuj: Jan Kowalski, jan@example.com, tel: 500 100 200, PESEL: 85071234567</span>
          <span class="ad-chip">📊 Oblicz statystyki dla liczb: 15, 42, 7, 93, 28, 64</span>
        </div>

        <!-- Wizualizacja kroków -->
        <div id="ad-steps-wrap" style="display:none">
          <p class="ad-section-label" style="margin-top:16px">Przebieg rozumowania (ReAct):</p>
          <div id="ad-steps"></div>
          <div id="ad-answer" class="ad-answer" style="display:none">
            <div class="ad-answer-label">✅ Odpowiedź agenta</div>
            <div id="ad-answer-text"></div>
          </div>
        </div>
      </div>

      <!-- TAB: ANONIMIZACJA -->
      <div id="ad-tab-anon" class="ad-tab-body" style="display:none">
        <div class="ad-anon-grid">

          <div>
            <p class="ad-section-label">Tekst z danymi osobowymi</p>
            <textarea id="ad-anon-input" class="ad-textarea"
              placeholder="Wklej tekst zawierający dane osobowe…

Przykład:
Klient Jan Kowalski (PESEL: 85071234567)
Email: jan.kowalski@example.com
Telefon: +48 500 100 200"></textarea>

            <div class="ad-type-row">
              <label class="ad-check"><input type="checkbox" class="ad-type" value="email" checked> 📧 Email</label>
              <label class="ad-check"><input type="checkbox" class="ad-type" value="phone" checked> 📱 Telefon</label>
              <label class="ad-check"><input type="checkbox" class="ad-type" value="pesel" checked> 🪹 PESEL</label>
              <label class="ad-check"><input type="checkbox" class="ad-type" value="name"  checked> 👤 Imiona</label>
            </div>

            <button id="ad-anon-btn" class="ad-btn-primary" style="margin-top:10px">🔒 Anonimizuj</button>
          </div>

          <div>
            <p class="ad-section-label">Wynik anonimizacji</p>
            <div id="ad-anon-out" class="ad-anon-out">
              <span style="color:#adb5bd">Wynik pojawi się tutaj…</span>
            </div>
            <div id="ad-findings" class="ad-findings"></div>
          </div>
        </div>
      </div>

    </main>
  </div>
</div>
        `);

        this._bind_events();
    }

    // -----------------------------------------------------------------------
    // Zdarzenia
    // -----------------------------------------------------------------------
    _bind_events() {
        // przełączanie zakładek
        this.$el.on("click", ".ad-tab", (e) => {
            const tab = $(e.currentTarget).data("tab");
            this.$el.find(".ad-tab").removeClass("active");
            $(e.currentTarget).addClass("active");
            this.$el.find(".ad-tab-body").hide();
            this.$el.find(`#ad-tab-${tab}`).show();
        });

        // uruchomienie agenta
        this.$el.find("#ad-run-btn").on("click", () => this._run_agent());
        this.$el.find("#ad-query").on("keydown", (e) => {
            if (e.key === "Enter") this._run_agent();
        });

        // przykładowe zapytania
        this.$el.on("click", ".ad-chip", (e) => {
            const raw = $(e.currentTarget).text().trim();
            // usuń ikonę z początku
            const text = raw.replace(/^[\p{Emoji}\s]+/u, "").trim();
            this.$el.find("#ad-query").val(text).focus();
        });

        // anonimizacja
        this.$el.find("#ad-anon-btn").on("click", () => this._run_anonymize());
    }

    // -----------------------------------------------------------------------
    // Status Ollamy
    // -----------------------------------------------------------------------
    _load_status() {
        frappe.call({
            method: "ai_agent_demo.ai_agent.api.get_agent_status",
            callback: (r) => {
                const s = r.message || {};
                const $dot = this.$el.find("#ad-dot");
                const $txt = this.$el.find("#ad-status-txt");
                const $mdl = this.$el.find("#ad-model-list");

                if (s.ollama_available) {
                    $dot.addClass("online");
                    $txt.text("Ollama: połączono");
                    $mdl.text(`Modele: ${s.models.slice(0, 3).join(", ")}`);
                } else {
                    $dot.addClass("offline");
                    $txt.html(
                        "Ollama offline — uruchom: "
                        + "<code>ollama serve</code> i "
                        + "<code>ollama pull llama3.2</code>"
                    );
                }
                this._load_tools();
            },
        });
    }

    // -----------------------------------------------------------------------
    // Lista narzędzi w sidebarze
    // -----------------------------------------------------------------------
    _load_tools() {
        frappe.call({
            method: "ai_agent_demo.ai_agent.api.get_available_tools",
            callback: (r) => {
                const $list = this.$el.find("#ad-tools-list").empty();
                (r.message || []).forEach((tool) => {
                    const icon = TOOL_ICONS[tool.name] || "🔧";
                    $list.append(`
<div class="ad-tool-card" id="ad-tool-${tool.name.replace(/_/g, "-")}">
  <div class="ad-tool-icon">${icon}</div>
  <div>
    <div class="ad-tool-name">${tool.name}</div>
    <div class="ad-tool-desc">${tool.description}</div>
  </div>
</div>`);
                });
            },
        });
    }

    _highlight_tool(name) {
        const id = `#ad-tool-${name.replace(/_/g, "-")}`;
        this.$el.find(".ad-tool-card").removeClass("active");
        this.$el.find(id).addClass("active");
        setTimeout(() => this.$el.find(".ad-tool-card").removeClass("active"), 2500);
    }

    // -----------------------------------------------------------------------
    // Uruchomienie agenta
    // -----------------------------------------------------------------------
    _run_agent() {
        const query = this.$el.find("#ad-query").val().trim();
        if (!query) return;

        const $btn = this.$el.find("#ad-run-btn");
        const $label = this.$el.find("#ad-btn-label");
        $btn.prop("disabled", true);
        $label.html('<span class="ad-spinner"></span> Myślę…');

        const $wrap = this.$el.find("#ad-steps-wrap").show();
        const $steps = this.$el.find("#ad-steps").empty();
        this.$el.find("#ad-answer").hide();

        $steps.append(`
<div class="ad-thinking">
  <div class="ad-spinner" style="border-color:rgba(0,0,0,.15);border-top-color:#4361ee"></div>
  Agent analizuje zapytanie i dobiera narzędzia…
</div>`);

        frappe.call({
            method: "ai_agent_demo.ai_agent.api.run_agent",
            args: { query, session_name: this.session },
            callback: (r) => {
                $btn.prop("disabled", false);
                $label.html("▶ Uruchom");
                $steps.empty();

                if (r.message) {
                    this._render_steps(r.message.steps || []);
                    if (r.message.answer) {
                        this.$el.find("#ad-answer-text").text(r.message.answer);
                        this.$el.find("#ad-answer").show();
                    }
                }
            },
            error: () => {
                $btn.prop("disabled", false);
                $label.html("▶ Uruchom");
                $steps.html('<div class="ad-thinking" style="color:#dc3545">❌ Błąd połączenia z agentem.</div>');
            },
        });
    }

    // -----------------------------------------------------------------------
    // Wizualizacja kroków ReAct
    // -----------------------------------------------------------------------
    _render_steps(steps) {
        const $steps = this.$el.find("#ad-steps");

        steps.forEach((step, i) => {
            const hasTool = step.tool_name && step.tool_name !== "FINISH";
            const icon = hasTool ? (TOOL_ICONS[step.tool_name] || "🔧") : "";

            if (hasTool) this._highlight_tool(step.tool_name);

            $steps.append(`
<div class="ad-step" style="animation-delay:${i * 0.12}s">
  <div class="ad-step-hdr">
    <span class="ad-step-num">${i + 1}</span>
    <span>Krok ${i + 1}</span>
    ${hasTool ? `<span class="ad-tool-badge" style="margin-left:auto">${icon} ${step.tool_name}</span>` : ""}
  </div>
  <div class="ad-step-body">

    <!-- MYŚL -->
    <div class="ad-row-thought">
      <span class="ad-row-icon">💭</span>
      <span>${frappe.utils.escape_html(step.thought)}</span>
    </div>

    ${hasTool ? `
    <!-- DZIAŁAJ -->
    <div class="ad-row-tool">
      <span>Wywołuje:</span>
      <span class="ad-tool-badge">${icon} ${step.tool_name}</span>
      <code class="ad-code">${frappe.utils.escape_html(JSON.stringify(step.tool_input))}</code>
    </div>

    <!-- OBSERWUJ -->
    <div class="ad-row-obs">
      <span class="ad-row-icon">✅</span>
      <span>${frappe.utils.escape_html(step.observation || "")}</span>
    </div>
    ` : ""}

  </div>
</div>`);
        });
    }

    // -----------------------------------------------------------------------
    // Anonimizacja danych
    // -----------------------------------------------------------------------
    _run_anonymize() {
        const text = this.$el.find("#ad-anon-input").val();
        if (!text.trim()) return;

        const data_types = [];
        this.$el.find(".ad-type:checked").each((_, el) => data_types.push(el.value));

        frappe.call({
            method: "ai_agent_demo.ai_agent.api.anonymize_text",
            args: { text, data_types: JSON.stringify(data_types) },
            callback: (r) => {
                if (!r.message) return;
                const { anonymized, findings } = r.message;

                this.$el.find("#ad-anon-out").text(anonymized);

                const $f = this.$el.find("#ad-findings").empty();
                const keys = Object.keys(findings);

                if (keys.length) {
                    $f.append('<span class="ad-findings-label">WYKRYTO:</span>');
                    keys.forEach((k) => {
                        const color = FINDING_COLORS[k] || "#6c757d";
                        $f.append(`
<span class="ad-finding-badge"
      style="background:${color}20;color:${color};border:1px solid ${color}50">
  ${k}: ${findings[k]}
</span>`);
                    });
                } else {
                    $f.html('<span style="color:#6c757d;font-size:12px">Brak wykrytych danych osobowych.</span>');
                }
            },
        });
    }
}

// =============================================================================
// Style CSS (wstrzykiwane inline — błyskawicznie, bez osobnego pliku)
// =============================================================================
function _inject_styles() {
    if (document.getElementById("ad-styles")) return;
    const style = document.createElement("style");
    style.id = "ad-styles";
    style.textContent = `
/* === LAYOUT === */
.ad-wrap { max-width:1200px; margin:0 auto; padding:20px; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
.ad-grid { display:grid; grid-template-columns:270px 1fr; gap:20px; margin-top:16px; }

/* === STATUS BAR === */
.ad-status-bar {
  display:flex; align-items:center; gap:12px;
  padding:10px 16px; background:#f8f9fa;
  border:1px solid #e9ecef; border-radius:8px;
  font-size:13px;
}
.ad-dot {
  width:10px; height:10px; border-radius:50%; background:#ffc107; flex-shrink:0;
  animation:ad-pulse 1.4s ease-in-out infinite;
}
.ad-dot.online  { background:#28a745; animation:none; }
.ad-dot.offline { background:#dc3545; animation:none; }
@keyframes ad-pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
#ad-model-list { margin-left:auto; color:#6c757d; font-size:12px; }

/* === KARTA === */
.ad-card {
  background:#fff; border:1px solid #e9ecef;
  border-radius:8px; padding:14px; margin-bottom:14px;
}
.ad-section-label {
  font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:1px; color:#6c757d; margin-bottom:10px;
}

/* === SIDEBAR === */
.ad-sidebar { display:flex; flex-direction:column; }
.ad-tool-card {
  display:flex; align-items:flex-start; gap:10px;
  padding:9px 10px; border:1px solid #e9ecef;
  border-radius:6px; margin-bottom:7px;
  transition:border-color .2s, background .2s;
}
.ad-tool-card.active { border-color:#4361ee; background:#f0f4ff; box-shadow:0 2px 8px rgba(67,97,238,.15); }
.ad-tool-icon { font-size:20px; line-height:1; flex-shrink:0; }
.ad-tool-name { font-weight:600; font-size:12px; }
.ad-tool-desc { font-size:11px; color:#6c757d; line-height:1.4; margin-top:2px; }

.ad-how .ad-step-info {
  display:flex; align-items:flex-start; gap:8px;
  font-size:12px; color:#495057; margin-bottom:10px;
}
.ad-step-bubble {
  width:20px; height:20px; background:#4361ee; color:#fff;
  border-radius:50%; display:flex; align-items:center;
  justify-content:center; font-size:10px; font-weight:700; flex-shrink:0;
}

/* === MAIN PANEL === */
.ad-main {
  background:#fff; border:1px solid #e9ecef;
  border-radius:8px; overflow:hidden;
}

/* === TABS === */
.ad-tabs { display:flex; border-bottom:1px solid #e9ecef; background:#f8f9fa; }
.ad-tab {
  padding:11px 20px; font-size:13px; font-weight:500;
  border:none; background:none; cursor:pointer; color:#6c757d;
  border-bottom:2px solid transparent; transition:all .2s;
}
.ad-tab.active { color:#4361ee; border-bottom-color:#4361ee; background:#fff; }
.ad-tab-body { padding:18px 20px; }

/* === INPUT === */
.ad-input-row { display:flex; gap:10px; margin-bottom:10px; }
.ad-input {
  flex:1; padding:9px 14px; border:1px solid #dee2e6;
  border-radius:6px; font-size:14px; outline:none;
  transition:border-color .2s, box-shadow .2s;
}
.ad-input:focus { border-color:#4361ee; box-shadow:0 0 0 3px rgba(67,97,238,.1); }

.ad-btn-primary {
  padding:9px 20px; background:#4361ee; color:#fff;
  border:none; border-radius:6px; font-weight:600;
  font-size:14px; cursor:pointer; display:flex;
  align-items:center; gap:8px; transition:background .2s;
  white-space:nowrap;
}
.ad-btn-primary:hover  { background:#3451d1; }
.ad-btn-primary:disabled { background:#a0aec0; cursor:not-allowed; }

/* === CHIPS === */
.ad-chips { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:16px; }
.ad-chip {
  padding:4px 10px; background:#f0f4ff; color:#4361ee;
  border:1px solid #c7d2fe; border-radius:20px;
  font-size:12px; cursor:pointer; transition:all .15s;
}
.ad-chip:hover { background:#4361ee; color:#fff; }

/* === SPINNER === */
.ad-spinner {
  display:inline-block; width:14px; height:14px;
  border:2px solid rgba(255,255,255,.4);
  border-top-color:#fff; border-radius:50%;
  animation:ad-spin .7s linear infinite;
}
@keyframes ad-spin { to { transform:rotate(360deg); } }

/* === THINKING === */
.ad-thinking {
  padding:12px 14px;
  border:1px dashed #dee2e6; border-radius:8px;
  display:flex; align-items:center; gap:10px;
  color:#6c757d; font-size:13px;
}

/* === KROK ReAct === */
.ad-step {
  border:1px solid #e9ecef; border-radius:8px;
  margin-bottom:10px; overflow:hidden;
  animation:ad-slide .3s ease both;
}
@keyframes ad-slide { from{opacity:0;transform:translateY(-8px)} to{opacity:1;transform:translateY(0)} }
.ad-step-hdr {
  display:flex; align-items:center; gap:8px;
  padding:9px 14px; background:#f8f9fa;
  border-bottom:1px solid #e9ecef;
  font-size:13px; font-weight:600;
}
.ad-step-num {
  width:22px; height:22px; background:#4361ee; color:#fff;
  border-radius:50%; display:flex; align-items:center;
  justify-content:center; font-size:11px; font-weight:700; flex-shrink:0;
}
.ad-step-body { padding:12px 14px; }

.ad-row-thought {
  display:flex; gap:8px; align-items:flex-start;
  font-size:13px; color:#495057; margin-bottom:9px;
}
.ad-row-icon { font-size:15px; flex-shrink:0; }

.ad-row-tool {
  display:flex; flex-wrap:wrap; align-items:center; gap:7px;
  padding:7px 10px; background:#f0f4ff;
  border-radius:6px; margin-bottom:7px; font-size:12px;
}
.ad-tool-badge {
  background:#4361ee; color:#fff;
  padding:2px 8px; border-radius:4px;
  font-size:11px; font-weight:600;
}
.ad-code {
  font-family:"Courier New",monospace;
  font-size:11px; color:#495057;
  word-break:break-all;
}

.ad-row-obs {
  display:flex; gap:8px; align-items:flex-start;
  padding:7px 10px; background:#f0fff4;
  border-radius:6px; font-size:12px; color:#2d6a4f;
}

/* === FINALNA ODPOWIEDŹ === */
.ad-answer {
  margin-top:14px; padding:14px;
  background:linear-gradient(135deg,#f0f4ff 0%,#f0fff4 100%);
  border:1px solid #c3dafe; border-radius:8px; font-size:14px;
}
.ad-answer-label {
  font-weight:700; font-size:11px; text-transform:uppercase;
  letter-spacing:1px; color:#4361ee; margin-bottom:6px;
}

/* === ANONIMIZACJA === */
.ad-anon-grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.ad-textarea {
  width:100%; padding:10px 12px;
  border:1px solid #dee2e6; border-radius:6px;
  font-family:"Courier New",monospace; font-size:12px;
  min-height:180px; resize:vertical; outline:none;
  transition:border-color .2s;
  box-sizing:border-box;
}
.ad-textarea:focus { border-color:#4361ee; box-shadow:0 0 0 3px rgba(67,97,238,.1); }

.ad-type-row { display:flex; flex-wrap:wrap; gap:10px; margin:10px 0; }
.ad-check { display:flex; align-items:center; gap:5px; font-size:13px; cursor:pointer; }

.ad-anon-out {
  min-height:180px; padding:10px 12px;
  background:#f8f9fa; border:1px solid #e9ecef;
  border-radius:6px; font-family:"Courier New",monospace;
  font-size:12px; white-space:pre-wrap; word-break:break-word;
}

.ad-findings { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; align-items:center; }
.ad-findings-label { font-size:11px; font-weight:700; color:#6c757d; }
.ad-finding-badge {
  padding:2px 10px; border-radius:12px;
  font-size:11px; font-weight:600;
}

/* Responsywność */
@media (max-width: 768px) {
  .ad-grid        { grid-template-columns:1fr; }
  .ad-anon-grid   { grid-template-columns:1fr; }
}
`;
    document.head.appendChild(style);
}
