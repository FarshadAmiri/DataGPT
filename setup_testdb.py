"""
Setup TestDB database with sample data using Python
Alternative to sqlcmd
"""

import pyodbc

def setup_testdb():
    """Create TestDB and populate with sample data"""
    
    print("=" * 60)
    print("Setting up TestDB Database")
    print("=" * 60)
    
    try:
        # Connect to master database to create TestDB
        print("\n1. Connecting to SQL Server...")
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 18 for SQL Server};'
            'SERVER=localhost\\SQLEXPRESS;'
            'DATABASE=master;'
            'Trusted_Connection=yes;'
            'TrustServerCertificate=yes;'
        )
        conn.autocommit = True
        cursor = conn.cursor()
        print("   ✓ Connected to master database")
        
        # Create TestDB database
        print("\n2. Creating TestDB database...")
        try:
            cursor.execute("CREATE DATABASE TestDB")
            print("   ✓ TestDB database created")
        except pyodbc.Error as e:
            if 'already exists' in str(e):
                print("   ℹ TestDB already exists, continuing...")
            else:
                raise
        
        # Create login
        print("\n3. Creating testuser login...")
        try:
            cursor.execute("CREATE LOGIN testuser WITH PASSWORD = 'Test@1234'")
            print("   ✓ testuser login created")
        except pyodbc.Error as e:
            if 'already exists' in str(e):
                print("   ℹ testuser already exists, continuing...")
            else:
                raise
        
        conn.close()
        
        # Connect to TestDB
        print("\n4. Connecting to TestDB...")
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 18 for SQL Server};'
            'SERVER=localhost\\SQLEXPRESS;'
            'DATABASE=TestDB;'
            'Trusted_Connection=yes;'
            'TrustServerCertificate=yes;'
        )
        conn.autocommit = True
        cursor = conn.cursor()
        print("   ✓ Connected to TestDB")
        
        # Create user
        print("\n5. Creating database user...")
        try:
            cursor.execute("CREATE USER testuser FOR LOGIN testuser")
            cursor.execute("ALTER ROLE db_owner ADD MEMBER testuser")
            print("   ✓ testuser added to TestDB with db_owner role")
        except pyodbc.Error as e:
            if 'already exists' in str(e):
                print("   ℹ testuser already exists in TestDB, continuing...")
            else:
                raise
        
        # Create tables
        print("\n6. Creating tables...")
        
        # Customers table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Customers')
            BEGIN
                CREATE TABLE Customers (
                    CustomerID INT PRIMARY KEY IDENTITY(1,1),
                    FirstName NVARCHAR(50),
                    LastName NVARCHAR(50),
                    Email NVARCHAR(100),
                    City NVARCHAR(50),
                    Country NVARCHAR(50),
                    JoinDate DATE
                )
            END
        """)
        print("   ✓ Customers table created")
        
        # Orders table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Orders')
            BEGIN
                CREATE TABLE Orders (
                    OrderID INT PRIMARY KEY IDENTITY(1,1),
                    CustomerID INT FOREIGN KEY REFERENCES Customers(CustomerID),
                    OrderDate DATE,
                    TotalAmount DECIMAL(10,2),
                    Status NVARCHAR(20)
                )
            END
        """)
        print("   ✓ Orders table created")
        
        # Products table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Products')
            BEGIN
                CREATE TABLE Products (
                    ProductID INT PRIMARY KEY IDENTITY(1,1),
                    ProductName NVARCHAR(100),
                    Category NVARCHAR(50),
                    Price DECIMAL(10,2),
                    Stock INT
                )
            END
        """)
        print("   ✓ Products table created")
        
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM Customers")
        customer_count = cursor.fetchone()[0]
        
        if customer_count == 0:
            print("\n7. Inserting sample data...")
            
            # Insert customers
            customers = [
                ('John', 'Doe', 'john.doe@email.com', 'New York', 'USA', '2024-01-15'),
                ('Jane', 'Smith', 'jane.smith@email.com', 'London', 'UK', '2024-02-20'),
                ('Bob', 'Johnson', 'bob.j@email.com', 'Paris', 'France', '2024-03-10'),
                ('Alice', 'Williams', 'alice.w@email.com', 'Berlin', 'Germany', '2024-04-05'),
                ('Charlie', 'Brown', 'charlie.b@email.com', 'Tokyo', 'Japan', '2024-05-12'),
                ('Diana', 'Davis', 'diana.d@email.com', 'Sydney', 'Australia', '2024-06-18'),
                ('Eve', 'Miller', 'eve.m@email.com', 'Toronto', 'Canada', '2024-07-22'),
                ('Frank', 'Wilson', 'frank.w@email.com', 'New York', 'USA', '2024-08-30'),
                ('Grace', 'Moore', 'grace.m@email.com', 'London', 'UK', '2024-09-14'),
                ('Henry', 'Taylor', 'henry.t@email.com', 'Paris', 'France', '2024-10-25')
            ]
            
            cursor.executemany(
                "INSERT INTO Customers (FirstName, LastName, Email, City, Country, JoinDate) VALUES (?, ?, ?, ?, ?, ?)",
                customers
            )
            print("   ✓ 10 customers inserted")
            
            # Insert products
            products = [
                ('Laptop Pro 15', 'Electronics', 1299.99, 45),
                ('Wireless Mouse', 'Electronics', 29.99, 150),
                ('Office Chair', 'Furniture', 249.99, 30),
                ('Desk Lamp', 'Furniture', 45.99, 80),
                ('USB-C Cable', 'Accessories', 12.99, 200),
                ('Monitor 27"', 'Electronics', 399.99, 25),
                ('Keyboard Mechanical', 'Electronics', 89.99, 60),
                ('Notebook Set', 'Stationery', 15.99, 120),
                ('Pen Pack', 'Stationery', 8.99, 300),
                ('Water Bottle', 'Accessories', 19.99, 100)
            ]
            
            cursor.executemany(
                "INSERT INTO Products (ProductName, Category, Price, Stock) VALUES (?, ?, ?, ?)",
                products
            )
            print("   ✓ 10 products inserted")
            
            # Insert orders
            orders = [
                (1, '2024-01-20', 1329.98, 'Completed'),
                (1, '2024-02-15', 45.99, 'Completed'),
                (2, '2024-03-01', 399.99, 'Completed'),
                (3, '2024-03-15', 249.99, 'Shipped'),
                (4, '2024-04-10', 89.99, 'Completed'),
                (5, '2024-05-20', 1299.99, 'Processing'),
                (6, '2024-06-25', 29.99, 'Completed'),
                (7, '2024-07-30', 650.97, 'Completed'),
                (8, '2024-08-05', 19.99, 'Shipped'),
                (9, '2024-09-20', 45.99, 'Completed'),
                (10, '2024-10-28', 399.99, 'Processing')
            ]
            
            cursor.executemany(
                "INSERT INTO Orders (CustomerID, OrderDate, TotalAmount, Status) VALUES (?, ?, ?, ?)",
                orders
            )
            print("   ✓ 11 orders inserted")
        else:
            print(f"\n7. Data already exists ({customer_count} customers found), skipping insert...")
        
        # Verify setup
        print("\n8. Verifying setup...")
        cursor.execute("SELECT COUNT(*) FROM Customers")
        customers = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM Orders")
        orders = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM Products")
        products = cursor.fetchone()[0]
        
        print(f"   ✓ Customers: {customers} records")
        print(f"   ✓ Orders: {orders} records")
        print(f"   ✓ Products: {products} records")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("✓ TestDB Setup Complete!")
        print("=" * 60)
        print("\nConnection string for RAG webapp:")
        print("mssql+pyodbc://testuser:Test@1234@localhost\\SQLEXPRESS:1433/TestDB?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes")
        print("\nYou can now create a SQL Server collection in your RAG webapp!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    setup_testdb()
