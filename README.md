# ⚖️ Contract Review Agent

An AI-powered legal contract analysis tool built with Python, Streamlit, and Groq.

## 🚀 Quick Setup (5 minutes)

### Step 1: Install dependencies
```bash
cd contract_review_agent
pip install -r requirements.txt
```

### Step 2: Add your Groq API key
Edit the `.env` file:
```
GROQ_API_KEY=your_actual_key_here
```
Get a free key at: https://console.groq.com

### Step 3: Run the app
```bash
streamlit run app.py
```

The app opens at: http://localhost:8501

---

## 📁 Project Structure

```
contract_review_agent/
├── app.py              ← Main Streamlit UI
├── groq_client.py      ← Groq API + CascadeFlow routing
├── database.py         ← SQLite operations
├── memory.py           ← Hindsight memory system
├── pdf_parser.py       ← PDF text extraction
├── clause_extractor.py ← Clause parsing utilities
├── risk_analysis.py    ← Risk scoring utilities
├── models.py           ← Data models
├── requirements.txt
├── .env                ← API keys (never commit this!)
├── data/               ← SQLite database stored here
├── memory_store/       ← Memory files
└── uploads/            ← Uploaded PDFs stored here
```

---

## 🔧 Features

| Feature | Description |
|---------|-------------|
| 📋 Contract Summary | Type, parties, duration, value, dates |
| 📑 Clause Extraction | Payment, confidentiality, termination, IP, liability, dispute resolution |
| ⚠️ Risk Analysis | High / Medium / Low with explanations |
| 📖 Plain English | Legal → simple language translation |
| 🔎 Missing Clauses | Detects absent critical clauses |
| 🧠 Hindsight Memory | Remembers your flagged clauses across sessions |
| ⚡ CascadeFlow | Smart routing: fast model for simple, powerful for complex |
| 📚 Contract History | SQLite-stored history with risk scores |
| 💬 Chat Interface | Ask anything about the contract |

---

## 💡 Usage Tips

1. Upload any legal contract PDF (NDA, service agreement, employment, etc.)
2. Wait ~30-60 seconds for full analysis
3. Use the **Chat** tab to ask questions
4. Use the **Risks** tab to get negotiation tips
5. Flag clauses you don't like — the agent remembers for next time!

---

## 🛠️ VS Code Setup

Install the Python extension and use the integrated terminal:
```bash
# In VS Code terminal (Ctrl+`)
streamlit run app.py
```

---

## 📝 Sample Questions to Ask

- "What are the biggest risks in this contract?"
- "Explain clause 5 in simple terms"
- "What should I negotiate before signing?"
- "Is there anything missing that I should add?"
- "Summarize the payment terms"
- "What happens if I want to terminate early?"
