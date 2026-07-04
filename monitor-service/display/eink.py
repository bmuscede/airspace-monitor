import sys
import os
from PIL import Image, ImageDraw, ImageFont

from waveshare_epd import epd2in7

class EInk:
    display = epd2in7.EPD()

    def __init__(self):
        # Initialize the display and clear it from any previous ghost images.
        self.display.init()
        self.display.Clear()

    def writeToScreen(self, canvas):
        # Display the image on the screen.
        # Ensure we sleep so we don't burn out the screen.
        self.display.display(self.display.getbuffer(canvas))
        self.display.sleep()

    def buildTicketFrame(self, draw):
        # Generate the overall boxes and lines to look like a ticket.
        draw.rectangle(
            [5,5, width-5, height-5],
            outline=0,
            fill=None,
            width=2,
        )
        draw.rectangle(
            [5,5, width-5, 40],
            outline=0,
            fill=0,
            width=1,
        )
        draw.line(
            [5, 90, width-5, 90],
            fill=0,
            width=1,
        )
        draw.line(
            [width/2, 95, width/2, height-10],
            fill=0,
            width=1,
        )

        return draw

    def buildTicketSubItems(self, draw, elev=None, heading=None, gs=None, aircraftType=None):
        # Build labels for subitems.
        draw.text(
            [8, 95],
            "ALTITUDE",
            font=fontSmall,
            fill=0
        )
        draw.text(
            [8, 135],
            "HEADING",
            font=fontSmall,
            fill=0
        )
        draw.text(
            [width/2 + 5, 95],
            "GROUND SPEED",
            font=fontSmall,
            fill=0
        )
        draw.text(
            [width/2 + 5, 135],
            "TYPE",
            font=fontSmall,
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
            font=fontLarge,
            fill=0
        )
        draw.text(
            [8, 147],
            f"{heading}",
            font=fontLarge,
            fill=0
        )
        draw.text(
            [width/2 + 5, 107],
            f"{gs}",
            font=fontLarge,
            fill=0
        )
        draw.text(
            [width/2 + 5, 147],
            f"{aircraftType}",
            font=fontLarge,
            fill=0
        )

        return draw

    def GetCanvasWidth(self):
        return self.display.width

    def GetCanvasHeight(self):
        return self.display.height

    def WriteNoFlight(self):
        width = self.GetCanvasWidth()
        height = self.GetCanvasHeight()

        # Create the canvas.
        # E-ink drivers usually require a '1' mode for 1-bit monochrome black/white.
        canvas = Image.new('1', (width, height), 255)
        draw = ImageDraw.Draw(canvas)
        
        # Load a TrueType system font
        fontLarge = ImageFont.truetype("/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono-Bold.ttf", 18)
        fontSmall = ImageFont.truetype("/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf", 11)

        # Start by building the ticket frame.
        draw = self.buildTicketFrame(draw)

        # Add labels to the ticket.
        draw.text(
            [8, 12],
            f"NO FLIGHTS OVERHEAD",
            font=fontLarge,
            fill=255
        )
        draw.text(
            [25, 50],
            "Cannot detect any ADS-B signals.",
            font=fontSmall,
            fill=0
        )
        draw.text(
            [72, 65],
            "Waiting on data...",
            font=fontSmall,
            fill=0
        )

        # Write the subportion of the ticket data.
        draw = self.buildTicketSubItems(draw, elev, heading, gs, aircraftType)

        # Send to the screen
        self.writeToScreen(canvas)

    def WriteFlightData(self, flightNum, origin, dest, elev, heading, gs, aircraftType):
        width = self.GetCanvasWidth()
        height = self.GetCanvasHeight()

        # Create the canvas.
        # E-ink drivers usually require a '1' mode for 1-bit monochrome black/white.
        canvas = Image.new('1', (width, height), 255)
        draw = ImageDraw.Draw(canvas)
        
        # Load a TrueType system font
        fontLarge = ImageFont.truetype("/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono-Bold.ttf", 18)
        fontSmall = ImageFont.truetype("/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf", 11)

        # Start by building the ticket frame.
        draw = self.buildTicketFrame(draw)

        # Add labels to the ticket.
        draw.text(
            [8, 12],
            f"{flightNum} OVERHEAD",
            font=fontLarge,
            fill=255
        )
        draw.text(
            [8, 45],
            "FLIGHT PATH",
            font=fontSmall,
            fill=0
        )
        draw.text(
            [(width/2)-4, 65],
            ">",
            font=fontLarge,
            fill=0
        )
        
        # Add origin and destination information.
        draw.text(
            [width/4 - 10, 65],
            f"{origin}",
            font=fontLarge,
            fill=0
        )
        draw.text(
            [width/2 + width/4 - 10, 65],
            f"{dest}",
            font=fontLarge,
            fill=0
        )
        
        # Write the subportion of the ticket.
        draw = self.buildTicketSubItems(draw, elev, heading, gs, aircraftType)
        
        # Send to the screen
        self.writeToScreen(canvas)
        

