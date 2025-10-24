"""
Generate sample inventory data
File: scripts/generate_data.py
"""

import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import random

fake = Faker()
Faker.seed(42)
np.random.seed(42)

print("Generating sample data...\n")

# ============================================
# 1. Products Data
# ============================================

print("Creating products...")

categories = ['Electronics', 'Clothing', 'Food', 'Home & Garden', 'Sports', 'Automotive']
products = []

for i in range(150):
    category = random.choice(categories)
    safety_stock = random.randint(10, 50)
    reorder_point = random.randint(safety_stock + 10, 100)
    products.append({
        'product_id': i + 1,
        'sku': f'SKU-{fake.unique.random_number(digits=6)}',
        'product_name': f'{category} {fake.word().title()} {fake.word().title()}',
        'category': category,
        'unit_cost': round(random.uniform(5, 200), 2),
        'unit_price': round(random.uniform(10, 400), 2),
        'reorder_point': reorder_point,
        'reorder_quantity': random.randint(50, 200),
        'safety_stock': safety_stock,
        'supplier_id': random.randint(1, 20),
        'lead_time_days': random.randint(7, 30)
    })

df_products = pd.DataFrame(products)
df_products.to_csv('data/products.csv', index=False)
print(f"Created {len(products)} products")

# ============================================
#2. Suppliers Data
# ============================================

print("Creating suppliers...")

suppliers = []
countries = ['USA', 'China', 'Germany', 'Japan', 'Mexico', 'Vietnam']

for i in range(20):
    suppliers.append({
        'supplier_id': i + 1,
        'supplier_name': fake.company(),
        'country': random.choice(countries),
        'reliability_score': round(random.uniform(3.0, 5.0), 1),
        'avg_lead_time': random.randint(7, 30)
    })

df_suppliers = pd.DataFrame(suppliers)
df_suppliers.to_csv('data/suppliers.csv', index=False)
print(f"Created {len(suppliers)} suppliers")

# ============================================
#3. Current Inventory Data
# ============================================

print("Creating inventory levels...")

inventory = []
for product_id in range(1, 151):
    product = df_products[df_products['product_id'] == product_id].iloc[0]

    #Create realistic scenarios
    scenario = random.random()

    if scenario < 0.15: #15% critical - out of stock or very low
        qty = random.randint(0, 5)
    elif scenario < 0.30: #15% below safety stock
        qty = random.randint(1, int(product['safety_stock']))
    elif scenario < 0.50: # 20% below reorder point
        qty = random.randint(int(product['safety_stock']), int(product['reorder_point']))
    else: # 50% healthy stock levels
        qty = random.randint(int(product['reorder_point']), int(product['reorder_point']) * 3)

        inventory.append({
            'product_id': product_id,
            'quantity_on_hand': qty,
            'warehouse_location': random.choice(['Warehouse A', 'Warehouse B', 'Warehouse C']),
            'last_counted': (datetime.now() - timedelta(days = random.randint(0, 30))).strftime('%Y-%m-%d'),
            'reserved_quantity': random.randint(0, min(10, qty)) # Orders not yet shipped
        })

    df_inventory = pd.DataFrame(inventory)
    df_inventory.to_csv('data/inventory.csv', index=False)
    print(f" Created {len(inventory)} inventory records")

# ============================================
#4. Sales transactions from the last 6 months
# ============================================

print("Creating sales transactions...")

transactions = []
start_date = datetime.now() - timedelta(days=180)

for i in range(800):
    product_id = random.randint(1, 150)
    product = df_products[df_products['product_id'] == product_id].iloc[0]

    sale_date = start_date + timedelta(days=random.randint(0, 180))
    quantity = random.randint(1, 20)

    transactions.append({
        'transaction_id': i + 1,
        'product_id': product_id,
        'transaction_date': sale_date.strftime('%Y-%m-%d'),
        'quantity_sold': quantity,
        'sale_amount': round(quantity * product['unit_price'], 2),
        'customer_type': random.choice(['Retail', 'Wholesale', 'Online'])
    })

df_transactions = pd.DataFrame(transactions)
df_transactions.to_csv('data/sales_transactions.csv', index=False)
print(f" Created {len(transactions)} sales transactions")

# ============================================
#5. Purchase Orders (Replenishment History)
# ============================================

print("Creating purchase orders...")

purchase_orders = []

for i in range(100):
    product_id = random.randint(1, 150)
    product = df_products[df_products['product_id'] == product_id].iloc[0]

    order_date = (datetime.now() - timedelta(days = random.randint(0, 180))).strftime('%Y-%m-%d')
    expected_delivery = (datetime.strptime(order_date, '%Y-%m-%d') + timedelta(days = int(product['lead_time_days']))).strftime('%Y-%m-%d')

    # 85% on-time, 15% delayed
    if random.random() < 0.85:
        actual_delivery = expected_delivery
    else:
        actual_delivery = (datetime.strptime(expected_delivery, '%Y-%m-%d') + timedelta(days = random.randint(1, 10))).strftime('%Y-%m-%d')
    
    purchase_orders.append({
        'po_id': i + 1,
        'product_id': product_id,
        'supplier_id': int(product['supplier_id']),
        'order_date': order_date,
        'expected_delivery_date': expected_delivery,
        'actual_delivery_date': actual_delivery,
        'quantity_ordered': int(product['reorder_quantity']),
        'unit_cost': product['unit_cost'],
        'status': 'Delivered'
    })

df_pos = pd.DataFrame(purchase_orders)
df_pos.to_csv('data/purchase_orders.csv', index=False)
print(f" Created {len(purchase_orders)} purchase orders")

# Summary
print("\n" + "="*50)
print("DATA GENERATION COMPLETE")
print("="*50)

print("\nDataset Statistics:")
print(f"Products: {len(products)}")
print(f"Suppliers: {len(suppliers)}")
print(f"Inventory Records: {len(inventory)}")
print(f"Sales Transactions: {len(transactions)}")
print(f"Purchase Orders: {len(purchase_orders)}")

# Quick Insights
critical_stock = df_inventory[df_inventory['quantity_on_hand'] == 0]
#low_stock = df_inventory[df_inventory['quantity_on_hand'] < df_products['safety_stock'].values]

print(f"\nInventory Alerts:")
print(f"Out of Stock: {len(critical_stock)} products")
#print(f"Below Safety Stock: {len(low_stock)} products")

print("\n All CSV files saved to 'data/' folder")
print("\nNext step: Run scripts/create_database.py")