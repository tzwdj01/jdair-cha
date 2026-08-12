import os, sys
os.environ["MCS8_PANEL_HOST"] = "0.0.0.0"
os.environ["MCS8_PANEL_PORT"] = "8788"
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.getcwd(), "offline_geo"))
from mcs8_web_panel import main
main()
