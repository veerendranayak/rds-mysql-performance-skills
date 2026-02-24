#!/usr/bin/env python3
"""
Query Analyzer for RDS MySQL

Analyzes queries using EXPLAIN and provides optimization recommendations.
"""

import json
import argparse
import pymysql
from pymysql.cursors import DictCursor
from typing import List, Dict, Any


class QueryAnalyzer:
    def __init__(self, config_file: str):
        """Initialize query analyzer with configuration"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        self.db_config = self.config['database']

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

    def explain_query(self, query: str) -> List[Dict[str, Any]]:
        """Run EXPLAIN on query and return results"""
        conn = self.connect_db()
        try:
            with conn.cursor() as cursor:
                # Remove trailing semicolon if present
                query = query.rstrip(';')

                cursor.execute(f"EXPLAIN {query}")
                return cursor.fetchall()
        finally:
            conn.close()

    def analyze_explain(self, explain_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze EXPLAIN output and generate recommendations"""
        issues = []
        recommendations = []

        for row in explain_results:
            table = row.get('table', 'unknown')
            select_type = row.get('select_type', '')
            type_ = row.get('type', '')
            key = row.get('key')
            rows = row.get('rows', 0)
            extra = row.get('Extra', '')

            # Check for full table scan
            if type_ == 'ALL':
                issues.append(f"Full table scan on table '{table}' (examining {rows} rows)")
                recommendations.append(f"Add index to table '{table}' on columns used in WHERE/JOIN")

            # Check for filesort
            if 'Using filesort' in extra:
                issues.append(f"Filesort operation on table '{table}'")
                recommendations.append(f"Add index on ORDER BY columns for table '{table}'")

            # Check for temporary table
            if 'Using temporary' in extra:
                issues.append(f"Temporary table created for table '{table}'")
                recommendations.append(f"Add index on GROUP BY columns for table '{table}'")

            # Check for high row examination
            if rows and rows > 10000:
                issues.append(f"High row examination on table '{table}' ({rows} rows)")
                recommendations.append(f"Review WHERE clause selectivity for table '{table}'")

            # Check if no index used
            if key is None and type_ not in ['system', 'const']:
                issues.append(f"No index used on table '{table}'")
                recommendations.append(f"Create appropriate index for table '{table}'")

        # Calculate severity
        severity = 'low'
        if any('Full table scan' in issue for issue in issues):
            severity = 'high'
        elif any('Filesort' in issue or 'temporary' in issue for issue in issues):
            severity = 'medium'

        return {
            'severity': severity,
            'issues': issues,
            'recommendations': list(set(recommendations)),  # Remove duplicates
            'explain_output': explain_results
        }

    def print_analysis(self, analysis: Dict[str, Any]):
        """Pretty print analysis results"""
        print("\n" + "="*60)
        print("EXPLAIN ANALYSIS")
        print("="*60)

        # Print EXPLAIN output
        print("\nEXPLAIN Output:")
        print("-"*60)
        for row in analysis['explain_output']:
            print(f"Table: {row.get('table', 'N/A')}")
            print(f"  Type: {row.get('type', 'N/A')}")
            print(f"  Key: {row.get('key', 'None')}")
            print(f"  Rows: {row.get('rows', 'N/A')}")
            print(f"  Extra: {row.get('Extra', 'N/A')}")
            print()

        # Print issues
        if analysis['issues']:
            severity_symbol = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(analysis['severity'], '⚪')
            print(f"\n{severity_symbol} Severity: {analysis['severity'].upper()}")
            print("\nIssues Found:")
            print("-"*60)
            for issue in analysis['issues']:
                print(f"  ❌ {issue}")
        else:
            print("\n✅ No issues found - query looks good!")

        # Print recommendations
        if analysis['recommendations']:
            print("\nRecommendations:")
            print("-"*60)
            for i, rec in enumerate(analysis['recommendations'], 1):
                print(f"  {i}. {rec}")

        print("\n" + "="*60)

    def analyze(self, query: str):
        """Run full analysis on query"""
        print(f"\nAnalyzing query:")
        print("-"*60)
        print(query)
        print("-"*60)

        explain_results = self.explain_query(query)
        analysis = self.analyze_explain(explain_results)
        self.print_analysis(analysis)

        return analysis


def main():
    parser = argparse.ArgumentParser(
        description='Analyze MySQL queries with EXPLAIN'
    )
    parser.add_argument(
        '--config',
        default='config.json',
        help='Configuration file path (default: config.json)'
    )
    parser.add_argument(
        '--query',
        help='SQL query to analyze'
    )
    parser.add_argument(
        '--file',
        help='File containing SQL query'
    )

    args = parser.parse_args()

    if not args.query and not args.file:
        parser.error("Either --query or --file must be provided")

    # Get query from argument or file
    if args.file:
        with open(args.file, 'r') as f:
            query = f.read()
    else:
        query = args.query

    analyzer = QueryAnalyzer(args.config)
    analyzer.analyze(query)


if __name__ == '__main__':
    main()
