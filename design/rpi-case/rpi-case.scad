//-----------------------------------------------------------------------
// Custom Raspberry Pi 4 + RTL-SDR + E-Ink Flight Tracker Enclosure
//
// Driven by YAPP Generator v3.3.7
// Designed by Bryan Muscedere
//
// This design is used to house the Raspberry Pi 4, RTL STR v4, 
// and Waveshare Eink screen.
//-----------------------------------------------------------------------

// ======================================================================
// 1. USER CONFIGURATION & HARDWARE DIMENSIONS
// ======================================================================

// -- Main Box Outer Boundaries (Driven by Main PCB) --
totalLength           = 185;  // X-axis length
totalWidth            = 125;  // Y-axis width
boxWallHeight         = 40;   // Z-axis height
boxWallThickness      = 2.0;  // Wall thickness in mm
boxFloorThickness     = 1.5;  // Bottom floor thickness in mm
lidCeilingThickness   = 1.5;  // Top lid thickness in mm
lidHeight             = 20;   // Z-axis height

// -- E-Ink Display Module Specs --
screenLength          = 170.2; // Total physical length of display module in mm
screenWidth           = 111.2; // Total physical width of display module in mm
screenActiveLength    = 160.0; // Visible window length in mm
screenActiveWidth     = 96.0;  // Visible window width in mm
screenThickness       = 1.6;   // Display PCB/glass backing thickness
screenLipGap          = 1.8;   // Depth of the recessed mounting shelf

// -- Waveshare Controller PCBs Specs --
wave1Length           = 65;    // Length in mm
wave1Width            = 56;    // Width in mm
wave1PosX             = 110;   // Distance from back wall
wave1PosY             = 15;    // Distance from left wall
wave2Length           = 65;    // Length in mm
wave2Width            = 56;    // Width in mm
wave2PosX             = 110;   // Distance from back wall
wave2PosY             = 70;    // Distance from left wall

// -- Raspberry Pi 4 Module Specs --
rpiSizeLength         = 85;    // Length in mm
rpiSizeWidth          = 56;    // Width in mm
rpiPosX               = 15;    // Distance from back wall
rpiPosY               = 15;    // Distance from left wall

// ======================================================================
// 2. YAPP CONFIGURATION
// ======================================================================
include <./dependencies/yapp-generator-v3.scad>

// -- Print Selection --
printBaseShell        = true;
printLidShell         = true;
printSwitchExtenders  = false;
printDisplayClips     = false;

// -- Main Box Outer Boundaries (Driven by Main PCB) --
pcbLength             = totalLength;         // X-axis length
pcbWidth              = totalWidth;          // Y-axis width
wallThickness         = boxWallThickness;    // Wall thickness in mm
basePlaneThickness    = boxFloorThickness;   // Bottom floor thickness in mm
lidPlaneThickness     = lidCeilingThickness; // Top lid thickness in mm

// -- Box Heights --
baseWallHeight        = boxWallHeight;       // Depth of the bottom shell
lidWallHeight         = lidHeight;           // Depth of the lid shell
standoffHeight        = 3.0;                 // Airflow gap beneath PCBs

// -- Padding Options --
// Do not change these values.
// Included here for information only.
paddingFront          = 0;
paddingBack           = 0;
paddingRight          = 0;
paddingLeft           = 0;

// ======================================================================
// 2. PCB DEFINITIONS
// ======================================================================
// Parameters are: [name, length, width, posx, posy, thickness, standoff_Height, stand_Dia, pin_Dia, slack]
pcb = 
[
  ["Main",        pcbLength,     pcbWidth,     0,         0,         1.6, standoffHeight, 7, 2.4, 0.4],
  ["RaspberryPi", rpiSizeLength, rpiSizeWidth, rpiPosX,   rpiPosY,   1.6, standoffHeight, 6, 2.4, 0.4],
  ["Waveshare1",  wave1Length,   wave1Width,   wave1PosX, wave1PosY, 1.6, standoffHeight, 5, 2.0, 0.4],
  ["Waveshare2",  wave2Length,   wave2Width,   wave2PosX, wave2PosY, 1.6, standoffHeight, 5, 2.0, 0.4]
];

// ======================================================================
// 3. DISPLAY MOUNTING & BEZELS
// ======================================================================
// Parameters are: [posx, posy, displayWidth, displayHeight, pinInsetH, pinInsetV, pinDiameter, postOverhang, walltoPCBGap, pcbThickness, windowWidth, windowHeight, windowOffsetH, windowOffsetV, bevel, yappCoordBoxInside]
displayMounts =
[
  // E-Ink viewing window with 4-post cradle and recessed tape lip.
  // Dynamically auto-centered based on box and screen dimensions.
  [
    (boxLength - screenLength) / 2, 
    (boxWidth - screenWidth) / 2, 
    screenLength, 
    screenWidth, 
    2.5, 
    2.5, 
    1.5, 
    -0.5, 
    screenLipGap, 
    screenThickness, 
    screenActiveLength, 
    screenActiveWidth, 
    0, 
    0, 
    1.5, 
    yappCoordBoxInside
  ]
];

// ======================================================================
// 4. STANDOFFS & PILLARS
// ======================================================================
// Arguments are: [posx, posy, standHeight, pcbGap, standDia, pinDia, holeSlack, filletRadius, pinLength, yappBaseOnly, yappPCBName]
pcbStands = 
[
  // Raspberry Pi 4 Standoffs (Anchored directly to the "RaspberryPi" PCB footprint)
  [3.5,      3.5,      undef, undef, undef, undef, undef, undef, undef, yappBaseOnly, [yappPCBName, "RaspberryPi"]],
  [3.5 + 58, 3.5,      undef, undef, undef, undef, undef, undef, undef, yappBaseOnly, [yappPCBName, "RaspberryPi"]],
  [3.5,      3.5 + 49, undef, undef, undef, undef, undef, undef, undef, yappBaseOnly, [yappPCBName, "RaspberryPi"]],
  [3.5 + 58, 3.5 + 49, undef, undef, undef, undef, undef, undef, undef, yappBaseOnly, [yappPCBName, "RaspberryPi"]]
];

// ======================================================================
// 5. PORT & CABLE CUTOUTS
// ======================================================================
// Arguments are: [posX, posY, width_X, length_Y, corner_radius, shape, depth, angle, yappCoordBoxInside]
cutoutsBase = 
[
  // Panel Mount USB-C Port
  [ 20, 20, 12, 7, 3.5, yappRoundedRect, 0, 0, yappCoordBoxInside ]
];

cutoutsRight =   
[
  // Scot Bezek 1x8 Splitflap Ribbon/Wire Slot
  [ 20, 15, 25, 5, 2.5, yappRoundedRect, 0, 0, yappCoordBoxInside ]
];

// ======================================================================
// 6. 3D MODEL HOOKS (STL IMPORTS)
// ======================================================================
module hookBaseInside()
{
  // Imports RTL-SDR stand and slides it into open space to the right of the Pi
  translate([145, 15, 0]) 
  import("dependencies/rtl-sdr-stand.stl");
}

// ======================================================================
// 7. UNUSED YAPP ARRAYS & HOOKS
// Keep these to prevent compiler errors. Unused in this project.
// ======================================================================
connectors = []; snapJoins = []; boxMounts = []; lightTubes = []; 
pushButtons = []; labelsPlane = []; cutoutsLid = []; cutoutsFront = []; 
cutoutsBack = []; cutoutsLeft = []; ridgeExtLeft = []; ridgeExtRight = []; 
ridgeExtFront = []; ridgeExtBack = [];

module hookLidInside() {}
module hookLidOutside() {}
module hookBaseOutside() {}

// ======================================================================
// 8. RENDER ENGINE
// Do not change these unless you know what you're doing.
// Needed to properly generate.
// ======================================================================
ridgeHeight = 5.0; ridgeSlack = 0.3; ridgeGap = 0.5; roundRadius = 3.0;
boxType = 0; printerLayerHeight = 0.2; renderQuality = 8; previewQuality = 5;
showSideBySide = true; colorLid = "YellowGreen"; colorBase = "BurlyWood";

// ======================================================================
// 9. RUN GENERATOR
// ======================================================================
YAPPgenerate();
