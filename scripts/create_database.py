"""
Create SQLite database and load CSV data
File: scripts/create_database.py
Run: python scripts/create_database.py
"""

import sqlite3
import pandas as pd

print("Creating SQLite database...\n")

# Connect to database (creates file if it doesn't exist)
conn = sqlite3.connect('inventory.db')
cursor = conn.cursor()

print("Creating tables...")

# CREATE TABLES

# Products table
cursor.execute('''
               CREATE TABLE IF NOT EXISTS products(
               product_id INTEGER PRIMARY KEY, 
               sku TEXT UNIQUE NOT NULL,
               product_name TEXT NOT NULL, 
               category TEXT,
               unit_cost REAL,
               unit_price REAL,
               reorder_point INTEGER,
               reorder_quantity INTEGER,
               safety_stock INTEGER,
               supplier_id INTEGER,
               lead_time_days INTEGER,
               FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
               )''')

# Suppliers table
cursor.execute('''
               CREATE TABLE IF NOT EXISTS products(
               supplier_id INTEGER PRIMARY KEY,
               supplier_name TEXT NOT NULL,
               country TEXT,
               reliability_score REAL,
               avg_lead_time INTEGER
               )''')

# Inventory table
cursor.execute('''
               CREATE TABLE IF NOT EXISTS inventory(
               product_id INTEGER PRIMARY KEY,
               quantity_on_hand INTEGER NOT NULL,
               warehouse_location TEXT,
               last_counted DATE,
               reserved_quantity INTEGER,
               FOREIGN KEY (product_id) REFERENCES products(product_id)
               )''')

# Sales transactions table
cursor.execute('''
               CREATE TABLE IF NOT EXISTS sales_transactions(
               transaction_id INTEGER PRIMARY KEY,
               product_id INTEGER,
               transaction_date DATE,
               quantity_sold INTEGER,
               sale_amount REAL,
               customer_type TEXT,
               FOREIGN KEY (product_id) REFERENCES products(product_id)
               )''')

# Purchase orders table
cursor.execute('''
               CREATE TABLE IF NOT EXISTS purchase_orders(
               po_id INTEGER PRIMARY KEY,
               product_id INTEGER,
               supplier_id INTEGER,
               order_date DATE,
               expected_delivery_date DATE,
               acutal_delivery_date DATE,
               quantity_ordered INTEGER,
               unit_cost REAL,
               status TEXT,
               FOREIGN KEY (product_id) REFERENCES products(product_id),
               FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
               )''')

conn.commit()
print(" Tables created")