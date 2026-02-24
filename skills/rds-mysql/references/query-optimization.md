# Query Optimization Reference

## EXPLAIN Plan Analysis

### Understanding EXPLAIN Output

#### Key Columns

**id**: Query identifier (higher executed first in subqueries)

**select_type**: Query type
- `SIMPLE`: No subqueries or unions
- `PRIMARY`: Outermost SELECT
- `SUBQUERY`: Subquery in SELECT
- `DERIVED`: Derived table (FROM subquery)
- `UNION`: Second or later SELECT in UNION

**type**: Join type (best to worst)
- `system`: Table has only one row
- `const`: At most one matching row (PRIMARY KEY or UNIQUE lookup)
- `eq_ref`: One row per previous table combination (JOIN on PRIMARY KEY/UNIQUE)
- `ref`: Multiple rows with matching index value
- `range`: Index range scan (BETWEEN, >, <)
- `index`: Full index scan
- `ALL`: Full table scan ❌

**possible_keys**: Indexes that could be used

**key**: Index actually used (NULL means no index)

**key_len**: Length of index used (shorter = better for multi-column indexes)

**ref**: Column or constant compared to key

**rows**: Estimated rows examined (lower = better)

**filtered**: Percentage of rows filtered by condition

**Extra**: Additional information
- `Using index`: Covering index (no table access needed) ✅
- `Using where`: Filtering after index lookup
- `Using temporary`: Temporary table needed ❌
- `Using filesort`: Sort operation needed ❌
- `Using index condition`: Index condition pushdown ✅

### EXPLAIN Format Options

```sql
-- Traditional format
EXPLAIN SELECT * FROM orders WHERE customer_id = 123;

-- JSON format (more detailed)
EXPLAIN FORMAT=JSON SELECT * FROM orders WHERE customer_id = 123;

-- Tree format (MySQL 8.0.16+)
EXPLAIN FORMAT=TREE SELECT * FROM orders WHERE customer_id = 123;

-- Analyze format (actual execution stats, MySQL 8.0.18+)
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 123;
```

### Red Flags in EXPLAIN

1. **type: ALL (Full Table Scan)**
```sql
-- Bad: Scanning entire table
EXPLAIN SELECT * FROM orders WHERE status = 'pending';
-- Solution: Add index on status
CREATE INDEX idx_status ON orders(status);
```

2. **Using filesort**
```sql
-- Bad: Sorting without index
EXPLAIN SELECT * FROM orders ORDER BY created_at DESC LIMIT 10;
-- Solution: Add index on created_at
CREATE INDEX idx_created_at ON orders(created_at);
```

3. **Using temporary**
```sql
-- Bad: Temporary table for GROUP BY
EXPLAIN SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id;
-- Solution: Add index on customer_id (if not already PK/FK)
CREATE INDEX idx_customer_id ON orders(customer_id);
```

4. **High rows with low filtered**
```sql
-- Bad: Examining 100K rows, filtering to 100
EXPLAIN SELECT * FROM orders
WHERE status = 'pending' AND total > 100;
-- rows: 100000, filtered: 0.1%

-- Solution: Composite index
CREATE INDEX idx_status_total ON orders(status, total);
```

## Index Design Patterns

### Composite Index Ordering

**Rule**: Equality predicates first, then range/sort columns

```sql
-- Query pattern
SELECT * FROM orders
WHERE customer_id = ?
  AND created_at > ?
ORDER BY created_at DESC;

-- Optimal index: equality (customer_id) first, then range/sort (created_at)
CREATE INDEX idx_customer_created ON orders(customer_id, created_at);
```

### Leftmost Prefix Rule

An index on `(a, b, c)` can be used for:
- ✅ `WHERE a = ?`
- ✅ `WHERE a = ? AND b = ?`
- ✅ `WHERE a = ? AND b = ? AND c = ?`
- ❌ `WHERE b = ?` (skips leftmost column)
- ❌ `WHERE a = ? AND c = ?` (skips middle column, only uses `a`)

```sql
CREATE INDEX idx_abc ON table(a, b, c);

-- Uses index fully
SELECT * FROM table WHERE a = 1 AND b = 2 AND c = 3;

-- Uses only (a) part of index
SELECT * FROM table WHERE a = 1 AND c = 3;

-- Cannot use index
SELECT * FROM table WHERE b = 2;
```

### Covering Indexes

Include all columns needed by query to avoid table access

```sql
-- Query
SELECT customer_id, created_at, total FROM orders
WHERE customer_id = ?;

-- Non-covering index (requires table lookup for 'total')
CREATE INDEX idx_customer ON orders(customer_id);

-- Covering index (all columns in index)
CREATE INDEX idx_customer_covering ON orders(customer_id, created_at, total);

-- EXPLAIN will show: Extra: Using index
```

### Index Selectivity

**Selectivity** = Unique values / Total rows (higher = better)

```sql
-- Check selectivity
SELECT
  COUNT(DISTINCT column) / COUNT(*) as selectivity,
  COUNT(DISTINCT column) as unique_values,
  COUNT(*) as total_rows
FROM table;

-- High selectivity (0.9+): Good index candidate
-- Low selectivity (<0.1): Poor index candidate (consider composite index)
```

**Examples**:
- ✅ Email, username, order_id: High selectivity
- ⚠️ Status, boolean flags: Low selectivity (still useful in composite indexes)
- ❌ Gender with 2 values: Very low selectivity

### Redundant Indexes

```sql
-- Redundant: idx_a is covered by idx_ab
CREATE INDEX idx_a ON table(a);
CREATE INDEX idx_ab ON table(a, b);  -- Drop idx_a

-- Not redundant: Different column order
CREATE INDEX idx_ab ON table(a, b);
CREATE INDEX idx_ba ON table(b, a);  -- Both useful

-- Redundant: Same column, different length
CREATE INDEX idx_name_full ON users(name);
CREATE INDEX idx_name_prefix ON users(name(10));  -- Drop one
```

## Common Query Anti-Patterns

### 1. SELECT *

```sql
-- Bad: Fetches all columns
SELECT * FROM orders WHERE customer_id = 123;

-- Good: Fetch only needed columns
SELECT id, order_date, total FROM orders WHERE customer_id = 123;
```

**Why**:
- Transfers more data over network
- Prevents covering indexes
- May fetch large TEXT/BLOB columns

### 2. Functions on Indexed Columns

```sql
-- Bad: Function prevents index usage
SELECT * FROM orders WHERE DATE(created_at) = '2024-01-15';

-- Good: Range condition uses index
SELECT * FROM orders
WHERE created_at >= '2024-01-15 00:00:00'
  AND created_at < '2024-01-16 00:00:00';
```

### 3. Leading Wildcards in LIKE

```sql
-- Bad: Leading wildcard prevents index usage
SELECT * FROM users WHERE email LIKE '%@example.com';

-- Good: No leading wildcard uses index
SELECT * FROM users WHERE email LIKE 'john%';

-- Alternative: Full-text index for pattern matching
ALTER TABLE users ADD FULLTEXT INDEX ft_email(email);
SELECT * FROM users WHERE MATCH(email) AGAINST('example.com');
```

### 4. OR Conditions on Different Columns

```sql
-- Bad: OR on different columns prevents index usage
SELECT * FROM orders WHERE customer_id = 123 OR status = 'pending';

-- Good: Use UNION if both columns are indexed
SELECT * FROM orders WHERE customer_id = 123
UNION
SELECT * FROM orders WHERE status = 'pending';
```

### 5. Implicit Type Conversion

```sql
-- Bad: customer_id is INT, but using string (implicit conversion)
SELECT * FROM orders WHERE customer_id = '123';

-- Good: Use correct type
SELECT * FROM orders WHERE customer_id = 123;

-- Check for implicit conversions in EXPLAIN: Extra: Using where
```

### 6. Negative Conditions

```sql
-- Bad: NOT, !=, <> often prevent index usage
SELECT * FROM orders WHERE status != 'cancelled';

-- Better: Specify positive conditions if possible
SELECT * FROM orders WHERE status IN ('pending', 'processing', 'shipped');
```

### 7. OFFSET Pagination

```sql
-- Bad: OFFSET scans and discards rows (slow for large offsets)
SELECT * FROM orders ORDER BY id LIMIT 100 OFFSET 50000;

-- Good: Cursor-based pagination
SELECT * FROM orders WHERE id > 50000 ORDER BY id LIMIT 100;
```

## Query Optimization Techniques

### 1. Batch Operations

**Insert**:
```sql
-- Bad: Individual inserts
INSERT INTO orders (customer_id, total) VALUES (1, 100);
INSERT INTO orders (customer_id, total) VALUES (2, 200);
-- Repeat 1000 times...

-- Good: Batch insert (500-5000 rows per batch)
INSERT INTO orders (customer_id, total) VALUES
  (1, 100), (2, 200), (3, 300), ..., (1000, 50000);
```

**Update**:
```sql
-- Bad: Updating one by one in loop
UPDATE orders SET status = 'shipped' WHERE id = 1;
UPDATE orders SET status = 'shipped' WHERE id = 2;

-- Good: Single update with IN clause
UPDATE orders SET status = 'shipped' WHERE id IN (1, 2, 3, ..., 100);
```

### 2. Join Optimization

**Index Foreign Keys**:
```sql
-- Always index foreign key columns
CREATE INDEX idx_order_customer ON orders(customer_id);
CREATE INDEX idx_orderitem_order ON order_items(order_id);
```

**Join Order** (MySQL optimizer usually handles this, but be aware):
- Smaller table first (driving table)
- Most restrictive WHERE clause first

**Avoid Subqueries in SELECT** (use JOINs instead):
```sql
-- Bad: Correlated subquery per row
SELECT o.*,
  (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count
FROM orders o;

-- Good: Join
SELECT o.*, COUNT(oi.id) as item_count
FROM orders o
LEFT JOIN order_items oi ON o.id = oi.order_id
GROUP BY o.id;
```

### 3. Subquery Optimization

**Derived Tables**:
```sql
-- Ensure derived tables are filtered
SELECT * FROM (
  SELECT * FROM orders
  WHERE created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
) recent_orders
WHERE customer_id = 123;
```

**EXISTS vs IN**:
```sql
-- EXISTS: Better for large subquery results (stops on first match)
SELECT * FROM customers c
WHERE EXISTS (
  SELECT 1 FROM orders o WHERE o.customer_id = c.id
);

-- IN: Better for small subquery results
SELECT * FROM orders
WHERE customer_id IN (SELECT id FROM customers WHERE country = 'US');
```

### 4. Aggregation Optimization

**Index for GROUP BY**:
```sql
-- Query
SELECT customer_id, SUM(total) FROM orders GROUP BY customer_id;

-- Index to avoid temporary table
CREATE INDEX idx_customer_total ON orders(customer_id, total);
```

**Filter Before Aggregation**:
```sql
-- Good: Filter before aggregation
SELECT customer_id, SUM(total)
FROM orders
WHERE created_at > DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY customer_id;

-- Bad: Filter after aggregation (processes all rows)
SELECT customer_id, SUM(total) as total
FROM orders
GROUP BY customer_id
HAVING total > 1000;
-- (Use WHERE for non-aggregated filters, HAVING only for aggregated)
```

### 5. UNION vs UNION ALL

```sql
-- UNION: Removes duplicates (requires sorting/deduplication)
SELECT id FROM orders WHERE status = 'pending'
UNION
SELECT id FROM orders WHERE status = 'processing';

-- UNION ALL: Keeps duplicates (faster, no deduplication)
SELECT id FROM orders WHERE status = 'pending'
UNION ALL
SELECT id FROM orders WHERE status = 'processing';
-- Use UNION ALL when you know there are no duplicates
```

## N+1 Query Problem

**Problem**: Executing one query, then N additional queries in a loop

```sql
-- Bad: N+1 queries
SELECT * FROM customers;  -- 1 query returns 100 customers
-- Then in application loop:
SELECT * FROM orders WHERE customer_id = ?;  -- 100 additional queries
```

**Solutions**:

1. **JOIN**:
```sql
SELECT c.*, o.*
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id;
```

2. **Batch Fetch with IN**:
```sql
-- Fetch all customers
SELECT * FROM customers;

-- Batch fetch all orders
SELECT * FROM orders WHERE customer_id IN (1, 2, 3, ..., 100);
```

3. **Application-Level Batching** (e.g., DataLoader pattern)

## Performance Testing Queries

### 1. Query Execution Time

```sql
SET profiling = 1;

SELECT * FROM orders WHERE customer_id = 123;

SHOW PROFILES;
SHOW PROFILE FOR QUERY 1;
```

### 2. Index Usage Stats

```sql
-- Check if indexes are being used
SELECT * FROM sys.schema_unused_indexes;

-- Index statistics
SELECT * FROM sys.schema_index_statistics
WHERE table_schema = 'mydb'
ORDER BY select_latency DESC;
```

### 3. Slow Query Analysis

```sql
-- Enable slow query log
SET GLOBAL slow_query_log = 1;
SET GLOBAL long_query_time = 1;
SET GLOBAL log_queries_not_using_indexes = 1;

-- Analyze with mysqldumpslow (on server) or pt-query-digest (Percona Toolkit)
```

## Query Rewriting Examples

### Example 1: Date Range Query

**Before**:
```sql
SELECT * FROM orders
WHERE YEAR(created_at) = 2024 AND MONTH(created_at) = 1;
-- type: ALL (full table scan)
```

**After**:
```sql
SELECT * FROM orders
WHERE created_at >= '2024-01-01' AND created_at < '2024-02-01';
-- type: range (uses index on created_at)
```

### Example 2: Count Optimization

**Before**:
```sql
SELECT COUNT(*) FROM orders WHERE status = 'pending';
-- Scans all rows with status='pending'
```

**After** (if exact count not needed):
```sql
-- For approximate count, use EXPLAIN
EXPLAIN SELECT * FROM orders WHERE status = 'pending';
-- Check 'rows' column for estimate

-- Or use summary table updated periodically
SELECT count FROM order_status_summary WHERE status = 'pending';
```

### Example 3: Complex WHERE Clause

**Before**:
```sql
SELECT * FROM orders
WHERE (status = 'pending' AND priority = 'high')
   OR (status = 'processing' AND priority = 'high');
-- Cannot efficiently use indexes
```

**After**:
```sql
SELECT * FROM orders
WHERE priority = 'high'
  AND status IN ('pending', 'processing');
-- Index: (priority, status)
```

## Tools for Query Analysis

1. **EXPLAIN / EXPLAIN ANALYZE**: Built-in MySQL query analysis
2. **Performance Schema**: Detailed query statistics
3. **sys Schema**: Simplified views of Performance Schema
4. **pt-query-digest**: Percona Toolkit for slow query analysis
5. **RDS Performance Insights**: AWS managed query monitoring
6. **mysqldumpslow**: Summarize slow query logs

## Further Reading

- MySQL 8.0 Optimization: https://dev.mysql.com/doc/refman/8.0/en/optimization.html
- EXPLAIN Output: https://dev.mysql.com/doc/refman/8.0/en/explain-output.html
- Performance Schema: https://dev.mysql.com/doc/refman/8.0/en/performance-schema.html
