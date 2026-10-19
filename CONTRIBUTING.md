# Contributing to Lumina Capital

Thank you for your interest in contributing to **Lumina Capital**! 🌟  
We welcome contributions from quantitative researchers, software engineers, data scientists, and algorithmic trading enthusiasts worldwide.

---

## 📜 Code of Conduct

All contributors are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md). Please treat all members of the community with respect, patience, and professional courtesy.

---

## 🛠️ How You Can Contribute

There are many ways to get involved:

1. **Quantitative Alpha Factors**: Propose or implement new mathematical factors (extending beyond Qlib Alpha158).
2. **Multi-Agent Personas & Strategies**: Design new investor debate personas, risk filters, or prompt workflows in LangGraph.
3. **Foundation Model Forecasting**: Improve or benchmark Google TimesFM, Chronos, or other foundation time-series forecasters.
4. **Knowledge Graph & GraphRAG**: Expand SEC 10-K parsing, supply-chain relationship extraction, or Neo4j Cypher queries.
5. **Bug Reports & Improvements**: Fix bugs, optimize vectorized calculations, or enhance execution simulation realism.
6. **Documentation & Localization**: Improve docs, add tutorials, or expand translations.

---

## 🚀 Development Workflow

### 1. Fork & Clone
Fork the repository on GitHub and clone your fork locally:
```bash
git clone https://github.com/<your-username>/lumina-ai-hedge-fund.git
cd lumina-ai-hedge-fund
```

### 2. Set Up Virtual Environment
We recommend Python 3.10 or higher:
```bash
python -m venv venv
# Linux / macOS:
source venv/bin/activate
# Windows PowerShell:
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and provide your test API keys:
```bash
cp .env.example .env
```
*(A free `GEMINI_API_KEY` from Google AI Studio is fully sufficient for testing all multi-agent features).*

### 4. Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 5. Verify & Test Locally
Before committing, make sure the codebase compiles and runs cleanly:
```bash
# Verify Python syntax
python -m py_compile app.py

# Launch the Streamlit dashboard locally
streamlit run app.py
```

---

## 📝 Pull Request Guidelines

1. **Keep PRs Focused**: Each Pull Request should ideally address a single feature, bug fix, or factor addition.
2. **Follow Code Conventions**:
   - Write clean, readable, PEP 8-compliant Python code.
   - Use type annotations where appropriate (`typing.List`, `typing.Dict`, `typing.Optional`, etc.).
   - Follow the core design principle: *"Models reason, software calculates"* (keep deterministic math in vectorized Python, and qualitative deliberation in LLM prompts).
3. **Commit Messages**: Write clear, descriptive commit messages (e.g., `feat(quant): add momentum-volatility interaction factor`, `fix(ui): resolve portfolio chart scaling`).
4. **Link Issues**: Reference any relevant issues in your PR description (e.g., `Closes #12`).

---

## 💬 Community & Discussion

If you'd like to discuss ideas or ask questions before opening a PR:
- Open a discussion or issue on GitHub.
- Reach out via X (Twitter) at [@prompter_note](https://x.com/prompter_note).

Thank you for helping push the frontier of autonomous quantitative finance! 🚀
