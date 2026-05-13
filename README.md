# 🤖 Frappe AI Agent Demo

Demo showing **how AI agent works** powered by **local LLM model** (Ollama).  
Designed with OOP principles – each class has single responsibility and is easy to understand.

---

## What does this application demonstrate?

| Feature | Description |
|---|---|
| **ReAct Loop** | Visualization of cycle: Think → Act → Observe |
| **Tool Selection** | Agent decides which tool to call |
| **Data Anonymization** | GDPR demo: email, phone, SSN, names protection |
| **Local Model** | Ollama – no data leaves your infrastructure |

---

## OOP Architecture

```
Agent                    # Coordinator – ReAct loop
├── LocalModel           # Adapter to Ollama HTTP API
├── ToolRegistry         # Registry of available tools
└── AgentStep            # Single reasoning step

Tool (ABC)               # Tool interface
├── AnonymizationTool    # → calls DataAnonymizer
├── DatabaseSearchTool   # → Frappe frappe.get_list()
├── DataAnalysisTool     # → statistics for number lists
└── DateTimeTool         # → datetime.now()

DataAnonymizer           # Strategy coordinator
├── EmailAnonymizer      # regex + masking
├── PhoneAnonymizer      # US phone number patterns
├── SSNAnonymizer        # Social Security Numbers
└── NameAnonymizer       # list of common English names
```

---

## Requirements

1. **Frappe** (v14+)
2. **Ollama** – local LLM server

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Download model (llama3.2 ~2GB)
ollama pull llama3.2

# Start server
ollama serve

# Optional: Install spaCy for enhanced NER
pip install spacy
python -m spacy download en_core_web_sm
```

---

## Frappe App Installation

```bash
# In frappe-bench directory
bench get-app https://github.com/siasty/ai-agent-demo-
bench --site your-site.local install-app ai_agent_demo
bench --site your-site.local migrate
bench build
bench restart
```

Then open in Frappe: **Menu → AI Agent Demo**

## Demo Data Setup

The app includes a patch that creates realistic test data for all three tools:

```bash
# Apply patch with demo data (runs automatically on migrate)
bench --site your-site.local migrate

# Or run manually in console
bench --site your-site.local console
>>> from ai_agent_demo.patches.v1_0.create_demo_data import execute
>>> execute()
```

**Created data:**
- **6 customers** - TechParts Inc. customers with sensitive data (ElectroTech Solutions, etc.)
- **10 electronic parts** - Microcontrollers, sensors, LEDs, etc.
- **6 sales orders** - Recent orders with various components

See [PATCH_DEMO_DATA.md](PATCH_DEMO_DATA.md) for complete details.

---

## Agent Workflow

```
User: "Analyze sales orders from last week"
                    │
                    ▼
              Agent.run(query)
                    │
          ┌─────────▼──────────┐
          │   LocalModel.chat  │  ← system prompt with tools list
          └─────────┬──────────┘
                    │ JSON: {thought, tool, input}
                    ▼
          ┌─────────────────────┐
          │   ToolRegistry.get  │  ← selects appropriate tool
          └─────────┬───────────┘
                    │
                    ▼
          Tool.execute()
                    │
                    ▼
          Process with data anonymization
                    │
          ┌─────────▼──────────┐
          │   LocalModel.chat  │  ← observation of result
          └─────────┬──────────┘
                    │ {tool: FINISH, answer: ...}
                    ▼
              Response to user
```

---

## File Structure

```
ai_agent_demo/
├── hooks.py
├── modules.txt
└── ai_agent_demo/          # Frappe module
    ├── core/
    │   ├── agent.py        # Agent class (ReAct)
    │   ├── tools.py        # Tool ABC + implementations
    │   ├── erp_tools.py    # ERPNext business tools
    │   ├── anonymizer.py   # DataAnonymizer + strategies
    │   └── local_model.py  # Ollama adapter
    ├── api.py              # whitelisted endpoints
    ├── doctype/
    │   ├── agent_session/  # conversation sessions
    │   └── agent_log/      # agent step logs
    └── page/
        └── ai_agent_demo/  # frontend (Frappe Page)
```

---

## License

MIT – use freely as starting point.
