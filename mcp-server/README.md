# RDS MySQL Performance MCP Server

AI-powered performance review and optimization guidance for Amazon RDS MySQL and Aurora MySQL instances.

## Overview

This MCP (Model Context Protocol) server provides expert guidance for analyzing and optimizing AWS MySQL database performance through AI assistants. It delivers context-rich prompts covering RDS MySQL and Aurora MySQL specific patterns, best practices, and optimization techniques.

## Installation

### Via uvx (Recommended)

```bash
uvx veerendranayak.rds-mysql-mcp-server@latest
```

### Via pip

```bash
pip install veerendranayak.rds-mysql-mcp-server
```

## Configuration

Add to your MCP client configuration (e.g., Claude Desktop, Cline, or other MCP-compatible tools):

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%/Claude/claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "rds-mysql-performance": {
      "command": "uvx",
      "args": ["veerendranayak.rds-mysql-mcp-server@latest"]
    }
  }
}
```

### Cline / VS Code

Add to your MCP settings:

```json
{
  "mcpServers": {
    "rds-mysql-performance": {
      "command": "uvx",
      "args": ["veerendranayak.rds-mysql-mcp-server@latest"]
    }
  }
}
```

## Available Tools

### 1. `rds_mysql_performance_review`

Comprehensive performance review guidance for standard RDS MySQL instances:
- CloudWatch metrics interpretation
- Schema design validation
- Index optimization
- Query tuning with EXPLAIN analysis
- Parameter group configuration
- Storage optimization (gp2, gp3, io1, io2)
- Read replica strategy

**When to use**: Working with standard RDS MySQL instances

### 2. `aurora_mysql_performance_review`

Aurora MySQL performance review with Aurora-specific considerations:
- **TempTable overflow prevention** (CRITICAL for readers)
- Aurora architecture and shared storage implications
- Fast failover with RDS Proxy
- Aurora replication behavior (sub-10ms lag)
- Reader vs writer workload routing
- Aurora Parallel Query optimization

**When to use**: Working with Aurora MySQL clusters

⚠️ **CRITICAL**: Aurora readers fail queries on TempTable overflow (unlike RDS MySQL which spills to disk)

### 3. `schema_analysis_guidance`

Schema design and validation best practices:
- Primary key design (auto-increment vs UUID)
- Data type selection
- Character set and collation (utf8mb4 best practices)
- Normalization strategies
- Foreign key relationships
- Table partitioning

**When to use**: Designing or reviewing database schemas

### 4. `query_optimization_guidance`

Query optimization techniques:
- EXPLAIN output interpretation
- Index strategy and covering indexes
- Common anti-patterns detection
- Query rewriting techniques
- JOIN vs subquery optimization
- Performance Schema usage

**When to use**: Analyzing and optimizing slow queries

### 5. `mysql_84_migration_guidance`

MySQL 8.4 migration planning:
- Breaking changes from MySQL 8.0 to 8.4
- Deprecated features and replacements
- Aurora MySQL 3.x to 4.x migration
- Testing and validation strategies
- Compatibility assessment

**When to use**: Planning upgrade to MySQL 8.4 or Aurora MySQL 4.x

## Usage Example

With your AI assistant (e.g., Claude):

```
I need help optimizing my Aurora MySQL cluster. Can you use the aurora_mysql_performance_review tool to guide me through a performance review?
```

The AI will invoke the tool and receive comprehensive expert guidance to help you:
1. Gather performance metrics and context
2. Identify Aurora-specific issues (like TempTable overflow)
3. Analyze schema, queries, and configuration
4. Provide prioritized recommendations
5. Create implementation and validation plans

## RDS MySQL vs Aurora MySQL

### Use `rds_mysql_performance_review` when:
- Running standard RDS MySQL instances
- Using EBS-backed storage (gp2, gp3, io1, io2)
- Have 5 or fewer read replicas
- Using Multi-AZ for high availability

### Use `aurora_mysql_performance_review` when:
- Running Aurora MySQL clusters
- Need TempTable overflow prevention guidance
- Working with Aurora's shared storage architecture
- Have up to 15 read replicas
- Using RDS Proxy for fast failover
- Need sub-10ms replication lag

## Key Aurora Differences

**TempTable Behavior** (CRITICAL):
- Aurora readers **fail queries** on TempTable overflow
- RDS MySQL spills to disk (slower but doesn't fail)
- Requires special attention to query routing and sizing

**Replication**:
- Aurora: Sub-10ms replica lag, up to 15 replicas
- RDS: 30s-300s lag typical, up to 5 replicas

**Failover**:
- Aurora: 30-60s typical, sub-5s with RDS Proxy
- RDS Multi-AZ: 60-120s typical

## Architecture

This MCP server follows the pattern established by AWS Labs' DynamoDB MCP server:

```
mcp-server/
├── veerendranayak/
│   └── rds_mysql_mcp_server/
│       ├── __init__.py
│       ├── server.py              # MCP server with tool definitions
│       └── prompts/
│           ├── rds_mysql_performance_review.md
│           └── aurora_mysql_performance_review.md
├── pyproject.toml
└── README.md
```

Each tool returns expert-level guidance stored as markdown prompts. The AI assistant receives this context and uses it to provide informed recommendations specific to your environment.

## Development

### Local Installation

```bash
# Clone the repository
git clone https://github.com/veerendranayak/rds-mysql-performance-skills.git
cd rds-mysql-performance-skills/mcp-server

# Install in development mode
pip install -e .

# Run the server
veerendranayak.rds-mysql-mcp-server
```

### Testing

```bash
# Install development dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

## Related Resources

- [AWS RDS MySQL Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_MySQL.html)
- [Aurora MySQL Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.BestPractices.html)
- [MySQL Performance Schema](https://dev.mysql.com/doc/refman/8.0/en/performance-schema.html)
- [RDS CloudWatch Metrics](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/MonitoringOverview.html)

## Contributing

Contributions are welcome! Please see the main repository for contribution guidelines.

## License

MIT License - See LICENSE file for details

## Acknowledgments

Inspired by the architecture and approach of [AWS Labs' DynamoDB MCP Server](https://github.com/awslabs/mcp/tree/main/src/dynamodb-mcp-server), which demonstrates the effective pattern of delivering expert context to AI assistants through structured prompts.
