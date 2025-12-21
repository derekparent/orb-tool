#!/usr/bin/env python3
"""
Dashboard Generator

Purpose: Generate a comprehensive markdown dashboard summarizing project state.
         Provides quick overview of workflow status, agent progress, and quality metrics.

Usage:
    python generate_dashboard.py [--output DASHBOARD.md] [--project-dir .]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Try to import workflow_state from skills directory
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "workflow-state" / "workflow-state" / "scripts"))

try:
    from workflow_state import WorkflowState
except ImportError:
    print("Warning: Could not import WorkflowState. Limited functionality available.")
    WorkflowState = None


class DashboardGenerator:
    """Generates project dashboard from workflow state and metrics."""

    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir).resolve()
        self.state = None
        self.metrics = None

        if WorkflowState:
            self.workflow_state = WorkflowState(project_dir)
            if self.workflow_state.exists():
                self.state = self.workflow_state.load()

        # Try to load metrics if available
        metrics_file = self.project_dir / "metrics.json"
        if metrics_file.exists():
            with open(metrics_file) as f:
                self.metrics = json.load(f)

    def generate(self) -> str:
        """Generate the complete dashboard markdown."""
        sections = [
            self._header(),
            self._project_overview(),
            self._phase_progress(),
            self._agent_status(),
            self._quality_metrics(),
            self._next_steps(),
            self._footer()
        ]

        return "\n\n".join(filter(None, sections))

    def _header(self) -> str:
        """Generate dashboard header."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""# Multi-Agent Workflow Dashboard

**Generated:** {now}
**Project:** {self.project_dir.name}
**Directory:** `{self.project_dir}`

---"""

    def _project_overview(self) -> str:
        """Generate project overview section."""
        if not self.state:
            return """## Project Overview

⚠️ No workflow state found. Initialize with:
```bash
python workflow_state.py . init
```"""

        phase = self.state.get('phase', 0)
        status = self.state.get('status', 'not_started')
        iteration = self.state.get('iteration', 0)

        phase_names = {
            0: "Not Started",
            1: "Requirements Analysis",
            2: "Architecture Design",
            3: "Code Review",
            4: "Implementation",
            5: "Integration",
            6: "QA Testing"
        }

        status_emoji = {
            'not_started': '⏸️',
            'in_progress': '🔄',
            'complete': '✅',
            'blocked': '🚫'
        }

        emoji = '🔄' if 'progress' in status else status_emoji.get(status, '❓')

        return f"""## Project Overview

| Metric | Value |
|--------|-------|
| **Current Phase** | Phase {phase}: {phase_names.get(phase, 'Unknown')} |
| **Status** | {emoji} {status.replace('_', ' ').title()} |
| **Iteration** | {iteration} |
| **Tech Stack** | {self.state.get('tech_stack', 'Not defined')} |"""

    def _phase_progress(self) -> str:
        """Generate phase progress section."""
        if not self.state:
            return None

        current_phase = self.state.get('phase', 0)
        history = self.state.get('history', [])
        completed_phases = {h['phase'] for h in history}

        phases = [
            "1. Requirements Analysis",
            "2. Architecture Design",
            "3. Code Review",
            "4. Implementation",
            "5. Integration",
            "6. QA Testing"
        ]

        lines = ["## Phase Progress", ""]
        for i, phase_name in enumerate(phases, 1):
            if i in completed_phases:
                lines.append(f"- [x] {phase_name} ✅")
            elif i == current_phase:
                lines.append(f"- [ ] {phase_name} 🔄 **(Current)**")
            else:
                lines.append(f"- [ ] {phase_name}")

        return "\n".join(lines)

    def _agent_status(self) -> str:
        """Generate agent status section."""
        if not self.state:
            return None

        agents = self.state.get('agents', [])
        if not agents:
            return "## Agent Status\n\nNo agents registered yet."

        # Group agents by status
        by_status = {
            'complete': [],
            'in_progress': [],
            'blocked': [],
            'not_started': []
        }

        for agent in agents:
            status = agent.get('status', 'not_started')
            by_status.get(status, by_status['not_started']).append(agent)

        lines = ["## Agent Status", ""]

        # Summary
        total = len(agents)
        complete = len(by_status['complete'])
        progress = (complete / total * 100) if total > 0 else 0

        lines.append(f"**Progress:** {complete}/{total} agents complete ({progress:.1f}%)")
        lines.append("")

        # Progress bar
        bar_length = 20
        filled = int(bar_length * progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        lines.append(f"`{bar}` {progress:.1f}%")
        lines.append("")

        # Detailed status
        if by_status['complete']:
            lines.append(f"### ✅ Complete ({len(by_status['complete'])})")
            lines.append("")
            for agent in by_status['complete']:
                pr = f" - PR #{agent.get('pr_number')}" if agent.get('pr_number') else ""
                lines.append(f"- **Agent {agent['id']}:** {agent['role']}{pr}")
            lines.append("")

        if by_status['in_progress']:
            lines.append(f"### 🔄 In Progress ({len(by_status['in_progress'])})")
            lines.append("")
            for agent in by_status['in_progress']:
                lines.append(f"- **Agent {agent['id']}:** {agent['role']}")
            lines.append("")

        if by_status['blocked']:
            lines.append(f"### 🚫 Blocked ({len(by_status['blocked'])})")
            lines.append("")
            for agent in by_status['blocked']:
                reason = agent.get('blocked_reason', 'Unknown')
                lines.append(f"- **Agent {agent['id']}:** {agent['role']}")
                lines.append(f"  - Reason: {reason}")
            lines.append("")

        if by_status['not_started']:
            lines.append(f"### ⏸️ Not Started ({len(by_status['not_started'])})")
            lines.append("")
            for agent in by_status['not_started']:
                lines.append(f"- **Agent {agent['id']}:** {agent['role']}")
            lines.append("")

        return "\n".join(lines)

    def _quality_metrics(self) -> str:
        """Generate quality metrics section."""
        if not self.metrics:
            return """## Quality Metrics

⚠️ No metrics available. Run:
```bash
python scripts/collect_metrics.py --output metrics.json
```"""

        m = self.metrics.get('metrics', {})
        lines = ["## Quality Metrics", ""]

        # File stats
        fs = m.get('file_stats', {})
        if fs:
            lines.append("### 📊 File Statistics")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Total Files | {fs.get('total_files', 0)} |")
            lines.append(f"| Python Files | {fs.get('python_files', 0)} |")
            lines.append(f"| JS/TS Files | {fs.get('javascript_files', 0)} |")
            lines.append(f"| Test Files | {fs.get('test_files', 0)} |")
            lines.append(f"| Total Lines | {fs.get('total_lines', 0):,} |")
            lines.append("")

        # Test coverage
        cov = m.get('test_coverage', {})
        if cov.get('available'):
            coverage = cov.get('total_coverage', 0)
            emoji = "✅" if coverage >= 80 else "⚠️" if coverage >= 60 else "❌"
            lines.append("### 🧪 Test Coverage")
            lines.append("")
            lines.append(f"{emoji} **{coverage:.1f}%** (Target: ≥80%)")
            lines.append("")

        # Complexity
        comp = m.get('complexity', {})
        if comp.get('available'):
            avg_complexity = comp.get('average_complexity', 0)
            high_complexity = len(comp.get('high_complexity_functions', []))
            emoji = "✅" if avg_complexity <= 5 else "⚠️" if avg_complexity <= 10 else "❌"

            lines.append("### 🔄 Code Complexity")
            lines.append("")
            lines.append(f"{emoji} Average: **{avg_complexity:.1f}**")
            if high_complexity > 0:
                lines.append(f"⚠️ {high_complexity} functions with complexity >10")
            lines.append("")

        # Security
        sec = m.get('security', {})
        if sec.get('available'):
            total = sec.get('total_issues', 0)
            high = sec.get('high_severity', 0)
            medium = sec.get('medium_severity', 0)

            emoji = "✅" if total == 0 else "❌" if high > 0 else "⚠️"

            lines.append("### 🔒 Security Issues")
            lines.append("")
            lines.append(f"{emoji} Total: **{total}**")
            if total > 0:
                lines.append(f"- High: {high}")
                lines.append(f"- Medium: {medium}")
                lines.append(f"- Low: {sec.get('low_severity', 0)}")
            lines.append("")

        # Lint
        lint = m.get('lint', {})
        if lint.get('available'):
            total = lint.get('total_issues', 0)
            emoji = "✅" if total == 0 else "⚠️"

            lines.append("### 📝 Lint Issues")
            lines.append("")
            lines.append(f"{emoji} Total: **{total}**")
            lines.append("")

        return "\n".join(lines)

    def _next_steps(self) -> str:
        """Generate next steps section."""
        if not self.state and not WorkflowState:
            return None

        lines = ["## 🎯 Next Steps", ""]

        if WorkflowState and self.workflow_state.exists():
            next_step = self.workflow_state.get_next_step()
            lines.append(next_step)

            # Add validation if phase is ready to complete
            phase = self.state.get('phase', 0)
            if phase > 0:
                is_valid, issues = self.workflow_state.validate_phase_completion(phase)
                if not is_valid:
                    lines.append("")
                    lines.append("### ⚠️ Blocking Issues")
                    lines.append("")
                    for issue in issues:
                        lines.append(f"- {issue}")
        else:
            lines.append("Initialize workflow state to see next steps.")

        return "\n".join(lines)

    def _footer(self) -> str:
        """Generate dashboard footer."""
        return """---

**Commands:**
- `python scripts/collect_metrics.py` - Update metrics
- `python scripts/auto_quality_audit.sh` - Run quality checks
- `python scripts/determine_merge_order.py` - Analyze PR merge order
- `python workflow_state.py . next-step` - Get next action

*Auto-generated dashboard. Update with `python scripts/generate_dashboard.py`*"""

    def save(self, output_file: str):
        """Save dashboard to file."""
        dashboard = self.generate()
        output_path = Path(output_file)

        with open(output_path, 'w') as f:
            f.write(dashboard)

        print(f"✅ Dashboard saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate project dashboard"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="DASHBOARD.md",
        help="Output markdown file (default: DASHBOARD.md)"
    )
    parser.add_argument(
        "--project-dir",
        "-p",
        default=".",
        help="Project directory (default: current directory)"
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print to stdout instead of saving"
    )

    args = parser.parse_args()

    generator = DashboardGenerator(args.project_dir)

    if args.print:
        print(generator.generate())
    else:
        generator.save(args.output)


if __name__ == "__main__":
    main()
