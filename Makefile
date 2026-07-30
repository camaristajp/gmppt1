.PHONY: install test s1 s2 lock clean
install:
	pip install -e ".[dev]"
test:
	pytest
s1:
	python scripts/s1_cec_characterisation.py
s2:
	python scripts/s2_stc_verification.py
lock:
	pip freeze > requirements-lock.txt
clean:
	rm -rf .pytest_cache **/__pycache__ *.egg-info
