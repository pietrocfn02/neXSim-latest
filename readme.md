# neXSim-latest

## Quick start

1. Clone the repo:
  git clone <repo-url>
  cd neXSim-latest

2. Install dependencies (example for Python):
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt

3. Fill the .env file with your configuration.

4. Run the application (see Running section below).

   gunicorn -c gunicorn_config.py app:app
   
   Or with Docker:
   docker compose build
   docker compose up -d
