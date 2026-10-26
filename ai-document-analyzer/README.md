# 🧠 AI Document Analyzer

[![CI](https://github.com/YOUR-USERNAME/ai-document-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR-USERNAME/ai-document-analyzer/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Chat with your PDF, Word, Excel and CSV files using Anthropic's Claude. Upload documents once, ask questions in plain language, and get streamed answers that cite the file, page or sheet they came from. Spreadsheets also get an interactive data explorer with automatic charts.

## Features

- **Multi-format ingestion**: PDF (PyMuPDF with a pdfplumber fallback), DOCX including tables, XLSX/XLS and CSV.
- **Streaming answers** with follow-up questions that remember the conversation.
- **Handles large inputs**: small inputs go straight to Claude (with prompt caching); very large ones use a map-reduce pipeline that reads the documents section by section and then combines the findings.
- **Data explorer**: table view, statistics and auto-generated Plotly charts (distributions, correlations, outliers, trends over time, top categories).
- **Chat history**: saved locally, searchable, renameable; export to Markdown, text or JSON.
- **Tested**: unit tests for extraction, chunking, history and charts plus a UI smoke test, run in CI.

## Quick start

```bash
git clone https://github.com/YOUR-USERNAME/ai-document-analyzer.git
cd ai-document-analyzer

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then put your Anthropic API key in .env
python run.py
```

The app opens at http://localhost:8501. You can also paste the API key into **Settings** in the sidebar instead of using `.env`. Get a key at [console.anthropic.com](https://console.anthropic.com).

## How it works

```
 upload ──► extractors.py ──► one text corpus ──► llm.py ──► streamed answer
            (cached, once)         │                 │
                                   │        small: single request (cached system prompt)
                                   │        large: map (per section) ──► reduce (combine)
                                   └──► charts.py (spreadsheets only)
```

| Path | Responsibility |
|------|----------------|
| `app.py` | Streamlit interface |
| `run.py` | One-command launcher |
| `docanalyzer/config.py` | Models, limits, system prompt |
| `docanalyzer/extractors.py` | PDF / DOCX / spreadsheet to text |
| `docanalyzer/llm.py` | Claude calls, streaming, chunking, map-reduce |
| `docanalyzer/history.py` | JSON chat store |
| `docanalyzer/charts.py` | Automatic Plotly charts |
| `tests/` | pytest suite |

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Limitations

- Scanned PDFs (images without a text layer) are not supported; run OCR first.
- Legacy `.doc` files are not supported; save as `.docx`.
- Token counts are estimated at about 4 characters per token.
- Chat history is stored in plain JSON in `chat_history/`. Uploaded file contents are **not** saved, so re-upload files to continue an old chat.
- Document text is sent to the Anthropic API. Do not upload data you are not allowed to share.

## License

MIT. See [LICENSE](LICENSE).
