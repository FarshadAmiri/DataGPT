"""
Quick test script to verify SQL Server connection
Run this before testing in the RAG webapp
"""

def test_sql_server_connection():
    """Test SQL Server connection and pyodbc installation"""
    
    print("=" * 60)
    print("SQL Server Connection Test")
    print("=" * 60)
    
    # Test 1: Check if pyodbc is installed
    print("\n1. Checking pyodbc installation...")
    try:
        import pyodbc
        print("   ✓ pyodbc is installed")
        print(f"   Version: {pyodbc.version}")
    except ImportError:
        print("   ✗ pyodbc is NOT installed")
        print("   Install it with: D:/Projects/venv2/Scripts/pip.exe install pyodbc")
        return False
    
    # Test 2: Check available ODBC drivers
    print("\n2. Checking available ODBC drivers...")
    drivers = [d for d in pyodbc.drivers() if 'SQL Server' in d]
    if drivers:
        print("   ✓ SQL Server ODBC drivers found:")
        for driver in drivers:
            print(f"     - {driver}")
    else:
        print("   ✗ No SQL Server ODBC drivers found")
        print("   Download from: https://go.microsoft.com/fwlink/?linkid=2223304")
        return False
    
    # Test 3: Try to connect to SQL Server
    print("\n3. Testing SQL Server connection...")
    
    # You may need to modify these based on your setup
    # Try multiple driver versions and connection formats
    test_connections = [
        {
            'name': 'Windows Auth (Driver 18)',
            'conn_str': 'DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost\\SQLEXPRESS;DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;'
        },
        {
            'name': 'Windows Auth (Driver 17)',
            'conn_str': 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost\\SQLEXPRESS;DATABASE=master;Trusted_Connection=yes;'
        },
        {
            'name': 'SQL Auth - testuser (Driver 18)',
            'conn_str': 'DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;DATABASE=TestDB;UID=testuser;PWD=Test@1234;TrustServerCertificate=yes;'
        },
        {
            'name': 'SQL Auth - testuser (Driver 17)',
            'conn_str': 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost,1433;DATABASE=TestDB;UID=testuser;PWD=Test@1234'
        },
        {
            'name': 'Windows Auth - Default Instance',
            'conn_str': 'DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;'
        }
    ]
    
    connected = False
    for test in test_connections:
        try:
            print(f"\n   Trying {test['name']}...")
            conn = pyodbc.connect(test['conn_str'], timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()[0]
            print(f"   ✓ Connected successfully!")
            print(f"   SQL Server version: {version[:60]}...")
            
            # Try to list databases
            cursor.execute("SELECT name FROM sys.databases ORDER BY name")
            databases = [row[0] for row in cursor.fetchall()]
            print(f"\n   Available databases: {', '.join(databases)}")
            
            # If TestDB exists, show tables
            if 'TestDB' in databases:
                cursor.execute("USE TestDB; SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
                tables = [row[0] for row in cursor.fetchall()]
                if tables:
                    print(f"\n   Tables in TestDB: {', '.join(tables)}")
                    
                    # Show row counts
                    for table in tables:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        print(f"     - {table}: {count} rows")
            
            conn.close()
            connected = True
            
            print(f"\n   ✓ Connection string for RAG webapp:")
            if 'Driver 18' in test['conn_str']:
                print(f"   mssql+pyodbc://testuser:Test@1234@localhost:1433/TestDB?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes")
            else:
                print(f"   mssql+pyodbc://testuser:Test@1234@localhost:1433/TestDB?driver=ODBC+Driver+17+for+SQL+Server")
            
            break
            
        except pyodbc.Error as e:
            print(f"   ✗ Failed: {str(e)[:100]}")
            continue
        except Exception as e:
            print(f"   ✗ Error: {str(e)[:100]}")
            continue
    
    if not connected:
        print("\n   ⚠ Could not connect to SQL Server")
        print("   Make sure:")
        print("   - SQL Server is running (check Services)")
        print("   - TCP/IP is enabled in SQL Server Configuration Manager")
        print("   - Port 1433 is open")
        print("   - You've created the testuser with password Test@1234")
        return False
    
    print("\n" + "=" * 60)
    print("✓ All tests passed! You're ready to test SQL Server in RAG webapp")
    print("=" * 60)
    return True


if __name__ == "__main__":
    test_sql_server_connection()
