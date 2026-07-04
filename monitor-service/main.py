import argparse
from controller import Controller

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Airspace Monitor Service")
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Run without hardware displays (uses DummyDisplay for logging only)."
    )
    args = parser.parse_args()

    controller = Controller(no_display=args.no_display)
    controller.Start()
