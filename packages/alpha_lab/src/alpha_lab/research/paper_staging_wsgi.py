"""WSGI entry point; import fails closed until all server settings are present."""
from alpha_lab.research.paper_staging_app import create_app

app = create_app()
