# RDS MySQL Performance Review Skill

## Purpose

Guide AI assistants through evidence-based performance analysis and optimization of Amazon RDS MySQL instances, covering schema design, indexing, query optimization, and RDS-specific operational patterns.

## Core Principles

1. **Evidence-Based**: All recommendations must be backed by measured data (metrics, EXPLAIN plans, query logs)
2. **RDS-Aware**: Account for RDS limitations, features, and best practices
3. **Safe Changes**: Prioritize online operations; validate impact before destructive changes
4. **Minimal Intervention**: Only recommend changes that address measured bottlenecks
5. **Rollback Planning**: Include rollback procedures for all schema/parameter changes

## Workflow

### Phase 1: Establish Context

Before making recommendations, gather:

1. **Workload Characteristics**
   - Query volume and distribution (read/write ratio)
   - Connection patterns and pooling
   - Peak vs. average load
   - Application access patterns

2. **RDS Environment**
   - Instance class and engine version
   - Storage type (gp2, gp3, io1, io2) and IOPS provisioned
   - Multi-AZ configuration
   - Read replicas in use
   - Parameter group settings
   - Maintenance window and backup configuration

3. **Current Performance State**
   - CloudWatch metrics: CPU, connections, IOPS, latency, replica lag
   - Slow query log analysis
   - `SHOW PROCESSLIST` snapshot
   - Performance Schema statistics (if enabled)
   - Recent schema changes or migrations

**Action**: Use diagnostic scripts to collect this data systematically.

### Phase 2: Consult References

Review relevant reference materials based on identified issues:

- `rds-best-practices.md`: RDS operational patterns
- `query-optimization.md`: Query tuning techniques
- `cloudwatch-metrics.md`: Metric interpretation
- MySQL version-specific documentation

### Phase 3: Analysis & Recommendations

Generate recommendations in priority order based on potential impact:

#### 3.1 Schema Design Review

**Primary Keys**
- ✅ Use `BIGINT UNSIGNED AUTO_INCREMENT` for monotonic integer keys
- ❌ Avoid random UUIDs as clustered index (causes page splits)
- ✅ If UUIDs required, store as `BINARY(16)` in secondary index, use surrogate PK
- ✅ Ensure all tables have explicit primary keys

**Data Types**
- ✅ Use smallest appropriate data type
- ✅ Prefer `DATETIME` over `TIMESTAMP` for dates beyond 2038
- ✅ Use `utf8mb4` character set (not `utf8`)
- ✅ Prefer `NOT NULL` columns when possible (simplifies indexing)
- ❌ Avoid `ENUM` types; use lookup tables for extensibility

**Normalization**
- ✅ Target 3NF for transactional tables
- ✅ Denormalize only with measured performance justification
- ✅ Document denormalization decisions and update patterns

**Example Issue Detection**:
```sql
-- Identify tables without primary keys
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

#### 3.2 Index Optimization

**Index Design Rules**
- ✅ Composite index order: equality predicates first, then range/sort columns
- ✅ Leverage leftmost prefix rule
- ✅ Remember: secondary indexes implicitly include primary key
- ✅ Consider covering indexes for frequent queries
- ❌ Avoid redundant indexes (e.g., index on `(a)` when `(a,b)` exists)
- ❌ Remove unused indexes (check `performance_schema.table_io_waits_summary_by_index_usage`)

**Index Analysis Queries**:
```sql
-- Find missing indexes (tables with high row reads, low index reads)
SELECT object_schema, object_name,
       count_read, count_fetch
FROM performance_schema.table_io_waits_summary_by_table
WHERE object_schema NOT IN ('mysql', 'performance_schema', 'sys')
  AND count_read > count_fetch * 10
ORDER BY count_read DESC;

-- Identify unused indexes
SELECT object_schema, object_name, index_name
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE index_name IS NOT NULL
  AND index_name != 'PRIMARY'
  AND count_star = 0
  AND object_schema NOT IN ('mysql', 'performance_schema', 'sys')
ORDER BY object_schema, object_name;
```

**RDS Consideration**: Dropping indexes is online in MySQL 5.6+; adding indexes uses ALGORITHM=INPLACE when possible.

#### 3.3 Query Optimization

**EXPLAIN Analysis Red Flags**
- ❌ `type: ALL` (full table scan)
- ❌ `type: index` (full index scan, only marginally better)
- ❌ `Extra: Using filesort` (sort operation not using index)
- ❌ `Extra: Using temporary` (requires temp table)
- ❌ `Extra: Using where` with `type: ALL` (filtering after full scan)
- ⚠️ `rows` examined >> `rows` returned (inefficient filtering)

**Query Patterns**
- ✅ Use cursor pagination (`WHERE id > ?`) instead of `OFFSET`
- ✅ Batch inserts (500-5,000 rows per statement)
- ✅ Limit result sets with `LIMIT` clauses
- ❌ Avoid `SELECT *`; specify only needed columns
- ❌ Avoid functions on indexed columns in WHERE (`WHERE DATE(created_at) = ?`)
- ✅ Use prepared statements (reduces parsing, enables query cache in older versions)

**N+1 Query Detection**
- Look for repeated similar queries in slow query log
- Check for queries inside application loops
- Recommend JOIN, IN clauses, or batch fetching

**Example**:
```sql
-- Instead of N queries:
SELECT * FROM orders WHERE user_id = ?; -- Repeated N times

-- Use batch fetch:
SELECT * FROM orders WHERE user_id IN (?, ?, ...);
```

#### 3.4 Transaction & Locking

**Isolation Levels**
- Default: `REPEATABLE READ` (provides snapshot consistency)
- Consider: `READ COMMITTED` for high-contention workloads (reduces gap locks)
- Validate: Application logic handles phantoms if switching from RR to RC

**Lock Management**
- ✅ Access rows in consistent order across transactions (prevents deadlocks)
- ✅ Keep transactions short and focused
- ❌ Minimize use of `SELECT ... FOR UPDATE`
- ✅ Monitor `SHOW ENGINE INNODB STATUS` for deadlocks
- ✅ Set appropriate `innodb_lock_wait_timeout` (default 50s)

**RDS-Specific**: Use RDS Performance Insights to identify lock wait events.

#### 3.5 Partitioning

**When to Partition**
- Tables > 50-100M rows
- Time-series data with clear archival patterns
- Query patterns that frequently filter by partition key

**Partition Requirements**
- Partition column must be in all UNIQUE and PRIMARY KEY constraints
- Use `RANGE` partitioning for time-series (most common)
- Include `MAXVALUE` catch-all partition
- Plan partition maintenance procedures (add/drop partitions)

**Example**:
```sql
CREATE TABLE events (
  id BIGINT UNSIGNED AUTO_INCREMENT,
  event_date DATE NOT NULL,
  event_type VARCHAR(50),
  data JSON,
  PRIMARY KEY (id, event_date),
  KEY idx_event_type (event_type, event_date)
) PARTITION BY RANGE (TO_DAYS(event_date)) (
  PARTITION p202401 VALUES LESS THAN (TO_DAYS('2024-02-01')),
  PARTITION p202402 VALUES LESS THAN (TO_DAYS('2024-03-01')),
  PARTITION pmax VALUES LESS THAN MAXVALUE
);
```

**RDS Consideration**: Partition management operations are online but can be resource-intensive.

#### 3.6 RDS Operations

**Parameter Groups**
- Review key parameters:
  - `max_connections`: Adequate for workload + buffer
  - `innodb_buffer_pool_size`: 70-80% of instance RAM for dedicated DB
  - `innodb_flush_log_at_trx_commit`: Balance durability vs. performance (1=durable, 2=fast)
  - `slow_query_log`: Enabled for diagnostics
  - `long_query_time`: Set to 1-2 seconds
  - `innodb_log_file_size`: 25% of buffer pool size (auto-managed in RDS 8.0+)

**Connection Pooling**
- Application-side: HikariCP, pgbouncer-equivalent (ProxySQL)
- RDS Proxy: Managed connection pooling, IAM auth, reduced failover time
- Monitor: `Threads_connected`, `Threads_running`, `Max_used_connections`

**Storage Optimization**
- **gp2**: Baseline 3 IOPS/GB, burst to 3,000 IOPS (good for dev/test)
- **gp3**: 3,000 IOPS baseline, configurable up to 16,000 IOPS (best price/performance)
- **io1/io2**: Provisioned IOPS, low latency (production workloads)
- Monitor: `ReadIOPS`, `WriteIOPS`, `ReadLatency`, `WriteLatency`

**Read Replicas**
- Use for read scaling (not for HA; use Multi-AZ for HA)
- Monitor replica lag: `ReplicaLag` CloudWatch metric
- Consider Aurora for more replicas and faster replication

**Backups & Maintenance**
- Automated backups: Enable with 7-30 day retention
- Maintenance window: Schedule during low-traffic periods
- Blue/green deployments: For major upgrades (RDS MySQL 8.0.28+)

### Phase 4: Implementation Plan

For each recommendation, provide:

1. **Change Description**: What will be modified
2. **Expected Impact**: Performance improvement, resource usage changes
3. **Risk Assessment**: Downtime, data migration, rollback complexity
4. **Implementation Steps**: Specific SQL or AWS CLI commands
5. **Validation**: How to verify the change worked
6. **Rollback**: How to undo if needed

**Example**:
```markdown
## Recommendation: Add Composite Index on orders(customer_id, created_at)

**Current State**: Query scanning 2.3M rows for customer order history
**Expected Impact**: Reduce query time from 2.1s to <50ms
**Risk**: Low (online index creation, no data change)

**Implementation**:
```sql
CREATE INDEX idx_customer_orders
  ON orders(customer_id, created_at)
  ALGORITHM=INPLACE, LOCK=NONE;
```

**Validation**:
```sql
EXPLAIN SELECT * FROM orders
WHERE customer_id = 12345
ORDER BY created_at DESC LIMIT 20;
-- Should show: type: ref, key: idx_customer_orders, rows: ~20
```

**Rollback**:
```sql
DROP INDEX idx_customer_orders ON orders;
```

**Monitoring**: Track query performance via slow query log and RDS Performance Insights.
```

### Phase 5: Validation & Monitoring

After implementing changes:

1. **Immediate Validation**
   - Re-run EXPLAIN plans to confirm index usage
   - Check slow query log for improvements
   - Monitor error logs for issues

2. **Ongoing Monitoring**
   - CloudWatch dashboards for key metrics
   - RDS Performance Insights for query-level analysis
   - Set up CloudWatch alarms for regressions
   - Document baseline vs. post-change metrics

3. **A/B Testing** (when possible)
   - Test changes on read replica first
   - Use feature flags for query changes
   - Compare metrics before/after

## Guardrails

- **Never** recommend destructive operations without explicit user approval
- **Always** provide rollback procedures for schema changes
- **Always** use `ALGORITHM=INPLACE, LOCK=NONE` when available
- **Never** assume MySQL version capabilities; check version-specific docs
- **Always** consider RDS limitations (no SUPER privilege, no host access)
- **Always** test recommendations on non-production environments first

## Version-Specific Notes

### MySQL 5.7 (End of RDS support: Feb 2024)
- Online DDL limited compared to 8.0
- No instant ADD COLUMN
- Performance Schema less complete

### MySQL 8.0
- Instant ADD COLUMN at end of table
- Improved online DDL (INSTANT, INPLACE algorithms)
- Better Performance Schema and sys schema
- Descending indexes supported

### RDS-Specific Features
- Enhanced Monitoring (OS-level metrics)
- Performance Insights (query-level analysis)
- RDS Proxy (connection pooling)
- Automated backups and point-in-time recovery

## Success Metrics

Track these KPIs before and after optimization:

- Query latency (p50, p95, p99)
- Slow query count and time
- CPU utilization
- IOPS and storage throughput
- Connection count and wait events
- Replica lag (if applicable)
- Application-level response times

## When to Escalate

Recommend alternative approaches when:

- Current instance class is undersized for workload
- Storage IOPS limits are consistently maxed
- Architectural changes needed (sharding, caching layer)
- Migration to Aurora MySQL would provide significant benefits
- Application-level optimization required (caching, query reduction)

## References

- `rds-best-practices.md`: RDS operational guidance
- `query-optimization.md`: Query tuning patterns
- `cloudwatch-metrics.md`: Metrics reference
- [AWS RDS MySQL Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_MySQL.html)
- [MySQL 8.0 Reference Manual](https://dev.mysql.com/doc/refman/8.0/en/)
