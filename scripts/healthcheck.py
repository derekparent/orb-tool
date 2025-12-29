#!/usr/bin/env python3
"""Health check script for Docker container.

Returns exit code 0 if healthy, 1 if unhealthy.
"""

import os
import sys
import urllib.request
import urllib.error


def check_health() -> bool:
    """Check if the application is healthy."""
    port = os.environ.get("PORT", "8000")
    url = f"http://localhost:{port}/health"

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return True
            return False
    except urllib.error.URLError as e:
        print(f"Health check failed: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Health check error: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if check_health():
        print("Healthy")
        sys.exit(0)
    else:
        print("Unhealthy")
        sys.exit(1)
