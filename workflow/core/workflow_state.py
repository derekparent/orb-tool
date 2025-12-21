#!/usr/bin/env python3
"""
Workflow State Management for Multi-Agent Workflow
Standalone version - no external dependencies beyond stdlib
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class WorkflowState:
    """Manages workflow state persistence"""
    
    STATE_FILE = "WORKFLOW_STATE.json"
    
    def __init__(self, project_path: str = "."):
        """Initialize with project path"""
        self.project_path = Path(project_path).resolve()
        self.state_file = self.project_path / self.STATE_FILE
        
    def exists(self) -> bool:
        """Check if state file exists"""
        return self.state_file.exists()
    
    def load(self) -> Dict[str, Any]:
        """Load state from file, return empty state if doesn't exist"""
        if not self.exists():
            return self._empty_state()
        
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️  Corrupt state file, creating fresh state")
            return self._empty_state()
    
    def save(self, state: Dict[str, Any]) -> None:
        """Save state to file"""
        state['last_updated'] = datetime.now().isoformat()
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def _empty_state(self) -> Dict[str, Any]:
        """Return empty state structure"""
        return {
            "project": self.project_path.name,
            "project_path": str(self.project_path),
            "phase": 0,
            "iteration": 0,
            "status": "not_started",
            "tech_stack": None,
            "agents": [],
            "history": [],
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
    
    def update_phase(self, phase: int, status: str = "in_progress") -> Dict[str, Any]:
        """Update current phase and status"""
        state = self.load()
        state['phase'] = phase
        state['status'] = status
        self.save(state)
        return state
    
    def complete_phase(self, phase: int) -> Dict[str, Any]:
        """Mark phase as complete"""
        state = self.load()
        state['history'].append({
            "phase": phase,
            "completed_at": datetime.now().isoformat()
        })
        state['status'] = f"phase_{phase}_complete"
        self.save(state)
        return state
    
    def add_agent(self, agent_id: int, role: str, status: str = "not_started") -> Dict[str, Any]:
        """Add agent to state"""
        state = self.load()
        agent = {
            "id": agent_id,
            "role": role,
            "status": status,
            "started_at": datetime.now().isoformat() if status != "not_started" else None,
            "completed_at": None,
            "pr_number": None
        }
        state['agents'].append(agent)
        self.save(state)
        return state
    
    def update_agent(self, agent_id: int, **kwargs) -> Dict[str, Any]:
        """Update agent status"""
        state = self.load()
        for agent in state['agents']:
            if agent['id'] == agent_id:
                agent.update(kwargs)
                if kwargs.get('status') == 'complete' and not agent.get('completed_at'):
                    agent['completed_at'] = datetime.now().isoformat()
                break
        self.save(state)
        return state
    
    def get_phase(self) -> int:
        """Get current phase number"""
        return self.load().get('phase', 0)
    
    def get_status(self) -> str:
        """Get current status"""
        return self.load().get('status', 'not_started')
    
    def get_agents(self) -> List[Dict[str, Any]]:
        """Get all agents"""
        return self.load().get('agents', [])
    
    def next_phase(self) -> int:
        """Get next phase number based on current state"""
        current_phase = self.get_phase()
        status = self.get_status()
        
        if "complete" in status:
            return current_phase + 1
        return current_phase
    
    def format_status(self) -> str:
        """Format current status for display"""
        state = self.load()
        phase = state.get('phase', 0)
        iteration = state.get('iteration', 0)
        status = state.get('status', 'not_started')
        
        output = [
            f"📊 {state.get('project', 'Unknown Project')}",
            f"Phase: {phase} | Iteration: {iteration}",
            f"Status: {status}",
            ""
        ]
        
        history = state.get('history', [])
        if history:
            output.append("✅ Completed:")
            for h in history[-5:]:
                output.append(f"   Phase {h['phase']}")
        
        agents = state.get('agents', [])
        active = [a for a in agents if a.get('status') in ['in_progress', 'not_started']]
        complete = [a for a in agents if a.get('status') == 'complete']
        
        if complete:
            output.append("")
            output.append(f"✅ Agents Complete: {len(complete)}")
            for a in complete:
                pr = f"PR #{a.get('pr_number')}" if a.get('pr_number') else ""
                output.append(f"   Agent {a['id']}: {a['role']} {pr}")
        
        if active:
            output.append("")
            output.append(f"🔄 Agents Active: {len(active)}")
            for a in active:
                output.append(f"   Agent {a['id']}: {a['role']} - {a.get('status', 'unknown')}")
        
        return "\n".join(output)
    
    def next_step(self) -> str:
        """Suggest next action based on current state"""
        state = self.load()
        phase = state.get('phase', 0)
        status = state.get('status', 'not_started')
        agents = state.get('agents', [])
        
        if status == 'not_started':
            return "→ Start Phase 1: Planning\n  Run: phase1-planning for this project"
        
        if phase == 4:
            # Check agent status
            incomplete = [a for a in agents if a.get('status') != 'complete']
            if incomplete:
                return f"→ Phase 4 in progress: {len(incomplete)} agents still working\n  Monitor agent progress and PRs"
            else:
                return "→ All agents complete! Start Phase 5: Integration\n  Run: phase5-integration for this project"
        
        if 'complete' in status:
            next_p = phase + 1
            if next_p > 6:
                return "→ Workflow complete! Consider starting a new iteration."
            return f"→ Start Phase {next_p}\n  Run: phase{next_p} skill for this project"
        
        return f"→ Continue Phase {phase} (status: {status})"


def main():
    """CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: workflow_state.py <project_path> [command]")
        print("")
        print("Commands:")
        print("  (none)      Show current status")
        print("  init        Initialize new state file")
        print("  next-step   Show recommended next action")
        print("  json        Output raw JSON state")
        print("  phase N     Update to phase N")
        print("  complete N  Mark phase N as complete")
        sys.exit(1)
    
    project_path = sys.argv[1]
    ws = WorkflowState(project_path)
    
    if len(sys.argv) == 2:
        print(ws.format_status())
        return
    
    command = sys.argv[2]
    
    if command == "init":
        ws.save(ws._empty_state())
        print("✅ Initialized WORKFLOW_STATE.json")
        
    elif command == "next-step":
        print(ws.next_step())
        
    elif command == "json":
        print(json.dumps(ws.load(), indent=2))
        
    elif command == "phase":
        if len(sys.argv) < 4:
            print("Usage: workflow_state.py <path> phase <number>")
            sys.exit(1)
        phase = int(sys.argv[3])
        ws.update_phase(phase)
        print(f"✅ Updated to Phase {phase}")
        
    elif command == "complete":
        if len(sys.argv) < 4:
            print("Usage: workflow_state.py <path> complete <phase_number>")
            sys.exit(1)
        phase = int(sys.argv[3])
        ws.complete_phase(phase)
        print(f"✅ Marked Phase {phase} complete")
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
