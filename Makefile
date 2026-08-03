.PHONY: install test stage1 stage2 stage3 stage4 figures lock clean
install:
	pip install -e ".[dev]"
test:
	pytest
stage1:                 # S1 + S2  (environment + STC verification)
	python phase1/s1_cec_characterisation.py
	python phase1/s2_stc_verification.py
stage2:                 # S3 + S4 (shading physics + external validation)
	python phase1/s3_reverse_bias_bypass.py
	python phase1/s4_external_validation.py
stage3:                 # S5  (array generalisation)
	python phase1/s5_array_generalisation.py
stage4:                 # S6 + S7 + S8 -> Gate A -- blocked until S4 green
	@echo "S6-S8 blocked: S4 must be green first"
figures:                # regenerate all figures
	python phase1/s1_cec_characterisation.py
	python phase1/s2_stc_verification.py
	python phase1/s3_reverse_bias_bypass.py
lock:
	pip freeze --exclude-editable > requirements-lock.txt
clean:
	rm -rf .pytest_cache **/__pycache__ *.egg-info
