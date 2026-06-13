# Makefile for Restoran

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
REMOTE_USER = oktay
REMOTE_HOST = debianoktay
REMOTE_DIR = ~/restoran
REMOTE_SERVICE = fastfoot.service

DEPLOY_EXCLUDES = \
	--exclude '.git' \
	--exclude '.venv' \
	--exclude '__pycache__' \
	--exclude '.env' \
	--exclude 'config.txt' \
	--exclude 'menu.txt' \
	--exclude 'waiters.json' \
	--exclude 'salons.json' \
	--exclude 'integrations.json' \
	--exclude 'active_adisyonlar.json' \
	--exclude 'cashiers.json' \
	--exclude 'kitchen.json' \
	--exclude 'users.json' \
	--exclude 'auth_sessions.json' \
	--exclude 'menu_meta.json' \
	--exclude 'table_notes.json' \
	--exclude 'portion_stock*.json' \
	--exclude 'gunluk_yemekler.txt' \
	--exclude 'gunluk_yemekler/' \
	--exclude 'sira_no.txt' \
	--exclude 'Fisler/' \
	--exclude 'output/' \
	--exclude 'web/uploads/'

.PHONY: help run install deploy deploy-dry-run status logs ssh

help:
	@echo "Platform Detected: $(PLATFORM)"
	@echo "Available commands:"
	@echo "  make run          - Run the web server locally"
	@echo "  make install      - Install dependencies from requirements.txt"
	@echo "  make deploy-dry-run - Preview deploy without changing remote files"
	@echo "  make deploy       - Sync files to remote server (Unix only)"
	@echo "  make status       - Check status of remote service"
	@echo "  make restart      - Restart the remote service"
	@echo "  make logs         - View remote service logs"
	@echo "  make ssh          - SSH into the remote server"
	@echo "  make onlyoffice   - Run OnlyOffice AI Proxy server"
	@echo "  make onlyoffice-install - Install OnlyOffice AI dependencies"

run:
	$(PYTHON) web_server.py

install:
	$(PYTHON) -m pip install -r requirements.txt

onlyoffice:
	@echo "Starting OnlyOffice AI Proxy Server..."
	source .env 2>/dev/null || true; $(PYTHON) onlyoffice_ai.py

onlyoffice-install:
	$(PYTHON) -m pip install -r requirements.txt
	@echo "OnlyOffice AI dependencies installed."

deploy:
	@echo "Deploying to $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_DIR)..."
	rsync -avz $(DEPLOY_EXCLUDES) ./ $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_DIR)
	@echo "Deployment complete."

deploy-dry-run:
	@echo "Previewing deploy to $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_DIR)..."
	rsync -avzn --itemize-changes $(DEPLOY_EXCLUDES) ./ $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_DIR)

status:
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "sudo systemctl status $(REMOTE_SERVICE)"

restart:
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "sudo systemctl restart $(REMOTE_SERVICE)"

logs:
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "sudo journalctl -u $(REMOTE_SERVICE) -f"

ssh:
	ssh $(REMOTE_USER)@$(REMOTE_HOST)
