"""Tests for RDS MySQL MCP Server"""

import pytest
from veerendranayak.rds_mysql_mcp_server.server import (
    rds_mysql_performance_review,
    aurora_mysql_performance_review,
    schema_analysis_guidance,
    query_optimization_guidance,
    mysql_84_migration_guidance,
)


@pytest.mark.asyncio
async def test_rds_mysql_performance_review():
    """Test RDS MySQL performance review tool returns guidance."""
    result = await rds_mysql_performance_review()
    assert isinstance(result, str)
    assert len(result) > 0
    assert 'RDS MySQL' in result
    assert 'Performance Review' in result
    assert 'CloudWatch' in result


@pytest.mark.asyncio
async def test_aurora_mysql_performance_review():
    """Test Aurora MySQL performance review tool returns guidance."""
    result = await aurora_mysql_performance_review()
    assert isinstance(result, str)
    assert len(result) > 0
    assert 'Aurora MySQL' in result
    assert 'TempTable' in result
    assert 'Performance Review' in result


@pytest.mark.asyncio
async def test_schema_analysis_guidance():
    """Test schema analysis guidance tool returns content."""
    result = await schema_analysis_guidance()
    assert isinstance(result, str)
    assert len(result) > 0
    assert 'schema' in result.lower()
    assert 'primary key' in result.lower()


@pytest.mark.asyncio
async def test_query_optimization_guidance():
    """Test query optimization guidance tool returns content."""
    result = await query_optimization_guidance()
    assert isinstance(result, str)
    assert len(result) > 0
    assert 'EXPLAIN' in result
    assert 'index' in result.lower()


@pytest.mark.asyncio
async def test_mysql_84_migration_guidance():
    """Test MySQL 8.4 migration guidance tool returns content."""
    result = await mysql_84_migration_guidance()
    assert isinstance(result, str)
    assert len(result) > 0
    assert 'MySQL 8.4' in result or 'mysql 8.4' in result.lower()
