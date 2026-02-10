# SQL Server Express Setup Guide for Testing

## Quick Setup Steps

### 1. Download SQL Server Express (FREE)
- Go to: https://www.microsoft.com/en-us/sql-server/sql-server-downloads
- Click "Download now" under "Express" edition
- Run the installer (SQLServer2022-SSEI-Expr.exe)

### 2. Installation
1. Choose **"Basic"** installation type
2. Accept license terms
3. Choose installation location (default is fine)
4. Wait for installation (~5-10 minutes)
5. **IMPORTANT**: Note the connection string shown at the end!
   - It will look like: `Server=localhost\SQLEXPRESS;Database=master;Trusted_Connection=True;`

### 3. Install SQL Server Management Studio (SSMS) - Optional but Helpful
- Download from: https://aka.ms/ssmsfullsetup
- Install (takes ~10 minutes)
- This gives you a GUI to manage databases

### 4. Enable TCP/IP and Mixed Mode Authentication

**Open SQL Server Configuration Manager:**
1. Press Win+R, type: `SQLServerManager16.msc` (or SQLServerManager15.msc for older versions)
2. Expand "SQL Server Network Configuration"
3. Click "Protocols for SQLEXPRESS"
4. Right-click "TCP/IP" → Enable
5. Double-click "TCP/IP" → Go to "IP Addresses" tab
6. Scroll to "IPAll" section
7. Set "TCP Port" to **1433**
8. Click OK

**Enable Mixed Mode Authentication:**
1. Open "SQL Server Services"
2. Right-click "SQL Server (SQLEXPRESS)" → Restart

**Enable SQL Server Authentication:**
1. Open SSMS and connect with Windows Authentication
2. Right-click server name → Properties
3. Go to "Security" page
4. Select "SQL Server and Windows Authentication mode"
5. Click OK
6. Restart SQL Server service

### 5. Create a Test User
Open SSMS or run this in Command Prompt:
```bash
sqlcmd -S localhost\SQLEXPRESS -E
```

Then run these SQL commands:
```sql
CREATE LOGIN testuser WITH PASSWORD = 'Test@1234';
GO
CREATE DATABASE TestDB;
GO
USE TestDB;
GO
CREATE USER testuser FOR LOGIN testuser;
GO
ALTER ROLE db_owner ADD MEMBER testuser;
GO
```

### 6. Create Sample Tables and Data
```sql
USE TestDB;
GO

-- Create Customers table
CREATE TABLE Customers (
    CustomerID INT PRIMARY KEY IDENTITY(1,1),
    FirstName NVARCHAR(50),
    LastName NVARCHAR(50),
    Email NVARCHAR(100),
    City NVARCHAR(50),
    Country NVARCHAR(50),
    JoinDate DATE
);

-- Create Orders table
CREATE TABLE Orders (
    OrderID INT PRIMARY KEY IDENTITY(1,1),
    CustomerID INT FOREIGN KEY REFERENCES Customers(CustomerID),
    OrderDate DATE,
    TotalAmount DECIMAL(10,2),
    Status NVARCHAR(20)
);

-- Create Products table
CREATE TABLE Products (
    ProductID INT PRIMARY KEY IDENTITY(1,1),
    ProductName NVARCHAR(100),
    Category NVARCHAR(50),
    Price DECIMAL(10,2),
    Stock INT
);

-- Insert sample customers
INSERT INTO Customers (FirstName, LastName, Email, City, Country, JoinDate)
VALUES 
    ('John', 'Doe', 'john.doe@email.com', 'New York', 'USA', '2024-01-15'),
    ('Jane', 'Smith', 'jane.smith@email.com', 'London', 'UK', '2024-02-20'),
    ('Bob', 'Johnson', 'bob.j@email.com', 'Paris', 'France', '2024-03-10'),
    ('Alice', 'Williams', 'alice.w@email.com', 'Berlin', 'Germany', '2024-04-05'),
    ('Charlie', 'Brown', 'charlie.b@email.com', 'Tokyo', 'Japan', '2024-05-12'),
    ('Diana', 'Davis', 'diana.d@email.com', 'Sydney', 'Australia', '2024-06-18'),
    ('Eve', 'Miller', 'eve.m@email.com', 'Toronto', 'Canada', '2024-07-22'),
    ('Frank', 'Wilson', 'frank.w@email.com', 'New York', 'USA', '2024-08-30'),
    ('Grace', 'Moore', 'grace.m@email.com', 'London', 'UK', '2024-09-14'),
    ('Henry', 'Taylor', 'henry.t@email.com', 'Paris', 'France', '2024-10-25');

-- Insert sample products
INSERT INTO Products (ProductName, Category, Price, Stock)
VALUES
    ('Laptop Pro 15', 'Electronics', 1299.99, 45),
    ('Wireless Mouse', 'Electronics', 29.99, 150),
    ('Office Chair', 'Furniture', 249.99, 30),
    ('Desk Lamp', 'Furniture', 45.99, 80),
    ('USB-C Cable', 'Accessories', 12.99, 200),
    ('Monitor 27"', 'Electronics', 399.99, 25),
    ('Keyboard Mechanical', 'Electronics', 89.99, 60),
    ('Notebook Set', 'Stationery', 15.99, 120),
    ('Pen Pack', 'Stationery', 8.99, 300),
    ('Water Bottle', 'Accessories', 19.99, 100);

-- Insert sample orders
INSERT INTO Orders (CustomerID, OrderDate, TotalAmount, Status)
VALUES
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
    (10, '2024-10-28', 399.99, 'Processing');

GO

-- Verify data
SELECT 'Customers' AS TableName, COUNT(*) AS RecordCount FROM Customers
UNION ALL
SELECT 'Orders', COUNT(*) FROM Orders
UNION ALL
SELECT 'Products', COUNT(*) FROM Products;
GO
```

### 7. Connection String for RAG Webapp
Use this format in your collection:
```
mssql+pyodbc://testuser:Test@1234@localhost:1433/TestDB?driver=ODBC+Driver+17+for+SQL+Server
```

### 8. Install pyodbc in venv
```bash
D:/Projects/venv2/Scripts/pip.exe install pyodbc
```

### 9. Test Queries to Try
Once you create the collection in your RAG webapp:
- "Show me all customers from USA"
- "What's the total amount of all orders?"
- "List all products under $50"
- "How many orders are in Processing status?"
- "Show customers who joined in 2024"
- "What's the average order amount?"
- "List all electronics products with their prices"
- "Which cities have customers?"

## Troubleshooting

### Can't connect?
1. Check if SQL Server is running:
   - Services → SQL Server (SQLEXPRESS) should be "Running"
2. Verify TCP/IP is enabled and port 1433 is set
3. Check Windows Firewall allows port 1433
4. Try connection in SSMS first

### Authentication failed?
- Make sure you created the login and user correctly
- Verify Mixed Mode Authentication is enabled
- Restart SQL Server service after any auth changes

### ODBC Driver not found?
- Download from: https://go.microsoft.com/fwlink/?linkid=2223304
- Install "ODBC Driver 18 for SQL Server"
- Update connection string to use: `driver=ODBC+Driver+18+for+SQL+Server`
- Add `TrustServerCertificate=yes` if needed
