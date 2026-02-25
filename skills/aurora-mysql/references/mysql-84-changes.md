# MySQL 8.4 Breaking Changes and Migration Guide

## Overview

Aurora MySQL 4.x is based on MySQL 8.4, which includes several breaking changes from MySQL 8.0. This guide covers what breaks, what's removed, and how to prepare for upgrade.

**Key Timeline**:
- MySQL 8.0: Innovation release (ended April 2024)
- MySQL 8.4: LTS release (support until April 2032)
- Aurora MySQL 3.x: Based on MySQL 8.0
- Aurora MySQL 4.x: Based on MySQL 8.4

## Critical Breaking Changes

### 1. mysql_native_password Disabled by Default

**What Changed**:
- MySQL 8.4 defaults to `caching_sha2_password`
- `mysql_native_password` plugin is **disabled** by default
- Older client libraries that only support native password will fail to connect

**Error You'll See**:
```
ERROR 2061 (HY000): Authentication plugin 'mysql_native_password' cannot be loaded:
plugin not enabled
```

**Pre-Upgrade Check**:
```sql
-- Find users using mysql_native_password
SELECT user, host, plugin
FROM mysql.user
WHERE plugin = 'mysql_native_password';
```

**Fix Option 1: Switch to caching_sha2_password** (Recommended)
```sql
-- Update user authentication
ALTER USER 'myapp'@'%' IDENTIFIED WITH caching_sha2_password BY 'password';
FLUSH PRIVILEGES;
```

**Fix Option 2: Enable mysql_native_password** (Not Recommended)
```bash
# Add to parameter group
aws rds modify-db-parameter-group \
  --db-parameter-group-name aurora-mysql84-params \
  --parameters "ParameterName=mysql_native_password,ParameterValue=ON,ApplyMethod=immediate"
```

**Client Compatibility**:
- **Python**: `PyMySQL >= 0.9.3` or `mysql-connector-python >= 8.0`
- **Java**: `mysql-connector-java >= 8.0.9`
- **Node.js**: `mysql2 >= 1.6.0`
- **PHP**: `php >= 7.4` with `mysqlnd`
- **Go**: `go-sql-driver/mysql >= 1.5.0`

### 2. Removed System Variables

These variables **no longer exist** in 8.4. Remove them from parameter groups or MySQL won't start.

**Removed Variables**:
```bash
# These will cause startup failure in 8.4
binlog_transaction_dependency_tracking  # Removed
old_alter_table                         # Removed
innodb_undo_tablespaces                 # Now auto-managed
```

**Pre-Upgrade Audit**:
```sql
-- Check parameter group for removed variables
aws rds describe-db-parameters \
  --db-parameter-group-name your-parameter-group \
  --query 'Parameters[?ParameterName==`binlog_transaction_dependency_tracking`]'

-- Remove from parameter group BEFORE upgrade
aws rds modify-db-parameter-group \
  --db-parameter-group-name your-parameter-group \
  --parameters "ParameterName=binlog_transaction_dependency_tracking,ApplyMethod=immediate,ResetAll Method=immediate"
```

### 3. Replication Metadata Must Use TABLE Format

FILE-based replication metadata (relay-log.info, master.info) is removed.

**Pre-Upgrade Check**:
```sql
-- Must be 'TABLE', not 'FILE'
SHOW VARIABLES LIKE 'master_info_repository';
SHOW VARIABLES LIKE 'relay_log_info_repository';

-- If either shows 'FILE', switch to TABLE
SET GLOBAL master_info_repository = 'TABLE';
SET GLOBAL relay_log_info_repository = 'TABLE';
```

**Aurora Note**: Aurora manages this automatically, but verify before upgrade.

### 4. GROUP BY No Longer Implies ORDER BY

**What Changed**:
- MySQL 8.0: `GROUP BY` implicitly sorted results
- MySQL 8.4: `GROUP BY` does **not** sort (matches SQL standard)

**Impact**: Queries relying on implicit ordering will return results in undefined order.

**Bad** (breaks in 8.4):
```sql
-- In 8.0: Returns results sorted by customer_id
-- In 8.4: Returns results in arbitrary order
SELECT customer_id, COUNT(*)
FROM orders
GROUP BY customer_id;
```

**Good** (explicit ORDER BY):
```sql
SELECT customer_id, COUNT(*)
FROM orders
GROUP BY customer_id
ORDER BY customer_id;  -- Explicit ordering
```

**Find Queries That May Break**:
```sql
-- Search stored procedures for GROUP BY without ORDER BY
SELECT routine_name, routine_definition
FROM information_schema.routines
WHERE routine_definition LIKE '%GROUP BY%'
  AND routine_definition NOT LIKE '%ORDER BY%';
```

## Deprecated Features (Still Work but Will Be Removed)

### utf8mb3 Charset Deprecated

**What's Changing**:
- `utf8` (alias for `utf8mb3`) is deprecated
- Use `utf8mb4` instead (full Unicode support)
- `utf8mb3` will be removed in future version

**Migration**:
```sql
-- Convert tables from utf8 to utf8mb4
ALTER TABLE users
CONVERT TO CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

-- Update default charset for database
ALTER DATABASE mydb
CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;
```

### OLD_PASSWORD() Function Removed

**Removed**: `OLD_PASSWORD()` function for ancient MySQL 4.1 password format.

**Check**:
```sql
-- Find any references in stored procedures
SELECT routine_name, routine_definition
FROM information_schema.routines
WHERE routine_definition LIKE '%OLD_PASSWORD%';
```

## New Features and Improvements

### 1. Improved Optimizer

**Hypergraph Optimizer** (experimental in 8.4):
- Better join order optimization
- Cost model improvements
- **May change query plans** - test critical queries

**Enable for Testing**:
```sql
SET SESSION optimizer_switch = 'hypergraph_optimizer=on';

EXPLAIN FORMAT=TREE
SELECT * FROM orders o
JOIN customers c ON c.id = o.customer_id
WHERE c.country = 'US';
```

### 2. Instant ADD COLUMN Enhancements

More column operations are instant (no table rebuild):

```sql
-- Instant operations in 8.4
ALTER TABLE users
ADD COLUMN preferences JSON,          -- Instant
ADD COLUMN status VARCHAR(20) DEFAULT 'active',  -- Instant
ALGORITHM=INSTANT;
```

### 3. Performance Schema Enhancements

New instrumentation for:
- `memory/temptable/*` (critical for Aurora reader monitoring)
- Improved query attribution
- Better connection tracking

```sql
-- Enable TempTable monitoring
UPDATE performance_schema.setup_instruments
SET ENABLED = 'YES', TIMED = 'YES'
WHERE NAME LIKE 'memory/temptable/%';
```

### 4. JSON Schema Validation

Built-in JSON schema validation:

```sql
ALTER TABLE users
ADD COLUMN metadata JSON,
ADD CONSTRAINT check_metadata
  CHECK (JSON_SCHEMA_VALID('{
    "type": "object",
    "properties": {
      "age": {"type": "number", "minimum": 0, "maximum": 150}
    }
  }', metadata));

-- Valid insert
INSERT INTO users (id, metadata) VALUES (1, '{"age": 30}');

-- Fails validation
INSERT INTO users (id, metadata) VALUES (2, '{"age": 200}');
-- ERROR 3819: Check constraint 'check_metadata' is violated.
```

## Pre-Upgrade Checklist

### 1. Authentication Audit
```sql
-- Check authentication plugins
SELECT user, host, plugin, authentication_string
FROM mysql.user;

-- Users with mysql_native_password need updating
-- OR enable mysql_native_password=ON in parameter group
```

### 2. Parameter Group Cleanup
```bash
# Check for removed parameters
aws rds describe-db-parameters \
  --db-parameter-group-name your-pg \
  --query 'Parameters[?ParameterName==`binlog_transaction_dependency_tracking` || ParameterName==`old_alter_table` || ParameterName==`innodb_undo_tablespaces`]'

# Remove them before upgrade
```

### 3. Application SQL Audit
```sql
-- Find GROUP BY without ORDER BY in stored procedures
SELECT routine_schema, routine_name
FROM information_schema.routines
WHERE routine_definition LIKE '%GROUP BY%'
  AND routine_definition NOT LIKE '%ORDER BY%'
  AND routine_schema NOT IN ('mysql', 'sys', 'information_schema', 'performance_schema');

-- Check application code for same pattern
-- Grep codebase: grep -r "GROUP BY" --include="*.sql" | grep -v "ORDER BY"
```

### 4. Charset/Collation Check
```sql
-- Find utf8 (utf8mb3) tables
SELECT table_schema, table_name, table_collation
FROM information_schema.tables
WHERE table_collation LIKE 'utf8\_%'
  AND table_schema NOT IN ('mysql', 'sys', 'information_schema', 'performance_schema');

-- Plan migration to utf8mb4
```

### 5. Client Library Versions
```bash
# Python
pip list | grep -i mysql
# Ensure: PyMySQL >= 0.9.3 or mysql-connector-python >= 8.0

# Java
# Ensure: mysql-connector-java >= 8.0.9 in pom.xml/build.gradle

# Node.js
npm list | grep mysql
# Ensure: mysql2 >= 1.6.0
```

### 6. Query Plan Testing
```sql
-- Export query plans from 8.0
EXPLAIN FORMAT=JSON
SELECT * FROM critical_query;

-- Save output, compare after upgrade
-- Watch for performance regressions
```

## Migration Strategy

### Option 1: Blue/Green Deployment (Recommended)

**Steps**:
1. Create Aurora MySQL 4.x cluster from snapshot
2. Run test suite against new cluster
3. Perform load testing
4. Switch application to new cluster
5. Monitor for issues
6. Keep old cluster as rollback option for 24-48 hours

```bash
# Create snapshot of current cluster
aws rds create-db-cluster-snapshot \
  --db-cluster-identifier myapp-aurora3 \
  --db-cluster-snapshot-identifier myapp-pre-upgrade-snapshot

# Restore to new Aurora 4.x cluster
aws rds restore-db-cluster-from-snapshot \
  --db-cluster-identifier myapp-aurora4 \
  --snapshot-identifier myapp-pre-upgrade-snapshot \
  --engine aurora-mysql \
  --engine-version 8.4.mysql_aurora.4.01.0

# Test on new cluster
# Switch application endpoint
# Keep old cluster running for rollback
```

### Option 2: In-Place Upgrade

**For Non-Production Only**:
```bash
aws rds modify-db-cluster \
  --db-cluster-identifier myapp-dev \
  --engine-version 8.4.mysql_aurora.4.01.0 \
  --allow-major-version-upgrade \
  --apply-immediately
```

**Downtime**: 15-30 minutes typical

### Option 3: Global Database Failover

**For Production with Global Database**:
1. Create 8.4 cluster in secondary region
2. Promote secondary to primary
3. Cutover application to new primary
4. Decommission old primary

## Post-Upgrade Validation

### 1. Verify Version
```sql
SELECT @@version;
-- Should show 8.4.x
```

### 2. Check Authentication
```sql
-- Verify users can connect
-- Test from application servers
mysql -h cluster-endpoint -u appuser -p
```

### 3. Run Test Suite
- Full application test suite
- Load testing for critical paths
- Check for query plan regressions

### 4. Monitor Performance Insights
```bash
# Check for new slow queries or wait events
aws rds describe-db-clusters \
  --db-cluster-identifier myapp \
  --query 'DBClusters[0].PerformanceInsightsEnabled'
```

### 5. Validate Query Plans
```sql
-- Re-run EXPLAIN on critical queries
EXPLAIN FORMAT=TREE
SELECT * FROM critical_query;

-- Compare with pre-upgrade plans
-- Look for:
-- - Different join order
-- - Different index selection
-- - Increased row estimates
```

### 6. Check Error Logs
```bash
# Download and review error log
aws rds download-db-log-file-portion \
  --db-instance-identifier myapp-writer \
  --log-file-name error/mysql-error-running.log
```

## Rollback Plan

### If Using Blue/Green
```bash
# Simply switch application back to old cluster
# Update DNS or connection strings

# Delete new cluster if necessary
aws rds delete-db-cluster \
  --db-cluster-identifier myapp-aurora4 \
  --skip-final-snapshot
```

### If In-Place Upgrade
```bash
# Restore from snapshot taken before upgrade
aws rds restore-db-cluster-from-snapshot \
  --db-cluster-identifier myapp-rollback \
  --snapshot-identifier myapp-pre-upgrade-snapshot

# Point application to restored cluster
```

**Note**: In-place upgrades cannot be directly rolled back. Always use snapshots.

## Testing Checklist

- [ ] All users can authenticate
- [ ] Critical queries perform as expected
- [ ] Application test suite passes
- [ ] Load testing shows acceptable performance
- [ ] No new errors in application logs
- [ ] No TempTable overflows on readers
- [ ] Connection pooling works correctly
- [ ] Scheduled jobs execute successfully
- [ ] Replication lag is normal (<10ms)
- [ ] Backup/restore tested

## Common Issues and Solutions

### Issue: Authentication Failures After Upgrade

**Symptom**:
```
ERROR 2061: Authentication plugin 'mysql_native_password' cannot be loaded
```

**Solution**:
```sql
-- Enable mysql_native_password
SET GLOBAL mysql_native_password = ON;

-- Or update user to caching_sha2_password
ALTER USER 'myapp'@'%' IDENTIFIED WITH caching_sha2_password BY 'password';
```

### Issue: Query Results in Different Order

**Symptom**: Reports show data in unexpected order after upgrade

**Solution**:
```sql
-- Add explicit ORDER BY to all queries that need specific ordering
SELECT customer_id, SUM(amount)
FROM orders
GROUP BY customer_id
ORDER BY customer_id;  -- Add this
```

### Issue: Startup Failure After Upgrade

**Symptom**: Cluster stuck in "incompatible-parameters" state

**Solution**:
```bash
# Check parameter group for removed variables
# Remove: binlog_transaction_dependency_tracking, old_alter_table, etc.

aws rds modify-db-parameter-group \
  --db-parameter-group-name your-pg \
  --parameters "ParameterName=binlog_transaction_dependency_tracking,ApplyMethod=immediate" \
  --reset-all-parameters
```

## Additional Resources

- [MySQL 8.4 Release Notes](https://dev.mysql.com/doc/relnotes/mysql/8.4/en/)
- [Aurora MySQL 4.x User Guide](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/)
- [MySQL 8.4 Upgrade Guide](https://dev.mysql.com/doc/refman/8.4/en/upgrading.html)
