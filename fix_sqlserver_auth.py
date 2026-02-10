"""
Fix SQL Server authentication for testuser
"""

import pyodbc

def fix_sql_auth():
    print("=" * 60)
    print("Fixing SQL Server Authentication")
    print("=" * 60)
    
    try:
        # Connect with Windows Authentication first
        print("\n1. Connecting with Windows Authentication...")
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 18 for SQL Server};'
            'SERVER=localhost\\SQLEXPRESS;'
            'DATABASE=master;'
            'Trusted_Connection=yes;'
            'TrustServerCertificate=yes;'
        )
        conn.autocommit = True
        cursor = conn.cursor()
        print("   ✓ Connected")
        
        # Enable mixed mode authentication
        print("\n2. Enabling SQL Server and Windows Authentication Mode...")
        cursor.execute("""
            EXEC xp_instance_regwrite 
                N'HKEY_LOCAL_MACHINE', 
                N'Software\\Microsoft\\MSSQLServer\\MSSQLServer',
                N'LoginMode', 
                REG_DWORD, 
                2
        """)
        print("   ✓ Mixed mode enabled (requires SQL Server restart)")
        
        # Drop existing login if exists and recreate
        print("\n3. Recreating testuser login...")
        try:
            cursor.execute("DROP LOGIN testuser")
            print("   ✓ Dropped existing testuser")
        except:
            print("   ℹ testuser doesn't exist, creating new...")
        
        cursor.execute("""
            CREATE LOGIN testuser 
            WITH PASSWORD = 'Test@1234',
            CHECK_POLICY = OFF,
            CHECK_EXPIRATION = OFF
        """)
        print("   ✓ testuser login created")
        
        # Grant sysadmin role to testuser
        cursor.execute("ALTER SERVER ROLE sysadmin ADD MEMBER testuser")
        print("   ✓ testuser granted sysadmin privileges")
        
        conn.close()
        
        # Connect to TestDB and set up user
        print("\n4. Setting up TestDB permissions...")
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 18 for SQL Server};'
            'SERVER=localhost\\SQLEXPRESS;'
            'DATABASE=TestDB;'
            'Trusted_Connection=yes;'
            'TrustServerCertificate=yes;'
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        try:
            cursor.execute("DROP USER testuser")
        except:
            pass
        
        cursor.execute("CREATE USER testuser FOR LOGIN testuser")
        cursor.execute("ALTER ROLE db_owner ADD MEMBER testuser")
        print("   ✓ testuser configured in TestDB")
        
        conn.close()
        
        print("\n5. Restarting SQL Server service...")
        import subprocess
        result = subprocess.run(
            ['net', 'stop', 'MSSQL$SQLEXPRESS'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("   ✓ Service stopped")
        else:
            print(f"   ⚠ Stop result: {result.stderr}")
        
        result = subprocess.run(
            ['net', 'start', 'MSSQL$SQLEXPRESS'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("   ✓ Service started")
        else:
            print(f"   ⚠ Start result: {result.stderr}")
        
        # Wait a moment for service to fully start
        import time
        print("\n6. Waiting for SQL Server to fully start...")
        time.sleep(5)
        print("   ✓ Ready")
        
        # Test SQL authentication
        print("\n7. Testing SQL Authentication with testuser...")
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 18 for SQL Server};'
            'SERVER=localhost\\SQLEXPRESS;'
            'DATABASE=TestDB;'
            'UID=testuser;'
            'PWD=Test@1234;'
            'TrustServerCertificate=yes;'
        )
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Customers")
        count = cursor.fetchone()[0]
        print(f"   ✓ Successfully connected! Found {count} customers")
        conn.close()
        
        print("\n" + "=" * 60)
        print("✓ SQL Server Authentication Fixed!")
        print("=" * 60)
        print("\nYou can now use these credentials in your RAG webapp:")
        print("  Host: localhost\\SQLEXPRESS")
        print("  Database: TestDB")
        print("  Username: testuser")
        print("  Password: Test@1234")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n" + "=" * 60)
        print("Alternative: Use Windows Authentication")
        print("=" * 60)
        print("\nIf SQL authentication continues to fail, you can use")
        print("Windows Authentication instead. Leave username and")
        print("password blank in the webapp form.")

if __name__ == "__main__":
    fix_sql_auth()
