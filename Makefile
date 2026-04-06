# This project was developed with assistance from AI tools.

.PHONY: install run test lint build push deploy undeploy mock-server clean

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
	oc apply -k deploy/

undeploy:
	oc delete -k deploy/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache *.egg-info
