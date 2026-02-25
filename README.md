# AWS MySQL Performance Skills

AI-powered performance review and optimization skills for Amazon RDS MySQL and Aurora MySQL.

## Overview

This repository provides structured workflows and diagnostic tools for AI coding assistants to analyze and optimize AWS RDS and Aurora MySQL database performance. These skills are specifically designed for AWS database environments with comprehensive coverage of RDS MySQL and Aurora MySQL specific features and optimizations.

## Features

- **Dual Skill Coverage**: Separate skills for RDS MySQL and Aurora MySQL with platform-specific guidance
- **Performance Diagnostics**: Automated collection and analysis of CloudWatch metrics, slow queries, and database health
- **Schema Review**: Evidence-based schema design validation following MySQL/InnoDB best practices
- **Query Optimization**: EXPLAIN analysis, index recommendations, query pattern analysis, and anti-pattern detection
- **Aurora-Specific Guidance**: TempTable overflow prevention, fast failover with RDS Proxy, parallel query optimization
- **RDS-Specific Guidance**: CloudWatch integration, parameter group optimization, storage configuration
- **MySQL 8.4 Migration**: Comprehensive breaking changes guide for upgrading to MySQL 8.4 / Aurora MySQL 4.x
- **Automated Reports**: Generate comprehensive performance review reports with actionable recommendations

## Quick Start

### Prerequisites

- Python 3.8+
- AWS CLI configured with appropriate credentials
- Access to RDS MySQL instance
- Required Python packages: `boto3`, `pymysql`, `pandas`

### Installation

```bash
# Clone the repository
git clone https://github.com/veerendranayak/rds-mysql-performance-skills.git
cd rds-mysql-performance-skills

# Install dependencies
pip install -r requirements.txt

# Configure your RDS connection
cp config.example.json config.json
# Edit config.json with your RDS details
```

### Usage with AI Assistants

#### With skills.sh

```bash
npx skills add veerendranayak/rds-mysql-performance-skills
```

#### Manual Usage

Reference the appropriate skill file in your AI assistant conversations:

**For RDS MySQL**:
```
Review my RDS MySQL performance using the guidance in:
https://github.com/veerendranayak/rds-mysql-performance-skills/blob/master/skills/rds-mysql/SKILL.md
```

**For Aurora MySQL**:
```
Review my Aurora MySQL cluster using the guidance in:
https://github.com/veerendranayak/rds-mysql-performance-skills/blob/master/skills/aurora-mysql/SKILL.md
```

### Standalone Diagnostic Tool

```bash
# Run full performance diagnostic
python scripts/rds_performance_diagnostic.py --config config.json

# Generate performance report
python scripts/generate_report.py --output report.html
```

## Skill Structure

### RDS MySQL Skill
```
skills/rds-mysql/
├── SKILL.md                    # RDS MySQL performance review workflow
└── references/
    ├── rds-best-practices.md   # RDS-specific operational guidance
    ├── query-optimization.md   # Query tuning patterns
    └── cloudwatch-metrics.md   # Key metrics to monitor
```

### Aurora MySQL Skill
```
skills/aurora-mysql/
├── SKILL.md                    # Aurora MySQL performance review workflow
└── references/
    ├── aurora-specifics.md     # Aurora architecture, TempTable, failover
    ├── mysql-84-changes.md     # MySQL 8.4 breaking changes
    └── query-patterns.md       # Common anti-patterns and fixes
```

## What's Included

### Diagnostic Scripts

- `rds_performance_diagnostic.py`: Collects performance metrics, slow queries, and database statistics (works for both RDS and Aurora)
- `query_analyzer.py`: Analyzes queries with EXPLAIN and provides optimization recommendations

### Key Capabilities

1. **Workload Assessment**
   - Connection statistics and patterns
   - Query volume and distribution
   - CloudWatch metric analysis (CPU, IOPS, connections)

2. **Schema Analysis**
   - Primary key design validation
   - Index coverage and redundancy detection
   - Foreign key relationship mapping
   - Data type optimization

3. **Query Performance**
   - Slow query log analysis
   - EXPLAIN plan interpretation
   - N+1 query detection
   - Missing index identification

4. **RDS Operations**
   - Parameter group recommendations
   - Storage and scaling guidance
   - Read replica optimization
   - Backup and maintenance window review

## RDS vs Aurora: When to Use Each Skill

### Use the RDS MySQL Skill When:
- Running standard RDS MySQL instances
- Need IOPS and storage provisioning guidance
- Working with EBS-backed storage (gp2, gp3, io1, io2)
- Have 5 or fewer read replicas
- Using Multi-AZ for high availability

### Use the Aurora MySQL Skill When:
- Running Aurora MySQL clusters
- Need guidance on TempTable overflow prevention (critical for Aurora readers)
- Working with Aurora's shared storage architecture
- Have up to 15 read replicas
- Using RDS Proxy for fast failover
- Planning to use Aurora Parallel Query
- Migrating to MySQL 8.4 / Aurora MySQL 4.x

### Key Aurora Differences

**TempTable Behavior (CRITICAL)**:
- Aurora readers **fail queries** on TempTable overflow
- RDS MySQL spills to disk (slower but doesn't fail)
- Requires special attention to query routing and TempTable sizing

**Replication**:
- Aurora: Sub-10ms replica lag typical, up to 15 replicas
- RDS: 30s-300s lag typical, up to 5 replicas

**Failover**:
- Aurora: 30-60s typical, sub-5s with RDS Proxy
- RDS Multi-AZ: 60-120s typical

**Storage**:
- Aurora: Shared, distributed, auto-scaling to 128TB
- RDS: EBS volumes, manual provisioning

## Example Workflow

1. **Connect to RDS**: Configure connection details in `config.json`
2. **Run Diagnostics**: Execute `rds_performance_diagnostic.py` to collect data
3. **Review with AI**: Share results with your AI assistant using the skill context
4. **Implement Changes**: Apply recommended optimizations
5. **Validate**: Re-run diagnostics to measure improvements

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License - See LICENSE file for details

## Acknowledgments

Built to address the growing need for automated database performance review and optimization in AWS environments, helping teams scale their database operations without proportionally scaling DBA headcount.

## Related Resources

- [AWS RDS MySQL Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_MySQL.html)
- [MySQL Performance Schema](https://dev.mysql.com/doc/refman/8.0/en/performance-schema.html)
- [RDS CloudWatch Metrics](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/MonitoringOverview.html)
