import sys
import os
import time
from PIL import Image, ImageDraw, ImageFont

try:
    import epaper
except ImportError:
    epaper = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_LARGE_PATH = os.path.join(BASE_DIR, "fonts", "DejaVuSansMono-Bold.ttf")
FONT_SMALL_PATH = os.path.join(BASE_DIR, "fonts", "DejaVuSansMono.ttf")

class EInk:
    def __init__(self):
        try:
            epd_module = epaper.epaper('epd7in3f')
            self.display = epd_module.EPD()

            self.display.init()
            self.display.Clear()

            self._width = self.display.width
            self._height = self.display.height
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to initialize E-Ink display: {e}")
            self.display = None

            self._width = 800
            self._height = 480

        # Drastically increased font sizes for the 800x480 resolution
        self._fontLarge = ImageFont.truetype(FONT_LARGE_PATH, 54)
        self._fontSmall = ImageFont.truetype(FONT_SMALL_PATH, 28)

        self._last_state = None
        self._last_update_time = 0
        self._throttle_seconds = 30

    def _get_centered_x(self, draw, text, font, area_start=0, area_width=None):
        """
        Calculates the X coordinate to perfectly center text within a given area.
        If area_width is None, it defaults to the entire screen width.
        """
        if area_width is None:
            area_width = self._width
            
        # Get the bounding box of the text: (left, top, right, bottom)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        
        # Calculate the centered X coordinate
        centered_x = area_start + ((area_width - text_width) / 2)
        return centered_x
        
    def _writeToScreen(self, canvas):
        if self.display is not None:
            self.display.display(self.display.getbuffer(canvas))
            self.display.sleep()

    def _buildTicketFrame(self, draw):
        # Outer border
        draw.rectangle(
            [5, 5, self._width - 5, self._height - 5],
            outline=0,
            fill=None,
            width=4,
        )
        # Top Header Bar (Expanded to 80px tall)
        draw.rectangle(
            [5, 5, self._width - 5, 80],
            outline=0,
            fill=0,
            width=1,
        )
        # Horizontal dividing line pushed to the middle of the screen (y=240)
        draw.line(
            [5, 240, self._width - 5, 240],
            fill=0,
            width=3,
        )
        # Vertical dividing line for the bottom half grid
        draw.line(
            [self._width / 2, 240, self._width / 2, self._height - 5],
            fill=0,
            width=3,
        )

        return draw

    def _buildTicketSubItems(self, draw, elev=None, heading=None, gs=None, aircraftType=None):
        # Row 1 Labels (y=255)
        draw.text([25, 255], "ALTITUDE", font=self._fontSmall, fill=0)
        draw.text([self._width / 2 + 25, 255], "GROUND SPEED", font=self._fontSmall, fill=0)

        # Row 1 Values (y=295)
        draw.text([25, 295], f"{elev or '-'}", font=self._fontLarge, fill=0)
        draw.text([self._width / 2 + 25, 295], f"{gs or '-'}", font=self._fontLarge, fill=0)

        # Row 2 Labels (y=365)
        draw.text([25, 365], "HEADING", font=self._fontSmall, fill=0)
        draw.text([self._width / 2 + 25, 365], "TYPE", font=self._fontSmall, fill=0)

        # Row 2 Values (y=405)
        draw.text([25, 405], f"{heading or '-'}", font=self._fontLarge, fill=0)
        draw.text([self._width / 2 + 25, 405], f"{aircraftType or '-'}", font=self._fontLarge, fill=0)

        return draw

    def WriteNoFlight(self):
        current_time = time.time()
        if self._last_state == "NO_FLIGHT":
            return
        if current_time - self._last_update_time < self._throttle_seconds:
            return

        canvas = Image.new('1', (self._width, self._height), 255)
        draw = ImageDraw.Draw(canvas)

        draw = self._buildTicketFrame(draw)

        # Header Text
        header_text = "NO FLIGHTS OVERHEAD"
        x_coord = self._get_centered_x(draw, header_text, self._fontLarge)
        draw.text([x_coord, 10], header_text, font=self._fontLarge, fill=255)
        
        # Center-screen idle state messages
        center_text = "Cannot detect any ADS-B signals."
        sub_center_text = "Waiting on data..."
        center_x_coord = self._get_centered_x(draw, center_text, self._fontSmall)
        sub_center_x_coord = self._get_centered_x(draw, sub_center_text, self._fontSmall)
        draw.text([center_x_coord, 110], center_text, font=self._fontSmall, fill=0)
        draw.text([sub_center_x_coord, 150], sub_center_text, font=self._fontSmall, fill=0)

        draw = self._buildTicketSubItems(draw)

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

        canvas = Image.new('1', (self._width, self._height), 255)
        draw = ImageDraw.Draw(canvas)

        draw = self._buildTicketFrame(draw)

        # Header Text
        header_text = f"{flightNum} OVERHEAD"
        x_coord = self._get_centered_x(draw, header_text, self._fontLarge)
        draw.text([x_coord, 10], header_text, font=self._fontLarge, fill=255)
        
        # Flight Path Section.
        draw.text([20, 100], "FLIGHT PATH", font=self._fontSmall, fill=0)
        
        # Center the directional arrow in the top half.
        center_arrow = ">"
        x_coord = self._get_centered_x(draw, center_arrow, self._fontLarge)
        draw.text([x_coord, 140], center_arrow, font=self._fontLarge, fill=0)
        
        # Space out origin and dest around the arrow
        origin_text = f"{origin}"
        dest_text = f"{dest}"
        origin_x_coord = self._get_centered_x(draw, origin_text, self._fontLarge, 0, self._width/2)
        dest_x_coord = self._get_centered_x(draw, dest_text, self._fontLarge, self._width/2, self._width/2)
        draw.text([origin_x_coord, 140], origin_text, font=self._fontLarge, fill=0)
        draw.text([dest_x_coord, 140], dest_text, font=self._fontLarge, fill=0)
        
        draw = self._buildTicketSubItems(draw, elev, heading, gs, aircraftType)
        
        self._writeToScreen(canvas)
        self._last_state = flight_state
        self._last_update_time = time.time()