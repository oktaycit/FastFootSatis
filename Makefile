# Makefile for FastFootSatıs

# Variables
REMOTE_USER = vet
REMOTE_HOST = kuvoz.local
REMOTE_DIR = ~/restoran
LOCAL_PYTHON = .venv/bin/python
REMOTE_SERVICE = kuvoz-web.service

.PHONY: help run install deploy status logs ssh

help:
	@echo "Available commands:"
	@echo "  make run      - Run the web server locally"
	@echo "  make install  - Install dependencies from requirements.txt"
	@echo "  make deploy   - Sync files to remote server and restart service"
	@echo "  make status   - Check status of remote service"
	@echo "  make logs     - View remote service logs"
	@echo "  make ssh      - SSH into the remote server"

run:
	$(LOCAL_PYTHON) web_server.py

install:
	$(LOCAL_PYTHON) -m pip install -r requirements.txt

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
