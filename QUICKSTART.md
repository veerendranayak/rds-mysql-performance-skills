# Quick Start Guide

Get started with RDS MySQL Performance Skills in 5 minutes.

## Prerequisites

- Python 3.8 or higher
- AWS CLI configured with credentials
- Access to an RDS MySQL instance
- MySQL client or Python MySQL connector

## Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/YOUR-USERNAME/rds-mysql-performance-skills.git
cd rds-mysql-performance-skills

# Install Python dependencies
pip install -r requirements.txt
```

## Step 2: Configure Connection

```bash
# Copy example configuration
cp config.example.json config.json

# Edit config.json with your RDS details
nano config.json
```

Update the following values in `config.json`:

```json
{
  "database": {
    "host": "your-db.xxxxxx.us-east-1.rds.amazonaws.com",
    "port": 3306,
    "user": "your_username",
    "password": "your_password",
    "database": "information_schema"
  },
  "aws": {
    "region": "us-east-1",
    "db_instance_identifier": "your-db-instance-name"
  }
}
```

**Security Note**: Never commit `config.json` to version control. It's included in `.gitignore`.

## Step 3: Run Diagnostic

```bash
# Run full performance diagnostic
python scripts/rds_performance_diagnostic.py --config config.json

# Collect 24 hours of CloudWatch metrics
python scripts/rds_performance_diagnostic.py --config config.json --hours 24
```

This will generate a JSON file with diagnostic results:
- CloudWatch metrics (CPU, memory, IOPS, connections)
- Database statistics (queries, buffer pool, connections)
- Schema information (tables, indexes)
- Performance recommendations

## Step 4: Analyze a Specific Query

```bash
# Analyze a query from command line
python scripts/query_analyzer.py \
  --config config.json \
  --query "SELECT * FROM orders WHERE customer_id = 12345 ORDER BY created_at DESC LIMIT 10"

# Analyze a query from file
echo "SELECT * FROM orders WHERE status = 'pending'" > query.sql
python scripts/query_analyzer.py --config config.json --file query.sql
```

The analyzer will:
- Run EXPLAIN on your query
- Identify issues (full table scans, filesorts, etc.)
- Provide optimization recommendations

## Step 5: Use with AI Assistants

### With Claude Code or similar AI tools

When discussing performance with your AI assistant, reference the skill:

```
I need help optimizing my RDS MySQL database. Please use the guidance in
skills/rds-mysql/SKILL.md to review my performance data.

Here are my diagnostic results: [paste results]
```

The AI will follow the structured workflow to:
1. Assess your workload and environment
2. Analyze performance bottlenecks
3. Provide evidence-based recommendations
4. Include implementation steps and rollback plans

## Common Use Cases

### 1. Monthly Performance Review

```bash
# Collect comprehensive diagnostics
python scripts/rds_performance_diagnostic.py --config config.json --hours 168

# Review output and discuss with AI assistant
```

### 2. Pre-Deployment Check

```bash
# Run diagnostics before deploying schema changes
python scripts/rds_performance_diagnostic.py --config config.json

# Review recommendations
# Make changes
# Re-run to validate improvements
```

### 3. Troubleshooting Slow Queries

```bash
# Get problematic query from application logs
python scripts/query_analyzer.py --config config.json --query "YOUR_SLOW_QUERY"

# Follow recommendations to add indexes or optimize query
```

## Viewing Results

Diagnostic results are saved as JSON files with timestamps:
```
diagnostic_results_20260224_153045.json
```

To view in a readable format:

```bash
# Pretty print JSON
python -m json.tool diagnostic_results_*.json | less

# Extract just recommendations
cat diagnostic_results_*.json | jq '.recommendations'

# Check CPU metrics
cat diagnostic_results_*.json | jq '.cloudwatch_metrics.CPUUtilization'
```

## Next Steps

1. **Review the Skill Documentation**: Read `skills/rds-mysql/SKILL.md` for comprehensive guidance
2. **Check Reference Materials**: Explore `skills/rds-mysql/references/` for best practices
3. **Set Up Monitoring**: Configure CloudWatch alarms based on diagnostic findings
4. **Automate**: Schedule regular diagnostic runs with cron or Lambda

## Troubleshooting

### Connection Issues

```bash
# Test database connection
mysql -h your-db.xxx.us-east-1.rds.amazonaws.com -u username -p

# Check security groups allow your IP
aws ec2 describe-security-groups --group-ids sg-xxxxx
```

### Permission Issues

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check IAM permissions for CloudWatch and RDS
aws iam get-user-policy --user-name your-user --policy-name your-policy
```

### Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Support

- **Issues**: Report bugs or feature requests on GitHub
- **Documentation**: See README.md for full documentation
- **AWS Documentation**: [RDS MySQL User Guide](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_MySQL.html)

## Security Best Practices

- Store credentials in AWS Secrets Manager or Parameter Store
- Use IAM database authentication where possible
- Restrict database security groups to known IPs
- Enable encryption at rest and in transit
- Rotate credentials regularly
