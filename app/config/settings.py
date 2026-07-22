from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = DATA_DIR / "erp.db"

# DATABASE_NAME = "erp.db"

# DATABASE_PATH = BASE_DIR / DATABASE_NAME

DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

APP_NAME = "Printing Press ERP"

COMPANY_NAME = "Chand Graphics"

APP_VERSION = "1.0.0"