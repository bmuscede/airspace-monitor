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
screenLength          = 170.5; // 170.05mm + tolerance for clean drop-in fit
screenWidth           = 112.2; // 111.80mm + tolerance for clean drop-in fit
screenActiveLength    = 160.0; // Visible window length in mm
screenActiveWidth     = 96.0;  // Visible window width in mm
screenThickness       = 1.6;   // Display PCB/glass backing thickness
screenLipGap          = 1.8;   // Depth of the recessed mounting shelf

// -- Waveshare Controller PCBs Specs --
wave1Length           = 45;    // Length in mm
wave1Width            = 21;    // Width in mm
wave1PosX             = totalLength / 2 - wave1Length / 2;   // Distance from back wall
wave1PosY             = totalWidth - wave1Width - 5;    // Distance from left wall
wave2Length           = 65;    // Length in mm
wave2Width            = 30;    // Width in mm
wave2PosX             = 30;    // Distance from back wall
wave2PosY             = 82;    // Distance from left wall
waveStandoffHeight    = 12.0;  // Waveshare Airflow Gap

// -- Raspberry Pi 4 Module Specs --
rpiSizeLength         = 85.46; // Length in mm
rpiSizeWidth          = 56;    // Width in mm
rpiPosX               = 15;    // Distance from back wall
rpiPosY               = 15;    // Distance from left wall

// ======================================================================
// 2. YAPP CONFIGURATION
// ======================================================================
include <./dependencies/yapp-generator-v3.scad>

// -- Print Selection --
printBaseShell        = true;
printLidShell         = false;
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
standoffHeight        = 3.0;                 // Main PCB Airflow Gap

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
  ["Waveshare1",  wave1Length,   wave1Width,   wave1PosX, wave1PosY, 1.6, waveStandoffHeight, 5, 2.0, 0.4],
  ["Waveshare2",  wave2Length,   wave2Width,   wave2PosX, wave2PosY, 1.6, waveStandoffHeight, 5, 2.0, 0.4]
];

// ======================================================================
// 3. DISPLAY MOUNTING & BEZELS
// ======================================================================
// Parameters: [posx, posy, displayWidth, displayHeight, pinInsetH, pinInsetV, pinDiameter, postOverhang, walltoPCBGap, pcbThickness, windowWidth, windowHeight, windowOffsetH, windowOffsetV, bevel, yappCoordPCB]
displayMounts =
[
  // E-Ink viewing window locked to dead center with zero pins (glue/tape mount).
  [
    (totalLength - screenLength) / 2,  // Exact X bottom-left corner of the PCB shelf
    (totalWidth - screenWidth) / 2,    // Exact Y bottom-left corner of the PCB shelf
    screenLength, 
    screenWidth, 
    0,                                 // 0 inset stops YAPP from shifting coordinates
    0,                                 // 0 inset stops YAPP from shifting coordinates
    0,                                 // 0 diameter completely removes mounting posts
    0,                                 // 0 post overhang
    screenLipGap, 
    screenThickness, 
    screenActiveLength, 
    screenActiveWidth, 
    0, 
    0, 
    1.5, 
    yappCoordPCB                       // Measures relative to the PCB cavity (185x125), NOT the outer walls (189x129)
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
  [3.5 + 58, 3.5 + 49, undef, undef, undef, undef, undef, undef, undef, yappBaseOnly, [yappPCBName, "RaspberryPi"]],
  
  // Second Waveshare Standoff (Anchored directly to the "Waveshare2" PCB footprint)
  [3.5,               3.5,               undef, undef, undef, undef, undef, undef, undef, yappBaseOnly, [yappPCBName, "Waveshare2"]],
  [wave2Length - 3.5, 3.5,               undef, undef, undef, undef, undef, undef, undef, yappBaseOnly, [yappPCBName, "Waveshare2"]],
  [3.5,               wave2Width - 3.5,  undef, undef, undef, undef, undef, undef, undef, yappBaseOnly, [yappPCBName, "Waveshare2"]],
  [wave2Length - 3.5, wave2Width - 3.5,  undef, undef, undef, undef, undef, undef, undef, yappBaseOnly, [yappPCBName, "Waveshare2"]],
];

// ======================================================================
// 5. PORT & CABLE CUTOUTS
// ======================================================================
// Arguments are: [posX, posY, width_X, length_Y, corner_radius, shape, depth, angle, yappCoordBoxInside]
cutoutsFront = 
[
  // Panel Mount USB-C Port (Bottom of Front Wall, near Left Corner)
  // 16mm from Left Wall, 6mm from floor, 12mm wide x 7mm tall
  [ pcbWidth - 27, 6, 9, 4, 2, yappRoundedRect, 0, 0, yappCoordBoxInside ],

  // Splitflap Ribbon/Wire Slot (Stacked directly ABOVE USB-C on Front Wall)
  // 10mm from Left Wall, 21mm from floor (leaving an 8mm plastic bridge above USB-C), 25mm wide x 5mm tall
  [ pcbWidth - 35, 21, 25, 5, 2.5, yappRoundedRect, 0, 0, yappCoordBoxInside ],
  
  // RTL-SDR Coax / SMA Port Hole
  // The first number (175) slides it left/right along the 185mm wall. 
  // 17mm from the floor (23mm from the 40mm top)
  [ pcbWidth - 51, 16, 7, 7, 3.5, yappRoundedRect, 0, 0, yappCoordBoxInside ]
];
cutoutsBase = 
[
  // Front-Left Honeycomb Mesh Cutout
  // [posx, posy, width, length, radius, shape, depth, angle, mask, coordinate_system]
  [ 10, 30, 80, 30, 15, yappRoundedRect, 0, 0, maskHoneycomb, yappCoordBox ]
];
labelsPlane =
[
  // Bottom Floor Text Label
  // [posx, posy, rotation, depth, plane, font, size, "text"]
  // Depth > 0 cuts into the plastic. Depth of 2.0 cuts completely through.
  [ 108, pcbWidth - 44, 0, 2.0, yappBase, "Arial:style=Bold", 6.5, "Airspace Monitor" ]
];

// ======================================================================
// 6. 3D MODEL HOOKS
// ======================================================================
module hookBaseInside()
{
    // --------------------------------------------------------------------
    // 1. Imports RTL-SDR stand and slides it into open space to the above cutouts
    // --------------------------------------------------------------------
    translate([185, 57, 0]) 
    rotate([0, 0, 90]) 
    difference() {
        scale([1.08, 1.08, 1.08])
        import("dependencies/rtl-sdr-stand.stl");
        
        translate([-100, -100, 30]) 
        cube([200, 200, 100]);
    }
}

module hookLidInside()
{
    // ====================================================================
    // 1. Custom 3-Sided E-Ink Screen Retaining Bracket
    // ====================================================================
    lipWidth  = 1.5;
    topWidth  = 3.5;
    lipHeight = screenLipGap + screenThickness + 3.0; // Shelf + screen + 3mm retaining lip
    lipBuffer = 0.5;                                  // 0.5mm air gap for clean insertion

    // Calculate exact screen boundary edges
    leftEdge   = (totalLength - screenLength) / 2;
    rightEdge  = leftEdge + screenLength;
    bottomEdge = (totalWidth - screenWidth) / 2;
    topEdge    = bottomEdge - lipWidth;

    sideWallLength = screenWidth + (2 * lipBuffer) + lipWidth;
    topWallLength  = screenLength + (2 * lipBuffer) + (2 * lipWidth);

    // Extrude bracket from negative Z space UP to touch lid ceiling at Z=0
    translate([leftEdge - lipBuffer - lipWidth, bottomEdge - lipBuffer, -lipHeight])
        cube([lipWidth, sideWallLength, lipHeight]);

    translate([rightEdge + lipBuffer, bottomEdge - lipBuffer, -lipHeight])
        cube([lipWidth, sideWallLength, lipHeight]);

    translate([leftEdge - lipBuffer - lipWidth, topEdge + lipBuffer, -lipHeight])
        cube([topWallLength, topWidth, lipHeight]);
}

// ======================================================================
// 7. UNUSED YAPP ARRAYS & HOOKS
// Keep these to prevent compiler errors. Unused in this project.
// ======================================================================
connectors = []; snapJoins = []; boxMounts = []; lightTubes = []; 
pushButtons = []; cutoutsLid = [];  
cutoutsBack = []; cutoutsLeft = []; cutoutsRight = []; ridgeExtLeft = []; ridgeExtRight = []; 
ridgeExtFront = []; ridgeExtBack = [];

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
