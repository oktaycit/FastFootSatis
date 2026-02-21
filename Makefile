# Makefile for FastFootSatıs

# OS Detection
ifeq ($(OS),Windows_NT)
    # Windows Settings
    VENV_BIN = .venv\Scripts
    PYTHON = $(VENV_BIN)\python.exe
    PIP = $(VENV_BIN)\pip.exe
    RM = del /Q /F
    PLATFORM = Windows
else
    # Unix Settings (Mac/Linux)
    VENV_BIN = .venv/bin
    PYTHON = $(VENV_BIN)/python
    PIP = $(VENV_BIN)/pip
    RM = rm -rf
    PLATFORM = Unix
endif

# Remote Server Variables
REMOTE_USER = vet
REMOTE_HOST = kuvoz.local
REMOTE_DIR = ~/restoran
REMOTE_SERVICE = kuvoz-web.service

.PHONY: help run install deploy status logs ssh

help:
	@echo "Platform Detected: $(PLATFORM)"
	@echo "Available commands:"
	@echo "  make run      - Run the web server locally"
	@echo "  make install  - Install dependencies from requirements.txt"
	@echo "  make deploy   - Sync files to remote server and restart service (Unix only)"
	@echo "  make status   - Check status of remote service"
	@echo "  make logs     - View remote service logs"
	@echo "  make ssh      - SSH into the remote server"

run:
	$(PYTHON) web_server.py

install:
	$(PYTHON) -m pip install -r requirements.txt

deploy:
	@echo "Deploying to $(REMOTE_HOST)..."
	rsync -avz --exclude '.git' --exclude '.venv' --exclude '__pycache__' ./ $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_DIR)
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "sudo systemctl restart $(REMOTE_SERVICE)"
	@echo "Deployment complete."

status:
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "sudo systemctl status $(REMOTE_SERVICE)"

logs:
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "sudo journalctl -u $(REMOTE_SERVICE) -f"

ssh:
	ssh $(REMOTE_USER)@$(REMOTE_HOST)
