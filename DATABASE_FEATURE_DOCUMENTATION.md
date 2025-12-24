# Database-Backed Collections Feature Documentation

## Overview
This feature extends the RAG web application to support database-backed collections in addition to document-based collections. Users can now query databases directly through natural language, with the LLM generating and executing appropriate SQL/MongoDB/Pandas queries.

## Feature Summary

### Collection Types
1. **Document-based Collections** (Original RAG functionality)
   - Upload and index .docx and .pdf files
   - Vector search with embeddings
   - Retrieval-Augmented Generation

2. **Database-backed Collections** (NEW)
   - Support for SQLite, MySQL, PostgreSQL, MongoDB
   - Schema analysis and LLM-powered query generation
   - Direct database querying without indexing

3. **Excel/CSV-backed Collections** (NEW)
   - Support for up to 5 Excel or CSV files
   - Pandas-based querying
   - Schema analysis of spreadsheet structure

## How It Works

### For Supervisors (Collection Creation)

1. **Navigate to Collections Page**
   - Click on "Collections" in the navigation menu

2. **Create a New Collection**
   - Click "Create new collection" button
   - Enter a collection name
   - Select collection type:
     - **Document-based**: Traditional RAG with PDF/DOCX files
     - **Database-backed**: Connect to a database
     - **Excel/CSV-backed**: Upload spreadsheet files

3. **For Database-backed Collections:**
   - Select database type (SQLite, MySQL, PostgreSQL, MongoDB)
   - For SQLite: Upload the .db/.sqlite/.sqlite3 file
   - For MySQL/PostgreSQL/MongoDB: Enter connection string
     - Format: `protocol://user:password@host:port/database`
     - Example: `mysql://admin:pass123@localhost:3306/mydb`
   - Optionally provide additional information about the database structure, relationships, or query patterns
   - Click "Create"
   - The system will:
     - Analyze the database schema
     - Use LLM to generate a comprehensive schema analysis
     - Store the analysis for future queries

4. **For Excel/CSV-backed Collections:**
   - Upload up to 5 Excel (.xlsx, .xls) or CSV files
   - Optionally provide additional information about data relationships
   - Click "Create"
   - The system will analyze the structure of each file/sheet

### For Users (Querying)

1. **Create a Thread**
   - Create a new RAG thread
   - Select a base collection (document, database, or Excel-based)

2. **Query Modes**
   - For document-based collections: Choose between **Standard** and **RAG**
   - For database/Excel-based collections: Choose between **Standard** and **Database**

3. **Database Mode Queries**
   - Ask questions in natural language
   - Examples:
     - "Show me all customers from New York"
     - "What's the total sales for last month?"
     - "Find the top 5 products by revenue"
     - "How many orders were placed in 2024?"
   - The system will:
     - Generate appropriate SQL/MongoDB/Pandas query
     - Execute the query (with automatic retry on failure)
     - Format and present results
     - Use results to generate natural language response

## Technical Implementation

### Database Schema Files

#### Models (`main/models.py`)
- Added fields to `Collection` model:
  - `collection_type`: Document, Database, or Excel
  - `db_type`: MySQL, PostgreSQL, SQLite, MongoDB
  - `db_connection_string`: Connection string or file path
  - `db_schema_analysis`: LLM-generated schema description
  - `db_extra_knowledge`: Supervisor-provided context
  - `excel_file_paths`: JSON array of file paths

#### Database Utilities (`main/utilities/database_utils.py`)
New module with functions for:
- `analyze_sqlite_schema()`: Extract SQLite schema information
- `analyze_mysql_schema()`: Extract MySQL schema information
- `analyze_postgresql_schema()`: Extract PostgreSQL schema information
- `analyze_mongodb_schema()`: Extract MongoDB schema information
- `analyze_excel_files()`: Analyze Excel/CSV file structure
- `generate_schema_analysis_text()`: LLM-powered schema description
- `generate_database_query()`: Generate SQL/MongoDB/Pandas queries
- `execute_sql_query()`: Execute SQL queries
- `execute_mongodb_query()`: Execute MongoDB queries
- `execute_pandas_query()`: Execute Pandas operations
- `format_query_results()`: Format results for LLM consumption

#### Views (`main/views.py`)
- Updated `collection_create_view()` to handle all collection types
- Schema analysis performed during collection creation
- Database connection validation

#### WebSocket Consumer (`main/consumers.py`)
- Added `_handle_database_query()` method
- Implements retry logic (up to 3 attempts)
- Query generation → Execution → Result formatting → Response generation
- Error handling without exposing errors to users

#### Templates (`main/templates/main/collections.html`)
- Updated collection creation modal
- Dynamic form fields based on collection type
- Support for file uploads and connection strings

#### Chat Interface (`main/templates/main/chat.html`)
- Dynamic mode selector (RAG/Database based on collection type)
- Updated JavaScript to handle database mode

### Query Flow

```
User Question
    ↓
LLM generates query (SQL/MongoDB/Pandas)
    ↓
Execute query on database/files
    ↓
[If error] → Retry with feedback → Generate new query
    ↓
Format results
    ↓
LLM generates natural language response using results
    ↓
Stream response to user
```

### Error Handling

- **Query Generation Failure**: Retry with different approach
- **Query Execution Error**: Retry up to 3 times with error context
- **Connection Errors**: Return generic error message to user
- **No Results**: LLM still generates helpful response

## Installation Requirements

### Python Packages
For full functionality, install optional database drivers:

```bash
# For MySQL support
pip install pymysql

# For PostgreSQL support
pip install psycopg2-binary

# For MongoDB support
pip install pymongo

# Already included in requirements
pip install pandas openpyxl
```

**Note**: The application will work without these packages, but only SQLite and Excel/CSV will be available.

## Security Considerations

1. **Query Safety**: Generated queries are read-only (no DELETE, UPDATE, DROP)
2. **Connection Strings**: Passwords are masked in schema analysis
3. **Pandas Execution**: Limited to safe operations, no file I/O or imports
4. **Error Messages**: Generic errors shown to users, detailed logs for admins
5. **Offline Operation**: All processing happens locally, no external API calls

## Configuration

### Database Connection Formats

**SQLite**: Upload file directly (no connection string needed)

**MySQL**: 
```
mysql://username:password@hostname:port/database
mysql://admin:secret@localhost:3306/myapp
```

**PostgreSQL**:
```
postgresql://username:password@hostname:port/database
postgresql://user:pass@localhost:5432/analytics
```

**MongoDB**:
```
mongodb://username:password@hostname:port/database
mongodb://admin:secret@localhost:27017/mydb
```

## Limitations

1. Excel/CSV collections limited to 5 files maximum
2. Query results limited to 100 rows/documents
3. Maximum 3 retry attempts for failed queries
4. MongoDB requires collection name in query (future improvement needed)
5. Read-only operations only (by design)

## Future Enhancements

- [ ] Support for database views and stored procedures
- [ ] Query result caching
- [ ] Support for JOINs across multiple Excel files
- [ ] Advanced MongoDB aggregation pipeline support
- [ ] Query performance optimization suggestions
- [ ] Export query results to Excel
- [ ] Query history and reuse
- [ ] Visual query builder

## Troubleshooting

### Collection creation fails
- Check database connection string format
- Verify database credentials
- Ensure database is accessible from server
- Check file permissions for SQLite/Excel files

### Queries return no results
- Verify database has data
- Check schema analysis for table/column names
- Try rephrasing the question
- Review generated query in logs

### Connection errors
- Confirm database server is running
- Check firewall settings
- Verify network connectivity
- Ensure correct port numbers

## Migration Information

Migration file: `main/migrations/0013_collection_collection_type_and_more.py`

Applied changes:
- Added new fields to Collection model
- Modified existing fields (description, docs) to support blank values
- No data loss for existing collections (default type is 'document')

## Testing Checklist

- [ ] Create SQLite-backed collection
- [ ] Create MySQL-backed collection
- [ ] Create PostgreSQL-backed collection
- [ ] Create MongoDB-backed collection
- [ ] Create Excel-backed collection
- [ ] Create CSV-backed collection
- [ ] Query with simple SELECT
- [ ] Query with JOINs
- [ ] Query with aggregations
- [ ] Test retry logic with invalid query
- [ ] Test error handling
- [ ] Test with empty database
- [ ] Test with large result sets
- [ ] Verify offline operation
