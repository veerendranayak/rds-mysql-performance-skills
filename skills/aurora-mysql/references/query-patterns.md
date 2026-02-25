# Common Query Patterns and Anti-Patterns

## Query Performance Red Flags

### 1. Aggregation Over Join (CRITICAL - Wrong Results)

This produces **silently incorrect data**. Most dangerous anti-pattern.

**Bad**:
```sql
-- Problem: Cartesian product inflates aggregations
SELECT
  c.name AS category,
  SUM(oi.quantity * oi.unit_price) AS revenue,
  AVG(r.rating) AS avg_rating,
  COUNT(DISTINCT r.id) AS review_count
FROM categories c
JOIN products p ON p.category_id = c.id
JOIN order_items oi ON oi.product_id = p.id  -- N rows
LEFT JOIN reviews r ON r.product_id = p.id   -- M rows
GROUP BY c.id, c.name;

/*
Problem:
- Product with 5 order_items and 3 reviews = 15 JOIN rows
- Revenue multiplied by 3 (wrong!)
- avg_rating calculation skewed
- No error, no warning - just wrong numbers
*/
```

**EXPLAIN Signs**:
```
rows: 45000  (Expected: 15000 order_items × 3 review_rows)
Extra: Using temporary
```

**Good**:
```sql
-- Aggregate each relationship independently
WITH category_revenue AS (
  SELECT
    p.category_id,
    SUM(oi.quantity * oi.unit_price) AS revenue
  FROM products p
  JOIN order_items oi ON oi.product_id = p.id
  GROUP BY p.category_id
),
category_ratings AS (
  SELECT
    p.category_id,
    AVG(r.rating) AS avg_rating,
    COUNT(*) AS review_count
  FROM products p
  JOIN reviews r ON r.product_id = p.id
  GROUP BY p.category_id
)
SELECT
  c.name,
  COALESCE(cr.revenue, 0) AS revenue,
  COALESCE(crt.avg_rating, 0) AS avg_rating,
  COALESCE(crt.review_count, 0) AS review_count
FROM categories c
LEFT JOIN category_revenue cr ON cr.category_id = c.id
LEFT JOIN category_ratings crt ON crt.category_id = c.id;

-- Correct numbers, each metric independent
```

**How to Detect**:
- Multiple `LEFT JOIN` in same query with aggregations
- `SUM`/`AVG`/`COUNT` over joined tables
- Results that seem too large
- `COUNT(*)` returns more rows than expected

### 2. Functions on Indexed Columns

Functions prevent index usage, forcing full table scans.

**Bad**:
```sql
-- Full table scan even with index on created_at
SELECT * FROM orders
WHERE YEAR(created_at) = 2024;

EXPLAIN:
type: ALL
rows: 5000000
Extra: Using where
```

**Good - Option 1: Range Condition**:
```sql
SELECT * FROM orders
WHERE created_at >= '2024-01-01'
  AND created_at < '2025-01-01';

EXPLAIN:
type: range
key: idx_created_at
rows: 180000
```

**Good - Option 2: Functional Index (MySQL 8.0.13+)**:
```sql
CREATE INDEX idx_orders_year ON orders((YEAR(created_at)));

SELECT * FROM orders
WHERE YEAR(created_at) = 2024;

EXPLAIN:
type: ref
key: idx_orders_year
rows: 180000
```

**More Examples**:
```sql
-- ❌ Bad: Function on indexed column
WHERE DATE(created_at) = '2024-01-15'
WHERE LOWER(email) = 'user@example.com'
WHERE CONCAT(first_name, ' ', last_name) = 'John Doe'

-- ✅ Good: Sargable (Search ARGument ABLE)
WHERE created_at >= '2024-01-15' AND created_at < '2024-01-16'
WHERE email = 'user@example.com'  -- Store lowercase, or use functional index
WHERE first_name = 'John' AND last_name = 'Doe'
```

### 3. Implicit Type Conversion

Comparing different types prevents index usage.

**Bad**:
```sql
-- customer_id is INT, but query uses STRING
SELECT * FROM orders WHERE customer_id = '12345';

EXPLAIN:
type: ALL  -- Full scan! Even with index on customer_id
Extra: Using where

-- MySQL converts every customer_id to string for comparison
```

**Good**:
```sql
-- Use correct type
SELECT * FROM orders WHERE customer_id = 12345;

EXPLAIN:
type: ref
key: idx_customer_id
rows: 25
```

**Detection**:
```sql
-- Look for type mismatches in slow query log
-- Query with '123' but column is INT
-- Query with 123 but column is VARCHAR
```

### 4. LIKE with Leading Wildcard

`LIKE '%term%'` or `LIKE '%term'` cannot use regular B-tree indexes.

**Bad**:
```sql
SELECT * FROM products WHERE name LIKE '%camera%';

EXPLAIN:
type: ALL
rows: 1000000
Extra: Using where
```

**Good - FULLTEXT Index**:
```sql
-- Add FULLTEXT index
ALTER TABLE products
ADD FULLTEXT INDEX ft_name(name);

-- Use MATCH AGAINST
SELECT * FROM products
WHERE MATCH(name) AGAINST('camera' IN NATURAL LANGUAGE MODE);

EXPLAIN:
type: fulltext
key: ft_name
rows: 150
```

**Good - Prefix Search**:
```sql
-- If searching from start of string
SELECT * FROM products WHERE name LIKE 'camera%';

EXPLAIN:
type: range
key: idx_name
rows: 150
```

### 5. OR Across Different Columns

OR conditions on different columns often prevent index usage.

**Bad**:
```sql
SELECT * FROM orders
WHERE customer_id = 123 OR status = 'pending';

EXPLAIN:
type: ALL  -- Can't efficiently use either index
rows: 5000000
```

**Good - UNION ALL**:
```sql
(SELECT * FROM orders WHERE customer_id = 123)
UNION ALL
(SELECT * FROM orders WHERE status = 'pending' AND customer_id != 123);

-- Each query uses its index
-- UNION ALL avoids deduplication cost
```

**When OR is OK**:
```sql
-- OR on same column is fine
SELECT * FROM orders
WHERE status = 'pending' OR status = 'processing';

-- Better yet: Use IN
SELECT * FROM orders
WHERE status IN ('pending', 'processing');
```

### 6. N+1 Query Problem

Executing one query then N additional queries in a loop.

**Bad**:
```python
# 1 query + N queries
customers = db.query("SELECT * FROM customers LIMIT 100")
for customer in customers:
    orders = db.query("SELECT * FROM orders WHERE customer_id = ?", customer.id)
    # Process orders

# Total: 101 queries
```

**Good - JOIN**:
```sql
SELECT c.*, o.*
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
WHERE c.id <= 100;

-- 1 query
```

**Good - Batch Fetch**:
```python
# 2 queries total
customers = db.query("SELECT * FROM customers LIMIT 100")
customer_ids = [c.id for c in customers]

orders = db.query("SELECT * FROM orders WHERE customer_id IN (%s)", customer_ids)

# Group orders by customer_id in application
orders_by_customer = {}
for order in orders:
    orders_by_customer.setdefault(order.customer_id, []).append(order)

# Total: 2 queries
```

### 7. SELECT * Instead of Specific Columns

**Bad**:
```sql
-- Fetches all columns including large TEXT/JSON fields
SELECT * FROM products WHERE category_id = 5;

-- Problems:
-- - More data transferred over network
-- - Cannot use covering indexes
-- - May fetch unused BLOB/TEXT columns
```

**Good**:
```sql
-- Fetch only needed columns
SELECT id, name, price, stock
FROM products
WHERE category_id = 5;

-- Benefits:
-- - Less network I/O
-- - Can use covering index
-- - Faster query execution
```

**Covering Index Example**:
```sql
CREATE INDEX idx_category_covering
ON products(category_id, id, name, price, stock);

SELECT id, name, price, stock
FROM products
WHERE category_id = 5;

EXPLAIN:
Extra: Using index  -- All data from index, no table access
```

### 8. Correlated Subqueries

Subquery executes once per outer row (slow).

**Bad**:
```sql
-- Subquery executes 100,000 times
SELECT
  u.id,
  u.name,
  (SELECT COUNT(*) FROM orders o WHERE o.customer_id = u.id) AS order_count
FROM users u;

EXPLAIN:
Extra: DEPENDENT SUBQUERY  -- Red flag
```

**Good - JOIN**:
```sql
SELECT
  u.id,
  u.name,
  COUNT(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON o.customer_id = u.id
GROUP BY u.id, u.name;

-- Subquery executes once
```

**When Subquery is OK**:
```sql
-- Non-correlated subquery (executes once)
SELECT * FROM orders
WHERE customer_id IN (
  SELECT id FROM customers WHERE country = 'US'
);

-- Or with EXISTS (stops on first match)
SELECT * FROM customers c
WHERE EXISTS (
  SELECT 1 FROM orders o WHERE o.customer_id = c.id
);
```

### 9. Large OFFSET in Pagination

OFFSET reads and discards rows. Performance degrades linearly.

**Bad**:
```sql
-- Page 1000: Reads and discards 50,000 rows to return 50
SELECT * FROM orders
ORDER BY id
LIMIT 50 OFFSET 50000;

-- Execution time increases with offset:
-- Page 1: 10ms
-- Page 100: 500ms
-- Page 1000: 5000ms
```

**Good - Keyset Pagination**:
```sql
-- Page 1
SELECT * FROM orders
ORDER BY id
LIMIT 50;
-- Note last id = 2550

-- Page 2
SELECT * FROM orders
WHERE id > 2550
ORDER BY id
LIMIT 50;
-- Note last id = 2600

-- Page 3
SELECT * FROM orders
WHERE id > 2600
ORDER BY id
LIMIT 50;

-- Constant performance regardless of page number
```

**With Composite Sort**:
```sql
-- Sort by created_at DESC, then id DESC
-- Page 1
SELECT * FROM orders
ORDER BY created_at DESC, id DESC
LIMIT 50;
-- Last row: created_at='2024-01-15 10:30:00', id=5000

-- Page 2
SELECT * FROM orders
WHERE (created_at, id) < ('2024-01-15 10:30:00', 5000)
ORDER BY created_at DESC, id DESC
LIMIT 50;
```

### 10. NOT IN with NULL Values

`NOT IN` behaves unexpectedly with NULLs.

**Bad**:
```sql
-- Returns zero rows if subquery contains any NULL
SELECT * FROM customers
WHERE id NOT IN (SELECT customer_id FROM blacklist);

-- If blacklist.customer_id has any NULL, this returns nothing!
-- MySQL: "Is id not equal to (1, 2, NULL)?" → Unknown → False
```

**Good - NOT EXISTS**:
```sql
SELECT * FROM customers c
WHERE NOT EXISTS (
  SELECT 1 FROM blacklist b WHERE b.customer_id = c.id
);

-- Handles NULLs correctly
```

**Good - Anti-Join**:
```sql
SELECT c.*
FROM customers c
LEFT JOIN blacklist b ON b.customer_id = c.id
WHERE b.customer_id IS NULL;
```

### 11. Redundant DISTINCT

**Bad**:
```sql
-- DISTINCT on primary key is redundant
SELECT DISTINCT id, name FROM users;

-- id is PRIMARY KEY, already unique
-- DISTINCT adds sorting/deduplication overhead for no benefit
```

**Good**:
```sql
-- Remove unnecessary DISTINCT
SELECT id, name FROM users;
```

**When DISTINCT is Needed**:
```sql
-- After JOIN that might create duplicates
SELECT DISTINCT c.id, c.name
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE o.status = 'completed';
```

### 12. Using COUNT(*) for Existence Check

**Bad**:
```sql
-- Scans all matching rows just to check if any exist
SELECT COUNT(*) FROM orders WHERE customer_id = 123;
-- Returns count, but we only need to know if > 0
```

**Good - EXISTS**:
```sql
-- Stops on first match
SELECT EXISTS(SELECT 1 FROM orders WHERE customer_id = 123);
-- Returns 1 or 0, much faster
```

**Application Usage**:
```python
# Bad
count = db.query("SELECT COUNT(*) FROM orders WHERE customer_id = ?", cust_id)[0][0]
if count > 0:
    # Do something

# Good
exists = db.query("SELECT EXISTS(SELECT 1 FROM orders WHERE customer_id = ?)", cust_id)[0][0]
if exists:
    # Do something
```

### 13. Storing Delimited Lists in Columns

**Bad**:
```sql
-- Storing comma-separated tags in VARCHAR
CREATE TABLE products (
  id INT PRIMARY KEY,
  name VARCHAR(255),
  tags VARCHAR(500)  -- 'electronics,camera,new'
);

-- Finding products with tag 'camera'
SELECT * FROM products WHERE tags LIKE '%camera%';
-- Matches 'cameras', 'security-camera', etc. (wrong)
-- Full table scan, can't use index
```

**Good - Junction Table**:
```sql
CREATE TABLE products (
  id INT PRIMARY KEY,
  name VARCHAR(255)
);

CREATE TABLE tags (
  id INT PRIMARY KEY,
  name VARCHAR(50) UNIQUE
);

CREATE TABLE product_tags (
  product_id INT,
  tag_id INT,
  PRIMARY KEY (product_id, tag_id),
  FOREIGN KEY (product_id) REFERENCES products(id),
  FOREIGN KEY (tag_id) REFERENCES tags(id)
);

-- Find products with tag 'camera'
SELECT p.*
FROM products p
JOIN product_tags pt ON pt.product_id = p.id
JOIN tags t ON t.id = pt.tag_id
WHERE t.name = 'camera';

-- Uses indexes, exact matching, no false positives
```

**Good - JSON Column (MySQL 8.0+)**:
```sql
CREATE TABLE products (
  id INT PRIMARY KEY,
  name VARCHAR(255),
  tags JSON
);

-- Virtual column + index for searching
ALTER TABLE products
ADD COLUMN tags_array VARCHAR(500) AS (JSON_UNQUOTE(JSON_EXTRACT(tags, '$'))) STORED;

CREATE INDEX idx_tags ON products((CAST(tags AS CHAR(500) ARRAY)));

-- Search
SELECT * FROM products
WHERE JSON_CONTAINS(tags, '"camera"');
```

## Query Optimization Workflow

1. **Identify Slow Queries**
   ```sql
   -- Enable slow query log
   SET GLOBAL slow_query_log = 1;
   SET GLOBAL long_query_time = 1;
   ```

2. **Run EXPLAIN**
   ```sql
   EXPLAIN SELECT * FROM problematic_query;
   ```

3. **Look for Red Flags**
   - `type: ALL` (full table scan)
   - `Extra: Using filesort` (sort without index)
   - `Extra: Using temporary` (temp table created)
   - High `rows` count
   - `NULL` in `key` column (no index used)

4. **Apply Optimizations**
   - Add indexes
   - Rewrite query to avoid functions on indexed columns
   - Use JOINs instead of subqueries
   - Break N+1 queries into batches

5. **Verify Improvement**
   ```sql
   EXPLAIN SELECT * FROM optimized_query;
   -- Check execution time before/after
   ```

6. **Monitor in Production**
   - Use Performance Insights
   - Check slow query log
   - Set up CloudWatch alarms

## References

- [MySQL EXPLAIN Output](https://dev.mysql.com/doc/refman/8.0/en/explain-output.html)
- [Optimization Techniques](https://dev.mysql.com/doc/refman/8.0/en/optimization.html)
- [Index Hints](https://dev.mysql.com/doc/refman/8.0/en/index-hints.html)
