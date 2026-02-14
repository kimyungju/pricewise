.PHONY: backend frontend dev

backend:
	uv run uvicorn aigent.api.app:create_app --factory --reload --port 8000

frontend:
	cd web && npm run dev

dev:
	$(MAKE) backend & $(MAKE) frontend
