# RDS MySQL Best Practices Reference

## Connection Management

### RDS Proxy
- Managed connection pooling service
- Reduces connection overhead and failover time
- Supports IAM authentication
- Multiplexes application connections to database connections
- Use for: Lambda functions, applications with connection churn

### Application Connection Pools
- Recommended: HikariCP (Java), SQLAlchemy (Python), Sequelize (Node.js)
- Pool size formula: `connections = ((core_count * 2) + effective_spindle_count)`
- For RDS: Start with 10-20 connections per application server
- Monitor: `Threads_connected`, `Aborted_connects`

### Connection Limits
- Determined by `max_connections` parameter (instance class dependent)
- Default formula: `{DBInstanceClassMemory/12582880}`
- Reserve 10-15% for monitoring and admin connections
- Use `SHOW VARIABLES LIKE 'max_connections';` to check

## Parameter Groups

### Key Parameters

**innodb_buffer_pool_size**
- Most important InnoDB parameter
- 70-80% of instance memory for dedicated database
- 50-60% if sharing with other services
- Monitor: `Innodb_buffer_pool_read_requests` vs `Innodb_buffer_pool_reads`
- Goal: >99% buffer pool hit rate

**innodb_flush_log_at_trx_commit**
- `0`: Write and flush once per second (fastest, risk data loss)
- `1`: Write and flush on every commit (ACID compliant, default)
- `2`: Write on commit, flush once per second (balanced)
- Use `1` for transactional systems, consider `2` for analytics

**innodb_log_file_size**
- Larger = fewer checkpoints, better write performance
- Recommendation: 25% of buffer pool size
- MySQL 8.0.30+: Auto-managed by RDS
- Monitor: Checkpoint age in `SHOW ENGINE INNODB STATUS`

**slow_query_log**
- Enable in production: `slow_query_log = 1`
- Set threshold: `long_query_time = 1` (1 second)
- Log queries without indexes: `log_queries_not_using_indexes = 1`
- Rotate logs regularly to manage storage

**max_connections**
- Set based on workload: `(max_app_servers * connections_per_server) + buffer`
- Too high: Memory waste (each connection uses ~256KB)
- Too low: Connection refused errors
- Monitor: `Max_used_connections` / `max_connections` ratio

**query_cache_size** (MySQL 5.7 only, removed in 8.0)
- Generally: Set to 0 (disabled)
- Reason: Cache mutex contention on write-heavy workloads
- Better: Use application-level caching (Redis, Memcached)

## Storage Configuration

### Storage Types

**General Purpose SSD (gp3)** - Recommended for most workloads
- 3,000 IOPS baseline (independent of size)
- Up to 16,000 IOPS configurable
- Up to 1,000 MB/s throughput
- Best price/performance ratio

**General Purpose SSD (gp2)** - Legacy
- 3 IOPS per GB (minimum 100 IOPS)
- Burst to 3,000 IOPS using burst credits
- Credits deplete on sustained high I/O
- Consider migrating to gp3

**Provisioned IOPS SSD (io1/io2)**
- Use for I/O intensive workloads
- Predictable, low-latency performance
- Up to 64,000 IOPS (io2 Block Express: 256,000 IOPS)
- 0.99.9% durability (io2: 99.999%)

**Magnetic (Standard)** - Deprecated
- Not recommended for production
- Use only for dev/test with low I/O requirements

### Storage Monitoring

**Key CloudWatch Metrics**:
- `ReadIOPS` / `WriteIOPS`: Operations per second
- `ReadLatency` / `WriteLatency`: Milliseconds per operation
- `ReadThroughput` / `WriteThroughput`: Bytes per second
- `DiskQueueDepth`: Outstanding I/O requests

**Performance Issues**:
- High queue depth (>10): Storage bottleneck, consider more IOPS
- High latency (>10ms): Undersized storage, consider io1/io2
- IOPS at limit: Need higher provisioned IOPS or larger gp3 volume

### Storage Scaling

**Autoscaling**:
- Enable storage autoscaling for unpredictable growth
- Set maximum storage threshold
- Scales in 10% increments or 10 GiB (whichever is larger)
- 6-hour cooldown between scaling operations

**Manual Scaling**:
- Can only increase storage size (never decrease)
- Minimum 6 hours between modifications
- Some modifications allow scaling IOPS independently (gp3, io1, io2)

## High Availability

### Multi-AZ Deployments

**Architecture**:
- Synchronous replication to standby in different AZ
- Automatic failover (60-120 seconds)
- Standby cannot serve read traffic (use read replicas for that)

**When to Use**:
- Production databases requiring HA
- RTO requirement < 5 minutes
- Databases that cannot tolerate data loss

**Failover Triggers**:
- Primary instance failure
- Availability Zone failure
- Manual failover via `reboot-db-instance --force-failover`
- OS maintenance or patching

### Read Replicas

**Use Cases**:
- Read scaling (offload SELECT queries)
- Analytics queries (avoid impacting primary)
- Disaster recovery in different region
- Blue-green deployments

**Replication**:
- Asynchronous replication
- Can lag behind primary (monitor `ReplicaLag` metric)
- Promote to standalone instance (breaks replication)

**Limitations**:
- Up to 5 read replicas per primary (15 for Aurora)
- Replica lag depends on write volume and network
- Not for HA (use Multi-AZ for that)

**Best Practices**:
- Monitor replica lag: Alert if > 30 seconds
- Use replica for read-only queries
- Consider Aurora for more replicas and faster replication

## Backup & Recovery

### Automated Backups

**Configuration**:
- Retention period: 1-35 days (7-30 days recommended)
- Backup window: 30-minute window, choose low-traffic time
- Stored in S3 (no additional charge for retention period)
- Enable automatic backups for point-in-time recovery

**Performance Impact**:
- Single-AZ: Brief I/O suspension during snapshot (seconds)
- Multi-AZ: Backup taken from standby (no primary impact)

### Manual Snapshots

**When to Use**:
- Before major schema changes
- Before application upgrades
- Long-term archival (beyond 35 days)
- Copy to different region for DR

**Characteristics**:
- Persist after instance deletion
- Can restore to new instance
- Incremental after first snapshot
- No retention limit

### Point-in-Time Recovery (PITR)

**Capabilities**:
- Restore to any second within retention period
- Creates new DB instance (does not overwrite)
- Useful for: Accidental data deletion, corruption

**Process**:
```bash
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier mydb \
  --target-db-instance-identifier mydb-restored \
  --restore-time 2024-01-15T12:00:00Z
```

## Monitoring & Alerting

### Essential CloudWatch Alarms

1. **High CPU Utilization**
   - Metric: `CPUUtilization`
   - Threshold: > 80% for 10 minutes
   - Action: Investigate queries, consider scaling

2. **Low Free Memory**
   - Metric: `FreeableMemory`
   - Threshold: < 256 MB
   - Action: Increase buffer pool or scale instance

3. **High Connection Count**
   - Metric: `DatabaseConnections`
   - Threshold: > 80% of max_connections
   - Action: Review connection pooling, check for leaks

4. **Replica Lag**
   - Metric: `ReplicaLag`
   - Threshold: > 30 seconds
   - Action: Check write volume, network, replica capacity

5. **Storage Space**
   - Metric: `FreeStorageSpace`
   - Threshold: < 10 GB or < 10%
   - Action: Enable autoscaling or increase storage

### RDS Performance Insights

**Features**:
- SQL-level performance monitoring
- Wait event analysis
- Top SQL identification
- Historical performance data (7 days free, up to 2 years paid)

**Key Metrics**:
- Average Active Sessions (AAS)
- DB Load (should be < vCPU count)
- Top SQL by load
- Wait events (I/O, lock, CPU)

**Usage**:
```bash
# Enable via CLI
aws rds modify-db-instance \
  --db-instance-identifier mydb \
  --enable-performance-insights \
  --performance-insights-retention-period 7
```

### Enhanced Monitoring

**Provides**:
- OS-level metrics (1-60 second granularity)
- Process list
- File system usage
- Detailed CPU metrics

**Use When**:
- Need sub-minute resolution
- Troubleshooting OS-level issues
- Monitoring specific processes

## Security Best Practices

### Network Security

- Use VPC for network isolation
- Security groups: Allow only necessary ports (3306 for MySQL)
- No public accessibility for production databases
- Use VPN or Direct Connect for on-premises access
- Consider VPC endpoints for AWS service access

### Authentication & Authorization

- Use IAM database authentication where possible
- Rotate master password regularly
- Use least privilege principle for database users
- Enable SSL/TLS for connections
- Store credentials in AWS Secrets Manager

### Encryption

**At Rest**:
- Enable encryption for new instances
- Uses AWS KMS (customer or AWS managed keys)
- Cannot enable after instance creation (must migrate)
- Encrypts: DB storage, backups, snapshots, read replicas

**In Transit**:
- Enforce SSL connections: `REQUIRE SSL` in GRANT statement
- Download RDS CA certificate bundle
- Configure application to use SSL

```sql
-- Enforce SSL for user
ALTER USER 'myuser'@'%' REQUIRE SSL;

-- Check SSL status
SHOW STATUS LIKE 'Ssl_cipher';
```

## Maintenance & Upgrades

### Maintenance Windows

- Weekly 30-minute window for patches and minor version upgrades
- Choose low-traffic period
- Defer maintenance if needed (temporary)
- Multi-AZ: Standby upgraded first, then failover, then former primary

### Version Upgrades

**Minor Version Upgrades**:
- Automated during maintenance window (if enabled)
- Low risk, backward compatible
- Recommend: Enable auto minor version upgrade

**Major Version Upgrades**:
- Manual process, requires testing
- Use Blue/Green deployments (MySQL 8.0.28+)
- Test in staging first
- Review MySQL upgrade notes for breaking changes

**Blue/Green Deployment**:
```bash
# Create blue/green deployment
aws rds create-blue-green-deployment \
  --blue-green-deployment-identifier mydb-upgrade \
  --source-arn arn:aws:rds:us-east-1:123456789012:db:mydb \
  --target-engine-version 8.0.35

# Switchover (seconds of downtime)
aws rds switchover-blue-green-deployment \
  --blue-green-deployment-identifier mydb-upgrade
```

## Cost Optimization

1. **Right-Size Instances**: Match instance class to workload
2. **Reserved Instances**: 1-3 year commitment for 30-60% discount
3. **Savings Plans**: Flexible commitment across AWS compute
4. **Storage Optimization**: gp3 typically cheaper than gp2 for same performance
5. **Delete Unused Snapshots**: Especially manual snapshots
6. **Stop Dev/Test Instances**: Stop when not in use (up to 7 days)
7. **Use Read Replicas Efficiently**: Don't over-provision
8. **Monitor Idle Connections**: Reduce max_connections if unused

## Common Anti-Patterns

### Don't:
- ❌ Use t2/t3 instance classes for production (burstable CPU)
- ❌ Run analytics queries on primary (use read replica)
- ❌ Disable automated backups in production
- ❌ Use magnetic storage (deprecated)
- ❌ Expose database publicly (use VPN/Direct Connect)
- ❌ Store secrets in application code (use Secrets Manager)
- ❌ Run without monitoring and alerting
- ❌ Skip testing of upgrades
- ❌ Ignore slow query log
- ❌ Over-provision max_connections (memory waste)

### Do:
- ✅ Use Multi-AZ for production
- ✅ Enable automated backups with adequate retention
- ✅ Use gp3 storage for most workloads
- ✅ Implement connection pooling
- ✅ Monitor key CloudWatch metrics
- ✅ Enable Performance Insights
- ✅ Use parameter groups for configuration
- ✅ Test failover procedures
- ✅ Review slow query log regularly
- ✅ Plan maintenance windows appropriately
