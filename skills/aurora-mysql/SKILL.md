# Aurora MySQL Performance Review Skill

## Purpose

Guide AI assistants through evidence-based performance analysis and optimization of Amazon Aurora MySQL clusters, covering Aurora-specific behaviors, query optimization, schema design, connection management, and MySQL version-specific considerations (8.0, 8.4).

## Core Principles

1. **Evidence-Based**: All recommendations backed by measured data (metrics, EXPLAIN plans, query logs)
2. **Aurora-Aware**: Account for Aurora-specific behaviors that differ from community MySQL and RDS
3. **Safe Changes**: Prioritize online operations; validate impact before destructive changes
4. **Minimal Intervention**: Only recommend changes that address measured bottlenecks
5. **Rollback Planning**: Include rollback procedures for all schema/parameter changes
6. **Version-Specific**: Distinguish between MySQL 8.0, 8.4, and Aurora-specific features

## Aurora MySQL vs RDS MySQL: Key Differences

Before applying optimizations, understand Aurora's unique architecture:

**Storage**:
- Aurora uses shared, distributed storage cluster (not EBS volumes)
- Writes go to all 6 storage replicas simultaneously (quorum write)
- Reads can come from local cache or storage nodes
- No storage IOPS provisioning needed (included with instance)

**Replication**:
- Up to 15 read replicas (vs 5 for RDS MySQL)
- Sub-10ms replica lag typical (vs 30s+ for RDS async replication)
- Shared storage means replicas don't re-execute writes

**Failover**:
- Typically 30-60 seconds for Aurora (vs 60-120s for RDS Multi-AZ)
- No storage replication needed during failover
- With RDS Proxy: sub-5 second application recovery

**TempTable Behavior** (CRITICAL):
- **Aurora readers**: TempTable overflow causes query failure (ERROR 1114)
- **RDS/Community MySQL**: TempTable spills to InnoDB on-disk temp tables
- Monitor: Performance Schema `memory/temptable/*` instruments

## Workflow

### Phase 1: Establish Context

Before making recommendations, gather:

1. **Aurora Environment**
   - Engine version (Aurora MySQL 3.x = MySQL 8.0, Aurora MySQL 4.x = MySQL 8.4)
   - Cluster topology (writer + number of readers)
   - Instance classes and vCPU counts
   - Read/write split configuration
   - RDS Proxy usage
   - Global Database or cross-region clusters
   - Parallel Query enabled (for analytics)

2. **Workload Characteristics**
   - Read/write ratio and routing
   - Connection patterns (long-lived vs. short-lived)
   - Query types (OLTP vs. OLAP)
   - Peak vs. average load
   - Temporary table usage patterns

3. **Current Performance State**
   - CloudWatch metrics: CPU, connections, buffer cache hit rate, commit latency
   - Aurora-specific metrics: AuroraReplicaLag, VolumeReadIOPs, VolumeWriteIOPs
   - Performance Insights: Top SQL and wait events
   - Slow query log analysis
   - TempTable overflow incidents on readers

**Action**: Use diagnostic scripts to collect this data systematically.

### Phase 2: Consult References

Review relevant reference materials based on identified issues:

- `aurora-specifics.md`: Aurora architecture, TempTable, failover
- `query-optimization.md`: Index strategy, EXPLAIN analysis, functional indexes
- `connection-management.md`: RDS Proxy, connection pooling, fast failover
- `schema-design.md`: Primary keys, data types, partitioning, online DDL
- `concurrency-locking.md`: Row locking, deadlock prevention, isolation levels
- `mysql-84-changes.md`: Breaking changes, removed features, migration guide
- `advanced-patterns.md`: CTEs, window functions, aggregation strategies

### Phase 3: Analysis & Recommendations

Generate recommendations in priority order based on potential impact:

#### 3.1 Aurora-Specific Issues (CRITICAL)

**TempTable Overflow on Readers**

Aurora readers **fail queries** instead of spilling to disk when TempTable memory is exhausted. This is the #1 Aurora-specific gotcha.

**Detection**:
```sql
-- Check TempTable memory usage
SELECT EVENT_NAME, CURRENT_NUMBER_OF_BYTES_USED
FROM performance_schema.memory_summary_global_by_event_name
WHERE EVENT_NAME LIKE 'memory/temptable/%';

-- Monitor for OOM events
SHOW GLOBAL STATUS LIKE 'Created_tmp_disk_tables';
```

**Prevention**:
- Route large analytical queries to writer (not readers)
- Increase `temptable_max_ram` for reader instances
- Optimize queries to reduce temporary table usage
- Use `SQL_BUFFER_RESULT` hint to force result to client memory
- Break large queries into smaller batches

**Example**:
```sql
-- Bad: Large GROUP BY on reader (risk of TempTable overflow)
SELECT user_id, COUNT(*), AVG(amount)
FROM orders
WHERE created_at >= '2024-01-01'
GROUP BY user_id;

-- Good: Add index to avoid temporary table
CREATE INDEX idx_orders_created_user
ON orders(created_at, user_id, amount);

-- Or: Route to writer with appropriate hint
-- Or: Use CTE to pre-filter before aggregation
WITH recent_orders AS (
  SELECT user_id, amount
  FROM orders
  WHERE created_at >= '2024-01-01'
    AND user_id IN (SELECT id FROM active_users)  -- Reduce rows first
)
SELECT user_id, COUNT(*), AVG(amount)
FROM recent_orders
GROUP BY user_id;
```

**RDS Proxy Fast Failover**

Without RDS Proxy, Aurora failover takes 30-60s and drops all connections. With RDS Proxy, in-flight transactions fail but connections are preserved.

**Setup**:
```bash
aws rds create-db-proxy \
  --db-proxy-name myapp-proxy \
  --engine-family MYSQL \
  --auth SecretArn \
  --role-arn arn:aws:iam::account:role/RDSProxyRole \
  --vpc-subnet-ids subnet-xxx subnet-yyy \
  --db-proxy-target-db-cluster-identifier myapp-cluster

# Configuration
aws rds modify-db-proxy \
  --db-proxy-name myapp-proxy \
  --idle-client-timeout 300 \
  --max-connections-percent 90
```

**Application Retry Pattern**:
```python
import pymysql
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
def execute_transaction(conn):
    with conn.cursor() as cursor:
        cursor.execute("BEGIN")
        # ... your queries
        cursor.execute("COMMIT")

# Usage
try:
    execute_transaction(conn)
except Exception as e:
    if "Lost connection" in str(e) or "1213" in str(e):  # Deadlock
        # Retry handled by decorator
        pass
    else:
        raise
```

#### 3.2 Query Performance Optimization

**Missing Indexes (CRITICAL)**

Full table scans are the #1 query performance killer.

**Detection**:
```sql
EXPLAIN SELECT * FROM orders WHERE customer_id = 123;
-- Red flag: type: ALL, rows: 5000000
```

**Fix**:
```sql
-- Add index
CREATE INDEX idx_orders_customer ON orders(customer_id);

-- Verify
EXPLAIN SELECT * FROM orders WHERE customer_id = 123;
-- Good: type: ref, key: idx_orders_customer, rows: 25
```

**Functional Indexes (MySQL 8.0+)**

Functions on indexed columns prevent index usage.

**Bad**:
```sql
-- Full table scan even with index on created_at
SELECT * FROM orders WHERE YEAR(created_at) = 2024;
```

**Good - Option 1: Rewrite as range**:
```sql
SELECT * FROM orders
WHERE created_at >= '2024-01-01'
  AND created_at < '2025-01-01';
-- Uses index on created_at
```

**Good - Option 2: Functional index (MySQL 8.0.13+)**:
```sql
CREATE INDEX idx_orders_year ON orders((YEAR(created_at)));

SELECT * FROM orders WHERE YEAR(created_at) = 2024;
-- Now uses idx_orders_year
```

**Composite Index Ordering**

Order matters: equality predicates first, then range/sort columns.

```sql
-- Query pattern
SELECT * FROM orders
WHERE customer_id = ?
  AND created_at > ?
ORDER BY created_at DESC;

-- Optimal index: equality first, then range/sort
CREATE INDEX idx_customer_created ON orders(customer_id, created_at);

-- Wrong order (less efficient):
CREATE INDEX idx_created_customer ON orders(created_at, customer_id);
-- Can't use customer_id for efficient filtering
```

**Covering Indexes**

Include all columns needed by query to avoid table lookups.

```sql
-- Query
SELECT order_id, customer_id, total, status
FROM orders
WHERE customer_id = 123
  AND status = 'pending';

-- Non-covering (requires table lookup for 'total')
CREATE INDEX idx_customer_status ON orders(customer_id, status);

-- Covering index (everything in index)
CREATE INDEX idx_customer_status_covering
ON orders(customer_id, status, order_id, total);
-- EXPLAIN shows: Extra: Using index
```

**LIKE with Leading Wildcard**

`LIKE '%term%'` or `LIKE '%term'` cannot use regular indexes.

**Bad**:
```sql
SELECT * FROM products WHERE name LIKE '%camera%';
-- Full table scan, even with index on name
```

**Good**:
```sql
-- Option 1: FULLTEXT index (for text search)
ALTER TABLE products ADD FULLTEXT INDEX ft_name(name);

SELECT * FROM products
WHERE MATCH(name) AGAINST('camera' IN NATURAL LANGUAGE MODE);

-- Option 2: If searching from start only
SELECT * FROM products WHERE name LIKE 'camera%';
-- Uses regular index on name
```

#### 3.3 Aggregation Over Join (Silent Correctness Issue)

This produces **wrong results** with no error. Critical for business logic.

**Bad**:
```sql
-- Joining order_items and reviews inflates counts
SELECT
  p.id,
  p.name,
  SUM(oi.quantity * oi.unit_price) AS revenue,
  AVG(r.rating) AS avg_rating,
  COUNT(DISTINCT r.id) AS review_count
FROM products p
JOIN order_items oi ON oi.product_id = p.id
LEFT JOIN reviews r ON r.product_id = p.id
GROUP BY p.id, p.name;

-- Problem: A product with 5 order_items and 3 reviews produces 15 rows
-- Revenue is multiplied by 3 (wrong!)
-- avg_rating calculation is incorrect
```

**Good**:
```sql
-- Aggregate each relationship separately in CTEs
WITH product_revenue AS (
  SELECT
    product_id,
    SUM(quantity * unit_price) AS revenue
  FROM order_items
  GROUP BY product_id
),
product_ratings AS (
  SELECT
    product_id,
    AVG(rating) AS avg_rating,
    COUNT(*) AS review_count
  FROM reviews
  GROUP BY product_id
)
SELECT
  p.id,
  p.name,
  COALESCE(pr.revenue, 0) AS revenue,
  COALESCE(prt.avg_rating, 0) AS avg_rating,
  COALESCE(prt.review_count, 0) AS review_count
FROM products p
LEFT JOIN product_revenue pr ON pr.product_id = p.id
LEFT JOIN product_ratings prt ON prt.product_id = p.id;

-- Correct numbers, each aggregation independent
```

#### 3.4 Schema Design

**Primary Keys**

✅ Use `BIGINT UNSIGNED AUTO_INCREMENT` for monotonic keys:
```sql
CREATE TABLE orders (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  customer_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME NOT NULL,
  INDEX idx_customer (customer_id)
) ENGINE=InnoDB;
```

❌ Avoid random UUIDs as clustered index (causes page splits):
```sql
-- Bad: Random UUID as primary key
CREATE TABLE orders (
  id CHAR(36) PRIMARY KEY DEFAULT (UUID()),  -- Random, causes fragmentation
  ...
);
```

✅ If UUIDs required, use binary storage with secondary index:
```sql
CREATE TABLE orders (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  uuid BINARY(16) NOT NULL UNIQUE DEFAULT (UUID_TO_BIN(UUID())),
  ...
);
-- App uses UUID externally, DB uses sequential PK internally
```

**Data Types**

```sql
-- ✅ Good: Right-sized types
CREATE TABLE users (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  age TINYINT UNSIGNED,              -- 0-255, 1 byte
  balance DECIMAL(10,2),              -- Exact precision for money
  created_at DATETIME NOT NULL,       -- Supports full date range
  is_active BOOLEAN DEFAULT TRUE      -- TINYINT(1)
);

-- ❌ Bad: Oversized or wrong types
CREATE TABLE users (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,  -- Should be UNSIGNED
  email VARCHAR(1000),                   -- Wastes space, no email is 1000 chars
  age INT,                               -- 4 bytes when 1 byte sufficient
  balance FLOAT,                         -- Imprecise for money
  created_at TIMESTAMP,                  -- Breaks after 2038
  status ENUM('active','inactive')       -- Not extensible, use lookup table
);
```

**Character Sets**

Always use `utf8mb4` (full Unicode support including emoji):
```sql
-- Database level
CREATE DATABASE myapp
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

-- Table level
CREATE TABLE posts (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  content TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
```

❌ Don't use `utf8` (it's actually utf8mb3, incomplete Unicode):
```sql
-- Bad: Can't store emoji, some Chinese characters
CREATE TABLE posts (
  content TEXT CHARACTER SET utf8  -- Missing characters
);
```

#### 3.5 Connection Management

**RDS Proxy Configuration**

For Lambda or high-churn connections:

```bash
# Create proxy
aws rds create-db-proxy \
  --db-proxy-name myapp-proxy \
  --engine-family MYSQL \
  --auth '[{"SecretArn":"arn:aws:secretsmanager:...:secret/db-secret"}]' \
  --role-arn arn:aws:iam::123456789012:role/RDSProxyRole \
  --vpc-subnet-ids subnet-xxx subnet-yyy

# Register Aurora cluster
aws rds register-db-proxy-targets \
  --db-proxy-name myapp-proxy \
  --db-cluster-identifiers myapp-aurora-cluster

# Configure settings
aws rds modify-db-proxy \
  --db-proxy-name myapp-proxy \
  --idle-client-timeout 300 \            # 5 minutes
  --max-connections-percent 90 \
  --max-idle-connections-percent 50 \
  --connection-borrow-timeout 120
```

**Important**: Min `max-connections-percent` varies by instance:
- db.t3.medium: 55%
- db.r5.large: 10%
- db.r5.xlarge: 5%

**Connection Pooling (Application-Side)**

```python
# Python with SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    'mysql+pymysql://user:pass@proxy-endpoint:3306/db',
    poolclass=QueuePool,
    pool_size=10,                    # Core connections
    max_overflow=20,                 # Additional connections under load
    pool_pre_ping=True,              # Verify connections before use
    pool_recycle=3600                # Recycle connections after 1 hour
)
```

```java
// Java with HikariCP
HikariConfig config = new HikariConfig();
config.setJdbcUrl("jdbc:mysql://proxy-endpoint:3306/db");
config.setUsername("user");
config.setPassword("pass");
config.setMaximumPoolSize(20);
config.setMinimumIdle(5);
config.setIdleTimeout(300000);       // 5 minutes
config.setConnectionTimeout(30000);   // 30 seconds
config.setKeepaliveTime(60000);      // 1 minute keepalive

HikariDataSource ds = new HikariDataSource(config);
```

#### 3.6 Concurrency & Locking

**Deadlock Prevention**

Always lock resources in consistent order:

**Bad**:
```sql
-- Transaction 1
BEGIN;
UPDATE products SET stock = stock - 1 WHERE id = 5;
UPDATE products SET stock = stock - 1 WHERE id = 3;
COMMIT;

-- Transaction 2 (different order = deadlock risk)
BEGIN;
UPDATE products SET stock = stock - 1 WHERE id = 3;
UPDATE products SET stock = stock - 1 WHERE id = 5;
COMMIT;
```

**Good - Single UPDATE**:
```sql
-- Atomic update, all locks acquired simultaneously
BEGIN;
UPDATE products
SET stock = stock - CASE id
  WHEN 5 THEN 1
  WHEN 3 THEN 1
  ELSE 0
END
WHERE id IN (3, 5);
COMMIT;
```

**Good - Consistent Ordering**:
```sql
-- Both transactions lock in ascending PK order
BEGIN;
UPDATE products SET stock = stock - 1 WHERE id = 3;  -- Lower ID first
UPDATE products SET stock = stock - 1 WHERE id = 5;
COMMIT;
```

**Row Locking Best Practices**

```sql
-- ✅ Lock only rows you'll modify
BEGIN;
SELECT * FROM orders
WHERE id = 123
FOR UPDATE;  -- Locks this row only

UPDATE orders SET status = 'shipped' WHERE id = 123;
COMMIT;

-- ❌ Locking too many rows
BEGIN;
SELECT * FROM orders
WHERE customer_id = 456
FOR UPDATE;  -- Locks ALL customer orders unnecessarily

UPDATE orders SET status = 'shipped' WHERE id = 123;
COMMIT;
```

**SKIP LOCKED for Queue Processing**

```sql
-- Multiple workers processing queue without contention
SELECT * FROM jobs
WHERE status = 'pending'
ORDER BY created_at
LIMIT 10
FOR UPDATE SKIP LOCKED;  -- Skip rows locked by other workers

-- Process jobs, update status
UPDATE jobs SET status = 'processing' WHERE id IN (...);
```

#### 3.7 Data Access Patterns

**N+1 Query Elimination**

**Bad**:
```python
# Fetches 1 query for users, then N queries for orders
users = db.query("SELECT * FROM users LIMIT 100")
for user in users:
    orders = db.query("SELECT * FROM orders WHERE user_id = ?", user.id)
    # Process orders
# Total: 101 queries
```

**Good - JOIN**:
```sql
SELECT u.*, o.*
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.id <= 100;
-- 1 query
```

**Good - Batch Fetch**:
```python
users = db.query("SELECT * FROM users LIMIT 100")
user_ids = [u.id for u in users]
orders = db.query("SELECT * FROM orders WHERE user_id IN (%s)", user_ids)
# Group orders by user_id in application
# Total: 2 queries
```

**Keyset Pagination (No OFFSET)**

**Bad**:
```sql
-- Reads and discards 10,000 rows to get 20
SELECT * FROM orders
ORDER BY id
LIMIT 20 OFFSET 10000;
-- Performance degrades linearly with offset
```

**Good**:
```sql
-- First page
SELECT * FROM orders
ORDER BY id
LIMIT 20;
-- Note last id = 50020

-- Next page (cursor-based)
SELECT * FROM orders
WHERE id > 50020
ORDER BY id
LIMIT 20;
-- Constant performance regardless of page depth
```

**Batch Inserts**

```sql
-- ❌ Bad: Individual inserts
INSERT INTO logs (user_id, action) VALUES (1, 'login');
INSERT INTO logs (user_id, action) VALUES (2, 'logout');
-- ... 1000 times

-- ✅ Good: Batch insert (500-5000 rows per batch)
INSERT INTO logs (user_id, action) VALUES
  (1, 'login'),
  (2, 'logout'),
  (3, 'view'),
  ...
  (1000, 'click');
-- 1 statement, much faster
```

### Phase 4: MySQL 8.4 Migration Considerations

If upgrading to Aurora MySQL 4.x (MySQL 8.4), note these breaking changes:

**mysql_native_password Disabled by Default**

```sql
-- ✅ Before upgrade: Check authentication methods
SELECT user, host, plugin FROM mysql.user;

-- If using mysql_native_password, switch to caching_sha2_password
ALTER USER 'myuser'@'%' IDENTIFIED WITH caching_sha2_password BY 'password';

-- Or enable native password in parameter group (not recommended)
-- mysql_native_password = ON
```

**Removed System Variables**

These variables no longer exist in 8.4:
- `binlog_transaction_dependency_tracking` - Remove from my.cnf
- `old_alter_table` - No longer needed
- `innodb_undo_tablespaces` - Now auto-managed

**Pre-Upgrade Checklist**:
```sql
-- Check for removed features
SELECT @@binlog_transaction_dependency_tracking;  -- Remove this setting

-- Check replication metadata format
SHOW VARIABLES LIKE 'master_info_repository';
-- Must be 'TABLE', not 'FILE'

-- Check for deprecated syntax in stored procedures
SELECT * FROM information_schema.routines
WHERE routine_definition LIKE '%OLD_PASSWORD%';
```

### Phase 5: Implementation Plan

For each recommendation, provide:

1. **Change Description**: What will be modified
2. **Expected Impact**: Performance improvement, resource usage changes
3. **Risk Assessment**: Aurora-specific risks (e.g., TempTable on readers)
4. **Implementation Steps**: Specific SQL or AWS CLI commands
5. **Validation**: How to verify the change worked
6. **Rollback**: How to undo if needed

**Example**:
```markdown
## Recommendation: Add Composite Index on orders(customer_id, created_at)

**Current State**: Query scanning 5M rows for customer order history
**Expected Impact**: Reduce query time from 8.2s to <50ms
**Risk**: Low (online index creation on Aurora, no table locking)

**Implementation**:
```sql
-- Add index (online operation)
CREATE INDEX idx_customer_orders
  ON orders(customer_id, created_at)
  ALGORITHM=INPLACE, LOCK=NONE;

-- Monitor progress
SELECT * FROM information_schema.innodb_metrics
WHERE name LIKE 'ddl%';
```

**Validation**:
```sql
EXPLAIN SELECT * FROM orders
WHERE customer_id = 12345
ORDER BY created_at DESC LIMIT 20;
-- Should show: type: ref, key: idx_customer_orders, rows: ~20
-- Extra: Using index
```

**Rollback**:
```sql
DROP INDEX idx_customer_orders ON orders;
```

**Monitoring**: Track query performance via Performance Insights and slow query log.
```

### Phase 6: Validation & Monitoring

After implementing changes:

1. **Immediate Validation**
   - Re-run EXPLAIN plans to confirm index usage
   - Check slow query log for improvements
   - Monitor error logs for issues
   - Verify no TempTable overflows on readers

2. **Ongoing Monitoring**
   - CloudWatch dashboards for key metrics
   - Performance Insights for query-level analysis
   - Aurora-specific metrics: `VolumeReadIOPs`, `AuroraReplicaLag`, `CommitLatency`
   - Set up CloudWatch alarms for regressions

3. **A/B Testing** (when possible)
   - Test changes on reader replica first
   - Use feature flags for query changes
   - Compare metrics before/after on writer

## Aurora-Specific Monitoring

**Key CloudWatch Metrics**:
- `DatabaseConnections`: Current connection count
- `AuroraReplicaLag`: Reader lag in milliseconds (should be <10ms typically)
- `CommitLatency`: Write latency (should be <5ms typically)
- `BufferCacheHitRatio`: Should be >99%
- `VolumeReadIOPs` / `VolumeWriteIOPs`: Storage layer I/O

**Performance Insights**:
- Top SQL by DB Load
- Wait events: `io/aurora_redo_log_flush`, `io/table/sql/handler`, `synch/mutex`
- TempTable memory usage on readers

**Alarms to Set**:
```bash
# High replica lag
aws cloudwatch put-metric-alarm \
  --alarm-name aurora-high-replica-lag \
  --metric-name AuroraReplicaLag \
  --namespace AWS/RDS \
  --statistic Average \
  --period 60 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold

# High commit latency
aws cloudwatch put-metric-alarm \
  --alarm-name aurora-high-commit-latency \
  --metric-name CommitLatency \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

## Guardrails

- **Never** recommend destructive operations without explicit user approval
- **Always** provide rollback procedures for schema changes
- **Always** use `ALGORITHM=INPLACE, LOCK=NONE` when available
- **Always** consider Aurora-specific behavior (TempTable, replication lag, failover)
- **Always** distinguish between MySQL versions (8.0 vs 8.4)
- **Always** test on non-production readers before applying to writer
- **Never** route large analytical queries to readers without checking TempTable limits

## Success Metrics

Track these KPIs before and after optimization:

- Query latency (p50, p95, p99)
- Slow query count and time
- CPU utilization (writer and readers separately)
- Buffer cache hit rate (should be >99%)
- Commit latency (should be <5ms)
- Replica lag (should be <10ms)
- TempTable overflow incidents (should be 0)
- Connection count and wait events
- Application-level response times

## When to Escalate

Recommend alternative approaches when:

- Current instance class is undersized for workload
- Aurora architecture doesn't fit access pattern (consider RDS MySQL or DynamoDB)
- Sharding required (consider Aurora multi-master or application-level sharding)
- Cross-region replication latency unacceptable (consider Global Database)
- Application-level optimization required (caching layer, query reduction)

## References

- `aurora-specifics.md`: Aurora architecture and unique behaviors
- `query-optimization.md`: Query patterns, indexing, EXPLAIN
- `connection-management.md`: RDS Proxy, connection pooling
- `schema-design.md`: Tables, data types, partitioning
- `concurrency-locking.md`: Transactions, deadlocks, isolation
- `mysql-84-changes.md`: MySQL 8.4 breaking changes
- `advanced-patterns.md`: CTEs, window functions, JSON
