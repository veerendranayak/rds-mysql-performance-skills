#!/usr/bin/env python3
"""
RDS MySQL Performance Diagnostic Tool

Collects comprehensive performance data from RDS MySQL instance including:
- CloudWatch metrics
- Database statistics
- Slow query analysis
- Schema and index information
- Connection and transaction stats
"""

import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any
import boto3
import pymysql
from pymysql.cursors import DictCursor

class RDSPerformanceDiagnostic:
    def __init__(self, config_file: str):
        """Initialize diagnostic tool with configuration"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        self.db_config = self.config['database']
        self.aws_config = self.config['aws']

        # Initialize AWS clients
        self.cloudwatch = boto3.client(
            'cloudwatch',
            region_name=self.aws_config['region']
        )
        self.rds = boto3.client(
            'rds',
            region_name=self.aws_config['region']
        )

        self.results = {
            'timestamp': datetime.now().isoformat(),
            'instance_id': self.aws_config['db_instance_identifier'],
            'cloudwatch_metrics': {},
            'database_stats': {},
            'slow_queries': [],
            'schema_info': {},
            'recommendations': []
        }

    def connect_db(self):
        """Establish database connection"""
        return pymysql.connect(
            host=self.db_config['host'],
            port=self.db_config.get('port', 3306),
            user=self.db_config['user'],
            password=self.db_config['password'],
            database=self.db_config.get('database', 'information_schema'),
            cursorclass=DictCursor,
            connect_timeout=10
        )

    def collect_cloudwatch_metrics(self, hours: int = 1):
        """Collect CloudWatch metrics for specified time period"""
        print(f"Collecting CloudWatch metrics for last {hours} hour(s)...")

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        metrics = [
            'CPUUtilization',
            'DatabaseConnections',
            'FreeableMemory',
            'ReadIOPS',
            'WriteIOPS',
            'ReadLatency',
            'WriteLatency',
            'ReadThroughput',
            'WriteThroughput',
            'DiskQueueDepth',
            'FreeStorageSpace'
        ]

        for metric_name in metrics:
            try:
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/RDS',
                    MetricName=metric_name,
                    Dimensions=[
                        {
                            'Name': 'DBInstanceIdentifier',
                            'Value': self.aws_config['db_instance_identifier']
                        }
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,  # 5 minutes
                    Statistics=['Average', 'Maximum', 'Minimum']
                )

                if response['Datapoints']:
                    datapoints = sorted(response['Datapoints'], key=lambda x: x['Timestamp'])
                    latest = datapoints[-1]

                    self.results['cloudwatch_metrics'][metric_name] = {
                        'latest_average': latest.get('Average', 0),
                        'latest_maximum': latest.get('Maximum', 0),
                        'latest_minimum': latest.get('Minimum', 0),
                        'period_average': sum(d['Average'] for d in datapoints) / len(datapoints),
                        'period_maximum': max(d.get('Maximum', 0) for d in datapoints),
                        'timestamp': latest['Timestamp'].isoformat()
                    }

            except Exception as e:
                print(f"  Warning: Could not collect metric {metric_name}: {e}")

        print(f"  Collected {len(self.results['cloudwatch_metrics'])} metrics")

    def collect_database_stats(self):
        """Collect MySQL database statistics"""
        print("Collecting database statistics...")

        conn = self.connect_db()
        try:
            with conn.cursor() as cursor:
                # Server version
                cursor.execute("SELECT VERSION() as version")
                self.results['database_stats']['version'] = cursor.fetchone()['version']

                # Uptime
                cursor.execute("SHOW GLOBAL STATUS LIKE 'Uptime'")
                uptime_seconds = int(cursor.fetchone()['Value'])
                self.results['database_stats']['uptime_hours'] = uptime_seconds / 3600

                # Connection statistics
                cursor.execute("SHOW GLOBAL STATUS LIKE 'Threads_connected'")
                threads_connected = int(cursor.fetchone()['Value'])

                cursor.execute("SHOW GLOBAL STATUS LIKE 'Max_used_connections'")
                max_used_connections = int(cursor.fetchone()['Value'])

                cursor.execute("SHOW VARIABLES LIKE 'max_connections'")
                max_connections = int(cursor.fetchone()['Value'])

                self.results['database_stats']['connections'] = {
                    'current': threads_connected,
                    'max_used': max_used_connections,
                    'max_allowed': max_connections,
                    'utilization_pct': (threads_connected / max_connections) * 100
                }

                # InnoDB buffer pool stats
                cursor.execute("SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_read_requests'")
                read_requests = int(cursor.fetchone()['Value'])

                cursor.execute("SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_reads'")
                disk_reads = int(cursor.fetchone()['Value'])

                if read_requests > 0:
                    hit_rate = ((read_requests - disk_reads) / read_requests) * 100
                else:
                    hit_rate = 0

                self.results['database_stats']['innodb_buffer_pool'] = {
                    'read_requests': read_requests,
                    'disk_reads': disk_reads,
                    'hit_rate_pct': hit_rate
                }

                # Query statistics
                cursor.execute("SHOW GLOBAL STATUS LIKE 'Questions'")
                questions = int(cursor.fetchone()['Value'])
                queries_per_second = questions / uptime_seconds if uptime_seconds > 0 else 0

                cursor.execute("SHOW GLOBAL STATUS LIKE 'Slow_queries'")
                slow_queries = int(cursor.fetchone()['Value'])

                self.results['database_stats']['queries'] = {
                    'total': questions,
                    'per_second': queries_per_second,
                    'slow_queries': slow_queries
                }

                # Table statistics
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_tables,
                        SUM(data_length + index_length) as total_size_bytes,
                        SUM(data_length) as data_size_bytes,
                        SUM(index_length) as index_size_bytes
                    FROM information_schema.tables
                    WHERE table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
                """)
                table_stats = cursor.fetchone()
                self.results['database_stats']['tables'] = table_stats

                print(f"  Version: {self.results['database_stats']['version']}")
                print(f"  Uptime: {self.results['database_stats']['uptime_hours']:.1f} hours")
                print(f"  Connections: {threads_connected}/{max_connections} ({self.results['database_stats']['connections']['utilization_pct']:.1f}%)")
                print(f"  Buffer pool hit rate: {hit_rate:.2f}%")

        finally:
            conn.close()

    def collect_schema_info(self):
        """Collect schema and index information"""
        print("Analyzing schema and indexes...")

        conn = self.connect_db()
        try:
            with conn.cursor() as cursor:
                # Tables without primary keys
                cursor.execute("""
                    SELECT t.table_schema, t.table_name, t.table_rows
                    FROM information_schema.tables t
                    LEFT JOIN information_schema.table_constraints tc
                      ON t.table_schema = tc.table_schema
                      AND t.table_name = tc.table_name
                      AND tc.constraint_type = 'PRIMARY KEY'
                    WHERE tc.constraint_name IS NULL
                      AND t.table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
                      AND t.table_type = 'BASE TABLE'
                    ORDER BY t.table_rows DESC
                    LIMIT 20
                """)
                self.results['schema_info']['tables_without_pk'] = cursor.fetchall()

                # Large tables
                cursor.execute("""
                    SELECT
                        table_schema,
                        table_name,
                        table_rows,
                        ROUND((data_length + index_length) / 1024 / 1024, 2) as size_mb,
                        ROUND(data_length / 1024 / 1024, 2) as data_size_mb,
                        ROUND(index_length / 1024 / 1024, 2) as index_size_mb
                    FROM information_schema.tables
                    WHERE table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
                      AND table_type = 'BASE TABLE'
                    ORDER BY (data_length + index_length) DESC
                    LIMIT 20
                """)
                self.results['schema_info']['largest_tables'] = cursor.fetchall()

                # Unused indexes (if performance_schema enabled)
                try:
                    cursor.execute("""
                        SELECT
                            object_schema,
                            object_name,
                            index_name
                        FROM performance_schema.table_io_waits_summary_by_index_usage
                        WHERE index_name IS NOT NULL
                          AND index_name != 'PRIMARY'
                          AND count_star = 0
                          AND object_schema NOT IN ('mysql', 'performance_schema', 'sys')
                        ORDER BY object_schema, object_name
                        LIMIT 50
                    """)
                    self.results['schema_info']['unused_indexes'] = cursor.fetchall()
                except Exception as e:
                    print(f"  Warning: Could not query performance_schema: {e}")
                    self.results['schema_info']['unused_indexes'] = []

                print(f"  Found {len(self.results['schema_info']['tables_without_pk'])} tables without primary keys")
                print(f"  Found {len(self.results['schema_info']['unused_indexes'])} potentially unused indexes")

        finally:
            conn.close()

    def collect_slow_queries(self):
        """Check slow query log configuration"""
        print("Checking slow query log configuration...")

        conn = self.connect_db()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SHOW VARIABLES LIKE 'slow_query_log'")
                slow_log_enabled = cursor.fetchone()['Value']

                cursor.execute("SHOW VARIABLES LIKE 'long_query_time'")
                long_query_time = float(cursor.fetchone()['Value'])

                cursor.execute("SHOW GLOBAL STATUS LIKE 'Slow_queries'")
                slow_queries_count = int(cursor.fetchone()['Value'])

                self.results['slow_queries'] = {
                    'enabled': slow_log_enabled == 'ON',
                    'threshold_seconds': long_query_time,
                    'total_count': slow_queries_count
                }

                print(f"  Slow query log: {'Enabled' if self.results['slow_queries']['enabled'] else 'Disabled'}")
                print(f"  Threshold: {long_query_time}s")
                print(f"  Total slow queries: {slow_queries_count}")

        finally:
            conn.close()

    def generate_recommendations(self):
        """Generate performance recommendations based on collected data"""
        print("\nGenerating recommendations...")

        recommendations = []

        # Check CPU utilization
        if 'CPUUtilization' in self.results['cloudwatch_metrics']:
            cpu = self.results['cloudwatch_metrics']['CPUUtilization']
            if cpu['period_average'] > 80:
                recommendations.append({
                    'severity': 'high',
                    'category': 'cpu',
                    'issue': f"High CPU utilization (avg: {cpu['period_average']:.1f}%)",
                    'recommendation': "Review top CPU-consuming queries in Performance Insights. Consider optimizing queries or scaling to a larger instance class."
                })

        # Check buffer pool hit rate
        if 'innodb_buffer_pool' in self.results['database_stats']:
            hit_rate = self.results['database_stats']['innodb_buffer_pool']['hit_rate_pct']
            if hit_rate < 99:
                recommendations.append({
                    'severity': 'medium',
                    'category': 'memory',
                    'issue': f"Low buffer pool hit rate ({hit_rate:.2f}%)",
                    'recommendation': "Consider increasing innodb_buffer_pool_size or scaling to an instance with more memory."
                })

        # Check connection utilization
        if 'connections' in self.results['database_stats']:
            conn_util = self.results['database_stats']['connections']['utilization_pct']
            if conn_util > 80:
                recommendations.append({
                    'severity': 'high',
                    'category': 'connections',
                    'issue': f"High connection utilization ({conn_util:.1f}%)",
                    'recommendation': "Implement connection pooling (RDS Proxy or application-level). Review for connection leaks."
                })

        # Check for tables without primary keys
        if self.results['schema_info'].get('tables_without_pk'):
            count = len(self.results['schema_info']['tables_without_pk'])
            recommendations.append({
                'severity': 'medium',
                'category': 'schema',
                'issue': f"{count} table(s) without primary keys",
                'recommendation': "Add primary keys to all tables. This is critical for replication and query performance."
            })

        # Check for unused indexes
        if self.results['schema_info'].get('unused_indexes'):
            count = len(self.results['schema_info']['unused_indexes'])
            if count > 0:
                recommendations.append({
                    'severity': 'low',
                    'category': 'indexes',
                    'issue': f"{count} potentially unused index(es)",
                    'recommendation': "Review and consider dropping unused indexes to reduce storage and write overhead."
                })

        # Check slow query log
        if not self.results['slow_queries'].get('enabled'):
            recommendations.append({
                'severity': 'medium',
                'category': 'monitoring',
                'issue': "Slow query log is disabled",
                'recommendation': "Enable slow query log (slow_query_log=1) to identify problematic queries."
            })

        # Check IOPS latency
        if 'ReadLatency' in self.results['cloudwatch_metrics']:
            latency = self.results['cloudwatch_metrics']['ReadLatency']
            if latency['period_average'] > 20:
                recommendations.append({
                    'severity': 'high',
                    'category': 'storage',
                    'issue': f"High read latency (avg: {latency['period_average']:.1f}ms)",
                    'recommendation': "Storage I/O bottleneck detected. Consider upgrading to gp3 with higher IOPS or io1/io2 storage."
                })

        self.results['recommendations'] = recommendations

        # Print summary
        print(f"\nGenerated {len(recommendations)} recommendation(s):")
        for rec in recommendations:
            severity_symbol = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(rec['severity'], '⚪')
            print(f"  {severity_symbol} [{rec['severity'].upper()}] {rec['issue']}")

    def save_results(self, output_file: str):
        """Save diagnostic results to JSON file"""
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\nResults saved to: {output_file}")

    def run(self, output_file: str, cloudwatch_hours: int = 1):
        """Run full diagnostic"""
        print("="*60)
        print("RDS MySQL Performance Diagnostic")
        print("="*60)
        print()

        try:
            self.collect_cloudwatch_metrics(hours=cloudwatch_hours)
            self.collect_database_stats()
            self.collect_schema_info()
            self.collect_slow_queries()
            self.generate_recommendations()
            self.save_results(output_file)

            print("\n" + "="*60)
            print("Diagnostic complete!")
            print("="*60)

        except Exception as e:
            print(f"\nError during diagnostic: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description='RDS MySQL Performance Diagnostic Tool'
    )
    parser.add_argument(
        '--config',
        default='config.json',
        help='Configuration file path (default: config.json)'
    )
    parser.add_argument(
        '--output',
        default=f'diagnostic_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
        help='Output file path'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=1,
        help='Hours of CloudWatch metrics to collect (default: 1)'
    )

    args = parser.parse_args()

    diagnostic = RDSPerformanceDiagnostic(args.config)
    diagnostic.run(args.output, cloudwatch_hours=args.hours)


if __name__ == '__main__':
    main()
