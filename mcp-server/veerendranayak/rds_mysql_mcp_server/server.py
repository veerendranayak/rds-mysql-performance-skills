"""RDS MySQL Performance MCP Server

The official MCP Server for AWS RDS MySQL and Aurora MySQL performance optimization.
"""

import os
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field


# Server instructions
SERVER_INSTRUCTIONS = """The official MCP Server for AWS RDS MySQL and Aurora MySQL performance optimization

This server provides expert guidance for analyzing and optimizing AWS MySQL database performance.

Available Tools:
--------------

1. rds_mysql_performance_review
   Retrieves comprehensive RDS MySQL performance review guidance covering:
   - CloudWatch metrics interpretation
   - Schema design validation
   - Index optimization and query tuning
   - RDS-specific operational patterns
   - Parameter group tuning
   - Storage optimization

   Use when: Working with standard RDS MySQL instances

2. aurora_mysql_performance_review
   Retrieves Aurora MySQL performance review guidance with Aurora-specific considerations:
   - TempTable overflow prevention (CRITICAL for readers)
   - Fast failover with RDS Proxy
   - Aurora replication architecture
   - Parallel query optimization
   - Aurora-specific monitoring

   Use when: Working with Aurora MySQL clusters

   🔴 CRITICAL: Aurora readers fail queries on TempTable overflow (unlike RDS MySQL)

3. schema_analysis_guidance
   Retrieves schema design best practices:
   - Primary key design
   - Data type selection
   - Normalization strategies
   - Foreign key relationships
   - Table partitioning

   Use when: Reviewing or designing database schemas

4. query_optimization_guidance
   Retrieves query optimization techniques:
   - EXPLAIN analysis interpretation
   - Index strategy and covering indexes
   - Common anti-patterns
   - Query rewriting techniques
   - Subquery vs JOIN optimization

   Use when: Optimizing slow queries

5. mysql_84_migration_guidance
   Retrieves MySQL 8.4 migration planning guidance:
   - Breaking changes from MySQL 8.0 to 8.4
   - Deprecated features and replacements
   - Aurora MySQL 3.x to 4.x migration
   - Testing and validation strategies

   Use when: Planning upgrade to MySQL 8.4 or Aurora MySQL 4.x

Usage Notes:
-----------
- Start with rds_mysql_performance_review or aurora_mysql_performance_review for comprehensive analysis
- Use specific tools (schema_analysis, query_optimization) for focused reviews
- Always gather metrics and evidence before making recommendations
- Test changes in non-production environments first
"""

# Initialize FastMCP server
app = FastMCP(
    "RDS MySQL Performance MCP Server",
    instructions=SERVER_INSTRUCTIONS,
)


def _load_prompt(prompt_file: str) -> str:
    """Load prompt content from file."""
    prompt_path = Path(__file__).parent / 'prompts' / prompt_file
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    return prompt_path.read_text(encoding='utf-8')


@app.tool()
async def rds_mysql_performance_review() -> str:
    """Retrieves comprehensive RDS MySQL performance review guidance.

    This tool returns expert guidance for analyzing and optimizing Amazon RDS MySQL instances.

    The guidance includes:
    - Structured performance review workflow (context → data collection → analysis → recommendations)
    - CloudWatch metrics interpretation and diagnosis
    - Schema design validation with MySQL/InnoDB best practices
    - Index optimization strategies and EXPLAIN analysis techniques
    - RDS-specific operational patterns and parameter tuning
    - Storage type selection (gp2, gp3, io1, io2) and optimization
    - Read replica configuration and monitoring
    - Connection pooling best practices
    - Implementation and validation procedures

    Use this tool when working with standard RDS MySQL instances (not Aurora).

    Returns: Complete RDS MySQL performance review guidance as markdown text.
    """
    return _load_prompt('rds_mysql_performance_review.md')


@app.tool()
async def aurora_mysql_performance_review() -> str:
    """Retrieves comprehensive Aurora MySQL performance review guidance.

    This tool returns expert guidance for analyzing and optimizing Amazon Aurora MySQL clusters,
    with special attention to Aurora-specific behaviors that differ from RDS MySQL.

    🔴 CRITICAL Aurora Differences Covered:
    - TempTable overflow behavior: Aurora readers FAIL queries (vs RDS spills to disk)
    - Shared storage architecture and implications
    - Sub-10ms replication lag (vs 30s-300s for RDS)
    - Fast failover with RDS Proxy (sub-5s vs 30-60s)
    - Aurora Parallel Query for analytics workloads

    The guidance includes:
    - Aurora architecture fundamentals (storage, replication, failover)
    - TempTable overflow detection, prevention, and mitigation strategies
    - RDS Proxy configuration for fast failover
    - Reader vs writer workload routing strategies
    - Aurora-specific CloudWatch metrics and monitoring
    - Parameter tuning for writer and reader instances
    - MySQL 8.0 (Aurora 3.x) and 8.4 (Aurora 4.x) considerations

    Use this tool when working with Aurora MySQL clusters.
    For standard RDS MySQL instances, use rds_mysql_performance_review instead.

    Returns: Complete Aurora MySQL performance review guidance as markdown text.
    """
    return _load_prompt('aurora_mysql_performance_review.md')


@app.tool()
async def schema_analysis_guidance() -> str:
    """Retrieves schema design and analysis best practices.

    This tool returns guidance for reviewing and optimizing MySQL database schemas,
    applicable to both RDS MySQL and Aurora MySQL.

    The guidance covers:
    - Primary key design (auto-increment vs UUID strategies)
    - Data type selection and optimization
    - Character set and collation choices (utf8mb4 best practices)
    - Normalization strategies (when to normalize, when to denormalize)
    - Foreign key relationships and referential integrity
    - Table partitioning strategies and limitations
    - Online DDL operations and algorithms
    - Schema migration best practices

    Common schema issues detected:
    - Tables without primary keys
    - Inefficient data types (using VARCHAR when INT appropriate)
    - UUID primary keys causing fragmentation
    - Missing or incorrect indexes on foreign keys
    - Over-normalization or under-normalization

    Use this tool when:
    - Designing new database schemas
    - Reviewing existing schema for optimization
    - Planning schema migrations or refactoring
    - Investigating schema-related performance issues

    Returns: Complete schema analysis guidance as markdown text.
    """
    prompt = """# MySQL Schema Design and Analysis Guidance

## Primary Key Design

### Auto-Increment Primary Keys (Recommended for Most Cases)

✅ **Best Practice**:
```sql
CREATE TABLE users (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_email (email)
) ENGINE=InnoDB;
```

**Advantages**:
- Sequential inserts minimize page splits
- Smaller index size (8 bytes vs 16 bytes for UUID)
- Better cache locality
- Predictable performance

**Sizing**:
- `INT UNSIGNED`: 0 to 4.3 billion (suitable for most cases)
- `BIGINT UNSIGNED`: 0 to 18.4 quintillion (future-proof)

### UUID Primary Keys (Use with Caution)

❌ **Anti-Pattern** (causes fragmentation):
```sql
CREATE TABLE orders (
  id BINARY(16) PRIMARY KEY,  -- Random UUID
  user_id BIGINT UNSIGNED,
  total DECIMAL(10,2),
  INDEX idx_user (user_id)
) ENGINE=InnoDB;
```

**Problems**:
- Random UUIDs cause page splits (non-sequential inserts)
- Larger index size (16 bytes)
- Worse buffer pool utilization
- Unpredictable write performance

✅ **Better Approach** (if UUIDs required):
```sql
CREATE TABLE orders (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,  -- Clustered index
  uuid BINARY(16) NOT NULL UNIQUE,                -- Secondary index
  user_id BIGINT UNSIGNED,
  total DECIMAL(10,2),
  INDEX idx_uuid (uuid),
  INDEX idx_user (user_id)
) ENGINE=InnoDB;
```

**Or use UUID v7** (time-ordered):
```sql
-- UUID v7 has timestamp prefix, reduces fragmentation
CREATE TABLE events (
  id BINARY(16) PRIMARY KEY,  -- UUID v7
  event_type VARCHAR(50),
  payload JSON
) ENGINE=InnoDB;
```

## Data Type Selection

### Integer Types

| Type | Storage | Range (UNSIGNED) | Use Case |
|------|---------|------------------|----------|
| TINYINT | 1 byte | 0-255 | Boolean, small enums |
| SMALLINT | 2 bytes | 0-65K | Small counters |
| MEDIUMINT | 3 bytes | 0-16M | Medium-sized IDs |
| INT | 4 bytes | 0-4.3B | Standard IDs, counters |
| BIGINT | 8 bytes | 0-18.4Q | Large IDs, timestamps |

✅ **Right-size your integers**:
```sql
CREATE TABLE products (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  category_id SMALLINT UNSIGNED,  -- Only 100 categories
  stock_quantity INT UNSIGNED,
  is_active BOOLEAN,  -- TINYINT(1)
  created_at DATETIME
) ENGINE=InnoDB;
```

### String Types

✅ **Use utf8mb4 (not utf8)**:
```sql
-- utf8mb4 supports full Unicode including emojis
ALTER DATABASE mydb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE comments (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  content TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  user_id BIGINT UNSIGNED
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

✅ **VARCHAR vs CHAR**:
```sql
-- Use VARCHAR for variable-length strings
email VARCHAR(255)          -- Average 25 chars, max 255
description VARCHAR(1000)   -- Variable length

-- Use CHAR for fixed-length strings
country_code CHAR(2)        -- Always 2 chars: 'US', 'UK'
md5_hash CHAR(32)           -- Always 32 chars
```

❌ **Avoid ENUM** (not extensible):
```sql
-- BAD: Adding values requires schema change
status ENUM('pending', 'approved', 'rejected')

-- GOOD: Use lookup table
CREATE TABLE order_statuses (
  id TINYINT UNSIGNED PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE orders (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  status_id TINYINT UNSIGNED,
  FOREIGN KEY (status_id) REFERENCES order_statuses(id)
);
```

### Date and Time Types

✅ **Prefer DATETIME over TIMESTAMP**:
```sql
-- DATETIME: 1000-01-01 to 9999-12-31
created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP

-- TIMESTAMP: 1970-01-01 to 2038-01-19 (Y2038 problem)
-- Only use if you need automatic timezone conversion
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
```

### JSON Type

✅ **Use JSON for flexible schemas**:
```sql
CREATE TABLE user_preferences (
  user_id BIGINT UNSIGNED PRIMARY KEY,
  settings JSON,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Query JSON
SELECT settings->>'$.theme' as theme
FROM user_preferences
WHERE user_id = 123;

-- Index JSON (MySQL 8.0+)
ALTER TABLE user_preferences
  ADD COLUMN theme VARCHAR(20) GENERATED ALWAYS AS (settings->>'$.theme') VIRTUAL,
  ADD INDEX idx_theme (theme);
```

## Normalization Strategies

### Third Normal Form (3NF) - Target for OLTP

✅ **Properly normalized**:
```sql
-- Users table
CREATE TABLE users (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(100)
);

-- Orders table
CREATE TABLE orders (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  total DECIMAL(10,2) NOT NULL,
  status_id TINYINT UNSIGNED NOT NULL,
  created_at DATETIME NOT NULL,
  INDEX idx_user_created (user_id, created_at),
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (status_id) REFERENCES order_statuses(id)
);

-- Order items table
CREATE TABLE order_items (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_id BIGINT UNSIGNED NOT NULL,
  product_id BIGINT UNSIGNED NOT NULL,
  quantity INT UNSIGNED NOT NULL,
  unit_price DECIMAL(10,2) NOT NULL,
  INDEX idx_order (order_id),
  FOREIGN KEY (order_id) REFERENCES orders(id),
  FOREIGN KEY (product_id) REFERENCES products(id)
);
```

### Strategic Denormalization

✅ **When to denormalize** (with caution):
```sql
-- Store frequently-accessed fields from related table
CREATE TABLE orders (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  user_email VARCHAR(255) NOT NULL,  -- Denormalized from users table
  user_name VARCHAR(100) NOT NULL,    -- Denormalized from users table
  total DECIMAL(10,2) NOT NULL,
  created_at DATETIME NOT NULL,
  INDEX idx_user (user_id)
);
```

**Justification for denormalization**:
- ✅ Read-heavy workload (10:1 read:write ratio)
- ✅ JOIN with users table on 80% of order queries
- ✅ User email/name rarely change
- ✅ Application handles updates to both tables

**Maintain consistency**:
```sql
-- Update denormalized data when source changes
UPDATE orders o
JOIN users u ON o.user_id = u.id
SET o.user_email = u.email, o.user_name = u.name
WHERE u.id = ?;
```

## Foreign Key Relationships

✅ **Define foreign keys for referential integrity**:
```sql
CREATE TABLE orders (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB;
```

**ON DELETE options**:
- `RESTRICT`: Prevent deletion if references exist (safest)
- `CASCADE`: Delete related rows (use carefully)
- `SET NULL`: Set foreign key to NULL (requires nullable column)
- `NO ACTION`: Same as RESTRICT

⚠️ **Foreign keys have overhead**:
- Add index automatically on referencing column
- Enforce consistency checks on INSERT/UPDATE/DELETE
- May impact write performance on high-volume tables

## Table Partitioning

✅ **When to partition**:
- Time-series data (partition by date)
- Very large tables (>100GB)
- Queries frequently filter on partition key
- Need to drop old data quickly (DROP PARTITION vs DELETE)

**Example: Range partitioning by date**:
```sql
CREATE TABLE events (
  id BIGINT UNSIGNED AUTO_INCREMENT,
  event_type VARCHAR(50),
  event_date DATE NOT NULL,
  payload JSON,
  PRIMARY KEY (id, event_date),  -- Must include partition key
  INDEX idx_type (event_type, event_date)
) ENGINE=InnoDB
PARTITION BY RANGE (TO_DAYS(event_date)) (
  PARTITION p202401 VALUES LESS THAN (TO_DAYS('2024-02-01')),
  PARTITION p202402 VALUES LESS THAN (TO_DAYS('2024-03-01')),
  PARTITION p202403 VALUES LESS THAN (TO_DAYS('2024-04-01')),
  PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- Drop old partitions (instant operation)
ALTER TABLE events DROP PARTITION p202401;
```

**Partitioning limitations**:
- All unique indexes must include partition key
- Foreign keys not supported
- Fulltext indexes not supported (MySQL <8.0)

## Online DDL Operations

### MySQL 8.0 Online DDL

✅ **Operations that support ALGORITHM=INSTANT**:
```sql
-- Add column at end (default value)
ALTER TABLE users
  ADD COLUMN phone VARCHAR(20),
  ALGORITHM=INSTANT;

-- Drop column
ALTER TABLE users
  DROP COLUMN phone,
  ALGORITHM=INSTANT;

-- Rename column
ALTER TABLE users
  RENAME COLUMN phone TO mobile,
  ALGORITHM=INSTANT;
```

✅ **Operations that support ALGORITHM=INPLACE** (no table copy):
```sql
-- Add/drop index
ALTER TABLE users
  ADD INDEX idx_email (email),
  ALGORITHM=INPLACE, LOCK=NONE;

-- Change column default
ALTER TABLE users
  ALTER COLUMN status SET DEFAULT 'active',
  ALGORITHM=INPLACE;
```

❌ **Operations that require table copy** (ALGORITHM=COPY):
```sql
-- Change column data type
ALTER TABLE users
  MODIFY COLUMN name VARCHAR(200),
  ALGORITHM=COPY;  -- Blocks reads/writes

-- Add column in middle of table (before MySQL 8.0.29)
ALTER TABLE users
  ADD COLUMN middle_name VARCHAR(100) AFTER name,
  ALGORITHM=COPY;
```

### Testing DDL Operations

```sql
-- Test with ALGORITHM and LOCK clauses
ALTER TABLE users
  ADD INDEX idx_email (email),
  ALGORITHM=INPLACE,
  LOCK=NONE;  -- Fail if operation requires locks

-- LOCK options:
-- NONE: No locks, fully concurrent
-- SHARED: Allow reads, block writes
-- EXCLUSIVE: Block reads and writes
-- DEFAULT: Let MySQL choose
```

## Schema Migration Best Practices

1. **Always test in non-production first**
2. **Check algorithm before production DDL**:
   ```sql
   -- Dry run with ALGORITHM and LOCK
   ALTER TABLE large_table
     ADD INDEX idx_new (column),
     ALGORITHM=INPLACE, LOCK=NONE;
   ```
3. **Monitor during DDL**:
   - CPU usage
   - IOPS
   - Replication lag (if replicas exist)
4. **Use pt-online-schema-change for risky operations**
5. **Schedule during low-traffic windows**
6. **Have rollback plan ready**

## Schema Analysis Queries

### Find tables without primary keys
```sql
SELECT t.table_schema, t.table_name
FROM information_schema.tables t
LEFT JOIN information_schema.table_constraints tc
  ON t.table_schema = tc.table_schema
  AND t.table_name = tc.table_name
  AND tc.constraint_type = 'PRIMARY KEY'
WHERE tc.constraint_name IS NULL
  AND t.table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
  AND t.table_type = 'BASE TABLE';
```

### Find tables with inefficient data types
```sql
-- VARCHAR columns that could be smaller integers
SELECT table_schema, table_name, column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE data_type = 'varchar'
  AND column_name LIKE '%_id'
  AND table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys');
```

### Check foreign key relationships
```sql
SELECT
  CONSTRAINT_NAME,
  TABLE_NAME,
  COLUMN_NAME,
  REFERENCED_TABLE_NAME,
  REFERENCED_COLUMN_NAME,
  DELETE_RULE,
  UPDATE_RULE
FROM information_schema.KEY_COLUMN_USAGE
WHERE REFERENCED_TABLE_NAME IS NOT NULL
  AND TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME, CONSTRAINT_NAME;
```
"""
    return prompt


@app.tool()
async def query_optimization_guidance() -> str:
    """Retrieves query optimization techniques and best practices.

    This tool returns comprehensive guidance for analyzing and optimizing MySQL queries,
    applicable to both RDS MySQL and Aurora MySQL.

    The guidance covers:
    - EXPLAIN output interpretation (JSON and traditional formats)
    - Index selection strategies and covering indexes
    - Common query anti-patterns and solutions
    - Query rewriting techniques (JOIN vs subquery, EXISTS vs IN)
    - Execution plan analysis (access types, join types, extra flags)
    - Performance Schema usage for query profiling
    - Slow query log analysis
    - Query hints and optimizer directives

    EXPLAIN analysis covered:
    - Access types: const, eq_ref, ref, range, index, ALL
    - Join types and algorithms
    - Index usage and key length
    - Rows examined vs returned
    - Extra flags: Using filesort, Using temporary, Using index, etc.

    Common anti-patterns detected:
    - Leading wildcards in LIKE: LIKE '%pattern'
    - Functions on indexed columns: WHERE YEAR(date_col) = 2024
    - Implicit type conversions: WHERE int_col = '123'
    - SELECT * when only few columns needed
    - Missing indexes causing full table scans
    - OR conditions on different columns

    Use this tool when:
    - Analyzing slow queries from slow query log
    - Understanding EXPLAIN output
    - Optimizing existing queries
    - Reviewing query patterns for best practices

    Returns: Complete query optimization guidance as markdown text.
    """

    # For now, return a comprehensive inline prompt
    # In production, this would load from a file
    prompt = """# MySQL Query Optimization Guidance

## EXPLAIN Analysis

### Understanding EXPLAIN Output

```sql
EXPLAIN FORMAT=JSON
SELECT u.name, o.total
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE u.email = 'test@example.com'
  AND o.created_at > '2024-01-01';
```

### Access Types (best to worst)

1. **const**: Single row match via primary key or unique index
   ```sql
   WHERE id = 123
   ```

2. **eq_ref**: One row match per previous table combination
   ```sql
   JOIN users u ON o.user_id = u.id  -- u.id is primary key
   ```

3. **ref**: Multiple rows match on non-unique index
   ```sql
   WHERE user_id = 123  -- user_id is indexed but not unique
   ```

4. **range**: Index scan for range conditions
   ```sql
   WHERE created_at BETWEEN '2024-01-01' AND '2024-12-31'
   ```

5. **index**: Full index scan (better than ALL, but still expensive)
   ```sql
   SELECT id FROM users  -- Scans entire index
   ```

6. **ALL**: Full table scan (worst case)
   ```sql
   WHERE YEAR(created_at) = 2024  -- Can't use index
   ```

### Key EXPLAIN Columns

- **type**: Access type (see above)
- **possible_keys**: Indexes MySQL considered
- **key**: Index actually used
- **key_len**: Bytes of index used
- **rows**: Estimated rows examined
- **filtered**: % of rows filtered by WHERE
- **Extra**: Additional information

### Extra Column Flags

✅ **Good**:
- `Using index`: Covering index (doesn't read table)
- `Using index condition`: Index pushdown optimization

⚠️ **Concerning**:
- `Using filesort`: Sort can't use index (may be unavoidable)
- `Using temporary`: Creates temp table
- `Using where`: Filters after reading rows

❌ **Bad**:
- `Using join buffer`: No useful index for join
- No index mentioned with large row count

## Index Optimization Strategies

### Covering Indexes

✅ **Covering index** (doesn't read table):
```sql
-- Query only needs indexed columns
SELECT user_id, created_at
FROM orders
WHERE user_id = 123
ORDER BY created_at DESC;

-- Index covers all columns in query
CREATE INDEX idx_user_created ON orders(user_id, created_at);

-- EXPLAIN shows "Using index"
```

### Composite Index Order

✅ **Correct order** (equality predicates first):
```sql
-- Query
SELECT * FROM orders
WHERE user_id = 123
  AND status = 'pending'
  AND created_at > '2024-01-01'
ORDER BY created_at DESC;

-- Optimal index: equality → equality → range/sort
CREATE INDEX idx_orders_lookup
ON orders(user_id, status, created_at);
```

❌ **Wrong order**:
```sql
-- Range first prevents use of subsequent columns
CREATE INDEX idx_wrong ON orders(created_at, user_id, status);
```

### Leftmost Prefix Rule

```sql
-- Index on (a, b, c)
CREATE INDEX idx_abc ON table1(a, b, c);

-- Can use index for:
WHERE a = 1
WHERE a = 1 AND b = 2
WHERE a = 1 AND b = 2 AND c = 3

-- CANNOT use index for:
WHERE b = 2
WHERE c = 3
WHERE b = 2 AND c = 3
```

## Common Anti-Patterns

### 1. Functions on Indexed Columns

❌ **Bad** (can't use index):
```sql
SELECT * FROM users
WHERE YEAR(created_at) = 2024;

SELECT * FROM users
WHERE LOWER(email) = 'test@example.com';
```

✅ **Good** (can use index):
```sql
SELECT * FROM users
WHERE created_at >= '2024-01-01'
  AND created_at < '2025-01-01';

-- Create functional index (MySQL 8.0+)
CREATE INDEX idx_email_lower ON users((LOWER(email)));
SELECT * FROM users WHERE LOWER(email) = 'test@example.com';

-- Or store normalized value
ALTER TABLE users ADD COLUMN email_lower VARCHAR(255) AS (LOWER(email)) STORED;
CREATE INDEX idx_email_lower ON users(email_lower);
```

### 2. Leading Wildcards in LIKE

❌ **Bad** (full table scan):
```sql
SELECT * FROM products WHERE name LIKE '%phone%';
```

✅ **Good** (can use index):
```sql
-- Index can be used
SELECT * FROM products WHERE name LIKE 'phone%';

-- For full-text search, use FULLTEXT index
ALTER TABLE products ADD FULLTEXT idx_name_ft (name);
SELECT * FROM products WHERE MATCH(name) AGAINST('phone');
```

### 3. Implicit Type Conversions

❌ **Bad** (can't use index on int column):
```sql
SELECT * FROM users WHERE user_id = '123';  -- String literal for INT column
```

✅ **Good**:
```sql
SELECT * FROM users WHERE user_id = 123;  -- INT literal
```

### 4. SELECT * Instead of Specific Columns

❌ **Bad**:
```sql
SELECT * FROM orders WHERE user_id = 123;
-- Returns 20 columns, only need 3
```

✅ **Good**:
```sql
SELECT id, total, created_at FROM orders WHERE user_id = 123;
-- Can use covering index
CREATE INDEX idx_user_order ON orders(user_id, id, total, created_at);
```

### 5. OR Conditions on Different Columns

❌ **Bad** (can't use index efficiently):
```sql
SELECT * FROM users
WHERE email = 'test@example.com'
   OR phone = '555-1234';
-- MySQL can't use both indexes efficiently
```

✅ **Good** (use UNION):
```sql
SELECT * FROM users WHERE email = 'test@example.com'
UNION
SELECT * FROM users WHERE phone = '555-1234';
-- Uses index on email, then index on phone
```

### 6. NOT IN with Subqueries

❌ **Bad** (poor performance):
```sql
SELECT * FROM users
WHERE id NOT IN (SELECT user_id FROM orders);
```

✅ **Good** (use LEFT JOIN):
```sql
SELECT u.*
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.user_id IS NULL;
```

## Query Rewriting Techniques

### Subquery vs JOIN

**Correlated subquery** (executes N times):
```sql
❌ SELECT *
FROM orders o
WHERE o.total > (
  SELECT AVG(total)
  FROM orders
  WHERE user_id = o.user_id
);
```

**JOIN with derived table** (executes once):
```sql
✅ SELECT o.*
FROM orders o
JOIN (
  SELECT user_id, AVG(total) as avg_total
  FROM orders
  GROUP BY user_id
) avg_orders ON o.user_id = avg_orders.user_id
WHERE o.total > avg_orders.avg_total;
```

### EXISTS vs IN

For large subquery result sets, `EXISTS` is faster:
```sql
-- EXISTS (stops at first match)
✅ SELECT * FROM users u
WHERE EXISTS (
  SELECT 1 FROM orders o
  WHERE o.user_id = u.id
);

-- IN (materializes entire subquery)
⚠️ SELECT * FROM users u
WHERE u.id IN (
  SELECT user_id FROM orders
);
```

### LIMIT with Offset Optimization

❌ **Bad** (scans offset + limit rows):
```sql
-- Page 1000: scans 10,000 rows, returns 10
SELECT * FROM orders
ORDER BY created_at DESC
LIMIT 10 OFFSET 9990;
```

✅ **Good** (use key-based pagination):
```sql
-- Store last seen ID from previous page
SELECT * FROM orders
WHERE id < 123456  -- Last ID from previous page
ORDER BY id DESC
LIMIT 10;
```

## Monitoring and Profiling

### Slow Query Log Analysis

```bash
# Enable slow query log on RDS
CALL mysql.rds_set_configuration('slow_query_log', 1);
CALL mysql.rds_set_configuration('long_query_time', 1);

# Download and analyze
aws rds download-db-log-file-portion \
  --db-instance-identifier my-instance \
  --log-file-name slowquery/mysql-slowquery.log

# Use pt-query-digest (Percona Toolkit)
pt-query-digest mysql-slowquery.log
```

### Performance Schema Queries

```sql
-- Top queries by total execution time
SELECT
  DIGEST_TEXT,
  COUNT_STAR,
  ROUND(AVG_TIMER_WAIT/1000000000000, 2) AS avg_sec,
  ROUND(SUM_TIMER_WAIT/1000000000000, 2) AS total_sec
FROM performance_schema.events_statements_summary_by_digest
ORDER BY SUM_TIMER_WAIT DESC
LIMIT 10;

-- Queries creating temp tables
SELECT
  DIGEST_TEXT,
  COUNT_STAR,
  SUM_CREATED_TMP_TABLES,
  SUM_CREATED_TMP_DISK_TABLES
FROM performance_schema.events_statements_summary_by_digest
WHERE SUM_CREATED_TMP_TABLES > 0
ORDER BY SUM_CREATED_TMP_DISK_TABLES DESC
LIMIT 10;

-- Table scans (no index used)
SELECT
  OBJECT_SCHEMA,
  OBJECT_NAME,
  COUNT_READ,
  COUNT_FETCH,
  SUM_TIMER_WAIT/1000000000000 AS total_sec
FROM performance_schema.table_io_waits_summary_by_table
WHERE OBJECT_SCHEMA NOT IN ('mysql', 'performance_schema', 'sys')
ORDER BY SUM_TIMER_WAIT DESC;
```

## Advanced Techniques

### Query Hints

```sql
-- Force index usage
SELECT * FROM orders FORCE INDEX (idx_user_created)
WHERE user_id = 123;

-- Ignore index
SELECT * FROM orders IGNORE INDEX (idx_created)
WHERE created_at > '2024-01-01';

-- Join order hint (MySQL 8.0+)
SELECT /*+ JOIN_ORDER(o, u) */ *
FROM orders o
JOIN users u ON o.user_id = u.id;
```

### Derived Table Optimization (MySQL 8.0+)

```sql
-- Automatic derived table materialization
SELECT *
FROM (
  SELECT user_id, SUM(total) as total_spent
  FROM orders
  GROUP BY user_id
) user_totals
WHERE total_spent > 1000;

-- MySQL materializes subquery, creates temp table with index
```

### Common Table Expressions (CTEs)

```sql
-- Recursive CTE for hierarchical data
WITH RECURSIVE category_tree AS (
  SELECT id, name, parent_id, 0 as level
  FROM categories
  WHERE parent_id IS NULL

  UNION ALL

  SELECT c.id, c.name, c.parent_id, ct.level + 1
  FROM categories c
  JOIN category_tree ct ON c.parent_id = ct.id
)
SELECT * FROM category_tree;
```

## Optimization Checklist

Before making index changes:

1. ✅ Captured EXPLAIN plan
2. ✅ Identified actual bottleneck (rows examined vs returned)
3. ✅ Considered query rewrite before adding index
4. ✅ Checked existing indexes for coverage
5. ✅ Validated index will be used (not too selective/not selective enough)
6. ✅ Estimated index size and write overhead
7. ✅ Tested in non-production
8. ✅ Measured before/after performance

Remember: Indexes speed up reads but slow down writes. Only add indexes that provide measurable benefit.
"""
    return prompt


@app.tool()
async def mysql_84_migration_guidance() -> str:
    """Retrieves MySQL 8.4 migration planning and compatibility guidance.

    This tool returns comprehensive guidance for planning and executing migrations
    from MySQL 8.0 to MySQL 8.4, or from Aurora MySQL 3.x to Aurora MySQL 4.x.

    The guidance covers:
    - Breaking changes between MySQL 8.0 and 8.4
    - Deprecated features and their replacements
    - Removed system variables and parameters
    - SQL syntax changes and incompatibilities
    - Character set and collation changes
    - Aurora MySQL 3.x to 4.x specific considerations
    - Testing and validation strategies
    - Rollback planning

    Major changes covered:
    - utf8mb3 deprecation (use utf8mb4)
    - Removed authentication plugins (mysql_native_password)
    - Removed system variables (query_cache, etc.)
    - INFORMATION_SCHEMA changes
    - Reserved keyword additions
    - Default parameter value changes
    - Replication compatibility

    Migration phases:
    1. Pre-migration assessment (compatibility check)
    2. Testing in non-production
    3. Application compatibility validation
    4. Performance baseline comparison
    5. Production migration planning
    6. Post-migration validation

    Use this tool when:
    - Planning upgrade to MySQL 8.4
    - Migrating Aurora MySQL 3.x to 4.x
    - Assessing migration impact and risk
    - Creating migration runbooks

    Returns: Complete MySQL 8.4 migration guidance as markdown text.
    """
    # Load from the actual reference file in the repository
    reference_path = Path(__file__).parent.parent.parent.parent / 'skills' / 'aurora-mysql' / 'references' / 'mysql-84-changes.md'
    if reference_path.exists():
        return reference_path.read_text(encoding='utf-8')
    else:
        # Fallback if file doesn't exist
        return """# MySQL 8.4 Migration Guidance

Detailed MySQL 8.4 migration guidance will be loaded from the skills/aurora-mysql/references/mysql-84-changes.md file.

Key areas covered:
- Breaking changes between MySQL 8.0 and 8.4
- Deprecated and removed features
- Character set and collation changes
- Aurora MySQL 3.x to 4.x migration
- Testing and validation strategies

Please ensure the reference file exists in the repository.
"""


def main():
    """Run the MCP server."""
    app.run()


if __name__ == '__main__':
    main()
