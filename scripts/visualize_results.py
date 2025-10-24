"""
Create visualizations from SQL analysis results
File: scripts/visualize_results.py
Run: python scripts/visualize_results.py
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)

print("Generating visualizations...\n")

# Connect to database
conn = sqlite3.connect('inventory.db')

# ============================================
# 1. STOCKOUT ALERTS DASHBOARD
# ============================================

print("Creating stockout alerts visualization...")

query = """
SELECT
    CASE
        WHEN i.quantity_on_hand = 0 THEN 'CRITICAL - Out of Stock'
        WHEN i.quantity_on_hand < p.safety_stock THEN 'URGENT - Below Safety'
        WHEN i.quantity_on_hand < p.reorder_point THEN 'WARNING - Below Reorder'
        ELSE 'OK'
    END as alert_level,
    COUNT(*) as product_count
FROM products p 
JOIN inventory i ON p.product_id = i.product_id
GROUP BY alert_level
ORDER BY
    CASE alert_level
        WHEN 'CRITICAL - Out of Stock' THEN 1
        WHEN 'URGENT - Below Safety' THEN 2
        WHEN 'WARNING - Below Reorder' THEN 3
        ELSE 4
    END
"""

df_alerts = pd.read_sql(query, conn)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Bar Chart
colors = ['#d62728', '#ff7f0e', '#ffff00', '#2ca02c']
axes[0].barh(df_alerts['alert_level'], df_alerts['product_count'], color=colors[:len(df_alerts)])
axes[0].set_xlabel('Number of Products')
axes[0].set_title('Inventory Alert Status Summary', fontweight='bold', fontsize=14)
axes[0].grid(axis = 'x', alpha = 0.3)

# Add value in labels
for i, v in enumerate(df_alerts['product_count']):
    axes[0].text(v + 0.5, i, str(v), va='center', fontweight='bold')

# Pie Chart
axes[1].pie(df_alerts['product_count'], labels=df_alerts['alert_level'],
            autopct='%1.1f%%', colors=colors[:len(df_alerts)], startangle=90)
axes[1].set_title('Distribution of Inventory Alerts', fontweight='bold', fontsize=14)

plt.tight_layout()
plt.savefig('results/01_stockout_alerts.png', dpi=300, bbox_inches='tight')
print(" Saved: results/01_stockout_alerts.png")

# ============================================
# 2. ABC ANALYSIS
# ============================================

print("Creating ABC analysis visualization...")

query = """
WITH inventory_value AS (
    SELECT
        p.product_id,
        p.product_name,
        p.category,
        (i.quantity_on_hand * p.unit_cost) as total_value
    FROM products p
    JOIN inventory i ON p.product_id = i.product_id
),
ranked AS (
    SELECT
        *,
        SUM(total_value) OVER () as grand_total,
        SUM(total_value) OVER (ORDER BY total_value DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as cumulative_value
        FROM inventory_value
)
SELECT
    product_id,
    product_name,
    category,
    ROUND(total_value, 2) as inventory_value,
    ROUND(100.0 * cumulative_value / grand_total, 2) as cumulative_pct,
    CASE
        WHEN 100.0 * cumulative_value / grand_total <= 80 THEN 'A'
        WHEN 100.0 * cumulative_value / grand_total <= 95 THEN 'B'
        ELSE 'C'
    END as abc_category
FROM ranked
ORDER BY total_value DESC
"""

df_abc = pd.read_sql(query, conn)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Pareto chart - Top 30 products
top_30 = df_abc.head(30)
x_pos = range(len(top_30))

ax1 = axes[0]
ax2 = ax1.twinx()

# Bar chart for inventory value
colors = ['red' if cat == 'A' else 'gold' if cat == 'B' else 'green'
          for cat in top_30['abc_category']]
ax1.bar(x_pos, top_30['inventory_value'], color=colors, alpha=0.7)
ax1.set_xlabel('Products (ranked by value)')
ax1.set_ylabel('Inventory Value ($)', color='black')
ax1.tick_params(axis='y', labelcolor='black')

# Line chart for cumulative percentage
ax2.plot(x_pos, top_30['cumulative_pct'], color='darkblue',
         marker='o', linewidth=2, markersize=4)
ax2.set_ylabel('Cumulative %', color='darkblue')
ax2.tick_params(axis='y', labelcolor='darkblue')
ax2.axhline(y=80, color='red', linestyle='--', alpha=0.5, label='80% threshold')
ax2.legend(loc='lower right')

ax1.set_title('ABC Inventory Analysis = Pareto Chart', fontweight='bold', fontsize=14)
ax1.set_xticks([])

# ABC category distribution
abc_summary = df_abc.groupby('abc_category').agg({
    'product_id': 'count',
    'inventory_value': 'sum'
}).reset_index()
abc_summary.columns = ['Category', 'Product Count', 'Total Value']

x = range(len(abc_summary))
width = 0.35

axes[1].bar([i - width/2 for i in x], abc_summary['Product Count'],
            width, label='Product Count', color='skyblue')
axes[1].bar([i + width/2 for i in x], abc_summary['Total Value']/100,
            width, label='Total Value ($100s)', color='navy')

axes[1].set_xlabel('ABC Category')
axes[1].set_ylabel('Count / Value')
axes[1].set_title('ABC Classification Summary', fontweight='bold', fontsize=14)
axes[1].set_xticks(x)
axes[1].set_xticklabels(abc_summary['Category'])
axes[1].legend()
axes[1].grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('results/02_abc_analysis.png', dpi=300, bbox_inches='tight')
print(" Saved: results/02_abc_analysis.png")

# ============================================
# 3. INVENTORY TURNOVER BY CATEGORY
# ============================================

query = """
WITH sales_summary AS (
    SELECT
        p.category,
        SUM(st.quantity_sold * p.unit_cost) as cogs
    FROM sales_transactions st
    JOIN products p ON st.product_id = p.product_id
    GROUP BY p.category 
),
inventory_summary AS (
    SELECT
        p.category,
        SUM(i.quantity_on_hand * p.unit_cost) as avg_inventory_value
    FROM inventory i
    JOIN products p ON i.product_id = p.product_id
    GROUP BY p.category
)
SELECT
    s.category,
    ROUND(s.cogs / NULLIF(inv.avg_inventory_value, 0), 2) as turnover_ratio,
    ROUND(365.0 / NULLIF((s.cogs / NULLIF(inv.avg_inventory_value, 0)), 0), 0) as days_inventory
FROM sales_summary s
JOIN inventory_summary inv ON s.category = inv.category
ORDER BY turnover_ratio DESC
"""

df_turnover = pd.read_sql(query, conn)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Turnover ratio
axes[0].barh(df_turnover['category'], df_turnover['turnover_ratio'], color='teal')
axes[0].set_xlabel('Turnover Ratio (higher is better)')
axes[0].set_title('Inventory Turnover by Category', fontweight='bold', fontsize=14)
axes[0].axvline(x=4, color='red', linestyle='--', alpha=0.5, label='Target: 4x')
axes[0].legend()
axes[0].grid(axis='x', alpha=0.3)

# Add value labels
for i, v in enumerate(df_turnover['turnover_ratio']):
    axes[0].text(v + 0.1, i, f'{v:2f}x', va='center', fontweight='bold')

# Days of inventory
axes[1].barh(df_turnover['category'], df_turnover['days_inventory'], color='coral')
axes[1].set_xlabel('Days of Inventory Outstanding (lower is better)')
axes[1].set_title('Average Days to Sell Inventory', fontweight='bold', fontsize=14)
axes[1].grid(axis='x', alpha=0.3)

# Add value labels
for i, v in enumerate(df_turnover['days_inventory']):
    axes[1].text(v + 5, i, f'{int(v)}d', va='center', fontweight='bold')

plt.tight_layout()
plt.savefig('results/03_inventory_turnover.png', dpi=300, bbox_inches='tight')
print(" Saved: results/03_inventory_turnover.png")

# ============================================
# 4 REORDER PRIORITY HEATMAP
# ============================================
print("Creating reorder priority visualization...")

query = """
WITH daily_sales AS (
    SELECT
        product_id,
        AVG(quantity_sold) as avg_daily_sales
    FROM sales_transactions
    WHERE transaction_date >= date('now', '-90 days')
    GROUP BY product_id
)
SELECT
    p.category,
    COUNT(*) as products_needing_reorder,
    SUM(p.reorder_quantity * p.unit_cost) as total_reorder_cost,
    ROUND(AVG(CASE
        WHEN COALESCE(ds.avg_daily_sales, 0) = 0 THEN 30
        ELSE i.quantity_on_hand / NULLIF(ds.avg_daily_sales, 0)
    END), 1) as avg_days_remaining
FROM products p
JOIN inventory i ON p.product_id = i.product_id
LEFT JOIN daily_sales ds ON p.product_id = ds.product_id
WHERE i.quantity_on_hand < p.reorder_point
GROUP BY p.category
ORDER BY products_needing_reorder DESC
"""

df_reorder = pd.read_sql(query, conn)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Products needing reorder by category
axes[0].barh(df_reorder['category'], df_reorder['products_needing_reorder'],
             color='crimson')
axes[0].set_xlabel('Number of Products')
axes[0].set_title('Products Needing Reorder by Category', fontweight='bold', fontsize=14)
axes[0].grid(axis='x', alpha=0.3)

for i, v in enumerate(df_reorder['products_needing_reorder']):
    axes[0].text(v + 0.3, i, str(int(v)), va='center', fontweight='bold')

# Total reorder cost
axes[1].barh(df_reorder['category'], df_reorder['total_reorder_cost'],
             color='darkgreen')
axes[1].set_xlabel('Estimated Reorder Cost ($)')
axes[1].set_title('Capital Required for Reorders', fontweight='bold', fontsize=14)
axes[1].grid(axis='x', alpha=0.3)

for i, v in enumerate(df_reorder['total_reorder_cost']):
    axes[1].text(v + 100, i, f'${v:,.0f}', va='center', fontweight='bold')

plt.tight_layout()
plt.savefig('results/04_reorder_priorities.png', dpi=300, bbox_inches='tight')
print(" Saved: results/04_reorder_priorities.png")

# ============================================
# 5. SUPPLIER PERFORMANCE
# ============================================
print("Creating supplier performance visualization...")

query = """
SELECT
    s.supplier_name,
    ROUND(
        100.0 * SUM(CASE
            WHEN po.actual_delivery_date <= po.expected_delivery_date THEN 1
            ELSE 0
        END) / COUNT(*),
    2) as on_time_pct,
    COUNT(*) as total_orders,
    s.reliability_score
FROM suppliers s
LEFT JOIN purchase_orders po ON s.supplier_id = po.supplier_id
GROUP BY s.supplier_id, s.supplier_name, s.reliability_score
HAVING COUNT(*) >= 3
ORDER BY on_time_pct DESC
LIMIT 15
"""

df_suppliers = pd.read_sql(query, conn)

fig, ax = plt.subplots(figsize=(12, 6))

# Color code by performance
colors = ['green' if x >= 85 else 'orange' if x >= 70 else 'red'
           for x in df_suppliers['on_time_pct']]

bars = ax.barh(df_suppliers['supplier_name'], df_suppliers['on_time_pct'], color=colors)
ax.set_xlabel('On-Time Delivery %')
ax.set_title('Supplier On-Time Delivery Performance', fontweight='bold', fontsize=14)
ax.axvline(x=85, color='darkgreen', linestyle='--', alpha=0.5, label='Target: 85%')
ax.legend()
ax.grid(axis='x', alpha=0.3)

# Add value labels
for i, (pct, orders) in enumerate(zip(df_suppliers['on_time_pct'], df_suppliers['total_orders'])):
    ax.text(pct + 1, i, f'{pct:.1f}% ({int(orders)})', va='center', fontsize=9)

plt.tight_layout()
plt.savefig('results/05_supplier_performance.png', dpi=300, bbox_inches='tight')
print(" Saved: results/05_supplier_performance.png")

# ============================================
# SUMMARY STATISTICS
# ============================================
print("\n" + "="*60)
print("ANALYSIS SUMMARY")
print("="*60)

# Overall inventory health
query = "SELECT COUNT(*) as total_products FROM products"
total_products = pd.read_sql(query, conn).iloc[0]['total_products']

query = "SELECT SUM(quantity_on_hand * unit_cost) as total_value FROM inventory i JOIN products p ON i.product_id = p.product_id"
total_value = pd.read_sql(query, conn).iloc[0]['total_value']

query = "SELECT COUNT(*) FROM inventory i JOIN products p ON i.product_id = p.product_id WHERE i.quantity_on_hand = 0"
out_of_stock = pd.read_sql(query, conn).iloc[0, 0]

query = "SELECT COUNT (*) FROM inventory i JOIN products p ON i.product_id = p.product_id WHERE i.quantity_on_hand < p.reorder_point"
needs_reorder = pd.read_sql(query, conn).iloc[0, 0]

query = "SELECT SUM(p.reorder_quantity * p.unit_cost) FROM products p JOIN inventory i ON p.product_id = i.product_id WHERE i.quantity_on_hand < p.reorder_point"
reorder_cost = pd.read_sql(query, conn).iloc[0, 0] or 0

print(f"\nInventory Overview:")
print(f" Total Products: {total_products}")
print(f" Total Inventory Value: ${total_value:,.2f}")
print(f" Out of Stock: {out_of_stock} products ({100 * out_of_stock / total_products:.1f}%)")
print(f" Needs Reorder: {needs_reorder} products ({100 * needs_reorder / total_products:.1f}%)")
print(f" Estimated Reorder Cost: ${reorder_cost:,.2f}")

# Slow-moving inventory
query = """
SELECT SUM(i.quantity_on_hand * p.unit_cost) as tied_up
FROM products p
JOIN inventory i ON p.product_id = i.product_id
LEFT JOIN (
    SELECT product_id, SUM(quantity_sold) as total_sold
    FROM sales_transactions
    WHERE transaction_date >= date('now', '-90 days')
    GROUP BY product_id
) rs ON p.product_id = rs.product_id
WHERE COALESCE(rs.total_sold, 0) < 5 AND i.quantity_on_hand > 0
"""

slow_value = pd.read_sql(query, conn).iloc[0, 0] or 0

print(f" \nSlow-Moving Inventory:")
print(f" Capital Tied Up: ${slow_value:,.2f}")
print(f" Potential Savings: ${slow_value * 0.7:,.2f} (if liquidated at 70% value)")

# Top category
query = """
SELECT category, SUM(quantity_on_hand * unit_cost) as value
FROM inventory i JOIN products p ON i.product_id = p.product_id
GROUP BY category ORDER BY value DESC LIMIT 1
"""

top_cat = pd.read_sql(query, conn).iloc[0]

print(f"\nTop Category by Value:")
print(f" {top_cat['category']}: ${top_cat['value']:,.2f}")

conn.close()

print("\n" + "="*60)
print(" All visualizations saved to 'results/' folder")
print("="*60)
print("\nNext step: Review the images and update your README.md with insights!")