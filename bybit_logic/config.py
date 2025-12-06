import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
DEMO_API_KEY = os.getenv("DEMO_API_KEY")
DEMO_API_SECRET = os.getenv("DEMO_API_SECRET")