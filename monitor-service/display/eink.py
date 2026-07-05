import sys
import os
import time
from PIL import Image, ImageDraw, ImageFont
import epaper

# Font paths used for E-Ink rendering.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_LARGE_PATH = os.path.join(BASE_DIR, "fonts", "DejaVuSansMono-Bold.ttf")
FONT_SMALL_PATH = os.path.join(BASE_DIR, "fonts", "DejaVuSansMono.ttf")

class EInk:
    def __init__(self):
        try:
            self.display = epaper.epaper('epd7in3f')

            # Initialize the display and clear it from any previous ghost images.
            self.display.init()
            self.display.Clear()

            # Cache canvas dimensions as instance attributes.
            self._width = self.display.width
            self._height = self.display.height
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to initialize E-Ink display: {e}")
            self.display = None

            # Provide fallback dimensions so the script doesn't crash later
            self._width = 800
            self._height = 480

        # Load fonts once at init so we don't re-read from disk every render cycle.
        self._fontLarge = ImageFont.truetype(FONT_LARGE_PATH, 18)
        self._fontSmall = ImageFont.truetype(FONT_SMALL_PATH, 11)

        # Caching and throttling state
        self._last_state = None
        self._last_update_time = 0
        self._throttle_seconds = 30

    def _writeToScreen(self, canvas):
        # Display the image on the screen.
        # Ensure we sleep so we don't burn out the screen.
        if self.display is not None:
            self.display.display(self.display.getbuffer(canvas))
            self.display.sleep()

    def _buildTicketFrame(self, draw):
        # Generate the overall boxes and lines to look like a ticket.
        draw.rectangle(
            [5, 5, self._width - 5, self._height - 5],
            outline=0,
            fill=None,
            width=2,
        )
        draw.rectangle(
            [5, 5, self._width - 5, 40],
            outline=0,
            fill=0,
            width=1,
        )
        draw.line(
            [5, 90, self._width - 5, 90],
            fill=0,
            width=1,
        )
        draw.line(
            [self._width / 2, 95, self._width / 2, self._height - 10],
            fill=0,
            width=1,
        )

        return draw

    def _buildTicketSubItems(self, draw, elev=None, heading=None, gs=None, aircraftType=None):
        # Build labels for subitems.
        draw.text(
            [8, 95],
            "ALTITUDE",
            font=self._fontSmall,
            fill=0
        )
        draw.text(
            [8, 135],
            "HEADING",
            font=self._fontSmall,
            fill=0
        )
        draw.text(
            [self._width / 2 + 5, 95],
            "GROUND SPEED",
            font=self._fontSmall,
            fill=0
        )
        draw.text(
            [self._width / 2 + 5, 135],
            "TYPE",
            font=self._fontSmall,
            fill=0
        )

        if elev is None:
            elev = "-"
        if heading is None:
            heading = "-"
        if gs is None:
            gs = "-"
        if aircraftType is None:
            aircraftType = "-"
        
        # Next, draw the actual subitems.
        draw.text(
            [8, 107],
            f"{elev}",
            font=self._fontLarge,
            fill=0
        )
        draw.text(
            [8, 147],
            f"{heading}",
            font=self._fontLarge,
            fill=0
        )
        draw.text(
            [self._width / 2 + 5, 107],
            f"{gs}",
            font=self._fontLarge,
            fill=0
        )
        draw.text(
            [self._width / 2 + 5, 147],
            f"{aircraftType}",
            font=self._fontLarge,
            fill=0
        )

        return draw

    def WriteNoFlight(self):
        current_time = time.time()
        if self._last_state == "NO_FLIGHT":
            return
        if current_time - self._last_update_time < self._throttle_seconds:
            return

        # Create the canvas.
        # E-ink drivers usually require a '1' mode for 1-bit monochrome black/white.
        canvas = Image.new('1', (self._width, self._height), 255)
        draw = ImageDraw.Draw(canvas)

        # Start by building the ticket frame.
        draw = self._buildTicketFrame(draw)

        # Add labels to the ticket.
        draw.text(
            [8, 12],
            f"NO FLIGHTS OVERHEAD",
            font=self._fontLarge,
            fill=255
        )
        draw.text(
            [25, 50],
            "Cannot detect any ADS-B signals.",
            font=self._fontSmall,
            fill=0
        )
        draw.text(
            [72, 65],
            "Waiting on data...",
            font=self._fontSmall,
            fill=0
        )

        # Write the subportion of the ticket data.
        draw = self._buildTicketSubItems(draw)

        # Send to the screen
        self._writeToScreen(canvas)

        self._last_state = "NO_FLIGHT"
        self._last_update_time = time.time()

    def WriteFlightData(self, flightNum, origin, dest, elev, heading, gs, aircraftType):
        current_time = time.time()
        flight_state = (flightNum, origin, dest, elev, heading, gs, aircraftType)
        
        if self._last_state == flight_state:
            return
        if current_time - self._last_update_time < self._throttle_seconds:
            return

        # Create the canvas.
        # E-ink drivers usually require a '1' mode for 1-bit monochrome black/white.
        canvas = Image.new('1', (self._width, self._height), 255)
        draw = ImageDraw.Draw(canvas)

        # Start by building the ticket frame.
        draw = self._buildTicketFrame(draw)

        # Add labels to the ticket.
        draw.text(
            [8, 12],
            f"{flightNum} OVERHEAD",
            font=self._fontLarge,
            fill=255
        )
        draw.text(
            [8, 45],
            "FLIGHT PATH",
            font=self._fontSmall,
            fill=0
        )
        draw.text(
            [(self._width / 2) - 4, 65],
            ">",
            font=self._fontLarge,
            fill=0
        )
        
        # Add origin and destination information.
        draw.text(
            [self._width / 4 - 10, 65],
            f"{origin}",
            font=self._fontLarge,
            fill=0
        )
        draw.text(
            [self._width / 2 + self._width / 4 - 10, 65],
            f"{dest}",
            font=self._fontLarge,
            fill=0
        )
        
        # Write the subportion of the ticket.
        draw = self._buildTicketSubItems(draw, elev, heading, gs, aircraftType)
        
        # Send to the screen
        self._writeToScreen(canvas)

        self._last_state = flight_state
        self._last_update_time = time.time()
