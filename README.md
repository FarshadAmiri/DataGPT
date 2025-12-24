# DataGPT

Chat with your data sources using natural language. Query documents, databases, and spreadsheets through a single interface - no SQL or coding required.

## What it does

Ask questions in plain English and get answers from:
- **Documents** (PDFs, text files) - classic RAG with vector search
- **Databases** - MySQL, PostgreSQL, SQLite, MongoDB
- **Excel/CSV files** - query spreadsheets like databases

The LLM automatically generates the right SQL/Pandas queries and returns actual data, not hallucinations.

## Core Capabilities

**Intelligent Retrieval**
- Vector-based semantic search across documents (RAG)
- Context-aware chunking with similarity scoring and reranking
- Automatic source attribution with citation tracking

**Database Intelligence**
- Automatic schema discovery and LLM-powered analysis for SQL databases (MySQL, PostgreSQL, SQLite) and MongoDB
- Natural language to SQL/NoSQL query translation
- Adaptive retry logic with error correction - learns from failed queries
- Schema reindexing for evolving database structures

**Spreadsheet Analysis**
- Pandas-based querying for Excel/CSV files (up to 5 files per collection)
- Automatic data profiling - column types, null analysis, unique value detection
- Smart data inspection - suggests correct values when queries return empty results

**Query Transparency**
- Response contexts modal displays actual SQL/Pandas queries and raw results
- Real-time query execution tracking with attempt history
- No black boxes - see exactly what's being queried

**Security & Performance**
- End-to-end encryption (RSA + AES-ECB) for all client-server communication
- WebSocket-based streaming for low-latency responses
- Per-collection access control with user permissions

## Tech stack

- Django + Channels (WebSockets)
- ChromaDB for vector storage
- Pandas for Excel/CSV queries
- vLLM for LLM inference (streaming)
- Bootstrap UI

Create a collection, upload files or connect a database, then start asking questions.
