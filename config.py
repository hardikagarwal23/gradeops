import os

# Base directory paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_exams")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# POPPLER PATH - Update this to point EXACTLY to your extracted bin folder
POPPLER_PATH = r"C:\poppler\poppler-26.02.0\Library\bin"  # Change this to your exact path

# In production (Cloud deployment), Poppler is installed natively via apt-get, 
# so we only need the path variable while developing on Windows.
IS_WINDOWS = os.name == 'nt'