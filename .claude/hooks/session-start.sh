#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# Install Python dependencies
# Force-install blinker first (system-managed version conflicts with Flask's requirement)
pip install --break-system-packages --ignore-installed "blinker>=1.9"
pip install --break-system-packages -r requirements.txt

# Make ruff and pytest available on PATH
echo "export PATH=\"$(python -m site --user-base)/bin:$PATH\"" >> "$CLAUDE_ENV_FILE"
