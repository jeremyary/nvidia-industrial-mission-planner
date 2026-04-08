# This project was developed with assistance from AI tools.

.PHONY: install run test lint build push deploy undeploy preflight deploy-models undeploy-models clean

NAMESPACE ?= nvidia-mission-planner

IMAGE_REGISTRY ?= quay.io
IMAGE_ORG ?= jary
IMAGE_NAME ?= mission-planner
IMAGE_TAG ?= latest
IMAGE ?= $(IMAGE_REGISTRY)/$(IMAGE_ORG)/$(IMAGE_NAME):$(IMAGE_TAG)

install:
	pip install -e ".[dev]"

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

run-mock:
	@echo "Starting mock model server on port 9000..."
	python tests/mock_server.py &
	COSMOS_ENDPOINT=http://localhost:9000/v1 \
	NEMOTRON_ENDPOINT=http://localhost:9000/v1 \
	uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

test:
	pytest -v

lint:
	ruff check --fix app/ tests/
	ruff format app/ tests/

build:
	podman build -f Containerfile -t $(IMAGE) .

push: build
	podman push $(IMAGE)

deploy:
	@oc get project $(NAMESPACE) >/dev/null 2>&1 || oc new-project $(NAMESPACE)
	oc apply -k deploy/ -n $(NAMESPACE)

undeploy:
	oc delete -k deploy/ -n $(NAMESPACE)

preflight:
	@NAMESPACE=$(NAMESPACE) deploy/models/preflight.sh

deploy-models: preflight
	@oc get project $(NAMESPACE) >/dev/null 2>&1 || oc new-project $(NAMESPACE)
	@if [ ! -f .env ]; then echo ".env file not found"; exit 1; fi
	@if ! oc get secret hf-token -n $(NAMESPACE) >/dev/null 2>&1; then \
		HF_TOKEN=$$(grep '^HF_TOKEN=' .env | cut -d'=' -f2-); \
		if [ -n "$$HF_TOKEN" ]; then \
			oc create secret generic hf-token -n $(NAMESPACE) --from-literal=HF_TOKEN=$$HF_TOKEN; \
		else \
			echo "HF_TOKEN not found in .env"; exit 1; \
		fi; \
	fi
	@if ! oc get sa model-sa -n $(NAMESPACE) >/dev/null 2>&1; then \
		oc create sa model-sa -n $(NAMESPACE); \
	fi
	@oc secrets link model-sa hf-token -n $(NAMESPACE) 2>/dev/null || true
	oc apply -f deploy/models/cosmos-reason2.yaml -n $(NAMESPACE)
	oc apply -f deploy/models/nemotron.yaml -n $(NAMESPACE)

undeploy-models:
	oc delete -f deploy/models/nemotron.yaml -n $(NAMESPACE) --ignore-not-found
	oc delete -f deploy/models/cosmos-reason2.yaml -n $(NAMESPACE) --ignore-not-found

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache *.egg-info
