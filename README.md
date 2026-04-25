# 🤖 Frappe AI Agent Demo

Demo pokazujące **jak działa agent AI** uruchomiony na **lokalnym modelu LLM** (Ollama).  
Zaprojektowane wg zasad OOP – każda klasa ma jedną odpowiedzialność i jest łatwa do zrozumienia.

---

## Co pokazuje ta aplikacja?

| Funkcja | Opis |
|---|---|
| **ReAct Loop** | Wizualizacja cyklu: Myśl → Działaj → Obserwuj |
| **Wybór narzędzi** | Agent sam decyduje, które narzędzie wywołać |
| **Anonimizacja danych** | Demo RODO: email, telefon, PESEL, imiona |
| **Lokalny model** | Ollama – żadne dane nie wychodzą na zewnątrz |

---

## Architektura OOP

```
Agent                    # Koordynator – ReAct loop
├── LocalModel           # Adapter do Ollama HTTP API
├── ToolRegistry         # Rejestr dostępnych narzędzi
└── AgentStep            # Jeden krok rozumowania

Tool (ABC)               # Interfejs narzędzia
├── AnonymizationTool    # → wywołuje DataAnonymizer
├── DatabaseSearchTool   # → Frappe frappe.get_list()
├── DataAnalysisTool     # → statystyki listy liczb
└── DateTimeTool         # → datetime.now()

DataAnonymizer           # Koordynator strategii
├── EmailAnonymizer      # regex + maskowanie
├── PhoneAnonymizer      # polskie numery
├── PeselAnonymizer      # 11-cyfrowy PESEL
└── NameAnonymizer       # lista polskich imion
```

---

## Wymagania

1. **Frappe** (v14+)
2. **Ollama** – lokalny serwer LLM

```bash
# Instalacja Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pobranie modelu (llama3.2 ~2GB)
ollama pull llama3.2

# Uruchomienie serwera
ollama serve
```

---

## Instalacja Frappe App

```bash
# W katalogu frappe-bench
bench get-app https://github.com/siasty/ai-agent-demo-
bench --site your-site.local install-app ai_agent_demo
bench --site your-site.local migrate
bench build
bench restart
```

Następnie otwórz w Frappe: **Menu → AI Agent Demo**

---

## Przepływ działania agenta

```
Użytkownik: "Zanonimizuj: Jan Kowalski, jan@firma.pl"
                    │
                    ▼
              Agent.run(query)
                    │
          ┌─────────▼──────────┐
          │   LocalModel.chat  │  ← system prompt z listą narzędzi
          └─────────┬──────────┘
                    │ JSON: {thought, tool, input}
                    ▼
          ┌─────────────────────┐
          │   ToolRegistry.get  │  ← wybiera AnonymizationTool
          └─────────┬───────────┘
                    │
                    ▼
          AnonymizationTool.execute()
                    │
                    ▼
          DataAnonymizer.anonymize()
                    │
          ┌─────────▼──────────┐
          │   LocalModel.chat  │  ← obserwacja wyniku
          └─────────┬──────────┘
                    │ {tool: FINISH, answer: ...}
                    ▼
              Odpowiedź użytkownikowi
```

---

## Struktura plików

```
ai_agent_demo/
├── hooks.py
├── modules.txt
└── ai_agent/               # moduł Frappe
    ├── core/
    │   ├── agent.py        # klasa Agent (ReAct)
    │   ├── tools.py        # Tool ABC + implementacje
    │   ├── anonymizer.py   # DataAnonymizer + strategie
    │   └── local_model.py  # adapter Ollama
    ├── api.py              # whitelisted endpoints
    ├── doctype/
    │   ├── agent_session/  # sesje rozmów
    │   └── agent_log/      # logi kroków agenta
    └── page/
        └── ai_agent_demo/  # frontend (Frappe Page)
```

---

## Licencja

MIT – użyj dowolnie jako punkt startowy.
