PYTHON ?= .venv/bin/python
HOST ?= 127.0.0.1
PORT ?= 8000
APP_DB_PATH ?= ./app.db

.PHONY: web

web:
	APP_DB_PATH=$(APP_DB_PATH) PYTHONPATH=. $(PYTHON) -m uvicorn api.main:app --host $(HOST) --port $(PORT)
