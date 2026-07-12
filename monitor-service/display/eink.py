import sys
import os
import time
import math
import csv
import random
from datetime import datetime
import pathlib

from PIL import Image, ImageDraw, ImageFont

from utils.utils import svg_to_png, get_svg_filename_from_code

try:
    import epaper
except ImportError:
    epaper = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
FONT_BOLD_PATH = os.path.join(DATA_DIR, "fonts", "DejaVuSansMono-Bold.ttf")
FONT_REGULAR_PATH = os.path.join(DATA_DIR, "fonts", "DejaVuSansMono.ttf")
COLOUR_PATH = os.path.join(DATA_DIR, "aircraft_colours.csv")
LOGO_PATH = os.path.join(DATA_DIR, "logos")
WEATHER_PATH = os.path.join(DATA_DIR, "weather-mono")
GENERIC_AIRLINE_CODE = "generic"

# TODO: Overall some colours are placed here. We should fix this.
COLOR_GREEN = (0, 255, 0)
COLOR_BLUE = (0, 0, 255)
COLOR_ORANGE = (255, 128, 0)  

class EInk:
    def __init__(self):
        try:
            epd_module = epaper.epaper('epd7in3f')
            self._display = epd_module.EPD()

            self._display.init()
            self._display.Clear()

            self._width = self._display.width
            self._height = self._display.height
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to initialize E-Ink display: {e}")
            self._display = None

            self._width = 800
            self._height = 480

        # Load fonts into memory.
        # TODO: We should provide a fallback here in case these can't be loaded.
        self._load_fonts()

        # Setup the initial state machine.
        # TODO: Throttle seconds needs to be configurable.
        self._last_state = None
        self._last_update_time = 0
        self._throttle_seconds = 90

        # Last, load the colour/livery cache into memory.
        self._load_aircraft_colour_list()

    def _load_fonts(self):
        # Load fonts for the flight display.
        self._fontFlightLarge = ImageFont.truetype(FONT_BOLD_PATH, 54)
        self._fontFlightSmall = ImageFont.truetype(FONT_REGULAR_PATH, 20)
        self._fontFlightTiny = ImageFont.truetype(FONT_REGULAR_PATH, 14)

        # Load fonts for the idle display.
        self._fontIdleTitle = ImageFont.truetype(FONT_BOLD_PATH, 32)
        self._fontIdleSubTitle = ImageFont.truetype(FONT_REGULAR_PATH, 14)
        self._fontIdleHeader = ImageFont.truetype(FONT_BOLD_PATH, 24)
        self._fontIdleRowBold = ImageFont.truetype(FONT_BOLD_PATH, 18)
        self._fontIdleRowRegular = ImageFont.truetype(FONT_REGULAR_PATH, 16)
        self._fontIdleRowSmall = ImageFont.truetype(FONT_REGULAR_PATH, 14)

    def _load_aircraft_colour_list(self, path=COLOUR_PATH):
        """
        Loads the aircraft colour list map into memory.
        By default we look in the colour path for the CSV
        """
        # Attempt to load the CSV into memory.
        try:
            with open(path, mode='r', encoding='utf-8') as colourFile:
                tempColourCache = {}

                reader = csv.DictReader(colourFile)
                for row in reader:
                    airline_code = row.get('icao', '').strip()
                    if airline_code:
                        # If the airline code was found, insert that entry into memory.
                        tempColourCache[airline_code] = {
                            "name": row.get('name', '').strip(),
                            "primary": ( 
                                int( row.get('primary_r', '0').strip() ), 
                                int( row.get('primary_g', '0').strip() ), 
                                int( row.get('primary_b', '0').strip() )
                            ),
                            "accent": ( 
                                int( row.get('accent_r', '0').strip() ), 
                                int( row.get('accent_g', '0').strip() ),
                                int( row.get('accent_b', '0').strip() ) 
                            ),
                            "logo": row.get('logo_filename', '').strip(),
                        }
        
            self._colour_cache = tempColourCache
            print(f"Successfully loaded {len(tempColourCache)} aircraft colours into memory.")

        except Exception as e:
            print(f"Error: Failed to load aircraft colour file: {e}")
            self._colour_cache = {}
        
        # Last, insert the fallback value.
        # This will be used if we can't load.
        self._colour_cache[GENERIC_AIRLINE_CODE] = {
            "name": "GENERAL AVIATION",
            "primary": (80, 80, 80),    # Dark Gray
            "accent": (0, 0, 0),        # Black
            "logo": "generic.png"      
        }

    def _get_centered_x(self, draw, text, font, area_start=0, area_width=None):
        """
        Calculates the X coordinate to perfectly center text within a specific column/area.
        If area_width is None, it defaults to the entire screen width.
        """
        if area_width is None:
            area_width = self._width
        
        # Get the bounding box of the text. Then calculate the centered X coordinate.
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        return area_start + ((area_width - text_width) / 2)

    def _get_right_justified_x(self, draw, text, font, right_edge_x):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        return right_edge_x - text_width

    def _get_idle_separator_x_position(self):
        return 460
    
    def _get_ticket_stub_x_position(self):
        """
        Helper function to get the ticket stub x position.
        """
        return self._width - 240

    def _get_main_ticket_width(self):
        """
        Helper function to get the main ticket's width.
        """
        return self._get_ticket_stub_x_position() - 10
 
    def _should_update_screen(self, last_state=None):
        """
        Checks if the screen should be updated. This ensures we don't overload the screen.
        Returns true if the state changes or if we hit a timeout.
        """
        current_time = time.time()
        if self._last_state == "NO_FLIGHT":
            return False
        if current_time - self._last_update_time < self._throttle_seconds:
            return False
        
        return True

    def _draw_perforation_line(self, draw, start_coord, end_coord, fill_colour=(100,100,100), dash=10, space=8, width=3):
        """
        Calculates a dotted line from a start coordinate to an end coordinate with a specified
        width. This provides defaults for the dash options.
        """
        # Figure out the distance to draw and the number of dashes.
        x1, y1 = start_coord
        x2, y2 = end_coord
        distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        dashes = int(distance / (dash + space))
        
        # For each dash, we need to draw it individually.
        # Compute the start x and y and then draw.
        for i in range(dashes):
            start_x = x1 + (x2 - x1) * (i * (dash + space) / distance)
            start_y = y1 + (y2 - y1) * (i * (dash + space) / distance)
            end_x = start_x + (x2 - x1) * (dash / distance)
            end_y = start_y + (y2 - y1) * (dash / distance)
            draw.line([(start_x, start_y), (end_x, end_y)], fill=fill_colour, width=width)
    
    def _draw_block_arrow(self, draw, x, y, width, height, fill_colour):
        """
        Draws a geometric analog arrow using standard polygons.
        """
        # Computes the height, width, and center y position of the stem. 
        stem_h = height * 0.35
        stem_w = width * 0.6
        stem_y = y + (height - stem_h) / 2
        
        # Draws the stem.
        draw.rectangle([x, stem_y, x + stem_w, stem_y + stem_h], fill=fill_colour)

        # Computes the head of the arrow. This is a sideways triangle.
        point_a = (x + stem_w, y)
        point_b = (x + width, y + height / 2)
        point_c = (x + stem_w, y + height)
        draw.polygon([point_a, point_b, point_c], fill=fill_colour)

    def _draw_procedural_barcode(self, draw, x_start, y_start, height=80, seed_text=""):
        """
        Draws a random barcode based on the input seed text. This will generate
        the same barcode any time the same seed text is used.
        """
        # Set the seed text.
        if seed_text != "":
            random.seed(seed_text)
        
        # Draw a random assortment of vertical lines based on the seed.
        current_x = x_start
        for _ in range(22):
            bar_width = random.choice([2, 4, 7])
            space_width = random.choice([3, 5])
            draw.rectangle([current_x, y_start, current_x + bar_width, y_start + height], fill=(0, 0, 0))
            current_x += bar_width + space_width

        # Reset the seed back to empty.
        random.seed()

    def _draw_idle_frame(self, draw, primary_colour, city_name):
        # Draw the top box and border for the idle frame.
        draw.rectangle([10, 10, self._width - 10, self._height - 10], outline=(0,0,0), width=3)
        draw.rectangle([10, 10, self._width - 10, 85], fill=primary_colour)
        
        # Determine the greeting based on the current hour.
        system_hour = datetime.now().hour
        if 5 <= system_hour < 12: 
            greeting_type = "Morning"
        elif 12 <= system_hour < 18: 
            greeting_type = "Afternoon"
        elif 18 <= system_hour < 23: 
            greeting_type = "Evening"
        else: 
            greeting_type = "Night"

        greeting = f"++  Good {greeting_type}, {city_name}!  ++"
        gx = self._get_centered_x(draw, greeting, self._fontIdleTitle)
        draw.text((gx, 22), greeting, font=self._fontIdleTitle, fill=(255,255,255))

        subtext = "SYSTEM STATUS // LOCAL AIRSPACE DETECTOR"
        sx = self._get_centered_x(draw, subtext, self._fontIdleSubTitle)
        draw.text((sx, 62), subtext, font=self._fontIdleSubTitle, fill=(255,255,255))
        
        # Last, create two boxes for the actual content.
        divider_x = self._get_idle_separator_x_position()
        self._draw_perforation_line(draw, (divider_x, 95), (divider_x, self._height - 20), dash=6, space=6, width=2)

    def _draw_idle_weather_section(self, draw, canvas, forecast_data, high_colour, low_colour):
        draw.text((30, 105), "4-DAY WEATHER FORECAST", font=self._fontIdleHeader, fill=(0,0,0))
        draw.text((30, 130), f"FOR {forecast_data['location_name'].upper()}", font=self._fontIdleRowBold, fill=(0,0,0))
    
        start_y = 175
        row_height = 70
        
        # Iterate through the forecast and add each one-by-one.
        for i, data in enumerate(forecast_data['forecast']):
            y = start_y + (i * row_height)
            
            # Day Label (Vertically centered at y + 20)
            draw.text((30, y + 20), data['day'], font=self._fontIdleRowBold, fill=(0,0,0))
            
            # Icon Handling (60x60 icon positioned at y + 5)
            icon_x = 150
            icon_y = y + 5

            svg_path = pathlib.Path(os.path.join(WEATHER_PATH, get_svg_filename_from_code(data['icon'])))
            temp_png_path = svg_path.with_suffix(".temp.png")
            
            if svg_to_png(svg_path, temp_png_path, output_width=60, output_height=60, dpi=96):
                try:
                    forecast_icon = Image.open(temp_png_path).convert("RGBA")
                    canvas.paste(forecast_icon, (icon_x, icon_y), mask=forecast_icon)
                except Exception as e:
                    print(f"Error pasting icon: {e}")
                finally:
                    if temp_png_path.exists():
                        temp_png_path.unlink()
                
            # Temperatures & Desc vertically aligned to match the icon center
            draw.text((225, y + 12), data['high'], font=self._fontIdleRowBold, fill=high_colour)
            draw.text((285, y + 12), f"/ {data['low']}", font=self._fontIdleRowBold, fill=low_colour)
            draw.text((225, y + 38), data['description'], font=self._fontIdleRowSmall, fill=(0,0,0))
            
            # Dividing line moved to bottom of row (y + 68) so icons don't clip through
            if i < 3:
                draw.line([(30, y + 68), (430, y + 68)], fill=(0,0,0), width=1)

    def _draw_idle_statistics_section(self, draw):
        draw.text((485, 105), "RECEIVER", font=self._fontIdleHeader, fill=(0,0,0))
        draw.text((485, 130), "STATISTICS", font=self._fontIdleHeader, fill=(0,0,0))
        
        # Radar Graphic in upper right
        # (Section contained definition call integration)
        # Procedural helper to draw radar scope scoping scoping scoping scoping scoping scoping scoping scoping
        def draw_radar_icon(draw, cx, cy, radius=40):
            """Draws a retro air traffic control radar sweep."""
            # Outer arcs
            draw.arc([cx - radius, cy - radius, cx + radius, cy + radius], 180, 0, fill=(0,0,0), width=2)
            draw.arc([cx - radius*0.6, cy - radius*0.6, cx + radius*0.6, cy + radius*0.6], 180, 0, fill=(0,0,0), width=1)
            # Base line
            draw.line([(cx - radius - 5, cy), (cx + radius + 5, cy)], fill=(0,0,0), width=2)
            # Grid lines
            draw.line([(cx, cy), (cx - radius*0.7, cy - radius*0.7)], fill=(0,0,0), width=1)
            draw.line([(cx, cy), (cx + radius*0.7, cy - radius*0.7)], fill=(0,0,0), width=1)
            # Radar Sweep Wedge (Green fill)
            draw.polygon([(cx, cy), (cx + radius*0.8, cy - radius*0.5), (cx + radius*0.4, cy - radius*0.9)], fill=COLOR_GREEN)
            # Center transmitter antenna tower
            draw.polygon([(cx - 3, cy), (cx + 3, cy), (cx, cy - 12)], fill=(0,0,0))
            
        draw_radar_icon(draw, cx=720, cy=150, radius=45)
        
        draw.line([(485, 165), (765, 165)], fill=(0,0,0), width=2)
        
        # Stats Grid - Right Justification Logic
        stats_y = 185
        spacing = 38
        right_edge_x = 760
        
        # Status
        draw.text((485, stats_y), "Status:", font=self._fontIdleRowRegular, fill=(0,0,0))
        # Apply Right Justification
        x_rj = self._get_right_justified_x(draw, "ACTIVE", self._fontIdleRowBold, right_edge_x)
        draw.text((x_rj, stats_y), "ACTIVE", font=self._fontIdleRowBold, fill=COLOR_GREEN)
        
        # Signal Strength
        draw.text((485, stats_y + spacing), "Signal Strength:", font=self._fontIdleRowRegular, fill=(0,0,0))
        # Apply Right Justification
        x_rj = self._get_right_justified_x(draw, "GOOD", self._fontIdleRowBold, right_edge_x)
        draw.text((x_rj, stats_y + spacing), "GOOD", font=self._fontIdleRowBold, fill=COLOR_ORANGE)
        
        # Up-Time
        draw.text((485, stats_y + (spacing * 2)), "Up-Time:", font=self._fontIdleRowRegular, fill=(0,0,0))
        # Apply Right Justification
        x_rj = self._get_right_justified_x(draw, "14d, 6 hrs", self._fontIdleRowRegular, right_edge_x)
        draw.text((x_rj, stats_y + (spacing * 2)), "14d, 6 hrs", font=self._fontIdleRowRegular, fill=(0,0,0))
        
        # Last Sync
        draw.text((485, stats_y + (spacing * 3)), "Today's Flights:", font=self._fontIdleRowRegular, fill=(0,0,0))
        # Apply Right Justification
        x_rj = self._get_right_justified_x(draw, "3", self._fontIdleRowBold, right_edge_x)
        draw.text((x_rj, stats_y + (spacing * 3)), "3", font=self._fontIdleRowBold, fill=COLOR_BLUE)
        
        # Total Flights Today
        draw.text((485, stats_y + (spacing * 4)), "Total Flights:", font=self._fontIdleRowRegular, fill=(0,0,0))
        # Apply Right Justification
        x_rj = self._get_right_justified_x(draw, "28", self._fontIdleRowBold, right_edge_x)
        draw.text((x_rj, stats_y + (spacing * 4)), "28", font=self._fontIdleRowBold, fill=COLOR_BLUE)

    def _draw_idle_tooltext_section(self, draw, tooltip_colour):
        # Dimensions for tooltext box.
        # Hardcoded to be at bottom right of screen.
        # TODO: We should have it fill out based on the screen's height and width.
        box_x1, box_y1 = 485, 385
        box_x2, box_y2 = 775, 455
        
        # Draw the tooltip box.
        draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=tooltip_colour, outline=(0,0,0), width=2)
        draw.rectangle([box_x1 + 3, box_y1 + 3, box_x2 - 3, box_y2 - 3], outline=(255,255,255), width=1)
        
        # Tooltip Text (Reflowed and Centered inside orange box)
        top_text = "No planes detected via ADS-B!"
        subtitle_text = "Searching..." 
        top_x = self._get_centered_x(draw, top_text, self._fontIdleRowSmall, area_start=box_x1, area_width=(box_x2 - box_x1))
        sub_x = self._get_centered_x(draw, subtitle_text, self._fontIdleRowBold, area_start=box_x1, area_width=(box_x2 - box_x1))
        draw.text((top_x, box_y1 + 10), top_text, font=self._fontIdleRowSmall, fill=(255,255,255))
        draw.text((sub_x, box_y1 + 34), subtitle_text, font=self._fontIdleRowBold, fill=(255,255,255))
    
    def _draw_ticket_frame(self, draw, primary_colour):
        """
        Draws the actual unfilled ticket template.
        This creates a ticket with no other data.
        """
        # Draw the outer border and top frame.
        draw.rectangle([10, 10, self._width - 10, self._height - 10], outline=(0,0,0), width=4)
        draw.rectangle([10, 10, self._width - 10, 75], fill=primary_colour)
    
        # Vertically center the header text.
        # Assume we are writing a 65 height top frame.
        header_text = "BOARDING PASS  //  LOCAL AIRSPACE DETECTOR"
        bbox = draw.textbbox((0, 0), header_text, font=self._fontFlightSmall)
        text_height = bbox[3] - bbox[1]
        header_y = 10 + ((65 - text_height) / 2)
        draw.text([30, header_y], header_text, font=self._fontFlightSmall, fill=(255, 255, 255))

        # Create the ticket stub portion.
        # The perforation line is 240px from the end.
        stub_x = self._get_ticket_stub_x_position()
        self._draw_perforation_line(draw, (stub_x, 75), (stub_x, self._height - 10), dash=12, space=6, width=2)

        # Last, writ the receipt text on the stub.
        draw.text([stub_x + 20, 95], "FLIGHT RECEIPT", font=self._fontFlightTiny, fill=(0,0,0))
        self._draw_perforation_line(draw, (stub_x + 15, 120), (self._width - 15, 120), dash=4, space=4, width=1)

    def _draw_ticket_main_section(self, draw, primary_colour, accent_colour, flight_num, airline_name, origin, dest):
        """
        Draws the main section of the ticket. This includes the flight number, airline, origin and destination, and
        data columns at the bottom of the ticket.
        """
        main_width = self._get_main_ticket_width()
    
        # Write the flight code and airline
        draw.text([35, 100], "FLIGHT NO:", font=self._fontFlightTiny, fill=(0,0,0))
        draw.text([35, 120], f"{flight_num}", font=self._fontFlightLarge, fill=(0,0,0))
        draw.text([35, 185], f"OPERATED BY: {airline_name}", font=self._fontFlightTiny, fill=primary_colour)

        # Write the route information box.
        draw.text([35, 230], "ROUTING:", font=self._fontFlightTiny, fill=(0,0,0))
    
        # Calculate the total width of Origin + Space + Arrow + Space + Destination
        route_y = 250
        arrow_width = 50
        spacing = 30
        origin_bbox = draw.textbbox((0, 0), origin, font=self._fontFlightLarge)
        dest_bbox = draw.textbbox((0, 0), dest, font=self._fontFlightLarge)
        origin_w = origin_bbox[2] - origin_bbox[0]
        dest_w = dest_bbox[2] - dest_bbox[0]
        total_route_width = origin_w + spacing + arrow_width + spacing + dest_w
    
        # Center the entire block in the main window
        start_x = 10 + ((main_width - total_route_width) / 2)
        
        # Draw Origin
        draw.text([start_x, route_y], origin, font=self._fontFlightLarge, fill=(0,0,0))
        
        # Draw Vector Arrow
        arrow_x = start_x + origin_w + spacing
        arrow_y = route_y + 17 # Nudge arrow down slightly to align with text center
        self._draw_block_arrow(draw, arrow_x, arrow_y, arrow_width, 30, accent_colour)
        
        # Draw Destination
        dest_x = arrow_x + arrow_width + spacing
        draw.text([dest_x, route_y], dest, font=self._fontFlightLarge, fill=(0,0,0))

    def _draw_ticket_bottom_section(self, draw, primary_colour, altitude, heading, gs):
        """
        Draws three equal bottom columns for holding altitude, heading, and ground
        speed.
        """
        # Determine the header y top and value y top.
        # We'll have three columns so split the width.
        grid_y_top = 405
        grid_y_val = 430
        col_width = (self._get_main_ticket_width() - 20) / 3

        # Column 1 (Altitude)
        col1_start = 10
        draw.text(
            (self._get_centered_x(draw, "ALTITUDE", self._fontFlightTiny, col1_start, col_width), grid_y_top),
            "ALTITUDE", font=self._fontFlightTiny, fill=primary_colour
        )
        draw.text(
            (self._get_centered_x(draw, f"{altitude}", self._fontFlightSmall, col1_start, col_width), grid_y_val),
            f"{altitude}", font=self._fontFlightSmall, fill=(0,0,0)
        )

        # Column 2 (Heading)
        col2_start = 10 + col_width
        draw.text(
            (self._get_centered_x(draw, "HEADING", self._fontFlightTiny, col2_start, col_width), grid_y_top),
            "HEADING", font=self._fontFlightTiny, fill=primary_colour
        )
        draw.text(
            (self._get_centered_x(draw, f"{heading}", self._fontFlightSmall, col2_start, col_width), grid_y_val),
            f"{heading}", font=self._fontFlightSmall, fill=(0,0,0)
        )

        # Column 3 (Speed)
        col3_start = 10 + (col_width * 2)
        draw.text(
            (self._get_centered_x(draw, "SPEED", self._fontFlightTiny, col3_start, col_width), grid_y_top),
            "SPEED", font=self._fontFlightTiny, fill=primary_colour
        )
        draw.text(
            (self._get_centered_x(draw, f"{gs}", self._fontFlightSmall, col3_start, col_width), grid_y_val),
            f"{gs}", font=self._fontFlightSmall, fill=(0,0,0)
        )

    def _draw_ticket_stub_section(self, draw, canvas, flight_num, aircraft_type, logo_filename):
        """
        Writes data and logos to the ticket stub portion of the ticket.
        """
        # Get the size of the ticket stub.
        stub_x = self._get_ticket_stub_x_position()

        # Start by drawing the logo if it exists.
        logo_path = os.path.join(DATA_DIR, "logos", LOGO_PATH, f"{logo_filename}")
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo = logo.resize((80, 80))
            canvas.paste(logo, (int(stub_x + 75), 140), mask=logo) 
        except FileNotFoundError:
            pass

        # Write the aircraft information below the logo.
        draw.text([stub_x + 20, 230], "AIRCRAFT:", font=self._fontFlightTiny, fill=(0,0,0))
        draw.text([stub_x + 20, 255], f"{aircraft_type or "Unknown"}", font=self._fontFlightSmall, fill=(0,0,0))

        # Write the barcode at the bottom.
        self._draw_procedural_barcode(draw, stub_x + 30, 360, height=75, seed_text=flight_num)

    def _prepare_for_epd(self, canvas):
        """
        Forces the PIL image to snap to the exact 7-color ACeP palette
        without applying messy checkerboard dithering.
        """
        # Create a 7-color palette image
        pal_image = Image.new("P", (1, 1))
        
        # Corresponds to Waveshare's 7 colour epd palette.
        palette = [
            0, 0, 0,          # 0: Black
            255, 255, 255,    # 1: White
            0, 255, 0,        # 2: Green
            0, 0, 255,        # 3: Blue
            255, 0, 0,        # 4: Red
            255, 255, 0,      # 5: Yellow
            255, 128, 0,      # 6: Orange
        ] + [0] * (256 * 3 - 21)
        pal_image.putpalette(palette)
        
        #  Ensure we don't dither when converting.
        quantized_image = canvas.quantize(palette=pal_image, dither=Image.NONE)
        return quantized_image.convert("RGB")

    def _writeToScreen(self, canvas):
        if self._display is not None:
            clean_image = self._prepare_for_epd(canvas)
            self._display.display(self._display.getbuffer(clean_image))
            self._display.sleep()

    def WriteNoFlight(self, forecast_data=None):
        # Check if we should update the screen before beginning.
        # TODO: This will refuse to update once set. We need a better way to check this for a change.
        flight_state = "NO_FLIGHT"
        if self._should_update_screen(flight_state) is False:
            return

        # Check if the forecast data is set.
        if forecast_data is None:
            forecast_data = {
                "city_name": "Unknown",
                "location_name": "Unknown, UNK",
                "forecast": []
            }
        
        # Next, if the forecast data is 
        # Creates a new canvas and drawing.
        canvas = Image.new('RGB', (self._width, self._height), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        # Build our colour palette based on the idle section.
        # TODO: Figure out a better way for these.
        COLOUR_BLUE = (0, 0, 255)
        COLOUR_ORANGE = (255, 128, 0)

        # Build the initial idle frame.
        self._draw_idle_frame(draw, COLOUR_BLUE, forecast_data['city_name'] )

        # Next, draw the three main sections.
        self._draw_idle_weather_section(draw, canvas, forecast_data, COLOUR_ORANGE, COLOUR_BLUE)
        self._draw_idle_statistics_section(draw)
        self._draw_idle_tooltext_section(draw, COLOUR_ORANGE)

        # Everything is done! Write to the screen and update our state.
        self._writeToScreen(canvas)
        self._last_state = flight_state
        self._last_update_time = time.time()

    def WriteFlightData(self, flight_num, origin, dest, elev, heading, gs, aircraft_type):
        # Check if we should update the screen before beginning.
        flight_state = (flight_num, origin, dest, elev, heading, gs, aircraft_type)
        if self._should_update_screen(flight_state) is False:
            return

        # Creates a new canvas and drawing.
        canvas = Image.new('RGB', (self._width, self._height), (245, 245, 240))
        draw = ImageDraw.Draw(canvas)

        # Determine the colour palette for this ticket.
        # Use this by getting the first three digits of the flight number and looking in the colour cache.
        airline_icao_code = flight_num[:3]
        if airline_icao_code not in self._colour_cache:
            airline_icao_code = GENERIC_AIRLINE_CODE
        
        primary_colour = self._colour_cache[airline_icao_code]['primary']
        accent_colour = self._colour_cache[airline_icao_code]['accent']
        airline_name = self._colour_cache[airline_icao_code]['name']
        logo_filename = self._colour_cache[airline_icao_code]['logo']

        # Build the initial ticket frame.
        self._draw_ticket_frame(draw, primary_colour)

        # Next draw the main part of the ticket frame
        # and other data columns.
        self._draw_ticket_main_section(draw, primary_colour, accent_colour, flight_num, airline_name, origin, dest)
        self._draw_ticket_bottom_section(draw, primary_colour, elev, heading, gs)

        # Draw the ticket stub data.
        self._draw_ticket_stub_section(draw, canvas, flight_num, aircraft_type, logo_filename)

        # Everything is done! Write to the screen and update our state.
        self._writeToScreen(canvas)
        self._last_state = flight_state
        self._last_update_time = time.time()