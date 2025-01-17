import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(".")/".env"
load_dotenv()  # Load environment variables from a .env file

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HIX_API_KEY = os.getenv("HIX_API_KEY")
HUMANISE_SUBMIT_URL = "https://bypass.hix.ai/api/hixbypass/v1/submit"
HUMANISE_RETRIEVE_URL = "https://bypass.hix.ai/api/hixbypass/v1/obtain"

# IEEE API Configuration
IEEE_API_KEY = os.getenv("IEEE_API_KEY", "7uf2eh4qtpdz8nuhsmnajvvc")
IEEE_API_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"

# Springer API Configuration
SPRINGER_API_KEY = os.getenv("SPRINGER_API_KEY", "afb38807408f472ed1e4c9666a9a644a")
SPRINGER_API_URL = "http://api.springernature.com/metadata/json"

# Output Directory
OUTPUT_DIR = "results"

#Google Client ID
GOOGLE_CLIENT_ID="170343969782-ku0ulmvbet8ct9dncgnuk9qj2l9c1lvv.apps.googleusercontent.com"