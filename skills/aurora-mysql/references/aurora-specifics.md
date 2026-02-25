# Aurora MySQL Specific Behaviors

## Aurora Architecture Fundamentals

### Storage Layer

**Unlike RDS MySQL**:
- Aurora uses shared, distributed storage cluster (not EBS)
- 6 storage replicas across 3 Availability Zones
- Writes use quorum (4 of 6 replicas acknowledge)
- Storage automatically scales from 10GB to 128TB
- No storage IOPS provisioning needed (included)

**Implications**:
- No "running out of IOPS" like gp2/gp3
- Storage layer handles replication, not database engine
- Page-level replication (not statement or row-level)
- Much faster backups and restores (metadata operation)

### Replication

**Aurora Replicas vs RDS Read Replicas**:

| Feature | Aurora Replicas | RDS Read Replicas |
|---------|----------------|-------------------|
| Max replicas | 15 | 5 |
| Replication method | Shared storage | Async binlog |
| Typical lag | < 10ms | 30s - 300s |
| Failover time | 30-60s | 60-120s |
| Storage duplication | No | Yes |
| Replica writes | Shared redo log | Re-execute writes |

**Key Point**: Aurora replicas don't re-execute writes. They apply redo log pages from shared storage.

### Failover Behavior

**Standard Failover** (30-60 seconds):
1. Aurora detects writer failure (~15s)
2. Promotes reader to writer (~20s)
3. DNS update propagates (~30s)
4. Applications reconnect

**With RDS Proxy** (sub-5 seconds):
1. RDS Proxy detects failure immediately
2. Redirects traffic to promoted writer
3. Existing connections preserved
4. In-flight transactions fail (must retry)

**Failover Priority**:
```sql
-- Set failover priority (tier 0 = highest)
aws rds modify-db-instance \
  --db-instance-identifier aurora-reader-1 \
  --promotion-tier 0

-- Lower priority for analytics reader
aws rds modify-db-instance \
  --db-instance-identifier aurora-reader-analytics \
  --promotion-tier 15
```

## TempTable Behavior (CRITICAL)

### The Problem

**Aurora Readers Fail on TempTable Overflow**

- **Community MySQL / RDS**: Spills to InnoDB on-disk temp tables (slower, but works)
- **Aurora Readers**: Query fails with `ERROR 1114: The table is full`
- **Aurora Writer**: Spills to disk (like community MySQL)

This is the #1 Aurora-specific gotcha that breaks production.

### When TempTable is Used

MySQL creates temporary tables for:
- `GROUP BY` without covering index
- `ORDER BY` with different table than FROM
- `DISTINCT` operations
- `UNION` (without `ALL`)
- Subqueries in `FROM` clause (derived tables)
- Window functions with large result sets

### Detection

**Check Current Usage**:
```sql
-- Memory usage by TempTable engine
SELECT EVENT_NAME, CURRENT_NUMBER_OF_BYTES_USED / 1024 / 1024 AS MB_USED
FROM performance_schema.memory_summary_global_by_event_name
WHERE EVENT_NAME LIKE 'memory/temptable/%';

-- Count temp tables created
SHOW GLOBAL STATUS LIKE 'Created_tmp_%';
-- Created_tmp_tables: Total temp tables
-- Created_tmp_disk_tables: Spilled to disk (on writer)
```

**Monitor for Overflows**:
```sql
-- Enable instrumentation
UPDATE performance_schema.setup_instruments
SET ENABLED = 'YES', TIMED = 'YES'
WHERE NAME LIKE 'memory/temptable/%';

-- Check limits
SHOW VARIABLES LIKE 'temptable_max_ram';
SHOW VARIABLES LIKE 'temptable_max_mmap_size';
```

### Prevention Strategies

#### 1. Route Large Queries to Writer

```python
# Application-side routing
def execute_query(sql, is_analytical=False):
    if is_analytical or "GROUP BY" in sql.upper():
        conn = writer_pool.get_connection()  # Route to writer
    else:
        conn = reader_pool.get_connection()  # Route to reader
    return conn.execute(sql)
```

#### 2. Increase TempTable Memory (Reader Parameter Group)

```bash
# Check current setting
aws rds describe-db-parameters \
  --db-parameter-group-name aurora-mysql8-reader-params \
  --query "Parameters[?ParameterName=='temptable_max_ram']"

# Increase limit (e.g., to 2GB for r5.2xlarge with 64GB RAM)
aws rds modify-db-parameter-group \
  --db-parameter-group-name aurora-mysql8-reader-params \
  --parameters "ParameterName=temptable_max_ram,ParameterValue=2147483648,ApplyMethod=immediate"

# Apply to reader instances
aws rds modify-db-instance \
  --db-instance-identifier aurora-reader-1 \
  --db-parameter-group-name aurora-mysql8-reader-params \
  --apply-immediately
```

**Sizing Guidelines**:
- `temptable_max_ram`: 5-10% of instance memory for OLTP readers
- `temptable_max_ram`: 15-25% of instance memory for analytics readers
- Monitor actual usage and adjust

#### 3. Optimize Queries to Avoid TempTable

**Add Covering Index**:
```sql
-- Query uses temporary table for GROUP BY
EXPLAIN SELECT customer_id, COUNT(*), SUM(amount)
FROM orders
GROUP BY customer_id;
-- Extra: Using temporary

-- Add covering index
CREATE INDEX idx_customer_amount ON orders(customer_id, amount);

-- Now uses index for grouping
EXPLAIN SELECT customer_id, COUNT(*), SUM(amount)
FROM orders
GROUP BY customer_id;
-- Extra: Using index
```

**Pre-Filter Before Aggregation**:
```sql
-- Bad: Large temp table
SELECT user_id, COUNT(*), AVG(amount)
FROM orders
WHERE created_at >= '2023-01-01'
GROUP BY user_id;

-- Good: Reduce rows before aggregation
WITH recent_orders AS (
  SELECT user_id, amount
  FROM orders
  WHERE created_at >= '2023-01-01'
    AND user_id IN (SELECT id FROM active_users WHERE last_login > '2023-01-01')
)
SELECT user_id, COUNT(*), AVG(amount)
FROM recent_orders
GROUP BY user_id;
```

#### 4. Break Large Queries into Batches

```sql
-- Instead of one huge query
SELECT date, SUM(amount)
FROM orders
WHERE created_at >= '2020-01-01'
GROUP BY DATE(created_at);

-- Process in monthly batches
SELECT date, SUM(amount)
FROM orders
WHERE created_at >= '2024-01-01'
  AND created_at < '2024-02-01'
GROUP BY DATE(created_at);
-- Repeat for each month, aggregate in application
```

#### 5. Use SQL_BUFFER_RESULT Hint

Forces result to client instead of temp table (for small result sets):
```sql
SELECT SQL_BUFFER_RESULT customer_id, COUNT(*)
FROM orders
GROUP BY customer_id
LIMIT 100;
```

### Real-World Example

**Scenario**: Analytics dashboard query fails on reader during peak hours.

**Bad Query**:
```sql
-- Runs on reader, creates 2GB temp table, fails
SELECT
  DATE(o.created_at) AS order_date,
  c.country,
  COUNT(DISTINCT o.id) AS orders,
  COUNT(DISTINCT o.customer_id) AS customers,
  SUM(oi.quantity * oi.unit_price) AS revenue
FROM orders o
JOIN customers c ON c.id = o.customer_id
JOIN order_items oi ON oi.order_id = o.id
WHERE o.created_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
GROUP BY DATE(o.created_at), c.country
ORDER BY order_date DESC, revenue DESC;
-- ERROR 1114: The table is full
```

**Fix 1: Route to Writer**
```python
# Application code
analytics_conn = get_writer_connection()  # Not reader
result = analytics_conn.execute(query)
```

**Fix 2: Optimize Query**
```sql
-- Aggregate in separate CTEs
WITH daily_orders AS (
  SELECT
    DATE(created_at) AS order_date,
    customer_id,
    COUNT(*) AS order_count
  FROM orders
  WHERE created_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
  GROUP BY DATE(created_at), customer_id
),
daily_revenue AS (
  SELECT
    DATE(o.created_at) AS order_date,
    c.country,
    SUM(oi.quantity * oi.unit_price) AS revenue
  FROM orders o
  JOIN customers c ON c.id = o.customer_id
  JOIN order_items oi ON oi.order_id = o.id
  WHERE o.created_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
  GROUP BY DATE(o.created_at), c.country
)
SELECT
  dr.order_date,
  dr.country,
  COUNT(DISTINCT dord.customer_id) AS customers,
  SUM(dord.order_count) AS orders,
  dr.revenue
FROM daily_revenue dr
JOIN daily_orders dord ON dord.order_date = dr.order_date
GROUP BY dr.order_date, dr.country
ORDER BY dr.order_date DESC, dr.revenue DESC;
```

## Fast Failover with RDS Proxy

### Without RDS Proxy

1. Aurora writer fails
2. DNS takes 30-60s to update
3. All application connections drop
4. Connection storm as all apps reconnect simultaneously
5. 1-2 minutes of downtime

### With RDS Proxy

1. Aurora writer fails
2. RDS Proxy detects new writer in seconds
3. Proxy redirects traffic internally
4. Client connections stay open
5. In-flight transactions fail (app retries)
6. 2-5 seconds of elevated errors, then recovery

### Setup

**Create Proxy**:
```bash
aws rds create-db-proxy \
  --db-proxy-name myapp-proxy \
  --engine-family MYSQL \
  --auth '[{
    "Description": "DB credentials",
    "AuthScheme": "SECRETS",
    "SecretArn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:db-secret",
    "IAMAuth": "DISABLED"
  }]' \
  --role-arn arn:aws:iam::123456789012:role/RDSProxyRole \
  --vpc-subnet-ids subnet-11111111 subnet-22222222 \
  --require-tls

# Register Aurora cluster
aws rds register-db-proxy-targets \
  --db-proxy-name myapp-proxy \
  --db-cluster-identifiers myapp-aurora-cluster

# Configure connection settings
aws rds modify-db-proxy \
  --db-proxy-name myapp-proxy \
  --idle-client-timeout 300 \
  --max-connections-percent 90 \
  --max-idle-connections-percent 50 \
  --connection-borrow-timeout 120
```

**Connection String**:
```
# Instead of cluster endpoint:
aurora-cluster.cluster-xxxxxx.us-east-1.rds.amazonaws.com

# Use proxy endpoint:
myapp-proxy.proxy-xxxxxx.us-east-1.rds.amazonaws.com
```

### Application Retry Pattern

**Python**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import pymysql

# Exceptions to retry
RETRIABLE_EXCEPTIONS = (
    pymysql.err.OperationalError,  # Lost connection
    pymysql.err.InternalError,     # Deadlock
)

@retry(
    retry=retry_if_exception_type(RETRIABLE_EXCEPTIONS),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def execute_transaction(conn):
    with conn.cursor() as cursor:
        cursor.execute("BEGIN")
        cursor.execute("UPDATE accounts SET balance = balance - 100 WHERE id = 1")
        cursor.execute("UPDATE accounts SET balance = balance + 100 WHERE id = 2")
        cursor.execute("COMMIT")

# Usage
try:
    execute_transaction(conn)
except Exception as e:
    logger.error(f"Transaction failed after retries: {e}")
    raise
```

**Java with AWS JDBC Driver**:
```java
import software.amazon.jdbc.Driver;

// Automatic failover handling
Properties props = new Properties();
props.setProperty("user", "admin");
props.setProperty("password", "password");
props.setProperty("wrapperPlugins", "failover,efm2");  // Enhanced Failure Monitoring
props.setProperty("failoverTimeoutMs", "60000");
props.setProperty("failoverClusterTopologyRefreshRateMs", "2000");

Connection conn = DriverManager.getConnection(
    "jdbc:aws-wrapper:mysql://myapp-proxy.proxy-xxx.us-east-1.rds.amazonaws.com:3306/mydb",
    props
);

// Use connection normally
// Driver automatically handles failover
```

### Connection Pinning

Some operations "pin" connections to a specific instance, preventing pooling:

**Pinning Operations**:
- Prepare statements
- Temporary tables
- Session variables
- Table locks

**Best Practice**: Minimize session state to allow connection reuse.

```sql
-- ❌ Pins connection for duration of temp table
CREATE TEMPORARY TABLE staging (id INT, data VARCHAR(100));
INSERT INTO staging SELECT ...;
-- Connection pinned until temp table dropped

-- ✅ Use CTE instead (no pinning)
WITH staging AS (
  SELECT id, data FROM source WHERE ...
)
SELECT * FROM staging;
```

## Aurora Parallel Query

For large table scans and aggregations on analytics queries.

### When to Use

- Table > 100 GB
- Aggregations (SUM, COUNT, AVG)
- Full table scans
- Joins on large tables
- Analytical queries (not OLTP)

### Enable

```sql
-- Enable at session level
SET SESSION aurora_parallel_query = ON;

-- Check if query uses parallel query
EXPLAIN SELECT COUNT(*), AVG(amount)
FROM orders
WHERE created_at >= '2020-01-01';
-- Extra: Using parallel query
```

### Limitations

- Only works on Aurora writer (not readers)
- Table must use InnoDB
- No text/blob columns in WHERE clause
- No fulltext indexes on queried columns
- Table size > 100 GB typically required

## Storage Auto-Scaling

Aurora storage grows automatically:
- Starts at 10 GB
- Grows in 10 GB increments
- Maximum 128 TB (64 TB for t3/t4g instances)
- No manual intervention needed

**Monitor**:
```bash
aws rds describe-db-clusters \
  --db-cluster-identifier myapp-cluster \
  --query 'DBClusters[0].[AllocatedStorage,StorageType]'
```

## Global Database

For cross-region disaster recovery and read scaling.

**Characteristics**:
- < 1 second replication lag to secondary regions
- Supports planned failover (RPO = 0, RTO < 1 minute)
- Unplanned failover (RPO < 1 second, RTO < 1 minute)
- Up to 5 secondary regions

**Setup**:
```bash
# Create global database
aws rds create-global-cluster \
  --global-cluster-identifier myapp-global \
  --engine aurora-mysql \
  --engine-version 8.0.mysql_aurora.3.04.0

# Add primary cluster
aws rds modify-db-cluster \
  --db-cluster-identifier myapp-primary \
  --global-cluster-identifier myapp-global

# Add secondary region cluster
aws rds create-db-cluster \
  --db-cluster-identifier myapp-secondary \
  --engine aurora-mysql \
  --global-cluster-identifier myapp-global \
  --region eu-west-1
```

## References

- [Aurora User Guide](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/)
- [Aurora MySQL Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraMySQL.BestPractices.html)
- [RDS Proxy](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/rds-proxy.html)
