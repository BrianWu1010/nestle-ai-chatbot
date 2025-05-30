# 🧠 Nestlé AI Chatbot — Product Search Assistant

A full-stack AI chatbot system designed for intelligent product Q&A using Azure-backed Retrieval-Augmented Generation (RAG) and Neo4j-based knowledge graphs. Built collaboratively for the Nestlé Technical Test, this system demonstrates real-time user interaction, structured scraping, smart document processing, and scalable data serving.

---

## 📁 Project Structure

```
nestle-ai-chatbot/
├── frontend/                  # Flask-based UI with custom chat interface
│   ├── app.py                 # Handles routing and client interaction
│   ├── templates/             # HTML (Jinja) views
│   └── static/                # CSS, JS, icons
│
├── backend/                   # Real backend (Azure + Neo4j)
│   ├── scrape_full.py         # Full scraping pipeline
│   ├── classify_urls.py       # Metadata labeling/classification
│   ├── text_splitter.py       # Text splitting logic
│   ├── splitter.py            # Alternative splitter implementation
│   ├── embed_and_upload.py    # Embedding & vector upload
│   ├── upload_to_neo4j.py     # Final graph ingestion
│   └── ...                    # Additional preprocessing utilities
│
├── data/                      # All intermediate + processed data
│   ├── *.json / *.html
│   ├── slices.jsonl.gz
│   └── slices_with_embed.jsonl.gz
│
├── __deprecated__/            # Archived prototype (legacy NLP intent model, etc.)
│   ├── chat.py, model.py, data.pth
│   └── (Not used in production. Kept for historical context.)
```

---

## ✅ Features

- 🎨 **Custom UI**: Responsive, styled chatbox interface
- 📄 **Web Scraping**: Robust URL scraping with content classification
- 🧠 **RAG Pipeline**: End-to-end retrieval + contextual answer generation
- 🔎 **Chunked Embedding**: Text split, vectorized, and searchable
- 🌐 **Neo4j Knowledge Graph**: Structured entity storage and fast retrieval
- 🧼 **Modular Structure**: Clean folder separation, no duplication, minimal technical debt

---

## 🚀 Quick Start

> Requirements: Python 3.9+, pip, virtualenv

1. **Clone this repository**

```bash
git clone https://github.com/yourusername/nestle-ai-chatbot.git
cd nestle-ai-chatbot
```

2. **Set up virtual environment**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. **Configure environment variables**

- Create a `.env` file at the root  
- Refer to `.env.example` if present  
- Add your Azure, OpenAI, Neo4j, and other credentials  

4. **Run the frontend**

```bash
cd frontend
python app.py
```

5. **Run the backend processing pipeline** (optional, if you want to regenerate data)

```bash
cd backend
python scrape_full.py
python classify_urls.py
python embed_and_upload.py
python upload_to_neo4j.py
```

