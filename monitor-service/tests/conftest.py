import os
import sys

# The service is run with monitor-service as the working directory (main.py
# does sys.path.append('./')), so imports are rooted there. Mirror that for
# tests instead of turning the package layout inside out.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
