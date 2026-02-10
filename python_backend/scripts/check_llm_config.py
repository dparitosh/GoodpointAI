import sys
import os
from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load env to get DB URL
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

# Add parent dir to path to import core/models
sys.path.append(str(Path(__file__).parent.parent))

from core.database import Base
from models.admin_config_models import LLMProviderConfig

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found!")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("Checking configured LLM Providers in DB:")
providers = db.query(LLMProviderConfig).all()
for p in providers:
    print(f"ID: {p.id} | Provider: {p.provider} | Status: {p.status} | Model: {p.default_chat_model} | Endpoint: {p.api_endpoint}")

print("\nDefault Provider:")
default = db.query(LLMProviderConfig).filter(LLMProviderConfig.is_default == True).first()
if default:
    print(f"ID: {default.id} | Provider: {default.provider}")
else:
    print("None configured as default.")
