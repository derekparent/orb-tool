#!/usr/bin/env python3
"""
Merge Order Determination Script

Purpose: Analyze PR dependencies and file overlap to determine optimal merge sequence.
         Minimizes merge conflicts and ensures dependency order is respected.

Usage:
    python determine_merge_order.py [--prs-dir PRs/] [--output merge_order.txt]
"""

import argparse
import json
import os
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


class PRAnalyzer:
    """Analyzes PRs to determine optimal merge order."""

    def __init__(self, prs_dir: str = "PRs"):
        self.prs_dir = Path(prs_dir)
        self.prs: Dict[str, Dict[str, Any]] = {}
        self.dependency_graph: Dict[str, List[str]] = defaultdict(list)
        self.file_ownership: Dict[str, Set[str]] = defaultdict(set)

    def load_prs(self):
        """Load all PR metadata from the PRs directory."""
        if not self.prs_dir.exists():
            print(f"Warning: PRs directory not found: {self.prs_dir}")
            return

        for pr_file in self.prs_dir.glob("*.md"):
            pr_id = pr_file.stem
            metadata = self._parse_pr_file(pr_file)
            self.prs[pr_id] = metadata

        print(f"Loaded {len(self.prs)} PRs")

    def _parse_pr_file(self, pr_file: Path) -> Dict[str, Any]:
        """Parse a PR markdown file to extract metadata."""
        metadata = {
            "id": pr_file.stem,
            "title": "",
            "files_changed": [],
            "dependencies": [],
            "blocks": []
        }

        with open(pr_file, 'r') as f:
            content = f.read()

            # Extract title (first # heading)
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if title_match:
                metadata["title"] = title_match.group(1)

            # Extract dependencies
            # Look for patterns like "Requires PR #123" or "Depends on: PR #456"
            dep_patterns = [
                r'Requires PR #(\w+)',
                r'Depends on:?\s*PR #(\w+)',
                r'Dependency:?\s*PR #(\w+)',
                r'After PR #(\w+)'
            ]
            for pattern in dep_patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    dep_id = match.group(1)
                    if dep_id not in metadata["dependencies"]:
                        metadata["dependencies"].append(dep_id)

            # Extract blocks
            # Look for patterns like "Blocks PR #123"
            block_patterns = [
                r'Blocks PR #(\w+)',
                r'Required by PR #(\w+)',
                r'Before PR #(\w+)'
            ]
            for pattern in block_patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    blocked_id = match.group(1)
                    if blocked_id not in metadata["blocks"]:
                        metadata["blocks"].append(blocked_id)

            # Extract files changed
            # Look for "Files Changed:" section
            files_section = re.search(
                r'\*\*Files Changed:\*\*\s*(.+?)(?=\n\n|\n\*\*|$)',
                content,
                re.DOTALL
            )
            if files_section:
                files_text = files_section.group(1)
                # Extract file paths (lines starting with - or * followed by a path)
                for line in files_text.split('\n'):
                    # Match patterns like "- path/to/file.py - description"
                    file_match = re.search(r'[-*]\s+`?([^\s`-]+\.\w+)`?\s*[-:]', line)
                    if file_match:
                        file_path = file_match.group(1)
                        metadata["files_changed"].append(file_path)

        return metadata

    def build_dependency_graph(self):
        """Build a directed graph of PR dependencies."""
        for pr_id, pr_meta in self.prs.items():
            # Add explicit dependencies
            for dep in pr_meta["dependencies"]:
                if dep in self.prs:
                    self.dependency_graph[dep].append(pr_id)

            # Add inverse of "blocks" relationships
            for blocked in pr_meta["blocks"]:
                if blocked in self.prs:
                    self.dependency_graph[pr_id].append(blocked)

        print(f"Built dependency graph with {len(self.dependency_graph)} relationships")

    def analyze_file_conflicts(self):
        """Analyze which PRs modify the same files."""
        for pr_id, pr_meta in self.prs.items():
            for file_path in pr_meta["files_changed"]:
                self.file_ownership[file_path].add(pr_id)

        # Find files with conflicts
        conflicting_files = {
            f: prs for f, prs in self.file_ownership.items() if len(prs) > 1
        }

        print(f"Found {len(conflicting_files)} files modified by multiple PRs")
        return conflicting_files

    def topological_sort(self) -> List[str]:
        """
        Perform topological sort to determine merge order.
        Returns list of PR IDs in merge order.
        """
        # Calculate in-degree for each node
        in_degree = {pr_id: 0 for pr_id in self.prs.keys()}
        for dependents in self.dependency_graph.values():
            for dependent in dependents:
                if dependent in in_degree:
                    in_degree[dependent] += 1

        # Queue of nodes with no dependencies
        queue = deque([pr_id for pr_id, degree in in_degree.items() if degree == 0])
        sorted_order = []

        while queue:
            # For nodes at the same level, prioritize by file conflicts
            # (merge PRs with fewer conflicts first)
            current_level = list(queue)
            queue.clear()

            # Sort by conflict count
            current_level.sort(key=lambda pr_id: self._get_conflict_count(pr_id))

            for pr_id in current_level:
                sorted_order.append(pr_id)

                # Reduce in-degree for dependents
                for dependent in self.dependency_graph.get(pr_id, []):
                    if dependent in in_degree:
                        in_degree[dependent] -= 1
                        if in_degree[dependent] == 0:
                            queue.append(dependent)

        # Check for cycles
        if len(sorted_order) != len(self.prs):
            remaining = set(self.prs.keys()) - set(sorted_order)
            print(f"Warning: Circular dependencies detected in PRs: {remaining}")
            # Add remaining PRs at the end
            sorted_order.extend(remaining)

        return sorted_order

    def _get_conflict_count(self, pr_id: str) -> int:
        """Count how many other PRs this PR conflicts with (same files)."""
        pr_files = set(self.prs[pr_id]["files_changed"])
        conflict_count = 0

        for file_path in pr_files:
            other_prs = self.file_ownership[file_path] - {pr_id}
            conflict_count += len(other_prs)

        return conflict_count

    def generate_merge_plan(self) -> List[Dict[str, Any]]:
        """Generate detailed merge plan with conflict warnings."""
        merge_order = self.topological_sort()
        plan = []

        merged_files: Set[str] = set()

        for i, pr_id in enumerate(merge_order, 1):
            pr_meta = self.prs[pr_id]
            pr_files = set(pr_meta["files_changed"])

            # Identify potential conflicts with already-merged PRs
            conflicts = pr_files & merged_files

            plan.append({
                "order": i,
                "pr_id": pr_id,
                "title": pr_meta["title"],
                "files_changed": pr_meta["files_changed"],
                "dependencies": pr_meta["dependencies"],
                "potential_conflicts": list(conflicts),
                "conflict_risk": "HIGH" if len(conflicts) > 3 else "MEDIUM" if len(conflicts) > 0 else "LOW"
            })

            # Mark files as merged
            merged_files.update(pr_files)

        return plan

    def print_merge_plan(self, plan: List[Dict[str, Any]]):
        """Print the merge plan in a readable format."""
        print("\n" + "="*70)
        print("RECOMMENDED MERGE ORDER")
        print("="*70)

        for step in plan:
            print(f"\n{step['order']}. PR #{step['pr_id']}: {step['title']}")
            print(f"   Conflict Risk: {step['conflict_risk']}")

            if step["dependencies"]:
                print(f"   Dependencies: {', '.join(f'PR #{d}' for d in step['dependencies'])}")

            if step["potential_conflicts"]:
                print(f"   ⚠ Potential conflicts in {len(step['potential_conflicts'])} files:")
                for f in step["potential_conflicts"][:5]:  # Show first 5
                    print(f"     - {f}")
                if len(step["potential_conflicts"]) > 5:
                    print(f"     ... and {len(step['potential_conflicts']) - 5} more")

        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"Total PRs: {len(plan)}")
        print(f"High Risk: {sum(1 for p in plan if p['conflict_risk'] == 'HIGH')}")
        print(f"Medium Risk: {sum(1 for p in plan if p['conflict_risk'] == 'MEDIUM')}")
        print(f"Low Risk: {sum(1 for p in plan if p['conflict_risk'] == 'LOW')}")
        print("="*70)

    def save_plan(self, plan: List[Dict[str, Any]], output_file: str):
        """Save merge plan to file."""
        with open(output_file, 'w') as f:
            f.write("RECOMMENDED MERGE ORDER\n")
            f.write("="*70 + "\n\n")

            for step in plan:
                f.write(f"{step['order']}. PR #{step['pr_id']}: {step['title']}\n")
                f.write(f"   Conflict Risk: {step['conflict_risk']}\n")

                if step["dependencies"]:
                    f.write(f"   Dependencies: {', '.join(f'PR #{d}' for d in step['dependencies'])}\n")

                if step["potential_conflicts"]:
                    f.write(f"   Potential conflicts: {', '.join(step['potential_conflicts'])}\n")

                f.write("\n")

        print(f"\n✓ Merge plan saved to: {output_file}")

        # Also save as JSON for programmatic use
        json_file = output_file.replace('.txt', '.json')
        with open(json_file, 'w') as f:
            json.dump(plan, f, indent=2)
        print(f"✓ JSON version saved to: {json_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Determine optimal merge order for PRs"
    )
    parser.add_argument(
        "--prs-dir",
        default="PRs",
        help="Directory containing PR markdown files (default: PRs)"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="merge_order.txt",
        help="Output file for merge plan (default: merge_order.txt)"
    )

    args = parser.parse_args()

    analyzer = PRAnalyzer(args.prs_dir)
    analyzer.load_prs()

    if not analyzer.prs:
        print("No PRs found. Exiting.")
        return

    analyzer.build_dependency_graph()
    analyzer.analyze_file_conflicts()

    plan = analyzer.generate_merge_plan()
    analyzer.print_merge_plan(plan)
    analyzer.save_plan(plan, args.output)


if __name__ == "__main__":
    main()
