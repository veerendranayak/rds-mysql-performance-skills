# RDS MySQL Performance Skills

AI-powered performance review and optimization skills for Amazon RDS MySQL instances.

## Overview

This repository provides structured workflows and diagnostic tools for AI coding assistants to analyze and optimize RDS MySQL database performance. Inspired by [PlanetScale's database-skills](https://github.com/planetscale/database-skills), these skills are specifically adapted for AWS RDS MySQL environments.

## Features

- **Performance Diagnostics**: Automated collection and analysis of RDS metrics, slow queries, and database health
- **Schema Review**: Evidence-based schema design validation following MySQL/InnoDB best practices
- **Query Optimization**: EXPLAIN analysis, index recommendations, and query pattern improvements
- **RDS-Specific Guidance**: CloudWatch integration, parameter group optimization, and RDS operational best practices
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

Reference the `skills/rds-mysql/SKILL.md` file in your AI assistant conversations to guide performance reviews.

### Standalone Diagnostic Tool

```bash
# Run full performance diagnostic
python scripts/rds_performance_diagnostic.py --config config.json

# Generate performance report
python scripts/generate_report.py --output report.html
```

## Skill Structure

```
skills/rds-mysql/
├── SKILL.md                    # Main skill instructions for AI assistants
└── references/
    ├── rds-best-practices.md   # RDS-specific operational guidance
    ├── query-optimization.md   # Query tuning patterns
    └── cloudwatch-metrics.md   # Key metrics to monitor
```

## What's Included

### Diagnostic Scripts

- `rds_performance_diagnostic.py`: Collects performance metrics, slow queries, and database statistics
- `schema_analyzer.py`: Reviews table structures, indexes, and foreign keys
- `query_analyzer.py`: Analyzes slow query logs and generates EXPLAIN plans
- `generate_report.py`: Creates HTML performance reports with visualizations

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

## RDS-Specific Considerations

This skill accounts for RDS limitations and features:

- Uses CloudWatch for system metrics (no direct host access)
- Respects RDS parameter group constraints
- Considers RDS storage types (gp2, gp3, io1, io2)
- Accounts for Multi-AZ and read replica configurations
- Adapts recommendations for RDS engine versions

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

Inspired by [PlanetScale's database-skills](https://github.com/planetscale/database-skills) project.

## Related Resources

- [AWS RDS MySQL Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_MySQL.html)
- [MySQL Performance Schema](https://dev.mysql.com/doc/refman/8.0/en/performance-schema.html)
- [RDS CloudWatch Metrics](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/MonitoringOverview.html)
