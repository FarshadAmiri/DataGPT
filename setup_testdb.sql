-- Connect to SQL Server and create TestDB with sample data
-- Run this file with: sqlcmd -S localhost -E -i setup_testdb.sql

-- Create TestDB database
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'TestDB')
BEGIN
    CREATE DATABASE TestDB;
    PRINT 'TestDB database created successfully';
END
ELSE
    PRINT 'TestDB database already exists';
GO

-- Create login and user
USE master;
GO

IF NOT EXISTS (SELECT name FROM sys.sql_logins WHERE name = 'testuser')
BEGIN
    CREATE LOGIN testuser WITH PASSWORD = 'Test@1234';
    PRINT 'testuser login created successfully';
END
ELSE
    PRINT 'testuser login already exists';
GO

USE TestDB;
GO

IF NOT EXISTS (SELECT name FROM sys.database_principals WHERE name = 'testuser')
BEGIN
    CREATE USER testuser FOR LOGIN testuser;
    ALTER ROLE db_owner ADD MEMBER testuser;
    PRINT 'testuser added to TestDB successfully';
END
ELSE
    PRINT 'testuser already exists in TestDB';
GO

-- Create Customers table
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
    );
    PRINT 'Customers table created';
END
GO

-- Create Orders table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Orders')
BEGIN
    CREATE TABLE Orders (
        OrderID INT PRIMARY KEY IDENTITY(1,1),
        CustomerID INT FOREIGN KEY REFERENCES Customers(CustomerID),
        OrderDate DATE,
        TotalAmount DECIMAL(10,2),
        Status NVARCHAR(20)
    );
    PRINT 'Orders table created';
END
GO

-- Create Products table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Products')
BEGIN
    CREATE TABLE Products (
        ProductID INT PRIMARY KEY IDENTITY(1,1),
        ProductName NVARCHAR(100),
        Category NVARCHAR(50),
        Price DECIMAL(10,2),
        Stock INT
    );
    PRINT 'Products table created';
END
GO

-- Insert sample customers
IF NOT EXISTS (SELECT * FROM Customers)
BEGIN
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
    PRINT '10 customers inserted';
END
GO

-- Insert sample products
IF NOT EXISTS (SELECT * FROM Products)
BEGIN
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
    PRINT '10 products inserted';
END
GO

-- Insert sample orders
IF NOT EXISTS (SELECT * FROM Orders)
BEGIN
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
    PRINT '11 orders inserted';
END
GO

-- Verify data
SELECT 'Setup Complete!' AS Status;
SELECT 'Customers' AS TableName, COUNT(*) AS RecordCount FROM Customers
UNION ALL
SELECT 'Orders', COUNT(*) FROM Orders
UNION ALL
SELECT 'Products', COUNT(*) FROM Products;
GO
