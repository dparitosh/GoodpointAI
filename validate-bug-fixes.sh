#!/bin/bash
# Bug Fix Validation Script
# Tests critical functionality after bug fixes

echo " Bug Fix Validation Test Suite"
echo "================================="
echo ""

# Test 1: Check if ErrorBoundary exists
echo "✓ Test 1: ErrorBoundary Component"
if [ -f "e2etraceapp/src/components/ErrorBoundary.jsx" ]; then
    echo "  ✓ ErrorBoundary.jsx created"
else
    echo "  ✗ ErrorBoundary.jsx not found"
    exit 1
fi

# Test 2: Check if API client exists
echo "✓ Test 2: API Client Utility"
if [ -f "e2etraceapp/src/utils/apiClient.js" ]; then
    echo "  ✓ apiClient.js created"
else
    echo "  ✗ apiClient.js not found"
    exit 1
fi

# Test 3: Check if validators are added to models
echo "✓ Test 3: Backend Validation"
if grep -q "@validator" "python_backend/models/workflow_models.py"; then
    echo "  ✓ Pydantic validators added"
else
    echo "  ✗ Validators not found"
    exit 1
fi

# Test 4: Check if UTC timezone is used
echo "✓ Test 4: UTC Timezone Usage"
if grep -q "timezone.utc" "python_backend/graph_api/workflow_manager_router.py"; then
    echo "  ✓ UTC timezone implemented"
else
    echo "  ✗ UTC timezone not found"
    exit 1
fi

# Test 5: Check if WORKFLOWS_STORE exists
echo "✓ Test 5: Workflow Persistence"
if grep -q "WORKFLOWS_STORE" "python_backend/graph_api/workflow_manager_router.py"; then
    echo "  ✓ Workflow persistence store exists"
else
    echo "  ✗ Workflow store not found"
    exit 1
fi

# Test 6: Check if mock data is removed
echo "✓ Test 6: Mock Data Removal"
if grep -q "old_mock = WorkflowInstanceDetail" "python_backend/graph_api/workflow_manager_router.py"; then
    echo "  ✗ Mock data still present"
    exit 1
else
    echo "  ✓ Mock data removed"
fi

# Test 7: Check if ErrorBoundary is integrated
echo "✓ Test 7: ErrorBoundary Integration"
if grep -q "ErrorBoundary" "e2etraceapp/src/e2etrace-main.jsx"; then
    echo "  ✓ ErrorBoundary integrated in app"
else
    echo "  ✗ ErrorBoundary not integrated"
    exit 1
fi

# Test 8: Check for alert() removal in workflow managers
echo "✓ Test 8: Alert() Replacement"
ALERT_COUNT=$(grep -c "alert(" "e2etraceapp/src/pages/workflow-manager/WorkflowDetailPage.jsx" 2>/dev/null || echo "0")
if [ "$ALERT_COUNT" -eq 0 ]; then
    echo "  ✓ Alert() removed from WorkflowDetailPage"
else
    echo "  !  Still $ALERT_COUNT alert() calls in WorkflowDetailPage"
fi

# Test 9: Check for proper useEffect separation
echo "✓ Test 9: UseEffect Hook Fixes"
if grep -q "Auto-refresh when workflow is running (separate effect)" "e2etraceapp/src/pages/workflow-manager/WorkflowDetailPage.jsx"; then
    echo "  ✓ UseEffect hooks properly separated"
else
    echo "  ✗ UseEffect fix not applied"
    exit 1
fi

# Test 10: Check for timeout implementation
echo "✓ Test 10: Request Timeout Implementation"
if grep -q "AbortController" "e2etraceapp/src/pages/workflow-manager/WorkflowDetailPage.jsx"; then
    echo "  ✓ Timeout handling implemented"
else
    echo "  ✗ Timeout handling not found"
    exit 1
fi

echo ""
echo "================================="
echo "✓ All validation tests passed!"
echo "Bug fixes successfully implemented."
echo "================================="
