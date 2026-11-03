# Verification — Alpha Labs v0.6

Run without downloads/API keys:

```sh
make research-test
make sites-test
make research-demo
```

The synthetic fixture is **not market data**; research output is strictly a smoke test.

For Codespaces with Python 3.12, optionally `python -m pip install -e .`, then invoke `python -m alpha_lab.cli ...`. If a sandbox blocks access to PyPI, use `PYTHONPATH=packages/alpha_lab/src` without installation.

## Operator UI v0.6

```sh
cd apps/sites
node --test tests/*.test.cjs
python tests/browser-smoke.py   # optional; requires Playwright + Chromium
```

36 JavaScript tests and 21 Python tests pass. Browser interactive smoke tests pass at 320, 390 and 1440 px. Browser checks are local only; no deployment or backend was tested.
