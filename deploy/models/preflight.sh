#!/usr/bin/env bash
# This project was developed with assistance from AI tools.
#
# Preflight checks for model deployment.
# Verifies cluster has the required resources before applying manifests.

set -euo pipefail

NAMESPACE="${NAMESPACE:-nvidia-mission-planner}"
REQUIRED_GPUS=2
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
PASS=0
FAIL=0

check() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} ${desc}"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}✗${NC} ${desc}"
        FAIL=$((FAIL + 1))
    fi
}

check_output() {
    local desc="$1"
    shift
    local output
    if output=$("$@" 2>&1); then
        echo -e "  ${GREEN}✓${NC} ${desc}: ${output}"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}✗${NC} ${desc}"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Model Deployment Preflight ==="
echo ""

# Cluster connectivity
echo "Cluster:"
check_output "Logged in as" oc whoami
echo -e "  ${GREEN}✓${NC} Target namespace: ${NAMESPACE}"
PASS=$((PASS + 1))

# GPU Operator
echo ""
echo "GPU Operator:"
check "NVIDIA ClusterPolicy CRD exists" oc get crd clusterpolicies.nvidia.com
check "NVIDIA driver CRD exists" oc get crd nvidiadrivers.nvidia.com

# GPU Nodes
echo ""
echo "GPU Nodes:"
GPU_COUNT=$(oc get nodes -o jsonpath='{range .items[*]}{.status.capacity.nvidia\.com/gpu}{"\n"}{end}' 2>/dev/null | grep -c '^[1-9]' || echo 0)
if [ "$GPU_COUNT" -ge "$REQUIRED_GPUS" ]; then
    echo -e "  ${GREEN}✓${NC} Found ${GPU_COUNT} GPU node(s) (need ${REQUIRED_GPUS})"
    PASS=$((PASS + 1))
else
    echo -e "  ${RED}✗${NC} Found ${GPU_COUNT} GPU node(s) (need ${REQUIRED_GPUS})"
    FAIL=$((FAIL + 1))
fi

# Show GPU details
oc get nodes -o custom-columns='NODE:.metadata.name,GPU:.status.capacity.nvidia\.com/gpu,TYPE:.metadata.labels.nvidia\.com/gpu\.product,INSTANCE:.metadata.labels.node\.kubernetes\.io/instance-type' 2>/dev/null | grep -v '<none>' | while read -r line; do
    echo "    $line"
done

# Available GPUs (not already allocated)
echo ""
echo "GPU Availability:"
ALLOCATABLE=$(oc get nodes -o jsonpath='{range .items[*]}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}' 2>/dev/null | awk '{s+=$1} END {print s+0}')
REQUESTED=$(oc get pods --all-namespaces -o jsonpath='{range .items[*]}{range .spec.containers[*]}{.resources.requests.nvidia\.com/gpu}{"\n"}{end}{end}' 2>/dev/null | awk '{s+=$1} END {print s+0}')
AVAILABLE=$((ALLOCATABLE - REQUESTED))
if [ "$AVAILABLE" -ge "$REQUIRED_GPUS" ]; then
    echo -e "  ${GREEN}✓${NC} ${AVAILABLE} GPU(s) available (${ALLOCATABLE} total, ${REQUESTED} in use)"
    PASS=$((PASS + 1))
else
    echo -e "  ${RED}✗${NC} ${AVAILABLE} GPU(s) available (${ALLOCATABLE} total, ${REQUESTED} in use) — need ${REQUIRED_GPUS}"
    FAIL=$((FAIL + 1))
fi

# KServe / Model Serving
echo ""
echo "Model Serving:"
check "InferenceService CRD exists" oc get crd inferenceservices.serving.kserve.io
check "ServingRuntime CRD exists" oc get crd servingruntimes.serving.kserve.io

# NGC Secret
echo ""
echo "NGC Access:"
if oc get secret ngc-secret -n "$NAMESPACE" >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} NGC secret 'ngc-secret' found in namespace"
    PASS=$((PASS + 1))
else
    echo -e "  ${YELLOW}!${NC} NGC secret 'ngc-secret' not found — will be created from .env during deploy"
    PASS=$((PASS + 1))
fi

# Summary
echo ""
echo "=== Result: ${PASS} passed, ${FAIL} failed ==="
if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}Fix the above issues before deploying models.${NC}"
    exit 1
else
    echo -e "${GREEN}Cluster is ready for model deployment.${NC}"
fi
