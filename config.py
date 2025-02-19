import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(".")/".env"
load_dotenv()  # Load environment variables from a .env file

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HIX_API_KEY = os.getenv("HIX_API_KEY")
HUMANISE_SUBMIT_URL = "https://bypass.hix.ai/api/hixbypass/v1/submit"
HUMANISE_RETRIEVE_URL = "https://bypass.hix.ai/api/hixbypass/v1/obtain"


# Springer API Configuration
SPRINGER_API_KEY = os.getenv("SPRINGER_API_KEY", "afb38807408f472ed1e4c9666a9a644a")
SPRINGER_API_URL = "http://api.springernature.com/metadata/json"

# Output Directory
OUTPUT_DIR = "results"
