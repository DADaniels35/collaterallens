.PHONY: install sample test api dashboard docker-up clean

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

sample:
	.venv/bin/python data/generate_synthetic_portfolio.py --rows 250 --output data/sample_portfolio.csv

test:
	.venv/bin/python -m pytest

api:
	.venv/bin/uvicorn app.main:app --reload

dashboard:
	.venv/bin/streamlit run dashboard/streamlit_app.py

docker-up:
	docker compose up --build

clean:
	find app dashboard tests -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache collateral_lens.db data/collateral_lens.db
