import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def get_project_path(*parts: str) -> str:
    return str(ROOT_DIR.joinpath(*parts))


def get_db_config() -> dict:
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "tcc_user"),
        "password": os.getenv("MYSQL_PASSWORD", "tcc_password"),
        "database": os.getenv("MYSQL_DATABASE", "tcc_localiza"),
        "charset": "utf8mb4",
        "autocommit": False,
    }


def get_gemini_api_key() -> str:
    return os.getenv("GOOGLE_API_KEY", "")
