//=======================================================================
// Airspace Monitor - Enclosure v2.9  ("picture frame")
//   Raspberry Pi 4  +  RTL-SDR Blog V4  +  Waveshare 7.3" e-Paper HAT (F)
//
//   Standalone OpenSCAD: no YAPP, no imported STLs.
//   Every board is held by heat-set inserts. The SMA hole is computed from
//   the same numbers as the SDR cradle, so the two can't drift apart.
//
//   v2.9  (new: shell, feet. Bezel, backer, port box, strap, clamps unchanged)
//     - Case 24.75 mm deeper for the stiff cables and the USB-A plug: the
//       backer sits at 55.45 instead of 30.7 (zBackerMin), so the case is
//       193 x 134 x 62.45.
//     - The corner screw holes get deeper with it, so the same M3x30
//       screws still reach the bezel (counterbore ~30.5 mm deep).
//     - Pi centred top to bottom on the left wall (piOffY = 0).
//     - Lowest slot of the vent above the Pi removed: it ran under the Pi's
//       top-right standoff once the Pi moved up. The other 5 slots stay.
//     - Desk feet grow to fit the deeper case.
//
//   v2.8  (new: io_box, backer. Shell and bezel unchanged)
//     - Port plate -> port box. The connectors sit in the end face of a box
//       that sticks out ioBoxH (20 mm) + the 3.6 mm end face from the back,
//       so their stiff bodies and cables have room to bend. Same two screws
//       into the shell's existing inserts.
//     - Driver HAT now sits on the Pi's GPIO header (hatOnBacker = false):
//       no HAT standoffs or inserts on the backer. Small-board rails and
//       clamps stay.
//     - Case depth held at the printed 37.7 (zBackerMin), so the v2.7 shell
//       and bezel still fit.
//
//   v2.7  (port plate only; case depth unchanged)
//     - Both connectors mount from inside: wings in pockets behind the
//       plate, port faces flush with the wings, plugs reach in through the
//       plate. USB-C wings 25.22 x 10.4, USB-A wings 38.64 x 11.25.
//     - USB-A hole is the measured port, 14.46 x 6.8; M3 holes 27.86 apart.
//     - Plate 3.6 thick with 1.2 in front of the wings (was 4.0 / 1.6), so
//       plugs go 0.4 mm further in. The wings sit where they did before.
//     - The two connectors are centred as a pair on the plate.
//
//   v2.5
//     - SMA nut goes on the OUTSIDE, in the 12 mm pocket on the outside of
//       the top wall. It pulls the end-plate screws snug against the inside
//       of the wall. (Replaces v2.4's nut pocket on the inside.)
//
//   v2.4  (after the first test print)
//     - Pi moved left until its left standoffs touch the left wall.
//     - microSD slot centred between the Pi's left standoffs, 20 -> 16 long.
//     - RTL-SDR is 70.75 long with its end-plate screws. The pads between
//       the SMA end and the top wall are gone: the SMA-end screws now sit
//       against the wall, and the USB-end stop moved to suit.
//
//   v2.3
//     - Port plate: the USB-C mounts from INSIDE. Its socket pokes through
//       the plate and its wings sit in a pocket behind it. Connector wings
//       are now held by M3 screws and nuts, no inserts or bosses.
//     - Port plate 2.4 -> 4.0 thick, so the USB-C's wings sit as far back
//       as before and the case stays 37.7 deep.
//     - SMA position measured: centred across the width, 2 mm from the back
//       face to the thread vs ~6 from the front. The hole is a 1 mm slot
//       front-to-back to absorb the rough reading.
//
//   v2.2  (caliper measurements)
//     - Window moved 2.5 mm down: the panel's ribbon-side border is 10 mm,
//       the other three are 5 mm.
//     - Copper ribbon 26.7 wide, 0.65 left of centre; small board 45.5 long;
//       SMA nut 1.8; winged USB-C is 9 x 3.3 with M3 wings 16.5 apart.
//     - The small board's float window is worked out from the copper
//       ribbon's free length (20.8 mm), so the board lands inside it.
//       The clamps moved up to clear the HAT's lower standoff.
//     - Case depth is also set by the longest port-plate connector
//       (ioBodyL). The USB-C needs 32.6 mm, so the case goes 35.5 -> 37.7.
//     - HAT standoffs 10 -> 11 mm so a socket-head clamp screw clears the
//       HAT (it had 0.5 mm).
//     - Insert holes sized for the kit inserts (#10 M3, #12 M2.5), plus an
//       insert test block (part = "insert_test") to dial the holes in.
//
//   v2.1
//     - Ribbon notch in the backer is open to the top edge, so the copper
//       ribbon (permanently bonded to the small board) can wrap round it.
//     - Small board between the copper and grey ribbons is clamped by two
//       screwed tabs; it can sit anywhere in an 8 mm window so the ribbon
//       decides the position, not the print.
//     - Port plate is its own part again, built for two WINGED panel-mount
//       connectors: wings on the outside, screws into heat-set inserts.
//     - Intake moved to slots in the bottom edge (the port plate took the
//       old intake spot).
//
//   STACK (back -> front)
//     shell   : Pi 4, RTL-SDR cradle, port plate, vents, 4 corner columns
//     backer  : clamps the panel; carries the driver HAT + small board
//     panel   : + ~1 mm foam between panel and backer
//     bezel   : window, panel pocket, corner insert bosses
//   4x M3 from the back run through the shell columns into the bezel;
//   the column tops also clamp the backer's corners.
//
//   COORDINATES (assembled): X right, Y up, Z toward the viewer, seen from
//   the FRONT. Origin = bottom-left corner of the rear face.
//   "inner" coordinates are measured from the inside faces of the walls.
//
//   PARTS - set `part`, render (F6), export STL. All fit a 256 mm bed.
//     shell        rear face on the bed, no supports
//     bezel        front face on the bed, no supports
//     backer       panel side on the bed, standoffs pointing up
//     io_box       ears on the bed; the end face bridges ~21 mm, no supports
//     small_parts  port box + SDR strap + 2 board clamps + 2 desk feet
//     insert_test  print this first: picks the insert hole sizes
//     assembly / exploded / on_stand   preview (F5); % ghosts = hardware
//
//   HARDWARE
//     Heat-set inserts from the kit, 4 mm long (#10 M3, #12 M2.5):
//       10x M3   4 bezel corners, 2 SDR strap, 2 board clamps,
//                2 port box -> shell
//        4x M2.5 Pi
//     Connector wings: the M3 screws that came with the connectors, + 4 nuts
//     4x M3x30 SHCS  shell -> bezel (heads sit ~30 mm down the corner
//                    holes: use the long arm of a 2.5 mm hex key)
//                                          2x M3x8    SDR strap
//     2x M3x8        board clamps          2x M3x8    port box -> shell
//     4x M2.5x6      Pi (or the HAT's own standoffs on the top two)
//     ~1 mm foam sheet behind the panel
//     Panel-mount connectors with screw wings (power USB-C + split-flap USB-A),
//     ideally with right-angle male ends; 10-15 cm USB-A extension for the SDR
//
//   MEASUREMENTS (search for "MEASURED")
//     Done: panel borders, copper ribbon, small board, SMA position and
//     nut, USB-C.
//     Still defaults: RTL-SDR body L/W/T, USB-A connector, Pi heights,
//     driver HAT, insert hole sizes (until the test block is done).
//
//   ASSEMBLY ORDER
//     1. Melt in all inserts.
//     2. Bezel face-down. Panel into the pocket with the small board hanging
//        past the top edge. Foam on the panel's back, clear of the ribbon.
//     3. Lower the backer, sliding the copper ribbon into the open notch.
//        Fold the small board over onto the backer, let it settle between
//        the rails where the ribbon lies flat, then screw down both clamps.
//     4. Shell: Pi with the HAT on its GPIO header; SDR with its SMA nut
//        removed, SMA through the top wall, nut back on from outside, then
//        the strap; connectors into the port box (nuts inside the box),
//        cables through the shell's window, box onto the shell; cables.
//     5. Grey ribbon from the small board into the HAT, close, 4x M3x30
//        from the back.
//=======================================================================

/* [Render] */
part = "shell"; // [assembly, exploded, on_stand, shell, bezel, backer, small_parts, io_box, sdr_strap, board_clamps, feet, insert_test]
show_hardware = true;  // ghost boards in the assembly views

/* [Shell] */
wall         = 2.4;  // side walls
floorT       = 2.0;  // rear face
cornerR      = 7.0;  // outer corner radius (keep == cornerInset so the corner bosses clear the walls)
backChamfer  = 0.6;  // rear edge (bed side, hides elephant's foot)
frontChamfer = 0.8;  // bezel front edge

/* [E-paper panel] */
panelW       = 170.2; // Waveshare 7.3" (F) outline
panelH       = 111.2;
panelT       = 0.91;
activeW      = 160.0;
activeH      = 96.0;
windowOffX   = 0;    // MEASURED: borders 5 left / 5 right. Active-area centre minus panel centre, + = right
windowOffY   = -2.5; // MEASURED: borders 10 top (ribbon side) / 5 bottom. + = up
windowMargin = 0.5;  // window larger than the active area by this much per side
panelClr     = 0.4;  // pocket clearance per side
pocketD      = 2.0;  // panel 0.91 + ~1 mm foam
fpcW         = 26.7;  // MEASURED: width of the copper ribbon
fpcOffX      = -0.65; // MEASURED: 71.1 from the glass's left edge. Ribbon centre minus panel centre, + = right
fpcFreeL     = 20.8;  // MEASURED: copper ribbon free length, glass edge to the small board
fpcSideClr   = 2.0;  // notch clearance each side of the ribbon

/* [Bezel and backer] */
border    = 11;   // pocket edge to outer edge
faceT     = 2.0;  // bezel thickness in front of the panel
backerT   = 3.0;
backerClr = 0.3;  // backer to shell inner wall

/* [Inserts and screws] */
// [hole dia, hole depth, boss dia]. Hole dia is a starting guess: print
// part = "insert_test" and put the winning sizes here. Depth stays 6.1 so
// the 4 mm inserts leave room for screw tips and screw lengths don't change.
insM3   = [3.6, 6.1, 7.2]; // kit #10: M3 x 4 long x 4.0 OD
insM25  = [3.1, 6.1, 7.2]; // kit #12: M2.5 x 4 long x 3.5 OD
m3Clr   = 3.4;
m3HeadD = 6.2;
cornerInset = 7.0;  // corner screw centres from the outer edges
colD        = 10;   // shell corner column
colFlangeD  = 12;   // column top flange (clamps the backer corners)
colFlangeH  = 3;
screwL      = 30;   // shell -> bezel screw length
screwEngage = 5;    // thread engaged in the bezel insert

/* [Seam] */
tongueOff = 1.2;  // tongue centreline from the outer edge
tongueW   = 1.0;
tongueH   = 1.2;
grooveW   = 1.5;
grooveD   = 1.5;

/* [Raspberry Pi 4] */
piL        = 85;
piW        = 56;
piPcbT     = 1.5;
piStandoff = 5.0;
piCompH    = 16.0;  // tallest part above the PCB (USB stack)
gpioWireH  = 20.0;  // jumper housings + wire bend above the PCB (~17.5 with right-angle jumpers)
topClr     = 1.5;   // Pi parts to backer
piHoles    = [[3.5, 3.5], [61.5, 3.5], [3.5, 52.5], [61.5, 52.5]];
piWallGap  = 0;     // left standoffs to the left wall (0 = touching)
piOffY     = 0;     // Pi is centred top to bottom on the left wall; + moves it up (piPos is worked out below)
piSdSlot    = true;  // fingernail slot in the left wall for the microSD
piSdCenterY = 28;    // MEASURED: midway between the left standoffs, above the Pi's bottom edge
piSdW       = 16;    // slot length along the wall

/* [Driver HAT] */
hatOnBacker = false;  // false: the HAT sits on the Pi's GPIO header (v2.8). true: on standoffs on the backer
hatL        = 65;
hatW        = 30.5;
hatPos      = [3.6, 87.0];  // inner coords, bottom-left corner
hatHoles    = [[3.5, 3.5], [61.5, 3.5], [3.5, 26.5], [61.5, 26.5]];
hatStandoff = 11;  // clears the 2x20 female header (~8.5 mm) facing the backer, and a socket-head clamp screw by 1.5 mm

/* [Small board between the ribbons (on the backer)] */
adL        = 45.5; // MEASURED
adW        = 21;   // MEASURED
adT        = 1.6;  // PCB thickness
adFloat    = 8;    // the board can sit anywhere in a window this tall
adLowClr   = 1.0;  // window reaches this far below the lowest the ribbon can put the board
adClr      = 0.3;
adRailW    = 1.2;
adRailH    = 1.2;  // lower than the PCB so only the clamp fingers touch it
adBossH    = 4.0;  // clamp boss height off the backer (M3 insert)
adClampT   = 2.5;
adClampW   = 8;
adClampLap = 2.0;  // how far each finger reaches onto the board's short edge

/* [RTL-SDR Blog V4] */
sdrL         = 69;    // end plate to end plate, screws not included
sdrLtot      = 70.75; // MEASURED: end to end including the end-plate screw heads
sdrW         = 27;    // MEASURE
sdrT         = 13;    // MEASURE
sdrClr       = 0.3;
sdrCx        = 163;   // inner X of the dongle centreline (vertical, SMA up)
sdrSmaNutT   = 1.8;   // MEASURED: SMA nut thickness (it goes on the outside of the top wall)
sdrEndClr    = 0.2;   // USB-end screws to the stop (the SMA-end screws touch the top wall)
sdrLift      = 1.2;   // air gap under the dongle
sdrRailH     = 7;
sdrRailW     = 2.0;
sdrStopT     = 2.0;
sdrUsbNotchW = 15;
sdrSmaOffX   = 0;    // MEASURED: centred. SMA centre minus body centre across the width, + = right
// Across the thickness, the SMA sits nearer one face. Put that face toward
// the case's rear wall. The offset is (back gap - front gap) / 2, which
// doesn't depend on the body thickness or the thread size.
sdrSmaGapBack  = 2.0;  // MEASURED: back face (toward the rear wall) to the near edge of the thread
sdrSmaGapFront = 6.0;  // MEASURED (rough): front face to the near edge of the thread
sdrSmaLen    = 9.0;  // SMA length past the end plate (nut included)
smaThreadD   = 6.35; // 1/4-36 SMA thread
smaHoleD     = 7.0;
smaSlotZ     = 1.0;  // hole stretched this much front-to-back for the rough reading
smaCbD       = 12;   // pocket on the outside of the top wall for the SMA nut
smaCbDepth   = 1.2;
strapT       = 3;
strapW       = 10;

/* [Port box (rear)] */
ioSize     = [97, 26];   // footprint on the shell, ears included
ioBoxW     = 81;         // box width; the ear screws sit just outside it
ioBoxH     = 20;         // how far the box sticks out, not counting the end face
ioBoxWall  = 2.4;
ioEarT     = 3;          // ears for the two shell screws
ioT        = 3.6;        // end face thickness
ioFaceT    = 1.2;        // end face left in front of wings that sit behind it (plugs reach through this much)
ioCenter   = [90, 17];   // inner coords
ioScrewX   = 44.5;       // box -> shell screws (the shell's existing inserts)
ioWindow   = [80, 18];   // opening in the shell behind the plate
ioBodyClr  = 0.5;        // connector body/cable to the backer plate
// Every connector is held by M3 screws through its wing holes, nuts inside.
// [x, y, [cutout w, h, corner r], wing hole spacing (0 = none),
//  wing pocket [w, h] ([] = wings on the plate's outer face),
//  body length behind the wings incl. cable bend, label]
// Wing pockets = measured wings + 0.3 per side. The two connectors are
// centred as a pair on the plate.
ioPorts = [
    // USB-C (power). MEASURED: port 9 x 3.3, wings 25.22 x 10.4, holes 16.5 apart
    [-23, 0, [ 9.6,  3.9, 1.9], 16.5,  [25.9, 11.0], 32.6, "5V"],
    // USB-A (split-flap). MEASURED: port 14.46 x 6.8 (hole is exactly that),
    // wings 38.64 x 11.25, holes 27.86 apart. Body length not measured (30 assumed)
    [ 17, 0, [14.46, 6.8, 1.0], 27.86, [39.3, 11.9], 30,   "FLAP"]
];

/* [Vents and label] */
slotT     = 2.0;
slotPitch = 4.2;
vents = [                 // inner [x, y, w, h], rear face
    [ 20,  4, 20, 22],    // under the Pi, left of the port box
    [  8, 94.2, 58, 19.8],// exhaust above the Pi: 5 slots. v2.9 drops its lowest slot (y 90),
                          // which ran under the Pi's top-right standoff once the Pi was centred
    [118, 72, 20, 46],    // exhaust, middle
    [156, 64, 14, 58]     // under the RTL-SDR
];
bottomSlotX = [40, 148];  // inner X range of intake slots in the bottom edge
bottomSlotZ = 6;
bottomSlotH = 14;
labelText  = "AIRSPACE MONITOR";
labelFont  = "Liberation Sans:style=Bold";
labelSize  = 4.5;
labelDepth = 0.6;
labelY     = 123.5;  // inner

/* [Desk feet] */
tilt           = 15;
footW          = 24;
footD          = 70;
footLipT       = 4;
footFloor      = 3;
footFrontCover = 8;
footBackCover  = 40;
footBackT      = 5;
footClr        = 0.4;
footInsetX     = 10;

/* [Insert test block] */
insTestM3  = [3.4, 3.5, 3.6, 3.7, 3.8];  // hole sizes to try for the #10 M3 inserts
insTestM25 = [2.9, 3.0, 3.1, 3.2, 3.3];  // ... and the #12 M2.5 inserts

/* [Hidden] */
$fa = 4;
$fs = 0.4;
e   = 0.01;

//-----------------------------------------------------------------------
// Derived values
//-----------------------------------------------------------------------
pocketW = panelW + 2*panelClr;
pocketH = panelH + 2*panelClr;
W       = pocketW + 2*border;
H       = pocketH + 2*border;
innerW  = W - 2*wall;
innerH  = H - 2*wall;

// Pi: left standoffs touch the left wall, centred top to bottom (inner
// coords of the Pi's bottom-left corner, GPIO along the top)
piPos   = [insM25[2]/2 - piHoles[0][0] + piWallGap, (innerH - piW)/2 + piOffY];

bezelT      = faceT + pocketD;
zStack      = floorT + piStandoff + piPcbT + max(piCompH + topClr, gpioWireH); // what the Pi needs
// port connectors: the wings sit on the end face's outer side
// (z = -ioBoxH - ioT) or in a pocket behind it (ioFaceT further in); the
// body runs from there toward the backer
zPorts      = max([for (p = ioPorts) (len(p[4]) > 0 ? ioFaceT : 0) - ioT - ioBoxH + p[5]]) + ioBodyClr;
zBackerMin  = 30.7 + 24.75;  // MEASURED (v2.9): 24.75 more room behind the backer for the stiff cables and USB-A plug
zBackerBack = max(zStack, zPorts, zBackerMin);
zBezelBack  = zBackerBack + backerT;   // top of the shell walls
D           = zBezelBack + bezelT;     // overall depth
zPanelFront = D - faceT;
cbDepth     = zBackerBack + screwEngage - screwL;

panelCx    = W/2;
panelCy    = H/2;
pocketTopY = border + pocketH;
fpcCx      = panelCx + fpcOffX;
fpcY0      = pocketTopY - 0.5;          // bottom of the ribbon notch
fpcCutW    = fpcW + 2*fpcSideClr;
backerTopY = H - wall - backerClr;

corners      = [[cornerInset, cornerInset], [W - cornerInset, cornerInset],
                [cornerInset, H - cornerInset], [W - cornerInset, H - cornerInset]];
outerCorners = [[0, 0], [W, 0], [0, H], [W, H]];

hatRightYs = [wall + hatPos[1] + hatHoles[1][1], wall + hatPos[1] + hatHoles[3][1]];

// Small board (global coords). The copper ribbon leaves the glass's top
// edge, U-turns round the backer and runs down its rear face. The tightest
// U-turn (a half circle) uses the least ribbon, so that's where the board
// sits lowest; a looser turn lifts it. The float window starts just under
// that lowest point and reaches adFloat above it.
glassTopY = border + panelClr + panelH;
fpcTurn   = PI * (zPanelFront - panelT - zBackerBack) / 2;
adYlow    = glassTopY - (fpcFreeL - fpcTurn);               // board top edge, tightest wrap
adY1      = min(fpcY0 - 1.5, adYlow - adLowClr + adFloat);  // highest position (top edge)
adY0      = adY1 - adW;
adX0      = fpcCx - adL/2;
adClampD  = adClr + adRailW + insM3[2]/2 - 0.5;             // boss centre to board edge
adClampYmid = (adY0 + adY1)/2 - adFloat/2;                  // centred on the float range
adClampYmin = hatRightYs[0] + insM25[2]/2 + adClampW/2 + 1.0; // clear of the HAT's lower-right standoff
adClampY  = hatOnBacker ? max(adClampYmid, adClampYmin) : adClampYmid;
adClampX  = [adX0 - adClampD, adX0 + adL + adClampD];
adZseat   = zBackerBack - adBossH;                          // clamp seats on the boss ends

// RTL-SDR (inner coords). The SMA-end screw heads sit against the top wall.
sdrScrewH  = (sdrLtot - sdrL) / 2;              // screw heads past each end plate
sdrY1      = innerH - sdrScrewH;                // SMA-end plate
sdrY0      = sdrY1 - sdrL;                      // USB-end plate
sdrChL     = sdrCx - sdrW/2 - sdrClr;
sdrChR     = sdrCx + sdrW/2 + sdrClr;
sdrZ0      = floorT + sdrLift;
sdrZc      = sdrZ0 + sdrT/2;
sdrStopY   = sdrY0 - sdrScrewH - sdrEndClr - sdrStopT;
strapZ     = sdrZ0 + sdrT + 0.3;
strapY     = (sdrY0 + sdrY1)/2;
strapBossX = [sdrChL - sdrRailW - insM3[2]/2 + 0.5, sdrChR + sdrRailW + insM3[2]/2 - 0.5];
sdrSmaOffZ = (sdrSmaGapBack - sdrSmaGapFront) / 2;   // + = toward the front
smaX       = wall + sdrCx + sdrSmaOffX;          // global
smaZ       = sdrZc + sdrSmaOffZ;
// thread left for the antenna cable: past the end plate, minus the screw
// gap, the wall under the outside pocket, and the SMA nut sitting in it
smaFree    = sdrSmaLen - sdrScrewH - (wall - smaCbDepth) - sdrSmaNutT;

// lowest point of the port box above the desk when the case is on its feet
ioBoxLow = footFloor + (wall + ioCenter[1] - ioSize[1]/2)*cos(tilt) - (ioBoxH + ioT)*sin(tilt);

echo(str("Airspace Monitor v2.9: ", W, " x ", H, " x ", D, " mm, port box sticks out ", ioBoxH + ioT, " mm"));
echo(str("Depth set by: ", zBackerBack == zBackerMin ? "zBackerMin (room for the cables)"
                          : zBackerBack == zPorts ? "a port connector's body length" : "the Pi stack"));
echo(str("Port box clears the desk by ", ioBoxLow, " mm on the feet"));
sdrTimplied = sdrSmaGapBack + smaThreadD + sdrSmaGapFront;
if (abs(sdrTimplied - sdrT) > 0.5)
    echo(str("CHECK: the SMA gaps add up to a ", sdrTimplied, " mm thick body but sdrT is ", sdrT,
             " - measure the body thickness"));
echo(str("Small board top edge: ", adYlow, " with the tightest ribbon wrap; float window ",
         adY1 - adFloat, " to ", adY1));
echo(str("Shell->bezel: 4x M3x", screwL, " SHCS, counterbore dia ", m3HeadD, " x ", cbDepth, " mm deep"));
echo(str("SMA thread free for the coax nut: ", smaFree, " mm (want >= 4)"));
echo(str("Port connectors need the backer at z >= ", zPorts, " mm; it is at ", zBackerBack, " mm"));

assert(cbDepth >= 2, "screwL too long for the corner columns");
assert(sdrStopY > 2, "RTL-SDR too long for the shell");
assert(wall - smaCbDepth >= 0.8, "SMA nut pocket leaves the top wall too thin");
assert(!hatOnBacker || wall + hatPos[0] + hatHoles[1][0] + insM25[2]/2 < adX0 - adClr - adRailW,
       "HAT standoffs collide with the small board's rails");
assert(!hatOnBacker || min([for (y = hatRightYs) abs(y - adClampY)]) > insM25[2]/2 + adClampW/2 + 0.5,
       "Left board clamp collides with a HAT standoff - adjust hatPos or adFloat");
assert(ioBoxLow > 1, "Port box would touch the desk on the feet - make ioBoxH smaller");
assert(ioBoxW/2 + 3 <= ioScrewX, "Port box too wide: the ear screws need room beside it");
assert(adClampY + adClampW/2 <= adY1 - adFloat + e && adClampY - adClampW/2 >= adY0 - e,
       "Board clamps can't reach the small board over its whole float window");
assert(adYlow <= adY1 - 2, "Copper ribbon too short: the small board would sit above its float window");
assert(!hatOnBacker || piPos[1] + piW < hatPos[1] + hatHoles[0][1] - insM25[2]/2,
       "Pi overlaps the HAT standoffs");
assert(ioFaceT >= 1.2 && ioFaceT < ioT, "ioFaceT must be at least 1.2 and less than ioT");

//-----------------------------------------------------------------------
// Helpers
//-----------------------------------------------------------------------
module rrect(size, r) {
    rr = min(r, min(size[0], size[1])/2 - e);
    offset(r = rr) offset(delta = -rr) square(size);
}

module rrectC(size, r) translate(-size/2) rrect(size, r);

module outline(inset = 0)
    translate([inset, inset]) rrect([W - 2*inset, H - 2*inset], max(cornerR - inset, 0.5));

module ring(inset, width)
    difference() { outline(inset - width/2); outline(inset + width/2); }

module at_inner(p) translate([wall + p[0], wall + p[1], 0]) children();

module boss(d, h, chamfer = 0) {
    cylinder(d = d, h = h - chamfer);
    if (chamfer > 0)
        translate([0, 0, h - chamfer - e]) cylinder(d1 = d, d2 = d - 2*chamfer, h = chamfer + e);
}

// Insert hole with a lead-in chamfer. Opening at height z; the hole runs
// down from z (default) or up from z (up = true).
module insert_hole(ins, z, up = false) {
    if (up) {
        translate([0, 0, z - e]) cylinder(d = ins[0], h = ins[1] + e);
        translate([0, 0, z - e]) cylinder(d1 = ins[0] + 1, d2 = ins[0], h = 0.5 + e);
    } else {
        translate([0, 0, z - ins[1]]) cylinder(d = ins[0], h = ins[1] + e);
        translate([0, 0, z - 0.5]) cylinder(d1 = ins[0], d2 = ins[0] + 1, h = 0.5 + e);
    }
}

module vent_slots(w, h) {
    n = floor((h - slotT) / slotPitch) + 1;
    for (i = [0 : n - 1])
        translate([0, i*slotPitch, -e]) linear_extrude(floorT + 2*e) rrect([w, slotT], slotT/2);
}

//-----------------------------------------------------------------------
// Rear shell
//-----------------------------------------------------------------------
module shell_body() {
    hull() {
        linear_extrude(backChamfer + e) outline(backChamfer);
        translate([0, 0, backChamfer]) linear_extrude(zBezelBack - backChamfer) outline(0);
    }
    translate([0, 0, zBezelBack - e]) linear_extrude(tongueH + e) ring(tongueOff, tongueW);
}

module shell_columns() {
    for (c = corners) translate([c[0], c[1], floorT - e]) {
        cylinder(d = colD, h = zBackerBack - floorT + e);
        // 45 deg lead-in so the flange isn't a flat overhang
        translate([0, 0, zBackerBack - floorT - colFlangeH - 1 + e])
            cylinder(d1 = colD, d2 = colFlangeD, h = 1 + e);
        translate([0, 0, zBackerBack - floorT - colFlangeH + e])
            cylinder(d = colFlangeD, h = colFlangeH);
    }
}

module pi_bosses() {
    for (h = piHoles)
        at_inner([piPos[0] + h[0], piPos[1] + h[1]])
            translate([0, 0, floorT - e]) boss(insM25[2], piStandoff + e, 0.6);
}

module sdr_cradle() {
    railTop = sdrLift + sdrRailH;
    translate([wall, wall, floorT - e]) {
        // lift strips under the body (air gap + flat datum)
        for (x = [sdrChL + 1, sdrChR - 5])
            translate([x, sdrY0, 0]) cube([4, sdrL, sdrLift + e]);
        // side rails, running into the top wall
        for (x = [sdrChL - sdrRailW, sdrChR])
            translate([x, sdrStopY, 0]) cube([sdrRailW, innerH - sdrStopY + e, railTop + e]);
        // (no pads at the SMA end: the end-plate screws sit against the top wall)
        // USB-end stop with a notch for the plug
        difference() {
            translate([sdrChL - sdrRailW, sdrStopY, 0])
                cube([sdrChR - sdrChL + 2*sdrRailW, sdrStopT, railTop + e]);
            translate([sdrCx - sdrUsbNotchW/2, sdrStopY - 1, sdrLift + 1.5])
                cube([sdrUsbNotchW, sdrStopT + 2, railTop]);
        }
        // strap bosses
        for (x = strapBossX)
            translate([x, strapY, 0]) cylinder(d = insM3[2], h = strapZ - floorT + e);
    }
}

module io_bosses() {
    for (s = [-1, 1])
        at_inner([ioCenter[0] + s*ioScrewX, ioCenter[1]])
            translate([0, 0, floorT - e]) cylinder(d = insM3[2], h = insM3[1] + 1.0 - floorT + e);
}

module shell_cuts() {
    // corner screws: through-hole + counterbore from the back
    for (c = corners) translate([c[0], c[1], 0]) {
        translate([0, 0, -e]) cylinder(d = m3Clr, h = zBezelBack + 5);
        translate([0, 0, -e]) cylinder(d = m3HeadD, h = cbDepth + e);
    }
    // Pi inserts
    for (h = piHoles)
        at_inner([piPos[0] + h[0], piPos[1] + h[1]]) insert_hole(insM25, floorT + piStandoff);
    // SDR strap inserts
    for (x = strapBossX) at_inner([x, strapY]) insert_hole(insM3, strapZ);
    // SMA through the top wall (slotted front-to-back)
    hull() for (dz = [-smaSlotZ/2, smaSlotZ/2])
        translate([smaX, H - wall - 1, smaZ + dz]) rotate([-90, 0, 0]) cylinder(d = smaHoleD, h = wall + 2);
    // pocket on the outside for the SMA nut
    if (smaCbDepth > 0)
        translate([smaX, H - smaCbDepth, smaZ]) rotate([-90, 0, 0]) cylinder(d = smaCbD, h = smaCbDepth + 1);
    // port plate window + its inserts (installed from outside)
    at_inner(ioCenter) translate([0, 0, -e]) linear_extrude(floorT + 2*e) rrectC(ioWindow, 2);
    for (s = [-1, 1])
        at_inner([ioCenter[0] + s*ioScrewX, ioCenter[1]]) insert_hole(insM3, 0, up = true);
    // rear vents
    for (v = vents) at_inner([v[0], v[1]]) vent_slots(v[2], v[3]);
    // intake slots in the bottom edge (vertical in the print, 2 mm bridges)
    for (x = [bottomSlotX[0] : slotPitch : bottomSlotX[1]])
        translate([wall + x, wall + e, bottomSlotZ]) rotate([90, 0, 0])
            linear_extrude(wall + 2*e) rrect([slotT, bottomSlotH], slotT/2);
    // microSD access in the left wall
    if (piSdSlot)
        translate([-e, wall + piPos[1] + piSdCenterY - piSdW/2, floorT + 1.5])
            cube([wall + 2*e, piSdW, 5]);
    // engraved label, mirrored so it reads from behind
    if (labelText != "")
        at_inner([W/2 - wall, labelY]) translate([0, 0, -e]) mirror([1, 0, 0])
            linear_extrude(labelDepth + e)
                text(labelText, size = labelSize, font = labelFont, halign = "center", valign = "center");
}

module shell() {
    difference() {
        union() {
            difference() {
                shell_body();
                translate([0, 0, floorT]) linear_extrude(zBezelBack + 10) outline(wall);
            }
            shell_columns();
            pi_bosses();
            sdr_cradle();
            io_bosses();
        }
        shell_cuts();
    }
}

//-----------------------------------------------------------------------
// Bezel
//-----------------------------------------------------------------------
module window_cut() {
    ww = activeW + 2*windowMargin;
    wh = activeH + 2*windowMargin;
    // 45 deg viewing chamfer: active size at the panel, +faceT per side at the front
    translate([panelCx + windowOffX, panelCy + windowOffY, 0]) hull() {
        translate([0, 0, zPanelFront - e]) linear_extrude(e) rrectC([ww, wh], 0.6);
        translate([0, 0, D]) linear_extrude(2*e) rrectC([ww + 2*faceT, wh + 2*faceT], 0.6 + faceT);
    }
}

module bezel() {
    difference() {
        union() {
            hull() {
                translate([0, 0, zBezelBack]) linear_extrude(bezelT - frontChamfer) outline(0);
                translate([0, 0, D - frontChamfer - e]) linear_extrude(frontChamfer + e) outline(frontChamfer);
            }
            // corner bosses reach back through the backer plane
            for (c = corners)
                translate([c[0], c[1], zBackerBack]) cylinder(d = insM3[2], h = backerT + e);
        }
        window_cut();
        // panel pocket
        translate([border, border, zBezelBack - e]) cube([pocketW, pocketH, pocketD + e]);
        // room for the ribbon's U-turn above the panel's top edge
        translate([fpcCx - fpcCutW/2, fpcY0, zBezelBack - e])
            cube([fpcCutW, backerTopY - fpcY0, pocketD + e]);
        // seam groove
        translate([0, 0, zBezelBack - e]) linear_extrude(grooveD + e) ring(tongueOff, grooveW);
        // corner inserts
        for (c = corners) translate([c[0], c[1], 0]) insert_hole(insM3, zBackerBack, up = true);
    }
}

//-----------------------------------------------------------------------
// Backer plate (display module: HAT + small board)
//-----------------------------------------------------------------------
module small_board_mount() {
    railY0 = adY0 - adFloat - adClr;
    railY1 = fpcY0 - 1.0;
    // side rails at the board's short ends; open top and bottom so it can slide in Y
    for (x = [adX0 - adClr - adRailW, adX0 + adL + adClr])
        translate([x, railY0, zBackerBack - adRailH]) cube([adRailW, railY1 - railY0, adRailH + e]);
    // clamp bosses
    for (x = adClampX)
        translate([x, adClampY, adZseat]) cylinder(d = insM3[2], h = adBossH + e);
}

module backer() {
    difference() {
        union() {
            translate([0, 0, zBackerBack]) linear_extrude(backerT) outline(wall + backerClr);
            // HAT standoffs (point toward the back), only if the HAT isn't on the Pi
            if (hatOnBacker) for (h = hatHoles)
                at_inner([hatPos[0] + h[0], hatPos[1] + h[1]])
                    translate([0, 0, zBackerBack - hatStandoff]) cylinder(d = insM25[2], h = hatStandoff + e);
            small_board_mount();
        }
        // clear the bezel's corner bosses and drop the thin corner slivers
        for (i = [0 : 3]) hull() {
            translate([corners[i][0], corners[i][1], zBackerBack - 1])
                cylinder(d = insM3[2] + 0.6, h = backerT + 2);
            translate([outerCorners[i][0] - 1, outerCorners[i][1] - 1, zBackerBack - 1])
                cube([2, 2, backerT + 2]);
        }
        // ribbon notch, open to the top edge so the ribbon can wrap round the plate
        translate([fpcCx - fpcCutW/2, fpcY0, zBackerBack - 1]) cube([fpcCutW, H, backerT + 2]);
        // bend relief where the ribbon turns onto the rear face
        translate([fpcCx - fpcCutW/2, fpcY0, zBackerBack]) hull() {
            translate([0, -1.5, -e]) cube([fpcCutW, 1.5 + e, e]);
            translate([0, -e, -e]) cube([fpcCutW, e, 1.5 + e]);
        }
        // HAT inserts (from the standoff tips)
        if (hatOnBacker) for (h = hatHoles)
            at_inner([hatPos[0] + h[0], hatPos[1] + h[1]])
                insert_hole(insM25, zBackerBack - hatStandoff, up = true);
        // small-board clamp inserts
        for (x = adClampX) translate([x, adClampY, 0]) insert_hole(insM3, adZseat, up = true);
    }
}

//-----------------------------------------------------------------------
// Small parts
//-----------------------------------------------------------------------
module sdr_strap() {
    span = strapBossX[1] - strapBossX[0];
    difference() {
        linear_extrude(strapT) rrectC([span + insM3[2], strapW], 2);
        for (s = [-1, 1]) translate([s*span/2, 0, -e]) cylinder(d = m3Clr, h = strapT + 2*e);
    }
}

// Board clamp. Local: screw at the origin, +x toward the board, plate on
// the bed, finger pointing up (it points at the backer when fitted).
module board_clamp() {
    reach = adClampD + adClampLap;
    difference() {
        union() {
            hull() {
                cylinder(d = insM3[2], h = adClampT);
                translate([reach - 1, -adClampW/2, 0]) cube([1, adClampW, adClampT]);
            }
            translate([adClampD - 0.5, -adClampW/2, adClampT - e])
                cube([adClampLap + 0.5, adClampW, adBossH - adT + e]);
        }
        translate([0, 0, -e]) cylinder(d = m3Clr, h = adClampT + 2*e);
    }
}

// Port box. Sticks out ioBoxH from the shell's rear face with the
// connectors in its end face, so their stiff bodies and cables have room
// to bend before they pass through the shell's window. Each connector is
// held by M3 screws through its wing holes, nuts inside the box. Wings sit
// on the end face's outer side (pocket = []) or in a pocket behind it that
// leaves ioFaceT in front; the plug reaches through that to the port.
// Local: ears (shell side) on the bed at z = 0, end face on top. It is
// seen from behind, so local x is global x flipped and the labels read
// right from outside. No supports: the end face bridges the box (~21 mm).
module io_box() {
    zTop  = ioBoxH + ioT;                                   // outer face of the end face
    inner = [ioBoxW - 2*ioBoxWall, ioSize[1] - 2*ioBoxWall];
    difference() {
        union() {
            linear_extrude(ioEarT) rrectC(ioSize, 3);             // ears
            linear_extrude(zTop) rrectC([ioBoxW, ioSize[1]], 3);  // box + end face
        }
        // hollow, open toward the shell
        translate([0, 0, -e]) linear_extrude(ioBoxH + e) rrectC(inner, 1);
        for (p = ioPorts) {
            x = -p[0];   // seen from behind
            // port / body cutout
            translate([x, p[1], ioBoxH - e]) linear_extrude(ioT + 2*e) rrectC([p[2][0], p[2][1]], p[2][2]);
            // pocket for wings that sit behind the end face
            if (len(p[4]) > 0)
                translate([x, p[1], ioBoxH - e]) linear_extrude(ioT - ioFaceT + e) rrectC(p[4], 1);
            // wing screws: clearance holes, nuts inside the box
            if (p[3] > 0) for (s = [-1, 1])
                translate([x + s*p[3]/2, p[1], ioBoxH - e]) cylinder(d = m3Clr, h = ioT + 2*e);
            // label near the top edge
            if (p[6] != "")
                translate([x, ioSize[1]/2 - 1.8, zTop - 0.4]) linear_extrude(0.4 + e)
                    text(p[6], size = 2.6, font = labelFont, halign = "center", valign = "top");
        }
        // box -> shell screws through the ears
        for (s = [-1, 1]) translate([s*ioScrewX, 0, -e]) cylinder(d = m3Clr, h = ioEarT + 2*e);
    }
}

// Desk foot: side profile extruded footW. Prints flat on its side.
// Profile coords: x = depth (front of foot at 0, toward the back), y = up.
module foot() {
    Ds = D + footClr;
    s  = sin(tilt);
    c  = cos(tilt);
    zf = footFloor + Ds*s;
    Pf = [footLipT, zf];                                   // frame front-bottom edge
    Pb = [footLipT + Ds*c, footFloor];                     // frame back-bottom edge
    Pl = [Pf[0] + footFrontCover*s, Pf[1] + footFrontCover*c];
    Pt = [Pb[0] + footBackCover*s, Pb[1] + footBackCover*c];
    Q  = [Pt[0] + footBackT*c, Pt[1] - footBackT*s];
    fd = max(footD, Q[0] + 3);                             // base reaches past the back support
    linear_extrude(footW)
        polygon([[0, 0], [fd, 0], [fd, 3], Q, Pt, Pb, Pf, Pl, [0, Pl[1]]]);
}

// Insert test block: a row of M3 holes and a row of M2.5 holes, each a
// little bigger than the last, the same depth and lead-in as the real ones.
// Print top face up. Melt an insert into each hole and keep the smallest
// hole where the insert goes in straight and flush, plastic doesn't bulge
// over the rim, and it doesn't spin when you drive a screw in hard.
// Put that size into insM3[0] / insM25[0].
function dec1(d) = str(floor(d), ".", round((d - floor(d)) * 10));

module insert_test() {
    pitch = 10;
    n     = max(len(insTestM3), len(insTestM25));
    sz    = [n*pitch + 2, 30, max(insM3[1], insM25[1]) + 2];
    rows  = [[insTestM3, insM3[1], 22], [insTestM25, insM25[1], 9]];  // [sizes, depth, row y]
    difference() {
        cube(sz);
        for (r = rows) for (i = [0 : len(r[0]) - 1]) {
            x = 1 + pitch/2 + i*pitch;
            translate([x, r[2], 0]) insert_hole([r[0][i], r[1], 0], sz[2]);
            translate([x, r[2] - 6, sz[2] - 0.4]) linear_extrude(0.4 + e)
                text(dec1(r[0][i]), size = 2.2, font = labelFont, halign = "center", valign = "center");
        }
    }
}

//-----------------------------------------------------------------------
// Previews
//-----------------------------------------------------------------------
module strap_in_place()
    translate([wall + (strapBossX[0] + strapBossX[1])/2, wall + strapY, strapZ]) sdr_strap();

module io_in_place()
    translate([wall + ioCenter[0], wall + ioCenter[1], 0]) rotate([0, 180, 0]) io_box();

module clamps_in_place()
    for (i = [0 : 1])
        translate([adClampX[i], adClampY, adZseat - adClampT]) rotate([0, 0, i == 0 ? 0 : 180]) board_clamp();

module hardware_ghosts() {
    // Pi 4: PCB, rough USB/Ethernet block, and either the HAT on its GPIO
    // header or the GPIO jumper envelope
    %translate([wall + piPos[0], wall + piPos[1], floorT + piStandoff]) {
        cube([piL, piW, piPcbT]);
        translate([piL - 21, 2, piPcbT]) cube([23.5, 52, piCompH]);
        if (hatOnBacker) translate([7, piW - 6, piPcbT]) cube([51, 5, gpioWireH]);
        else translate([0, piW - hatW, piPcbT + 11]) cube([hatL, hatW, 1.6]);
    }
    // RTL-SDR body + SMA
    %translate([wall + sdrCx - sdrW/2, wall + sdrY0, sdrZ0]) cube([sdrW, sdrL, sdrT]);
    %translate([smaX, wall + sdrY1, smaZ]) rotate([-90, 0, 0]) cylinder(d = 6.35, h = sdrSmaLen);
    // panel
    %translate([border + panelClr, border + panelClr, zPanelFront - panelT]) cube([panelW, panelH, panelT]);
    // driver HAT on the backer (header toward the backer)
    if (hatOnBacker)
        %translate([wall + hatPos[0], wall + hatPos[1], zBackerBack - hatStandoff - 1.6]) cube([hatL, hatW, 1.6]);
    // small board, highest and lowest positions
    %translate([adX0, adY0, zBackerBack - adT]) cube([adL, adW, adT]);
    %translate([adX0, adY0 - adFloat, zBackerBack - adT]) cube([adL, adW, adT]);
}

module assembled() {
    color("SlateGray") shell();
    color("Tan")       backer();
    color("DimGray")   bezel();
    color("Silver")    strap_in_place();
    color("Silver")    io_in_place();
    color("Silver")    clamps_in_place();
    if (show_hardware) hardware_ghosts();
}

module exploded() {
    color("SlateGray") shell();
    color("Silver")    translate([0, 0, 15]) strap_in_place();
    color("Silver")    translate([0, 0, -20]) io_in_place();
    color("Silver")    translate([0, 0, 25]) clamps_in_place();
    color("Tan")       translate([0, 0, 40]) backer();
    color("DimGray")   translate([0, 0, 70]) bezel();
    if (show_hardware) hardware_ghosts();
}

module on_stand() {
    rotate([-tilt, 0, 0]) assembled();
    Ds = D + footClr;
    for (x0 = [footInsetX, W - footInsetX - footW])
        color("Gray") translate([x0, -footFloor, footLipT + Ds*cos(tilt)]) rotate([0, 90, 0]) foot();
}

//-----------------------------------------------------------------------
// Output
//-----------------------------------------------------------------------
if (part == "assembly")          assembled();
else if (part == "exploded")     exploded();
else if (part == "on_stand")     on_stand();
else if (part == "shell")        shell();
else if (part == "bezel")        translate([W, 0, D]) rotate([0, 180, 0]) bezel();
else if (part == "backer")       translate([W, 0, zBezelBack]) rotate([0, 180, 0]) backer();
else if (part == "io_box")       io_box();
else if (part == "sdr_strap")    sdr_strap();
else if (part == "board_clamps") { board_clamp(); translate([0, 15, 0]) board_clamp(); }
else if (part == "feet")         { foot(); translate([0, 50, 0]) foot(); }
else if (part == "insert_test")  insert_test();
else if (part == "small_parts") {
    io_box();
    translate([0, 25, 0]) sdr_strap();
    translate([-30, 40, 0]) board_clamp();
    translate([-10, 40, 0]) board_clamp();
    translate([-90, 55, 0]) foot();
    translate([0, 55, 0]) foot();
}
