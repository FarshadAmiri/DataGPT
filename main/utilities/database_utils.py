"""
Database utilities for schema analysis and query execution
Supports MySQL, PostgreSQL, SQLite, MongoDB, Excel/CSV
"""

import sqlite3
import pandas as pd
import json
import os
from typing import Dict, List, Tuple, Optional, Any
import requests


def analyze_sqlite_schema(db_path: str) -> Dict[str, Any]:
    """
    Analyze SQLite database schema
    Returns dict with tables, columns, relationships, etc.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    schema_info = {
        'database_type': 'SQLite',
        'database_path': db_path,
        'tables': {}
    }
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    for (table_name,) in tables:
        table_info = {
            'columns': [],
            'primary_keys': [],
            'foreign_keys': [],
            'indexes': []
        }
        
        # Get column information
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns:
            col_info = {
                'name': col[1],
                'type': col[2],
                'nullable': not col[3],
                'default': col[4],
                'is_primary_key': bool(col[5])
            }
            table_info['columns'].append(col_info)
            if col[5]:  # is primary key
                table_info['primary_keys'].append(col[1])
        
        # Get foreign key information
        cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        fks = cursor.fetchall()
        for fk in fks:
            fk_info = {
                'column': fk[3],
                'referenced_table': fk[2],
                'referenced_column': fk[4]
            }
            table_info['foreign_keys'].append(fk_info)
        
        # Get indexes
        cursor.execute(f"PRAGMA index_list({table_name})")
        indexes = cursor.fetchall()
        for idx in indexes:
            table_info['indexes'].append(idx[1])
        
        schema_info['tables'][table_name] = table_info
    
    conn.close()
    return schema_info


def analyze_mysql_schema(connection_string: str) -> Dict[str, Any]:
    """
    Analyze MySQL database schema
    Connection string format: mysql://user:password@host:port/database
    """
    try:
        import pymysql
    except ImportError:
        raise ImportError("pymysql is required for MySQL connections. Install it with: pip install pymysql")
    
    # Parse connection string
    from urllib.parse import urlparse
    parsed = urlparse(connection_string)
    
    conn = pymysql.connect(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path.lstrip('/')
    )
    
    cursor = conn.cursor()
    schema_info = {
        'database_type': 'MySQL',
        'connection_string': connection_string.replace(parsed.password, '****') if parsed.password else connection_string,
        'tables': {}
    }
    
    # Get all tables
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    
    for (table_name,) in tables:
        table_info = {
            'columns': [],
            'primary_keys': [],
            'foreign_keys': [],
            'indexes': []
        }
        
        # Get column information
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        for col in columns:
            col_info = {
                'name': col[0],
                'type': col[1],
                'nullable': col[2] == 'YES',
                'key': col[3],
                'default': col[4],
                'extra': col[5]
            }
            table_info['columns'].append(col_info)
            if col[3] == 'PRI':
                table_info['primary_keys'].append(col[0])
        
        # Get foreign keys
        cursor.execute(f"""
            SELECT 
                COLUMN_NAME, 
                REFERENCED_TABLE_NAME, 
                REFERENCED_COLUMN_NAME
            FROM 
                INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE 
                TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = '{table_name}'
                AND REFERENCED_TABLE_NAME IS NOT NULL
        """)
        fks = cursor.fetchall()
        for fk in fks:
            fk_info = {
                'column': fk[0],
                'referenced_table': fk[1],
                'referenced_column': fk[2]
            }
            table_info['foreign_keys'].append(fk_info)
        
        schema_info['tables'][table_name] = table_info
    
    conn.close()
    return schema_info


def analyze_postgresql_schema(connection_string: str) -> Dict[str, Any]:
    """
    Analyze PostgreSQL database schema
    Connection string format: postgresql://user:password@host:port/database
    """
    try:
        import psycopg2
    except ImportError:
        raise ImportError("psycopg2 is required for PostgreSQL connections. Install it with: pip install psycopg2-binary")
    
    from urllib.parse import urlparse
    parsed = urlparse(connection_string)
    
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path.lstrip('/')
    )
    
    cursor = conn.cursor()
    schema_info = {
        'database_type': 'PostgreSQL',
        'connection_string': connection_string.replace(parsed.password, '****') if parsed.password else connection_string,
        'tables': {}
    }
    
    # Get all tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    tables = cursor.fetchall()
    
    for (table_name,) in tables:
        table_info = {
            'columns': [],
            'primary_keys': [],
            'foreign_keys': [],
            'indexes': []
        }
        
        # Get column information
        cursor.execute(f"""
            SELECT 
                column_name, 
                data_type, 
                is_nullable, 
                column_default
            FROM 
                information_schema.columns
            WHERE 
                table_name = '{table_name}'
        """)
        columns = cursor.fetchall()
        for col in columns:
            col_info = {
                'name': col[0],
                'type': col[1],
                'nullable': col[2] == 'YES',
                'default': col[3]
            }
            table_info['columns'].append(col_info)
        
        # Get primary keys
        cursor.execute(f"""
            SELECT column_name
            FROM information_schema.key_column_usage
            WHERE table_name = '{table_name}'
            AND constraint_name LIKE '%_pkey'
        """)
        pks = cursor.fetchall()
        table_info['primary_keys'] = [pk[0] for pk in pks]
        
        # Get foreign keys
        cursor.execute(f"""
            SELECT
                kcu.column_name,
                ccu.table_name AS referenced_table,
                ccu.column_name AS referenced_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = '{table_name}'
        """)
        fks = cursor.fetchall()
        for fk in fks:
            fk_info = {
                'column': fk[0],
                'referenced_table': fk[1],
                'referenced_column': fk[2]
            }
            table_info['foreign_keys'].append(fk_info)
        
        schema_info['tables'][table_name] = table_info
    
    conn.close()
    return schema_info


def analyze_mongodb_schema(connection_string: str) -> Dict[str, Any]:
    """
    Analyze MongoDB database schema
    Connection string format: mongodb://user:password@host:port/database
    """
    try:
        from pymongo import MongoClient
    except ImportError:
        raise ImportError("pymongo is required for MongoDB connections. Install it with: pip install pymongo")
    
    client = MongoClient(connection_string)
    db_name = connection_string.split('/')[-1]
    db = client[db_name]
    
    schema_info = {
        'database_type': 'MongoDB',
        'database_name': db_name,
        'collections': {}
    }
    
    # Get all collections
    collection_names = db.list_collection_names()
    
    for coll_name in collection_names:
        collection = db[coll_name]
        
        # Sample documents to infer schema
        sample_docs = list(collection.find().limit(100))
        
        if not sample_docs:
            schema_info['collections'][coll_name] = {'fields': [], 'sample_count': 0}
            continue
        
        # Infer fields from sample documents
        all_fields = set()
        field_types = {}
        
        for doc in sample_docs:
            for key, value in doc.items():
                all_fields.add(key)
                type_name = type(value).__name__
                if key not in field_types:
                    field_types[key] = set()
                field_types[key].add(type_name)
        
        fields = []
        for field in all_fields:
            fields.append({
                'name': field,
                'types': list(field_types[field])
            })
        
        schema_info['collections'][coll_name] = {
            'fields': fields,
            'sample_count': len(sample_docs),
            'total_count': collection.count_documents({})
        }
    
    client.close()
    return schema_info


def analyze_excel_files(file_paths: List[str]) -> Dict[str, Any]:
    """
    Analyze Excel/CSV files structure using Pandas
    Supports .xlsx, .xls, and .csv files
    """
    schema_info = {
        'database_type': 'Excel/CSV',
        'files': {}
    }
    
    for file_path in file_paths:
        if not os.path.exists(file_path):
            schema_info['files'][os.path.basename(file_path)] = {
                'error': f'File not found: {file_path}'
            }
            continue
        
        file_ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)
        
        try:
            if file_ext in ['.xlsx', '.xls']:
                # Determine engine based on file extension
                engine = 'openpyxl' if file_ext == '.xlsx' else None
                
                try:
                    # Read Excel file with appropriate engine
                    if file_ext == '.xls':
                        # For .xls files, try openpyxl first, then xlrd
                        try:
                            # Try reading with openpyxl (convert if needed)
                            excel_file = pd.ExcelFile(file_path, engine='openpyxl')
                        except Exception:
                            # Fall back to xlrd for old .xls files
                            try:
                                excel_file = pd.ExcelFile(file_path, engine='xlrd')
                            except ImportError:
                                raise ImportError(
                                    "xlrd library is required for .xls files. "
                                    "Install with: pip install xlrd OR convert the file to .xlsx format"
                                )
                    else:
                        # For .xlsx files
                        excel_file = pd.ExcelFile(file_path, engine='openpyxl')
                    
                    sheets_info = {}
                    
                    # Get base filename without extension for DataFrame keys
                    file_name_base = os.path.splitext(os.path.basename(file_path))[0]
                    
                    for sheet_name in excel_file.sheet_names:
                        # Read first 1000 rows to analyze structure
                        df = pd.read_excel(excel_file, sheet_name=sheet_name, nrows=1000)
                        
                        # Get total row count (read whole file for accurate count)
                        df_full = pd.read_excel(excel_file, sheet_name=sheet_name)
                        total_rows = len(df_full)
                        
                        # Analyze columns and get unique values for categorical columns
                        columns_info = []
                        for col in df_full.columns:
                            col_data = df_full[col]
                            
                            # Determine actual data type
                            dtype = str(col_data.dtype)
                            if dtype == 'object':
                                # Check if it's actually numeric stored as string
                                try:
                                    pd.to_numeric(col_data.dropna(), errors='raise')
                                    dtype = 'numeric (stored as text)'
                                except:
                                    dtype = 'text'
                            elif 'int' in dtype:
                                dtype = 'integer'
                            elif 'float' in dtype:
                                dtype = 'float/decimal'
                            elif 'datetime' in dtype:
                                dtype = 'datetime'
                            
                            # Get sample values (non-null)
                            sample_values = col_data.dropna().head(5).tolist()
                            
                            # For categorical columns (text with low unique count), get all unique values
                            unique_values = None
                            if dtype == 'text' and col_data.nunique() <= 20:
                                unique_values = sorted([str(v) for v in col_data.dropna().unique().tolist()])
                            
                            columns_info.append({
                                'name': str(col),
                                'type': dtype,
                                'null_count': int(col_data.isnull().sum()),
                                'null_percentage': round(float(col_data.isnull().sum() / len(col_data) * 100), 2),
                                'unique_count': int(col_data.nunique()),
                                'sample_values': [str(v) for v in sample_values[:3]],  # First 3 samples
                                'unique_values': unique_values  # All unique values for categorical columns
                            })
                        
                        # Create the DataFrame key that will be used in queries
                        df_key = f"{file_name_base}_{sheet_name}"
                        
                        sheets_info[sheet_name] = {
                            'dataframe_key': df_key,  # CRITICAL: This is the key to use in Pandas queries
                            'columns': columns_info,
                            'total_rows': total_rows,
                            'analyzed_rows': len(df)
                        }
                    
                    schema_info['files'][file_name] = {
                        'type': 'Excel',
                        'file_extension': file_ext,
                        'sheets': sheets_info,
                        'total_sheets': len(sheets_info)
                    }
                    
                except ImportError as ie:
                    schema_info['files'][file_name] = {
                        'type': 'Excel',
                        'file_extension': file_ext,
                        'error': str(ie),
                        'suggestion': 'Install required library: pip install openpyxl xlrd'
                    }
                except Exception as ex:
                    # Catch any other Excel reading errors
                    schema_info['files'][file_name] = {
                        'type': 'Excel',
                        'file_extension': file_ext,
                        'error': f'Failed to read Excel file: {str(ex)}',
                        'suggestion': 'Check if file is corrupted or password-protected'
                    }
            
            elif file_ext == '.csv':
                # Read CSV file
                df_full = pd.read_csv(file_path)
                total_rows = len(df_full)
                
                # Get base filename without extension for DataFrame key
                file_name_base = os.path.splitext(os.path.basename(file_path))[0]
                
                # Analyze columns
                columns_info = []
                for col in df_full.columns:
                    col_data = df_full[col]
                    
                    # Determine data type
                    dtype = str(col_data.dtype)
                    if dtype == 'object':
                        dtype = 'text'
                    elif 'int' in dtype:
                        dtype = 'integer'
                    elif 'float' in dtype:
                        dtype = 'float/decimal'
                    elif 'datetime' in dtype:
                        dtype = 'datetime'
                    
                    # Get sample values
                    sample_values = col_data.dropna().head(5).tolist()
                    
                    # For categorical columns, get all unique values
                    unique_values = None
                    if dtype == 'text' and col_data.nunique() <= 20:
                        unique_values = sorted([str(v) for v in col_data.dropna().unique().tolist()])
                    
                    columns_info.append({
                        'name': str(col),
                        'type': dtype,
                        'null_count': int(col_data.isnull().sum()),
                        'null_percentage': round(float(col_data.isnull().sum() / len(col_data) * 100), 2),
                        'unique_count': int(col_data.nunique()),
                        'sample_values': [str(v) for v in sample_values[:3]],
                        'unique_values': unique_values
                    })
                
                schema_info['files'][file_name] = {
                    'type': 'CSV',
                    'dataframe_key': file_name_base,  # CRITICAL: This is the key to use in Pandas queries
                    'columns': columns_info,
                    'total_rows': total_rows,
                    'analyzed_rows': len(df_full)
                }
            
            else:
                schema_info['files'][file_name] = {
                    'error': f'Unsupported file format: {file_ext}. Supported formats: .xlsx, .xls, .csv'
                }
                
        except Exception as e:
            schema_info['files'][file_name] = {
                'type': 'Excel' if file_ext in ['.xlsx', '.xls'] else 'CSV',
                'file_extension': file_ext,
                'error': f'{type(e).__name__}: {str(e)}',
                'suggestion': 'Check if the file is corrupted or in the correct format'
            }
    
    return schema_info


def generate_schema_analysis_text(schema_dict: Dict[str, Any], llm_url: str, extra_knowledge: str = "") -> str:
    """
    Use LLM to generate human-readable schema analysis text
    """
    from main.utilities.variables import model_name
    
    schema_json = json.dumps(schema_dict, indent=2)
    db_type = schema_dict.get('database_type', 'Unknown')
    
    # Check if there are any errors in the schema
    has_errors = False
    if 'files' in schema_dict:
        for file_info in schema_dict['files'].values():
            if 'error' in file_info:
                has_errors = True
                break
    
    # Customize prompt based on database type
    if db_type == 'Excel/CSV':
        prompt = f"""You are a data analyst specializing in Excel and CSV files. Analyze the following file schema and provide a comprehensive, well-structured description that will help an AI assistant understand and query this data using Pandas.

File Schema:
{schema_json}

Additional Information from Supervisor:
{extra_knowledge if extra_knowledge else "None provided"}

IMPORTANT: This is an Excel/CSV-based data source. Queries will be executed using Pandas DataFrames.

{"CRITICAL: Some files have errors. Report these errors clearly and do NOT generate hypothetical/fake data." if has_errors else ""}

Provide a detailed analysis in markdown format including:
1. **Overview**: Describe the file structure (number of files, sheets, total rows). If there are errors, mention them prominently.
2. **Files and Sheets**: For each file and sheet, CRITICALLY include:
   - The exact **DataFrame key** to use in queries (e.g., `dfs['filename_sheetname']`)
   - This is the MOST IMPORTANT piece of information for querying
3. **Column Descriptions**: For each successfully loaded sheet/file, describe:
   - Column name and data type
   - Sample values (from the schema - use ACTUAL sample values provided, not made up ones)
   - If unique_values is provided (for categorical columns), list ALL unique values
   - Data quality (null percentages, unique values)
4. **Data Relationships**: If multiple files/sheets exist, describe how they might be related based on column names
5. **Query Examples**: Provide actual Pandas code examples using the EXACT DataFrame keys shown in the schema:
   - Example: `dfs['file_example_XLS_50_Sheet1']['Country'].value_counts()`
   - Example: `dfs['file_example_XLS_50_Sheet1'][dfs['file_example_XLS_50_Sheet1']['Age'] > 30]`
6. **Data Quality Notes**: Mention any issues (high null counts, data type mismatches, etc.)
7. **Special Considerations**: Any important notes about the data

CRITICAL REQUIREMENTS:
- DO NOT invent hypothetical column names or sample data. Use ONLY the information provided in the schema.
- ALWAYS show the exact DataFrame key (dataframe_key field) for each sheet/file
- Use ACTUAL unique values when provided in the schema
- Show concrete query examples with the correct DataFrame keys
Use markdown headers (##, ###) and bullet points (-) for clear formatting."""
    else:
        prompt = f"""You are a database schema analyst. Analyze the following database/file schema and provide a comprehensive, well-structured description that will help an AI assistant understand and query this data source.

Database Schema:
{schema_json}

Additional Information from Supervisor:
{extra_knowledge if extra_knowledge else "None provided"}

Provide a detailed analysis in markdown format including:
1. **Overview**: Database type and structure
2. **Tables/Collections**: List all tables with their purposes
3. **Column Descriptions**: Each column with data types and constraints
4. **Relationships**: Primary keys and foreign keys
5. **Indexes**: Any indexes or constraints
6. **Query Patterns**: Suggested query patterns for common operations
7. **Special Considerations**: Any important notes

Use markdown headers (##, ###) and bullet points (-) for clear formatting."""

    endpoint = llm_url.rstrip("/") + "/chat/completions"
    
    messages = [
        {"role": "system", "content": "You are a database schema analyst."},
        {"role": "user", "content": prompt}
    ]
    
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False}
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=60)
        if resp.status_code != 200:
            return f"Error generating schema analysis: {resp.status_code}\n\nRaw Schema:\n{schema_json}"
        
        data = resp.json()
        analysis = data["choices"][0]["message"]["content"].strip()
        return analysis
    except Exception as e:
        return f"Error generating schema analysis: {str(e)}\n\nRaw Schema:\n{schema_json}"


def execute_sql_query(db_type: str, connection_info: str, query: str) -> Tuple[bool, Any]:
    """
    Execute SQL query on database
    Returns (success, result_or_error)
    """
    try:
        if db_type == 'sqlite':
            conn = sqlite3.connect(connection_info)
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            columns = [description[0] for description in cursor.description] if cursor.description else []
            conn.close()
            return True, {'columns': columns, 'rows': results}
        
        elif db_type == 'mysql':
            import pymysql
            from urllib.parse import urlparse
            parsed = urlparse(connection_info)
            conn = pymysql.connect(
                host=parsed.hostname,
                port=parsed.port or 3306,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path.lstrip('/')
            )
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            conn.close()
            return True, {'columns': columns, 'rows': results}
        
        elif db_type == 'postgresql':
            import psycopg2
            from urllib.parse import urlparse
            parsed = urlparse(connection_info)
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path.lstrip('/')
            )
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            conn.close()
            return True, {'columns': columns, 'rows': results}
        
        else:
            return False, f"Unsupported database type: {db_type}"
    
    except Exception as e:
        return False, str(e)


def execute_mongodb_query(connection_string: str, collection_name: str, query_dict: Dict) -> Tuple[bool, Any]:
    """
    Execute MongoDB query
    Returns (success, result_or_error)
    """
    try:
        from pymongo import MongoClient
        
        client = MongoClient(connection_string)
        db_name = connection_string.split('/')[-1]
        db = client[db_name]
        collection = db[collection_name]
        
        results = list(collection.find(query_dict).limit(100))
        
        # Convert ObjectId to string for JSON serialization
        for doc in results:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
        
        client.close()
        return True, results
    
    except Exception as e:
        return False, str(e)


def execute_pandas_query(file_paths: List[str], query_code: str) -> Tuple[bool, Any]:
    """
    Execute pandas query on Excel/CSV files
    query_code should be Python code that uses 'dfs' dictionary
    Returns (success, result_or_error)
    """
    try:
        # Load all files into dataframes
        dfs = {}
        for file_path in file_paths:
            if not os.path.exists(file_path):
                continue
            
            file_ext = os.path.splitext(file_path)[1].lower()
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            
            if file_ext in ['.xlsx', '.xls']:
                # For Excel, load all sheets with appropriate engine
                try:
                    if file_ext == '.xls':
                        # Try openpyxl first, then xlrd for old .xls files
                        try:
                            excel_file = pd.ExcelFile(file_path, engine='openpyxl')
                        except:
                            excel_file = pd.ExcelFile(file_path, engine='xlrd')
                    else:
                        excel_file = pd.ExcelFile(file_path, engine='openpyxl')
                    
                    for sheet_name in excel_file.sheet_names:
                        key = f"{file_name}_{sheet_name}"
                        dfs[key] = pd.read_excel(excel_file, sheet_name=sheet_name)
                        
                except Exception as e:
                    return False, f"Error reading Excel file {file_name}: {str(e)}. For .xls files, install openpyxl or xlrd."
                    
            elif file_ext == '.csv':
                dfs[file_name] = pd.read_csv(file_path)
        
        if not dfs:
            return False, "No valid files could be loaded. Check file paths and formats."
        
        # Create a safe execution environment
        safe_globals = {
            'pd': pd,
            'dfs': dfs,
            '__builtins__': {
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'sum': sum,
                'max': max,
                'min': min,
                'print': print,
                'round': round,
                'sorted': sorted,
                'enumerate': enumerate,
                'zip': zip,
            }
        }
        
        # Execute the query code
        local_vars = {}
        exec(query_code, safe_globals, local_vars)
        
        # Get the result (should be stored in 'result' variable)
        if 'result' in local_vars:
            result = local_vars['result']
            
            # Convert DataFrame to dict for JSON serialization
            if isinstance(result, pd.DataFrame):
                return True, result.to_dict(orient='records')
            elif isinstance(result, pd.Series):
                return True, result.to_dict()
            else:
                return True, result
        else:
            return False, "Query code must assign result to 'result' variable"
    
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)}"


def generate_database_query(user_question: str, schema_analysis: str, db_type: str, llm_url: str, 
                           chat_history: List[Dict] = None, previous_error: str = None) -> str:
    """
    Use LLM to generate SQL/MongoDB/Pandas query based on user question and schema
    """
    from main.utilities.variables import model_name
    
    chat_history = chat_history or []
    
    # Create appropriate prompt based on database type
    if db_type in ['sqlite', 'mysql', 'postgresql']:
        query_type = "SQL"
        query_instructions = """Generate a valid SQL query to answer the user's question.

CRITICAL RULES - YOU MUST FOLLOW THESE EXACTLY:
1. Return ONLY the SQL query text, absolutely NO explanations, comments, or markdown
2. Use ONLY the exact table and column names provided in the schema above
3. NEVER use columns that don't exist in the schema
4. Check the schema carefully - if a column like 'DepartmentName' is in the departments table, use d.DepartmentName, NOT e.DepartmentName
5. Use proper JOINs only when needed and ensure join columns exist in both tables
6. Query should be safe (no DROP, DELETE, UPDATE, INSERT, etc.)
7. Add LIMIT 100 to prevent excessive results
8. Double-check column names match the schema exactly (case-sensitive)
9. SYNTAX CRITICAL: Check for typos, missing commas, unmatched parentheses
10. LOGIC CRITICAL: Verify the query answers the actual question"""
    
    elif db_type == 'mongodb':
        query_type = "MongoDB"
        query_instructions = """Generate a valid MongoDB query (as Python dict) to answer the user's question.

CRITICAL RULES:
1. Return ONLY the query dict, absolutely NO explanations
2. Use ONLY collection and field names from the schema above
3. Use proper MongoDB query syntax
4. Query should be safe (no delete operations)
5. Limit results to 100 documents
6. SYNTAX CRITICAL: Proper Python dict syntax with matching braces"""
    
    else:  # Excel/CSV
        query_type = "Pandas"
        query_instructions = """Generate valid Python/Pandas code to answer the user's question.

CRITICAL RULES:
1. The code has access to a 'dfs' dictionary containing DataFrames
2. The schema above shows the EXACT DataFrame keys to use (look for 'dataframe_key' field)
3. DataFrame keys are formatted as: 'filename_sheetname' (e.g., 'file_example_XLS_50_Sheet1')
4. Return ONLY the Python code, absolutely NO explanations or markdown
5. Store the final result in a variable called 'result'
6. Use ONLY column names that exist in the schema above
7. Use pandas operations for data manipulation (filtering, grouping, value_counts, etc.)
8. Keep code safe (no file I/O, no imports)
9. SYNTAX CRITICAL: All strings must have matching quotes - 'text' or "text" (not 'text or text")
10. SYNTAX CRITICAL: All brackets must be balanced - [] () {}
11. Example for counting: result = dfs['filename_Sheet1']['Country'].value_counts()
12. Example for filtering: result = len(dfs['filename_Sheet1'][dfs['filename_Sheet1']['Country'] == 'France'])

IMPORTANT: Check the schema for the exact dataframe_key and use it correctly!"""
    
    # Add error context if this is a retry
    error_context = ""
    if previous_error:
        error_context = f"""

⚠️ CRITICAL - YOUR PREVIOUS QUERY FAILED:
{previous_error}

🚫 DO NOT GENERATE THE SAME BROKEN QUERY AGAIN!
✅ You MUST fix the specific error mentioned above.

If the error says 'unterminated string', FIX your quotes.
If the error says 'KeyError', use the EXACT column name from schema.
If the error says 'SyntaxError', carefully review Python syntax.

📝 REMEMBER: You are trying to answer the user's question below.
Generate a CORRECTED query that:
1. Fixes the error
2. Actually answers the user's question"""
    
    prompt = f"""You are a {query_type} query generation assistant.

Database Schema Information:
{schema_analysis}

{query_instructions}{error_context}

User Question: {user_question}

Generate ONLY the {query_type} query (no explanations, no markdown, no code blocks):"""

    endpoint = llm_url.rstrip("/") + "/chat/completions"
    
    messages = [
        {"role": "system", "content": f"You are a {query_type} query generation expert. Generate queries based on schema and user questions."},
        *chat_history,
        {"role": "user", "content": prompt}
    ]
    
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.2,  # Low temperature for precise query generation
        "max_tokens": 512,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False}
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        query = data["choices"][0]["message"]["content"].strip()
        
        # Clean up the query (remove markdown code blocks if present)
        if query.startswith("```"):
            lines = query.split("\n")
            query = "\n".join(lines[1:-1]) if len(lines) > 2 else query
            query = query.replace("```sql", "").replace("```python", "").replace("```", "").strip()
        
        return query
    except Exception as e:
        print(f"Error generating query: {e}")
        return None


def format_query_results(results: Any, db_type: str) -> str:
    """
    Format query results into human-readable text for LLM to use in response
    """
    try:
        if db_type in ['sqlite', 'mysql', 'postgresql']:
            # SQL results
            if isinstance(results, dict) and 'columns' in results and 'rows' in results:
                columns = results['columns']
                rows = results['rows']
                
                if not rows:
                    return "No results found."
                
                # Create a formatted table
                formatted = "Query Results:\n"
                formatted += " | ".join(columns) + "\n"
                formatted += "-" * (sum(len(col) for col in columns) + 3 * len(columns)) + "\n"
                
                for row in rows[:50]:  # Limit to first 50 rows
                    formatted += " | ".join(str(val) for val in row) + "\n"
                
                if len(rows) > 50:
                    formatted += f"\n... and {len(rows) - 50} more rows"
                
                return formatted
        
        elif db_type == 'mongodb':
            # MongoDB results
            if isinstance(results, list):
                if not results:
                    return "No results found."
                
                formatted = f"Query Results ({len(results)} documents):\n"
                for i, doc in enumerate(results[:20], 1):  # Limit to first 20 docs
                    formatted += f"\nDocument {i}:\n"
                    formatted += json.dumps(doc, indent=2) + "\n"
                
                if len(results) > 20:
                    formatted += f"\n... and {len(results) - 20} more documents"
                
                return formatted
        
        else:  # Excel/CSV
            # Handle numeric results (counts, sums, averages)
            if isinstance(results, (int, float)):
                return f"**RESULT: {results}**\n\nThis is the exact answer from the Excel/CSV data."
            
            # Handle list results
            if isinstance(results, list):
                if not results:
                    return "No results found (0 rows matched the query)."
                
                # Convert list of dicts to formatted table
                if results and isinstance(results[0], dict):
                    columns = list(results[0].keys())
                    formatted = f"Query Results ({len(results)} rows):\n"
                    formatted += " | ".join(columns) + "\n"
                    formatted += "-" * (sum(len(col) for col in columns) + 3 * len(columns)) + "\n"
                    
                    for row in results[:50]:  # Limit to first 50 rows
                        formatted += " | ".join(str(row.get(col, '')) for col in columns) + "\n"
                    
                    if len(results) > 50:
                        formatted += f"\n... and {len(results) - 50} more rows"
                    
                    return formatted
                
                # Handle list of simple values
                return f"Query Results ({len(results)} items):\n" + "\n".join(str(item) for item in results[:100])
            
            # Handle dict results (e.g., from value_counts)
            if isinstance(results, dict):
                formatted = "Query Results:\n"
                for key, value in list(results.items())[:50]:
                    formatted += f"{key}: {value}\n"
                return formatted
            
            # Fallback: show the actual value clearly
            return f"**RESULT: {results}**\n\nType: {type(results).__name__}"
    
    except Exception as e:
        return f"Error formatting results: {str(e)}\n\nRaw results: {str(results)}"

