"""
This file makes the src directory a Python package.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Set up environment variables for all src modules
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


# Configure environment variables
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
