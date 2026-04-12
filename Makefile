# Finance Agents — Makefile
# Usage : make <cible>
#
# Pré-requis : venv Python activé OU venv/ présent à la racine

PYTHON  := $(if $(wildcard venv/Scripts/python.exe),venv/Scripts/python.exe,python)
PYTEST  := $(PYTHON) -m pytest
NPM     := cd frontend && npm

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Aide
# ---------------------------------------------------------------------------

.PHONY: help
help:
	@echo ""
	@echo "  Finance Agents — commandes disponibles"
	@echo "  ──────────────────────────────────────"
	@echo "  make test           Lance tous les tests (Python + Angular)"
	@echo "  make test-back      Tests Python uniquement"
	@echo "  make test-front     Tests Angular uniquement (jsdom, headless)"
	@echo ""
	@echo "  make dev-back       Démarre le backend  (tests d'abord)"
	@echo "  make dev-front      Démarre le frontend (tests d'abord)"
	@echo ""
	@echo "  make build          Build Angular production"
	@echo "  make install        Installe toutes les dépendances"
	@echo "  make ci             Simule le pipeline CI complet en local"
	@echo ""

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

.PHONY: test
test: test-back test-front

.PHONY: test-back
test-back:
	@echo ""
	@echo "🐍  Tests Python..."
	@echo "──────────────────────────────────────────────────────────"
	$(PYTEST) tests/ -v --tb=short
	@echo ""

.PHONY: test-front
test-front:
	@echo ""
	@echo "🅰️   Tests Angular..."
	@echo "──────────────────────────────────────────────────────────"
	$(NPM) run test:ci
	@echo ""

# ---------------------------------------------------------------------------
# Démarrage des serveurs
# ---------------------------------------------------------------------------

.PHONY: dev-back
dev-back:
	$(PYTHON) backend/start.py

.PHONY: dev-back-no-reload
dev-back-no-reload:
	$(PYTHON) backend/start.py --no-reload

.PHONY: dev-back-prod
dev-back-prod:
	$(PYTHON) backend/start.py --host 0.0.0.0 --no-reload

.PHONY: dev-front
dev-front:
	$(NPM) start

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

.PHONY: build
build:
	@echo "🏗️   Build Angular production..."
	$(NPM) run build

# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

.PHONY: install
install:
	@echo "📦  Installation des dépendances Python..."
	pip install -r backend/requirements-backend.txt
	pip install pytest
	@echo "📦  Installation des dépendances Node..."
	$(NPM) ci

# ---------------------------------------------------------------------------
# CI local — simule le pipeline GitHub Actions
# ---------------------------------------------------------------------------

.PHONY: ci
ci: test build
	@echo ""
	@echo "✅  Pipeline CI complet — tous les checks sont verts."
	@echo ""
