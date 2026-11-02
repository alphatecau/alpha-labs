# Local developer convenience, no network requirements.
.PHONY: research-test research-demo sites-test verify
research-test:
	PYTHONPATH=packages/alpha_lab/src python -m unittest discover -s tests/unit -p test_*.py -v
research-demo:
	PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.cli examples/SYNTHETIC_SOLUSDC_1h.csv --quote USDC --provenance synthetic --output research-output.json
sites-test:
	node --test apps/sites/tests/*.test.cjs
verify: research-test sites-test
