#!/bin/bash
#
# Quality Audit Automation Script
#
# Purpose: Single command to run all linters, tests, and security checks.
#          Generates a "Go/No-Go" report for Phase 5.5.
#
# Usage:
#   ./auto_quality_audit.sh [--strict] [--output report.txt]
#
# Options:
#   --strict    Fail on any warnings (not just errors)
#   --output    Save report to file (default: quality_audit_report.txt)
#   --no-tests  Skip running tests (only run static analysis)
#

set -e  # Exit on error (can be overridden by || true for individual checks)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STRICT_MODE=false
OUTPUT_FILE="quality_audit_report.txt"
SKIP_TESTS=false
EXIT_CODE=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --strict)
            STRICT_MODE=true
            shift
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --no-tests)
            SKIP_TESTS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Initialize report
exec > >(tee "$OUTPUT_FILE")
exec 2>&1

echo "======================================================================="
echo "                     QUALITY AUDIT REPORT"
echo "======================================================================="
echo "Date: $(date)"
echo "Directory: $(pwd)"
echo "Strict Mode: $STRICT_MODE"
echo "======================================================================="
echo ""

# Function to print section header
print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Function to print status
print_status() {
    local status=$1
    local message=$2

    if [ "$status" == "PASS" ]; then
        echo -e "${GREEN}✓ PASS${NC} - $message"
    elif [ "$status" == "WARN" ]; then
        echo -e "${YELLOW}⚠ WARN${NC} - $message"
        if [ "$STRICT_MODE" == true ]; then
            EXIT_CODE=1
        fi
    elif [ "$status" == "FAIL" ]; then
        echo -e "${RED}✗ FAIL${NC} - $message"
        EXIT_CODE=1
    else
        echo "  $message"
    fi
}

# 1. File Structure Check
print_header "1. File Structure Check"

if [ -f "README.md" ]; then
    print_status "PASS" "README.md exists"
else
    print_status "WARN" "README.md not found"
fi

if [ -f "requirements.txt" ] || [ -f "package.json" ]; then
    print_status "PASS" "Dependency file found"
else
    print_status "WARN" "No dependency file (requirements.txt or package.json) found"
fi

# 2. Python Linting
print_header "2. Python Linting (flake8)"

if command -v flake8 &> /dev/null; then
    if flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics; then
        print_status "PASS" "No critical linting errors"
    else
        print_status "FAIL" "Critical linting errors found"
    fi

    # Check for warnings
    WARNING_COUNT=$(flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics 2>&1 | tail -n 1 | awk '{print $1}')
    if [ -z "$WARNING_COUNT" ] || [ "$WARNING_COUNT" -eq 0 ]; then
        print_status "PASS" "No linting warnings"
    else
        print_status "WARN" "$WARNING_COUNT linting warnings found"
    fi
else
    print_status "WARN" "flake8 not installed, skipping Python linting"
fi

# 3. Python Type Checking
print_header "3. Python Type Checking (mypy)"

if command -v mypy &> /dev/null; then
    if mypy . --ignore-missing-imports --no-strict-optional 2>&1 | tee /tmp/mypy_output.txt; then
        print_status "PASS" "Type checking passed"
    else
        ERROR_COUNT=$(grep -c "error:" /tmp/mypy_output.txt || echo "0")
        if [ "$ERROR_COUNT" -gt 0 ]; then
            print_status "FAIL" "$ERROR_COUNT type errors found"
        else
            print_status "PASS" "Type checking passed"
        fi
    fi
    rm -f /tmp/mypy_output.txt
else
    print_status "WARN" "mypy not installed, skipping type checking"
fi

# 4. Security Scan
print_header "4. Security Scan (bandit)"

if command -v bandit &> /dev/null; then
    if bandit -r . -ll -f txt 2>&1 | tee /tmp/bandit_output.txt; then
        print_status "PASS" "No high/medium security issues"
    else
        ISSUE_COUNT=$(grep -c "Issue:" /tmp/bandit_output.txt || echo "0")
        if [ "$ISSUE_COUNT" -gt 0 ]; then
            print_status "FAIL" "$ISSUE_COUNT security issues found"
        else
            print_status "PASS" "No high/medium security issues"
        fi
    fi
    rm -f /tmp/bandit_output.txt
else
    print_status "WARN" "bandit not installed, skipping security scan"
fi

# 5. Code Complexity
print_header "5. Code Complexity (radon)"

if command -v radon &> /dev/null; then
    # Check for functions with complexity > 10
    COMPLEX_FUNCTIONS=$(radon cc . -a -nb -s | grep -E "^\s+[A-Z]\s+" | wc -l || echo "0")
    if [ "$COMPLEX_FUNCTIONS" -eq 0 ]; then
        print_status "PASS" "No overly complex functions"
    else
        print_status "WARN" "$COMPLEX_FUNCTIONS functions with high complexity (>10)"
    fi

    # Show average complexity
    AVG_COMPLEXITY=$(radon cc . -a -s | grep "Average complexity:" | awk '{print $3}' | head -1)
    echo "  Average complexity: $AVG_COMPLEXITY"
else
    print_status "WARN" "radon not installed, skipping complexity analysis"
fi

# 6. Tests
if [ "$SKIP_TESTS" == false ]; then
    print_header "6. Test Suite"

    if command -v pytest &> /dev/null; then
        if pytest --maxfail=1 --disable-warnings -q 2>&1 | tee /tmp/pytest_output.txt; then
            print_status "PASS" "All tests passed"
        else
            FAILED_COUNT=$(grep -E "^(FAILED|ERROR)" /tmp/pytest_output.txt | wc -l || echo "0")
            print_status "FAIL" "$FAILED_COUNT tests failed"
        fi
        rm -f /tmp/pytest_output.txt
    elif [ -f "package.json" ] && command -v npm &> /dev/null; then
        if npm test 2>&1 | tee /tmp/npm_test_output.txt; then
            print_status "PASS" "All tests passed"
        else
            print_status "FAIL" "Tests failed"
        fi
        rm -f /tmp/npm_test_output.txt
    else
        print_status "WARN" "No test runner found (pytest or npm)"
    fi

    # 7. Test Coverage
    print_header "7. Test Coverage"

    if command -v pytest &> /dev/null && python -c "import pytest_cov" 2>/dev/null; then
        COVERAGE=$(pytest --cov=. --cov-report=term-missing --cov-report=term:skip-covered -q 2>&1 | grep "TOTAL" | awk '{print $4}' | sed 's/%//')
        if [ -n "$COVERAGE" ]; then
            echo "  Total coverage: ${COVERAGE}%"
            if [ "$COVERAGE" -ge 80 ]; then
                print_status "PASS" "Coverage is ${COVERAGE}% (≥80%)"
            elif [ "$COVERAGE" -ge 60 ]; then
                print_status "WARN" "Coverage is ${COVERAGE}% (target: ≥80%)"
            else
                print_status "FAIL" "Coverage is ${COVERAGE}% (target: ≥80%)"
            fi
        else
            print_status "WARN" "Could not determine coverage"
        fi
    else
        print_status "WARN" "pytest-cov not installed, skipping coverage check"
    fi
else
    echo ""
    echo "⊘ Tests skipped (--no-tests flag)"
fi

# 8. Git Status
print_header "8. Git Status"

if command -v git &> /dev/null && [ -d .git ]; then
    UNCOMMITTED=$(git status --porcelain | wc -l)
    if [ "$UNCOMMITTED" -eq 0 ]; then
        print_status "PASS" "No uncommitted changes"
    else
        print_status "WARN" "$UNCOMMITTED uncommitted changes"
    fi

    # Check if on main/master
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" == "main" ] || [ "$CURRENT_BRANCH" == "master" ]; then
        print_status "WARN" "Currently on $CURRENT_BRANCH branch (should be on feature branch?)"
    else
        print_status "PASS" "On feature branch: $CURRENT_BRANCH"
    fi
else
    print_status "WARN" "Not a git repository"
fi

# 9. Dependency Check
print_header "9. Dependency Check"

if [ -f "requirements.txt" ] && command -v pip &> /dev/null; then
    # Check for outdated packages
    OUTDATED=$(pip list --outdated --format=freeze 2>/dev/null | wc -l || echo "0")
    if [ "$OUTDATED" -eq 0 ]; then
        print_status "PASS" "All Python packages up to date"
    else
        print_status "WARN" "$OUTDATED outdated Python packages"
    fi
fi

if [ -f "package.json" ] && command -v npm &> /dev/null; then
    if npm outdated 2>&1 | grep -q "Package"; then
        OUTDATED_NPM=$(npm outdated 2>&1 | tail -n +2 | wc -l)
        print_status "WARN" "$OUTDATED_NPM outdated npm packages"
    else
        print_status "PASS" "All npm packages up to date"
    fi
fi

# Final Summary
echo ""
echo "======================================================================="
echo "                          FINAL VERDICT"
echo "======================================================================="
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ GO - Quality audit PASSED${NC}"
    echo ""
    echo "All checks passed. Code is ready for merge."
else
    echo -e "${RED}✗ NO-GO - Quality audit FAILED${NC}"
    echo ""
    echo "Some checks failed. Review the issues above before merging."
fi

echo ""
echo "======================================================================="
echo "Report saved to: $OUTPUT_FILE"
echo "======================================================================="

exit $EXIT_CODE
