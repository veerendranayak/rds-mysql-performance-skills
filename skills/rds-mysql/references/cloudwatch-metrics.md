# CloudWatch Metrics Reference for RDS MySQL

## Core Performance Metrics

### CPU Utilization

**Metric**: `CPUUtilization`
**Unit**: Percent
**Description**: Percentage of CPU used by the DB instance

**Interpretation**:
- **< 40%**: Healthy, room for growth
- **40-70%**: Moderate load, monitor trends
- **70-90%**: High load, investigate queries, consider scaling
- **> 90%**: Critical, immediate action required

**Common Causes of High CPU**:
- Inefficient queries (missing indexes, full table scans)
- High query volume
- CPU-intensive operations (sorting, hashing, regex)
- Undersized instance class

**Actions**:
1. Check Performance Insights for top CPU-consuming queries
2. Review EXPLAIN plans for problematic queries
3. Add indexes for full table scans
4. Consider larger instance class with more vCPUs
5. Enable query cache (MySQL 5.7 only, if appropriate)

---

### Free Memory

**Metric**: `FreeableMemory`
**Unit**: Bytes
**Description**: Amount of available RAM

**Interpretation**:
- **> 20% of total**: Healthy
- **10-20% of total**: Monitor buffer pool efficiency
- **< 10% of total**: Critical, risk of OOM

**Related Parameters**:
- `innodb_buffer_pool_size`: Should be 70-80% of instance memory
- `max_connections`: Each connection uses ~256KB-1MB

**Actions**:
1. Check buffer pool hit rate (should be >99%)
2. Review connection count vs. max_connections
3. Identify queries using lots of memory (temp tables, sorts)
4. Reduce max_connections if over-provisioned
5. Scale to larger instance class if needed

---

### Database Connections

**Metric**: `DatabaseConnections`
**Unit**: Count
**Description**: Number of client connections to the database

**Interpretation**:
- Monitor ratio: `DatabaseConnections / max_connections`
- **< 60%**: Healthy
- **60-80%**: Moderate, ensure connection pooling
- **> 80%**: High risk of connection exhaustion
- **= max_connections**: Connection refused errors

**Common Issues**:
- Connection leaks in application code
- Missing connection pooling
- max_connections set too low

**Actions**:
1. Implement connection pooling (HikariCP, SQLAlchemy, RDS Proxy)
2. Check for connection leaks (connections not properly closed)
3. Review `max_connections` setting vs. workload needs
4. Monitor `Threads_connected` and `Max_used_connections` in MySQL
5. Consider RDS Proxy for connection management

---

## Storage Metrics

### Read/Write IOPS

**Metrics**: `ReadIOPS`, `WriteIOPS`
**Unit**: Count/Second
**Description**: Average I/O operations per second

**Storage Type Limits**:
- **gp2**: 3 IOPS/GB (min 100, max 16,000)
- **gp3**: 3,000 IOPS baseline (configurable to 16,000)
- **io1**: Up to 64,000 IOPS
- **io2**: Up to 64,000 IOPS (io2 Block Express: 256,000)

**Interpretation**:
- At or near limit: Storage bottleneck
- Sudden spike: Check for problematic queries
- Sustained high: May need more IOPS

**Actions**:
1. Check if hitting storage IOPS limits
2. Review slow queries causing excessive disk reads
3. Optimize buffer pool size to reduce disk I/O
4. Consider gp3 with higher IOPS configuration
5. Consider io1/io2 for I/O intensive workloads

---

### Read/Write Latency

**Metrics**: `ReadLatency`, `WriteLatency`
**Unit**: Milliseconds
**Description**: Average time per I/O operation

**Interpretation**:
- **< 5ms**: Excellent
- **5-10ms**: Good (typical for SSD)
- **10-20ms**: Moderate, monitor
- **> 20ms**: Poor, investigate storage bottleneck

**Common Causes of High Latency**:
- Storage IOPS limit reached
- High disk queue depth
- Undersized storage (gp2 with low baseline IOPS)
- Network issues (rare)

**Actions**:
1. Check `DiskQueueDepth` metric
2. Review `ReadIOPS`/`WriteIOPS` vs. provisioned limits
3. Upgrade to gp3 or io1/io2 for consistent low latency
4. Optimize queries to reduce I/O
5. Increase buffer pool to cache more data in memory

---

### Disk Queue Depth

**Metric**: `DiskQueueDepth`
**Unit**: Count
**Description**: Number of outstanding I/O requests waiting for disk

**Interpretation**:
- **< 5**: Healthy
- **5-10**: Moderate load
- **> 10**: Storage bottleneck, I/O subsystem saturated

**Actions**:
1. Check if IOPS limit is reached
2. Increase provisioned IOPS (gp3, io1, io2)
3. Optimize queries to reduce I/O operations
4. Increase buffer pool size
5. Consider read replicas to distribute read load

---

### Free Storage Space

**Metric**: `FreeStorageSpace`
**Unit**: Bytes
**Description**: Available storage space

**Interpretation**:
- **> 20%**: Healthy
- **10-20%**: Plan for scaling
- **< 10%**: Critical, enable autoscaling or increase storage
- **< 5%**: Immediate action required

**Actions**:
1. Enable storage autoscaling
2. Archive old data
3. Drop unused indexes and temp tables
4. Review slow query log and general log size
5. Schedule manual storage increase

---

## Throughput Metrics

### Network Throughput

**Metrics**: `NetworkReceiveThroughput`, `NetworkTransmitThroughput`
**Unit**: Bytes/Second
**Description**: Network traffic to/from DB instance

**Instance Network Limits**: Varies by instance class
- **t3.micro**: 128 Mbps
- **t3.medium**: 1 Gbps
- **m5.large**: 10 Gbps
- **r5.large**: 10 Gbps

**Actions if at Limit**:
1. Reduce result set sizes (SELECT only needed columns)
2. Implement pagination
3. Use compression for large transfers
4. Scale to larger instance class with more network capacity
5. Consider caching layer to reduce database queries

---

### Read/Write Throughput

**Metrics**: `ReadThroughput`, `WriteThroughput`
**Unit**: Bytes/Second
**Description**: Bytes read/written to disk per second

**Storage Throughput Limits**:
- **gp2**: 128-250 MB/s
- **gp3**: 125 MB/s baseline (configurable to 1,000 MB/s)
- **io1**: 500 MB/s (1,000 MB/s for volumes > 32,000 IOPS)
- **io2**: 1,000 MB/s

**Actions if at Limit**:
1. Upgrade to gp3 with higher throughput
2. Consider io1/io2 for high-throughput workloads
3. Optimize queries to reduce data transfer
4. Increase buffer pool to reduce disk reads

---

## Replication Metrics

### Replica Lag

**Metric**: `ReplicaLag`
**Unit**: Seconds
**Description**: Time read replica is behind the primary

**Interpretation**:
- **0-5s**: Excellent
- **5-30s**: Moderate, monitor
- **30-300s**: High, investigate
- **> 300s**: Critical, replica may be unusable

**Common Causes**:
- High write volume on primary
- Undersized replica instance
- Network latency between AZs/regions
- Long-running transactions
- Single-threaded replication (MySQL < 5.7)

**Actions**:
1. Check write volume on primary (WriteIOPS, WriteThroughput)
2. Scale replica to same or larger instance class as primary
3. Enable parallel replication threads (MySQL 5.7+)
4. Reduce transaction size on primary
5. Monitor `Seconds_Behind_Master` in MySQL

---

### Bin Log Disk Usage

**Metric**: `BinLogDiskUsage`
**Unit**: Bytes
**Description**: Disk space used by binary logs

**Interpretation**:
- Binary logs required for replication and PITR
- Large size indicates high write activity or long retention

**Actions**:
1. Review binlog retention period (RDS retains for backup retention period)
2. High write volume is normal; ensure adequate storage
3. Consider Aurora for more efficient replication
4. Binary logs auto-purged after retention period

---

## Transaction & Lock Metrics

### Active Transactions

**Metric**: `ActiveTransactions`
**Unit**: Count (Enhanced Monitoring)
**Description**: Number of currently executing transactions

**Interpretation**:
- High count: May indicate long-running transactions or high concurrency
- Monitor in conjunction with lock waits

**Actions**:
1. Identify long-running transactions: `SELECT * FROM information_schema.innodb_trx`
2. Review transaction isolation level (REPEATABLE READ vs READ COMMITTED)
3. Ensure transactions are committed promptly
4. Break large transactions into smaller batches

---

### Deadlocks

**Metric**: `Deadlocks`
**Unit**: Count/Minute (Performance Insights)
**Description**: Number of deadlocks detected

**Interpretation**:
- Occasional deadlocks: Normal in high-concurrency systems
- Frequent deadlocks: Design issue

**Actions**:
1. Review deadlock logs: `SHOW ENGINE INNODB STATUS`
2. Access rows in consistent order across transactions
3. Keep transactions short
4. Use appropriate isolation level
5. Add proper indexes to reduce lock ranges

---

## RDS-Specific Metrics

### RDS Events

**CloudWatch Events**: Instance events (failover, maintenance, backup)

**Key Events**:
- **DB_INSTANCE_FAILURE**: Failover initiated
- **MAINTENANCE**: Patching or maintenance operation
- **BACKUP_START/END**: Automated backup window
- **PARAMETER_GROUP_CHANGE**: Parameter modified

**Actions**:
1. Set up CloudWatch alarms for critical events
2. Review event history for patterns
3. Plan maintenance windows during low-traffic periods

---

### Burst Balance (T3/T2 instances only)

**Metric**: `BurstBalance`
**Unit**: Percent
**Description**: CPU burst credits remaining

**Interpretation**:
- **> 50%**: Healthy, CPU not consistently maxed
- **20-50%**: Monitor, may need larger instance
- **< 20%**: CPU throttled, upgrade to non-burstable instance

**Actions**:
1. T2/T3 instances are for dev/test only
2. Production workloads should use M5, R5, or similar
3. If burst balance consistently depleted, scale to non-burstable instance

---

## Composite Metrics & Alarms

### Suggested CloudWatch Alarms

```bash
# High CPU
aws cloudwatch put-metric-alarm \
  --alarm-name rds-high-cpu \
  --metric-name CPUUtilization \
  --namespace AWS/RDS \
  --dimensions Name=DBInstanceIdentifier,Value=mydb \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold

# Low Free Memory
aws cloudwatch put-metric-alarm \
  --alarm-name rds-low-memory \
  --metric-name FreeableMemory \
  --namespace AWS/RDS \
  --dimensions Name=DBInstanceIdentifier,Value=mydb \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 268435456 \
  --comparison-operator LessThanThreshold  # 256 MB

# High Connections
aws cloudwatch put-metric-alarm \
  --alarm-name rds-high-connections \
  --metric-name DatabaseConnections \
  --namespace AWS/RDS \
  --dimensions Name=DBInstanceIdentifier,Value=mydb \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold  # Adjust based on max_connections

# High Replica Lag
aws cloudwatch put-metric-alarm \
  --alarm-name rds-high-replica-lag \
  --metric-name ReplicaLag \
  --namespace AWS/RDS \
  --dimensions Name=DBInstanceIdentifier,Value=mydb-replica \
  --statistic Average \
  --period 60 \
  --evaluation-periods 5 \
  --threshold 30 \
  --comparison-operator GreaterThanThreshold

# Low Storage Space
aws cloudwatch put-metric-alarm \
  --alarm-name rds-low-storage \
  --metric-name FreeStorageSpace \
  --namespace AWS/RDS \
  --dimensions Name=DBInstanceIdentifier,Value=mydb \
  --statistic Average \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10737418240 \
  --comparison-operator LessThanThreshold  # 10 GB
```

---

## Performance Insights Metrics

### Database Load (AAS)

**Metric**: Average Active Sessions
**Description**: Average number of sessions actively executing

**Interpretation**:
- **< vCPU count**: Healthy
- **= vCPU count**: Saturated, all vCPUs busy
- **> vCPU count**: Overloaded, sessions waiting

**Top Wait Events**:
- `io/file/innodb/innodb_data_file`: Disk I/O wait (optimize queries, add indexes, increase buffer pool)
- `io/socket/sql/client_connection`: Network wait (client side issue)
- `synch/mutex/*`: Lock contention (review transaction design)
- `CPU`: CPU saturation (optimize queries, scale instance)

---

## Enhanced Monitoring Metrics

**Additional OS-level metrics** (1-60 second granularity):
- `cpuUtilization.guest`, `.nice`, `.steal`, `.system`, `.user`, `.wait`
- `memory.active`, `.inactive`, `.free`, `.cached`
- `swap.in`, `.out`, `.free`
- `tasks.running`, `.sleeping`, `.stopped`, `.zombie`
- `diskIO.readKbPS`, `.writeKbPS`, `.await`
- `network.rx`, `.tx`

**Use Cases**:
- Detailed CPU breakdown (user vs. system vs. I/O wait)
- Memory pressure analysis (swap usage)
- Disk I/O latency at OS level
- Process-level monitoring

---

## Monitoring Best Practices

1. **Set up dashboards**: Create CloudWatch dashboard with key metrics
2. **Configure alarms**: Alert on critical thresholds before issues occur
3. **Review regularly**: Weekly review of trends and anomalies
4. **Correlate metrics**: Cross-reference CPU, IOPS, latency, connections
5. **Use Performance Insights**: Identify top SQL and wait events
6. **Enable Enhanced Monitoring**: For detailed OS-level troubleshooting
7. **Export to S3**: Long-term metric storage and analysis
8. **Integrate with APM**: Correlate DB metrics with application metrics

## References

- [RDS CloudWatch Metrics](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/MonitoringOverview.html)
- [Performance Insights](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PerfInsights.html)
- [Enhanced Monitoring](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_Monitoring.OS.html)
