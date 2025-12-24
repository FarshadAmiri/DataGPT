# DataGPT

Chat with your data sources using natural language. Query documents, databases, and spreadsheets through a single interface - no SQL or coding required.

## What it does

Ask questions in plain English and get answers from:
- **Documents** (PDFs, text files) - classic RAG with vector search
- **Databases** - MySQL, PostgreSQL, SQLite, MongoDB
- **Excel/CSV files** - query spreadsheets like databases

The LLM automatically generates the right SQL/Pandas queries and returns actual data, not hallucinations.

## Key features

- Real-time streaming chat (like ChatGPT)
- Multiple collection types - documents, databases, or Excel files
- Smart query generation with auto-retry on errors
- Data inspection - when a query returns nothing, it checks what values actually exist
- Per-collection schema analysis (LLM-generated descriptions of your data)
- Reindex capability for database/Excel collections when schema changes
- Response contexts modal - see the actual queries and raw results
- RSA + AES encryption for client-server communication
- Dark theme UI

## Tech stack

- Django + Channels (WebSockets)
- ChromaDB for vector storage
- Pandas for Excel/CSV queries
- vLLM for LLM inference (streaming)
- Bootstrap UI

Create a collection, upload files or connect a database, then start asking questions.
