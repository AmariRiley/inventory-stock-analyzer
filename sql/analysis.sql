-- Inventory Stockout Analysis
-- File: sql/analysis.sql
-- This file contains SQL queries for inventory management
-- QUERY 1: CRITICAL STOCKOUT ALERTS
-- Business Question: Which products are out of stock or critically low?
SELECT
    p.product_id,
    p.sku,
    p.product_name,
    p.category,
    i.quantity_on_hand,
    i.reserved_quantity,
    (i.quantity_on_hand - i.reserved_quantity) as available_qty,
    p.safety_stock,
    p.reorder_point,
    CASE
        WHEN i.quantity_on_hand = 0 THEN 'CRITICAL - OUT OF STOCK'
        WHEN i.quantity_on_hand < p.safety_stock THEN 'URGENT - Below Safety Stock'
        WHEN i.quantity_on_hand < p.safety_stock THEN 'WARNING - Below Reorder Point'
        ELSE 'OK'
    END as alert_level,
    s.supplier_name,
    p.lead_time_days
FROM
    products p
    JOIN inventory i ON p.product_id = i.product_id
    JOIN suppliers s ON p.supplier_id = s.supplier_id
WHERE
    i.quantity_on_hand < p.reorder_point
ORDER BY
    CASE
        WHEN i.quantity_on_hand = 0 THEN 1
        WHEN i.quantity_on_hand < p.safety_stock THEN 2
        ELSE 3
    END,
    i.quantity_on_hand;

-- QUERY 2: ABC INVENTORY CLASSIFICATION
-- Business Question: Which products represent the most inventory value?
WITH inventory_value AS(
    SELECT
        p.product_id,
        p.product_name,
        p.category,
        i.quantity_on_hand,
        p.unit_cost,
        (i.quantity_on_hand * p.unit_cost) as total_value
    FROM
        products p
        JOIN inventory i ON p.product_id = i.product_id
),
ranked AS (
    SELECT
        *,
        SUM(total_value) OVER () as grand_total SUM(total_value) OVER (
            ORDER BY
                total_value DESC ROWS BETWEEN UNBOUNDED PRECEDING
                AND CURRENT ROW
        ) as cumulative_value
    FROM
        inventory_value
)
SELECT
    product_id,
    product_name,
    category,
    quantity_on_hand,
    ROUND(total_value, 2) as inventory_value,
    ROUND(100.0 * cumulative_value / grand_total, 2) as cumulative_pct,
    CASE
        WHEN 100.0 * cumulative_value / grand_total <= 80 THEN 'A - High Value'
        WHEN 100.0 * cumulative_value / grand_total <= 95 THEN 'B - Medium Value'
        ELSE 'C - Low Value'
    END as abc_category
FROM
    ranked
ORDER BY
    total_value DESC;

-- QUERY 3: INVENTORY TURNOVER BY CATEGORY
-- Business Question: How quickly are we selling inventory in each category
WITH sales_summary AS (
    SELECT
        p.category,
        SUM(st.quantity_sold * p.unit_cost) as cogs,
        -- Cost of Goods Sold
        COUNT(DISTINCT st.transaction_date) as days_with_sales
    FROM
        sales_transactions st
        JOIN products p ON st.product_id = p.product_id
    GROUP BY
        p.category
),
inventory_summary AS (
    SELECT
        p.category,
        SUM(i.quantity_on_hand * p.unit_cost) as avg_inventory_value
    FROM
        inventory i
        JOIN products p ON i.product_id = p.product_id
    GROUP BY
        p.category
)
SELECT
    s.category,
    ROUND(s.cogs, 2) as total_cogs,
    ROUND(inv.avg_inventory_value, 2) as current_inventory_value,
    ROUND(s.cogs / NULLIF(inv.avg_inventory_value, 0), 2) as turnover_ratio,
    ROUND(
        365.0 / NULLIF((s.cogs / NULLIF(inv.avg_inventory_value, 0)), 0),
        0
    ) as days_inventory_outstanding
FROM
    sales_summary s
    JOIN inventory_summary inv ON s.category = inv.category
ORDER BY
    turnover_ratio DESC;

-- QUERY 4: RECOMMENDED REORDER QUANTITIES
-- Business Question: What should we order and how much?
WITH daily_sales AS (
    SELECT
        product_id,
        AVG(quantity_sold) as avg_daily_sales
    FROM
        sales_transactions
    WHERE
        transaction_date >= date('now', '-90 days')
    GROUP BY
        product_id
)
SELECT
    p.product_id,
    p.sku,
    p.product_name,
    p.category,
    i.quantity_on_hand,
    p.safety_stock,
    p.reorder_point,
    p.reorder_quantity as standard_reorder_qty,
    ROUND(COALESCE(ds.avg_daily_sales, 0), 1) as avg_daily_sales,
    p.lead_time_days,
    -- Calculated recommended order quantity
    CASE
        WHEN i.quantity_on_hand < p.safety_stock THEN p.reorder_quantity + (p.safety_stock - i.quantity_on_hand)
        ELSE p.reorder_quantityEND as recommded_order_qty,
        -- Priority score (lower is more urgent)
        ROUNd(
            CASE
                WHEN COALESCE(ds.avg_daily_sales, 0) = 0 THEN 999
                ELSE i.quantity_on_hand / NULLIF(ds.avg_daily_sales, 0)
            END,
            1
        ) as days_of_stock_remaining,
        s.supplier_name,
        s.reliability_score
        FROM
            products p
            JOIN inventory i ON p.product_id = i.product_id
            LEFT JOIN daily_sales ds ON p.product_id = ds.product_id
            JOIN suppliers s ON p.supplier_id = s.supplier_id
        WHERE
            i.quantity_on_hand < p.reorder_point
        ORDER BY
            days_of_stock_remaining ASC;

-- QUERY 5: SLOW-MOVING INVENTORY
-- Business Question: Which products aren't selling and tying up capital?
WITH recent_sales AS (
    SELECT
        product_id,
        SUM(quantity_sold) as total_sold,
        MAX(transaction_date) as last_sale_date,
        COUNT(*) as num_transactions
    FROM
        sales_transactions
    WHERE
        transaction_date >= date ('now', '-90 days')
    GROUP BY
        product_id
)
SELECT
    p.product_id,
    p.product_name,
    p.category,
    i.quantity_on_hand,
    p.unit_cost,
    ROUND(i.quantity_on_hand * p.unit_cost, 2) as tied_up_capital,
    COALESCE(rs.total_sold, 0) as sold_last_90_days,
    COALESCE(rs.last_sale_date, 'No recent sales') as last_sale_date,
    ROUND(
        julianday('now') - julianday(COALESCE(rs.last_sale_date, '2020-01-01')),
        0
    ) as days_since_last_sale,
    i.warehouse_location
FROM
    products p
    JOIN inventory i ON p.product_id = i.product_id
    LEFT JOIN recent_sales rs ON p.product_id = rs.product_id
WHERE
    COALESCE(rs.total_sold, 0) < 5 -- Less than 5 units sold in 90 days
    AND i.quantity_on_hand > 0
ORDER BY
    tied_up_capital DESC
LIMIT
    20;

-- QUERY 6: SUPPLIER PERFORMANCE SUMMARY
-- Business Question: Which suppliers are most reliable for critical reorders?
SELECT
    s.supplier_id,
    s.supplier_name,
    s.country,
    s.reliability_score,
    COUNT(DISTINCT po.po_id) as total_orders,
    ROUND(AVG(po.unit_cost * po.quantity_ordered), 2) as avg_order_value,
    -- On-time delivery rate
    ROUND(
        100.0 * SUM(
            CASE
                WHEN po.actual_delivery_date <= po.expected_delivery_date THEN 1
                ELSE 0
            END
        ) / COUNT(*),
        2
    ) as on_time_delivery_pct,
    -- Average delay
    ROUND(
        AVG(
            julianday(po.actual_delivery_date) - julianday(po.expected_delivery_date)
        ),
        1
    ) as avg_delay_days,
    -- Number of products they supply
    COUNT(DISTINCT p.product_id) as products_supplied,
    -- How many of their products need reordering now
    SUM(
        CASE
            WHEN i.quantity_on_hand < p.reorder_point THEN 1
            ELSE 0
        END
    ) as products_needing_reorder
FROM
    suppliers s
    LEFT JOIN purchase_orders po ON s.supplier_id = po.supplier_id
    LEFT JOIN products p ON s.supplier_id = p.supplier_id
    LEFT JOIN inventory i ON p.product_id = i.product_id
GROUP BY
    s.supplier_id,
    s.supplier_name,
    s.country,
    s.reliability_score
ORDER BY
    on_time_delivery_pct DESC;

-- QUERY 7: INVENTORY VALUE BY LOCATION
-- Business Question: How much capital is tied up in each warehouse?
SELECT
    i.warehouse_location,
    COUNT(DISTINCT i.product_id) as num_products,
    SUM(i.quantity_on_hand) as total_units,
    ROUND(SUM(i.quantity_on_hand * p.unit_cost), 2) as total_inventory_value,
    ROUND(AVG(i.quantity_on_hand * p.unit_cost), 2) as avg_value_per_product,
    -- Count alerts by location
    SUM(
        CASE
            WHEN i.quantity_on_hand < p.safety_stock THEN 1
            ELSE 0
        END
    ) as products_below_safety,
    SUM(
        CASE
            WHEN i.quantity_on_hand = 0 THEN 1
            ELSE 0
        END
    ) as out_of_stock_products
FROM
    inventory inJOIN products p ON i.product_id = p.product_id
GROUP BY
    i.warehouse_location
ORDER BY
    total_inventory_value DESC;

-- QUERY 8: TOP SELLING PRODUCTS (REVENUE)
-- Business Question: Which products generate the most revenue?
SELECT
    p.product_id,
    p.product_name,
    p.category,
    COUNT(st.transaction_id) as num_transactions,
    SUM(st.quantity_sold) as total_units_sold,
    ROUND(SUM(st.sale_amount), 2) as total_revenue,
    ROUND(AVG(st.sale_amount / st.quantity_sold), 2) as avg_sale_price,
    i.quantity_on_hand as current_stock,
    CASE
        WHEN i.quantity_on_hand < p.reorder_point THEN 'Needs Reorder'
        ELSE 'Stock OK'
    END as stock_status
FROM
    sales_transactions st
    JOIN products p ON st.product_id = p.product_id
    JOIN inventory i ON p.product_id = i.product_id
GROUP BY
    p.product_id,
    p.product_name,
    p.category,
    i.quantity_on_hand,
    p.reorder_point
ORDER BY
    total_revenue DESC
LIMIT
    15;