
help:
	@echo "scholar - run Google Scholar report"

scholar:
	uv run scripts/scholar_sync.py --user-id kxCnpPEAAAAJ --update-scholar-id
