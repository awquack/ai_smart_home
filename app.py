import os, sys, subprocess

sprint4 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprint4")
subprocess.run([sys.executable, os.path.join(sprint4, "app.py")], cwd=sprint4)
