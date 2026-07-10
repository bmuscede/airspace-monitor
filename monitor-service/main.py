import argparse
import os
import sys
sys.path.append('./')

from controller.controller import Controller
from utils.logs import InitializeLogging

if __name__ == "__main__":
    cwd = os.getcwd()

    parser = argparse.ArgumentParser(description="Airspace Monitor Service")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Run in development mode (simulates radio data and shows displays on screen)."
    )
    parser.add_argument(
        "--config_dir",
        type=str, 
        default=cwd,
        help="Locatation of configuration directory."
    )
    parser.add_argument(
        "--log_dir",
        type=str,
        default=cwd,
        help="Location of log files for this program."
    )
    args = parser.parse_args()

    # Initialize our logging framework.
    InitializeLogging("AirspaceMonitor", args.log_dir)

    # Setup and start the controller.
    # This will only terminate on OS signal.
    controller = Controller(configDir=args.config_dir, devMode=args.dev)
    controller.Start()
