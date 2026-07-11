import os
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk, ImageFont
from display.eink import EInk

# Font paths (Reused from your EInk file)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
FONT_BOLD_PATH = os.path.join(DATA_DIR, "fonts", "DejaVuSansMono-Bold.ttf")
FONT_REGULAR_PATH = os.path.join(DATA_DIR, "fonts", "DejaVuSansMono.ttf")

class DevDisplay(EInk):
    def __init__(self, mode="E-Ink"):
        # Initialize a fake E-Ink window.
        self.mode = mode
        self._width = 800
        self._height = 480
        
        # Load fonts.
        self._load_fonts()

        # Caching and throttling state for the EInk display.
        self._last_state = None
        self._last_update_time = 0
        self._throttle_seconds = 30

        # Load the colour/livery cache into memory.
        self._load_aircraft_colour_list()

        # Set up the Tkinter Window
        self.root = tk.Tk()
        self.root.title(f"Airspace Monitor - Dev Display ({self.mode})")
        self.root.geometry(f"{self._width}x{self._height}")
        self.root.configure(bg='black')
        
        # This label will hold our image canvas
        self.label = tk.Label(self.root, bg='black')
        self.label.pack(expand=True)
        
        # Force the window to draw immediately (non-blocking)
        self.root.update()

    def _load_fonts(self):
        super()._load_fonts()

        # Load the splitflap font here.
        self._fontFlap = ImageFont.truetype(FONT_BOLD_PATH, 40)

    def SetMode(self, mode):
        """Called to change thn the dae mode of the active display."""
        self.mode = mode
        self.root.title(f"Airspace Monitor - Dev Display ({self.mode})")
        self.root.update()

    def _writeToScreen(self, canvas):
        """
        OVERRIDE: Intercepts the final canvas from the EInk parent class.
        Instead of pushing to hardware, we render it to the desktop window.
        """
        # E-Ink images are 1-bit monochrome. Tkinter requires RGB.
        img = canvas.convert("RGB")
        self.tk_image = ImageTk.PhotoImage(img)
        self.label.config(image=self.tk_image)
        
        # Non-blocking GUI update. This allows your controller.py while-loop 
        # to keep spinning without freezing the desktop window!
        self.root.update()

    def WriteFlightData(self, flightNum, origin, dest, elev, heading, gs, aircraftType):
        if self.mode == "E-Ink":
            # Pass the data up to the parent EInk class. It will build the ticket UI,
            # and when it finishes, it will call OUR overridden _writeToScreen!
            super().WriteFlightData(flightNum, origin, dest, elev, heading, gs, aircraftType)
        else:
            # Simulate a 3-row Split-Flap mechanical display
            self._draw_splitflap_sim([
                f"{flightNum:^14}",
                f"{origin}-{dest:^14}",
                f"{aircraftType[:14]:^14}"
            ])

    def WriteNoFlight(self, forecast_data):
        if self.mode == "E-Ink":
            super().WriteNoFlight(forecast_data)
        else:
            self._draw_splitflap_sim([
                "NO FLIGHTS".center(14),
                "".center(14),
                "".center(14)
            ])

    def _draw_splitflap_sim(self, lines):
        """Draws a visual representation of mechanical split-flap cards."""
        canvas = Image.new('RGB', (self._width, self._height), (30, 30, 30))
        draw = ImageDraw.Draw(canvas)
        
        start_y = 100
        for row_idx, line in enumerate(lines):
            start_x = 75
            # Draw up to 14 characters per row
            for char in line[:14]: 
                # Draw the physical flap card background
                draw.rectangle([start_x, start_y, start_x + 40, start_y + 60], fill=(10, 10, 10), outline=(100, 100, 100))
                # Draw the horizontal mechanical split line in the center
                draw.line([start_x, start_y + 30, start_x + 40, start_y + 30], fill=(0, 0, 0), width=2)
                
                # Draw the character if it isn't a blank space
                if char != " ":
                    draw.text((start_x + 8, start_y + 5), char, font=self._fontFlap, fill=(255, 255, 255))
                
                start_x += 45
            start_y += 80
            
        self._writeToScreen(canvas)