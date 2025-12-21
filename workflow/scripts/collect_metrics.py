#!/usr/bin/env python3
"""
Metrics Collection Script

Purpose: Automate gathering of code quality metrics for Phase 3 and Phase 5 reviews.
Outputs: JSON file with test coverage, complexity, security issues, and other metrics.

Usage:
    python collect_metrics.py [--output metrics.json] [--project-dir .]
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class MetricsCollector:
    """Collects various code quality metrics."""

    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir).resolve()
        self.metrics: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "project_dir": str(self.project_dir),
            "metrics": {}
        }

    def run_command(self, cmd: List[str], capture_output: bool = True) -> Optional[subprocess.CompletedProcess]:
        """Run a shell command and return the result."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_dir,
                capture_output=capture_output,
                text=True,
                check=False
            )
            return result
        except FileNotFoundError:
            print(f"Warning: Command '{cmd[0]}' not found. Skipping.", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Error running {cmd}: {e}", file=sys.stderr)
            return None

    def collect_test_coverage(self) -> Dict[str, Any]:
        """Collect test coverage metrics using pytest-cov."""
        print("Collecting test coverage...")
        coverage_data = {
            "available": False,
            "total_coverage": 0.0,
            "line_coverage": 0.0,
            "branch_coverage": 0.0,
            "files": []
        }

        # Try pytest with coverage
        result = self.run_command([
            "pytest",
            "--cov=.",
            "--cov-report=json",
            "--cov-report=term",
            "-q"
        ])

        if result and result.returncode == 0:
            # Check for coverage.json
            coverage_file = self.project_dir / ".coverage.json"
            if coverage_file.exists():
                try:
                    with open(coverage_file) as f:
                        cov_data = json.load(f)
                        coverage_data["available"] = True
                        coverage_data["total_coverage"] = cov_data.get("totals", {}).get("percent_covered", 0.0)
                except Exception as e:
                    print(f"Warning: Could not parse coverage data: {e}", file=sys.stderr)

        return coverage_data

    def collect_complexity(self) -> Dict[str, Any]:
        """Collect cyclomatic complexity using radon."""
        print("Collecting complexity metrics...")
        complexity_data = {
            "available": False,
            "average_complexity": 0.0,
            "max_complexity": 0,
            "high_complexity_functions": []
        }

        # Try radon for Python files
        result = self.run_command([
            "radon",
            "cc",
            ".",
            "-a",
            "--json"
        ])

        if result and result.returncode == 0 and result.stdout:
            try:
                radon_data = json.loads(result.stdout)
                complexity_data["available"] = True

                all_complexities = []
                high_complexity = []

                for file_path, functions in radon_data.items():
                    for func in functions:
                        complexity = func.get("complexity", 0)
                        all_complexities.append(complexity)

                        if complexity > 10:  # Threshold for "high complexity"
                            high_complexity.append({
                                "file": file_path,
                                "function": func.get("name", "unknown"),
                                "complexity": complexity,
                                "line": func.get("lineno", 0)
                            })

                if all_complexities:
                    complexity_data["average_complexity"] = sum(all_complexities) / len(all_complexities)
                    complexity_data["max_complexity"] = max(all_complexities)
                    complexity_data["high_complexity_functions"] = high_complexity

            except Exception as e:
                print(f"Warning: Could not parse radon output: {e}", file=sys.stderr)

        return complexity_data

    def collect_security_issues(self) -> Dict[str, Any]:
        """Collect security issues using bandit."""
        print("Collecting security issues...")
        security_data = {
            "available": False,
            "total_issues": 0,
            "high_severity": 0,
            "medium_severity": 0,
            "low_severity": 0,
            "issues": []
        }

        # Try bandit for Python files
        result = self.run_command([
            "bandit",
            "-r",
            ".",
            "-f",
            "json",
            "--quiet"
        ])

        if result and result.stdout:
            try:
                bandit_data = json.loads(result.stdout)
                security_data["available"] = True

                results = bandit_data.get("results", [])
                security_data["total_issues"] = len(results)

                for issue in results:
                    severity = issue.get("issue_severity", "UNDEFINED")

                    if severity == "HIGH":
                        security_data["high_severity"] += 1
                    elif severity == "MEDIUM":
                        security_data["medium_severity"] += 1
                    elif severity == "LOW":
                        security_data["low_severity"] += 1

                    security_data["issues"].append({
                        "file": issue.get("filename", "unknown"),
                        "line": issue.get("line_number", 0),
                        "severity": severity,
                        "confidence": issue.get("issue_confidence", "UNDEFINED"),
                        "issue": issue.get("issue_text", ""),
                        "test_id": issue.get("test_id", "")
                    })

            except Exception as e:
                print(f"Warning: Could not parse bandit output: {e}", file=sys.stderr)

        return security_data

    def collect_lint_issues(self) -> Dict[str, Any]:
        """Collect linting issues using flake8/pylint."""
        print("Collecting lint issues...")
        lint_data = {
            "available": False,
            "total_issues": 0,
            "errors": 0,
            "warnings": 0,
            "issues": []
        }

        # Try flake8 for Python files
        result = self.run_command([
            "flake8",
            ".",
            "--format=json"
        ])

        if result and result.stdout:
            try:
                # flake8 with --format=json requires flake8-json plugin
                # Fallback to parsing default output
                issues = []
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    # Format: path/to/file.py:line:col: CODE message
                    parts = line.split(":", 3)
                    if len(parts) >= 4:
                        issues.append({
                            "file": parts[0],
                            "line": int(parts[1]) if parts[1].isdigit() else 0,
                            "column": int(parts[2]) if parts[2].isdigit() else 0,
                            "message": parts[3].strip()
                        })

                lint_data["available"] = True
                lint_data["total_issues"] = len(issues)
                lint_data["issues"] = issues

            except Exception as e:
                print(f"Warning: Could not parse flake8 output: {e}", file=sys.stderr)

        return lint_data

    def collect_file_stats(self) -> Dict[str, Any]:
        """Collect basic file statistics."""
        print("Collecting file statistics...")
        stats = {
            "total_files": 0,
            "python_files": 0,
            "javascript_files": 0,
            "test_files": 0,
            "total_lines": 0
        }

        for ext, key in [(".py", "python_files"), (".js", "javascript_files"), (".ts", "javascript_files")]:
            files = list(self.project_dir.rglob(f"*{ext}"))
            stats[key] += len(files)
            stats["total_files"] += len(files)

            # Count test files
            test_files = [f for f in files if "test" in f.name.lower()]
            stats["test_files"] += len(test_files)

            # Count lines
            for file in files:
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        stats["total_lines"] += sum(1 for _ in f)
                except Exception:
                    pass

        return stats

    def collect_all(self) -> Dict[str, Any]:
        """Collect all metrics."""
        print(f"Collecting metrics for project: {self.project_dir}\n")

        self.metrics["metrics"]["file_stats"] = self.collect_file_stats()
        self.metrics["metrics"]["test_coverage"] = self.collect_test_coverage()
        self.metrics["metrics"]["complexity"] = self.collect_complexity()
        self.metrics["metrics"]["security"] = self.collect_security_issues()
        self.metrics["metrics"]["lint"] = self.collect_lint_issues()

        print("\n✓ Metrics collection complete")
        return self.metrics

    def save(self, output_file: str):
        """Save metrics to JSON file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(self.metrics, f, indent=2)

        print(f"\n✓ Metrics saved to: {output_path}")

    def print_summary(self):
        """Print a summary of collected metrics."""
        print("\n" + "="*60)
        print("METRICS SUMMARY")
        print("="*60)

        m = self.metrics["metrics"]

        print("\n📊 File Statistics:")
        fs = m.get("file_stats", {})
        print(f"  Total Files: {fs.get('total_files', 0)}")
        print(f"  Python Files: {fs.get('python_files', 0)}")
        print(f"  JavaScript/TypeScript Files: {fs.get('javascript_files', 0)}")
        print(f"  Test Files: {fs.get('test_files', 0)}")
        print(f"  Total Lines: {fs.get('total_lines', 0):,}")

        print("\n🧪 Test Coverage:")
        cov = m.get("test_coverage", {})
        if cov.get("available"):
            print(f"  Total Coverage: {cov.get('total_coverage', 0):.1f}%")
        else:
            print("  Not available (install pytest-cov)")

        print("\n🔄 Complexity:")
        comp = m.get("complexity", {})
        if comp.get("available"):
            print(f"  Average Complexity: {comp.get('average_complexity', 0):.1f}")
            print(f"  Max Complexity: {comp.get('max_complexity', 0)}")
            print(f"  High Complexity Functions: {len(comp.get('high_complexity_functions', []))}")
        else:
            print("  Not available (install radon)")

        print("\n🔒 Security Issues:")
        sec = m.get("security", {})
        if sec.get("available"):
            print(f"  Total Issues: {sec.get('total_issues', 0)}")
            print(f"  High Severity: {sec.get('high_severity', 0)}")
            print(f"  Medium Severity: {sec.get('medium_severity', 0)}")
            print(f"  Low Severity: {sec.get('low_severity', 0)}")
        else:
            print("  Not available (install bandit)")

        print("\n📝 Lint Issues:")
        lint = m.get("lint", {})
        if lint.get("available"):
            print(f"  Total Issues: {lint.get('total_issues', 0)}")
        else:
            print("  Not available (install flake8)")

        print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Collect code quality metrics for multi-agent workflow"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="metrics.json",
        help="Output JSON file (default: metrics.json)"
    )
    parser.add_argument(
        "--project-dir",
        "-p",
        default=".",
        help="Project directory to analyze (default: current directory)"
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only print summary, don't save to file"
    )

    args = parser.parse_args()

    collector = MetricsCollector(args.project_dir)
    collector.collect_all()

    if not args.summary_only:
        collector.save(args.output)

    collector.print_summary()


if __name__ == "__main__":
    main()
