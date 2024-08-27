# Makefile to run a persistent Neo4j Docker container with correct permissions and APOC plugin

# Default password, can be overridden by setting N4J_PASSWORD in the environment
N4J_PASSWORD ?= supersafepassword

# Local directory to store Neo4j data (absolute path)
N4J_DATA_DIR ?= $(shell mkdir -p ./n4j && cd ./n4j && pwd)

# URL to download the APOC plugin
APOC_VERSION ?= 4.4.0.10
APOC_URL ?= https://github.com/neo4j-contrib/neo4j-apoc-procedures/releases/download/$(APOC_VERSION)/apoc-$(APOC_VERSION)-all.jar

# Current user's UID and GID
UID := $(shell id -u)
GID := $(shell id -g)

# Default logging level (can be overridden)
NEO4J_LOGGING_LEVEL ?= INFO

# Target to create the data directory if it doesn't exist
prepare-directories:
	@echo "Preparing neo4j directory..."
	@mkdir -p $(N4J_DATA_DIR)/data $(N4J_DATA_DIR)/logs $(N4J_DATA_DIR)/import $(N4J_DATA_DIR)/plugins
	@echo "done"

# Target to download the APOC plugin
download-apoc: prepare-directories
	@echo "Downloading APOC plugin..."
	@curl -L $(APOC_URL) -o $(N4J_DATA_DIR)/plugins/apoc.jar
	@echo "done"

# Target to create Neo4j container if it doesn't exist
create-neo4j-container: download-apoc
	@echo "Checking if neo4j container exists..."
	@if [ -z "$$(docker ps -aq -f name=neo4j)" ]; then \
		echo "Creating neo4j container..."; \
		docker create --name neo4j \
		--user=$(UID):$(GID) \
		-p 7474:7474 -p 7687:7687 \
		-e NEO4J_AUTH=neo4j/$(N4J_PASSWORD) \
		-e NEO4J_dbms_allow__upgrade=true \
		-e NEO4J_dbms_security_procedures_unrestricted=apoc.* \
		-e NEO4J_dbms_logs_query_enabled=$(NEO4J_LOGGING_LEVEL) \
		-v $(N4J_DATA_DIR)/data:/data \
		-v $(N4J_DATA_DIR)/logs:/logs \
		-v $(N4J_DATA_DIR)/import:/var/lib/neo4j/import \
		-v $(N4J_DATA_DIR)/plugins:/plugins \
		neo4j:4.4.0; \
	else \
		echo "Neo4j container already exists."; \
	fi
	@echo "done"

# Target to start Neo4j container
run-neo4j: create-neo4j-container
	@echo "Starting neo4j..."
	@if [ ! $$(docker ps -q -f name=neo4j) ]; then \
		docker start neo4j || echo "Failed to start Neo4j container"; \
	else \
		echo "Neo4j is already running."; \
	fi
	@echo "Sleeping for 15 seconds... (waiting for Neo4j to start)"
	@sleep 15
	@echo "done"

stop-neo4j:
	@echo "Stopping neo4j..."
	@docker stop neo4j || echo "Neo4j is not running"
	@echo "done"

wipe-data:
	@echo "Wiping neo4j data..."
	@rm -rf $(N4J_DATA_DIR)/data/*
	@rm -rf $(N4J_DATA_DIR)/logs/*
	@rm -rf $(N4J_DATA_DIR)/import/*
	@echo "done"

import-data:
	@echo "Importing data..."
	@python scripts/import_kegg.py -d data/kegg/xml
	@echo "done"

reset-neo4j: stop-neo4j wipe-data run-neo4j

test-neo4j:
	@echo "Testing neo4j connection..."
	@docker exec -it neo4j cypher-shell -u neo4j -p $(N4J_PASSWORD) "RETURN apoc.version();" || echo "Neo4j test failed"
	@sleep 5
	@echo "done"

test:
	@echo "Running pytest..."
	PYTHONPATH=$(shell pwd) pytest tests/ --disable-warnings
	@echo "done"

test-fast:
	@echo "Running pytest..."
	PYTHONPATH=$(shell pwd) pytest tests/ -k "not slow" --disable-warnings
	@echo "done"

install-requirements:
	@echo "Installing requirements..."
	@pip install -r requirements.txt
	@pip install -r requirements-test.txt
	@pip install -r requirements-scripts.txt
	@echo "done"

install: install-requirements prepare-directories download-apoc run-neo4j test-neo4j import-data
	@echo "Installation complete"

run:
	@echo "Running..."
	@python -m ha -W ignore
	@echo "done"

clean:
	@echo "Cleaning up..."
	@docker stop neo4j || echo "Neo4j is not running"
	@docker rm neo4j || echo "Neo4j container does not exist"
	@rm -rf $(N4J_DATA_DIR)
	@echo "done"

.PHONY: prepare-directories download-apoc run-neo4j stop-neo4j wipe-data reset-neo4j test-neo4j run-pytest create-neo4j-container clean
