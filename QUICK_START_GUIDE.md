# Quick Start Guide - Database-Backed Collections

## Installation

### 1. Apply Database Migration
The migration has already been applied, but if you need to reapply or are setting up on a new system:

```bash
cd d:\Projects\RAG-webapp
D:/Projects/venv2/Scripts/python.exe manage.py migrate
```

### 2. Install Optional Database Drivers (as needed)

For **MySQL** support:
```bash
D:/Projects/venv2/Scripts/pip.exe install pymysql
```

For **PostgreSQL** support:
```bash
D:/Projects/venv2/Scripts/pip.exe install psycopg2-binary
```

For **MongoDB** support:
```bash
D:/Projects/venv2/Scripts/pip.exe install pymongo
```

**Note**: SQLite and Excel/CSV work without additional packages (pandas is already installed).

## Quick Test

### Test 1: Create SQLite Collection

1. Start your application
2. Login as supervisor/admin
3. Go to Collections page
4. Click "Create new collection"
5. Fill in:
   - Name: "Test SQLite DB"
   - Collection Type: "Database-backed"
   - Database Type: "SQLite"
   - Upload a .sqlite or .db file
   - (Optional) Add context about the database
6. Click "Create"
7. Wait for schema analysis to complete

### Test 2: Create Excel Collection

1. Go to Collections page
2. Click "Create new collection"
3. Fill in:
   - Name: "Test Excel Data"
   - Collection Type: "Excel/CSV-backed"
   - Upload 1-5 Excel or CSV files
   - (Optional) Add context about the data
4. Click "Create"

### Test 3: Query the Database

1. Create a new thread
2. Select the database collection as base collection
3. In the chat interface, you'll see "Standard" and "Database" modes
4. Select "Database" mode
5. Ask questions like:
   - "Show me the first 10 rows from the users table"
   - "What tables are in this database?"
   - "Count total records in each table"
   - "Find all entries where status is active"

## Example Database Queries

### For SQL Databases:
- "Show me all customers from California"
- "What's the total sales amount for 2024?"
- "List the top 5 products by price"
- "How many orders were placed last month?"
- "Show me customer details with their order count"

### For Excel/CSV Files:
- "Show me the first 20 rows"
- "What's the average of the price column?"
- "Filter rows where status is 'completed'"
- "Group by category and sum the amounts"
- "Show unique values in the region column"

### For MongoDB:
- "Find all documents in the users collection"
- "Show me products with price greater than 100"
- "Count documents by category"
- "Find the most recent 10 entries"

## Troubleshooting

### Schema Analysis Fails
- **Check**: LLM server is running (vllm on WSL)
- **Verify**: llm_url in `main/utilities/variables.py` is correct
- **Solution**: Restart vllm server if needed

### Database Connection Error
- **Check**: Connection string format is correct
- **Verify**: Database server is running and accessible
- **For SQLite**: Ensure file exists and is readable
- **For MySQL/PostgreSQL**: Test connection with a database client first

### Query Execution Fails
- **Check**: Database has actual data
- **Review**: Generated query in console logs
- **Try**: Rephrasing your question
- **Note**: System will retry up to 3 times automatically

### Import Errors
- **Error**: "No module named 'pymysql'"
- **Solution**: Install the required driver (see Installation section above)
- **Alternative**: Use SQLite which requires no additional packages

## Verifying Installation

Run this Python script to verify database support:

```python
# Check database driver availability
import sys

drivers = {
    'SQLite': True,  # Always available
    'Pandas': True,  # Always available (for Excel/CSV)
}

try:
    import pymysql
    drivers['MySQL'] = True
except ImportError:
    drivers['MySQL'] = False

try:
    import psycopg2
    drivers['PostgreSQL'] = False
except ImportError:
    drivers['PostgreSQL'] = False

try:
    import pymongo
    drivers['MongoDB'] = True
except ImportError:
    drivers['MongoDB'] = False

print("Database Driver Support:")
print("-" * 40)
for db, available in drivers.items():
    status = "✓ Available" if available else "✗ Not installed"
    print(f"{db:20s} {status}")
```

Save as `check_db_support.py` and run:
```bash
D:/Projects/venv2/Scripts/python.exe check_db_support.py
```

## Configuration

### Update LLM URL (if needed)
Edit `main/utilities/variables.py`:
```python
llm_url = "http://localhost:8002/v1"  # Update if your vllm runs on different port
```

### Adjust Query Limits
Edit `main/utilities/database_utils.py` to change:
- Result limit (default: 100 rows)
- Retry attempts (default: 3)
- Query timeout (default: 30 seconds)

## Common Use Cases

### 1. Sales Database Analysis
Collection Type: Database-backed (MySQL/PostgreSQL)
Example Questions:
- "What were our total sales this quarter?"
- "Which products have the highest profit margin?"
- "Show me customer purchase trends"

### 2. Inventory Management
Collection Type: Excel-backed
Example Questions:
- "Which items are low in stock?"
- "What's the total inventory value?"
- "Show me items that haven't moved in 30 days"

### 3. User Analytics
Collection Type: Database-backed (MongoDB)
Example Questions:
- "How many users signed up this month?"
- "What's the distribution of users by country?"
- "Show me users who haven't logged in recently"

### 4. Financial Reports
Collection Type: Excel-backed (multiple CSV files)
Example Questions:
- "Sum expenses by category"
- "Compare revenue across quarters"
- "Calculate profit margins"

## Best Practices

### For Supervisors Creating Collections:

1. **Provide Context**: Use the "Additional Information" field to describe:
   - Important relationships between tables
   - Business rules or constraints
   - Common query patterns
   - Any data quality issues

2. **Test Connection**: Before creating, verify database is accessible

3. **Naming**: Use clear, descriptive collection names

4. **Security**: For production databases, use read-only credentials

### For Users Querying:

1. **Be Specific**: "Show customers from NY" vs "Show me data"
2. **Use Proper Names**: Reference actual table/column names when possible
3. **Start Simple**: Begin with basic queries, then get more complex
4. **Review Results**: Check if the query returned what you expected
5. **Rephrase if Needed**: If results aren't right, try asking differently

## Maintenance

### Regular Checks:
- Monitor query logs for failed queries
- Review schema analyses for accuracy
- Update additional context as database evolves
- Clean up unused collections

### Performance:
- Consider adding database indexes for frequently queried columns
- Limit result sets in queries (system does this automatically)
- For large databases, consider creating summary tables/views

## Support

For issues or questions:
1. Check console logs for detailed error messages
2. Review [DATABASE_FEATURE_DOCUMENTATION.md](DATABASE_FEATURE_DOCUMENTATION.md)
3. Check [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for technical details

## What's Next?

After successful testing:
1. ✅ Create collections for your actual databases
2. ✅ Train users on effective query phrasing
3. ✅ Monitor usage and optimize common queries
4. ✅ Gather feedback for improvements
5. ✅ Consider implementing query caching for frequently asked questions
