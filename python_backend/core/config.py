import os
import logging
from dotenv import load_dotenv
from pathlib import Path

# --- Environment and Configuration ---
# Construct the path to the .env file.
# __file__ is the path to the current file (config.py)
# .parent is the 'core' directory
# .parent.parent is the 'python_backend' directory, where .env is located.
dotenv_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=dotenv_path)
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://2cccd05b.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "TCS12345")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# --- NiFi Configuration ---
NIFI_BASE_URL = os.getenv("NIFI_BASE_URL", "http://localhost:8080/nifi-api")
NIFI_USERNAME = os.getenv("NIFI_USERNAME") # Optional: for username/password auth
NIFI_PASSWORD = os.getenv("NIFI_PASSWORD") # Optional: for username/password auth

