//=======================================================================
// Airspace Monitor - Enclosure v2  ("picture frame")
//   Raspberry Pi 4  +  RTL-SDR Blog V4  +  Waveshare 7.3" e-Paper HAT (F)
//
//   Standalone OpenSCAD: no YAPP, no imported STLs.
//   Every board is held by heat-set inserts. The SMA hole is computed from
//   the same numbers as the SDR cradle, so the two can't drift apart.
//
//   STACK (back -> front)
//     shell   : Pi 4, RTL-SDR cradle, I/O plate, vents, 4 corner columns
//     backer  : clamps the panel; carries the driver HAT + FPC adapter
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
//     small_parts  I/O plate + SDR strap + 2 desk feet
//     assembly / exploded / on_stand   preview (F5); % ghosts = hardware
//
//   HARDWARE
//     Heat-set inserts, 5.7 mm long (ruthex-style):
//       8x M3    4 bezel corners, 2 SDR strap, 2 I/O plate
//       8x M2.5  4 Pi, 4 driver HAT
//     4x M3x30 SHCS  shell -> bezel        2x M3x8    SDR strap
//     2x M3x8        I/O plate             8x M2.5x6  Pi + HAT
//     ~1 mm foam sheet behind the panel; VHB tape for the FPC adapter
//     10-15 cm USB-A M->F extension for the SDR (use a black USB 2.0 port)
//
//   MEASURE BEFORE PRINTING (search for "MEASURE")
//     - panel active-area offset (windowOffX/Y), FPC width/position
//     - RTL-SDR body L/W/T, SMA offset from body centre, SMA nut thickness
//     - Pi 4 SD-card centre (piSdCenterY)
//     - your panel-mount USB-C / USB-A cutouts (ioPorts)
//
//   ASSEMBLY ORDER
//     1. Melt in all inserts.
//     2. Bezel face-down. Panel into the pocket, foam on its back.
//     3. Backer on top (FPC through the slot). Adapter into its rails (VHB),
//        plug the short ribbon. HAT on its standoffs, adapter->HAT ribbon,
//        PH2.0 cable.
//     4. Shell: Pi, SDR + strap, I/O plate, internal cables.
//     5. PH2.0 jumpers onto the Pi GPIO, close, 4x M3x30 from the back.
//=======================================================================

/* [Render] */
part = "exploded"; // [assembly, exploded, on_stand, shell, bezel, backer, small_parts, io_plate, sdr_strap, feet]
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
windowOffX   = 0;    // MEASURE: active-area centre minus panel centre, + = right
windowOffY   = 0;    // MEASURE: + = up. The FPC exits the TOP edge; that border is often wider
windowMargin = 0.5;  // window larger than the active area by this much per side
panelClr     = 0.4;  // pocket clearance per side
pocketD      = 2.0;  // panel 0.91 + ~1 mm foam
fpcW         = 30;   // MEASURE: width of the panel's FPC tail
fpcOffX      = 0;    // MEASURE: FPC centre minus panel centre, + = right
fpcSlot      = 4.0;  // FPC pass-through, measured outward from the pocket edge

/* [Bezel and backer] */
border    = 11;   // pocket edge to outer edge
faceT     = 2.0;  // bezel thickness in front of the panel
backerT   = 3.0;
backerClr = 0.3;  // backer to shell inner wall

/* [Inserts and screws] */
insM3   = [4.0, 6.1, 7.2]; // [hole dia, hole depth, boss dia] for M3 x 5.7 inserts
insM25  = [4.0, 6.1, 7.2]; // ruthex M2.5x5.7 also wants 4.0; many other brands want ~3.6 - check yours
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
piPos      = [3.0, 29.5];  // inner coords of the Pi's bottom-left corner, GPIO along the top
piHoles    = [[3.5, 3.5], [61.5, 3.5], [3.5, 52.5], [61.5, 52.5]];
piSdSlot    = true;  // fingernail slot in the left wall for the microSD
piSdCenterY = 25;    // MEASURE: SD card centre above the Pi's bottom edge
piSdW       = 20;

/* [Driver HAT (on the backer)] */
hatL        = 65;
hatW        = 30.5;
hatPos      = [3.6, 87.0];  // inner coords, bottom-left corner
hatHoles    = [[3.5, 3.5], [61.5, 3.5], [3.5, 26.5], [61.5, 26.5]];
hatStandoff = 10;  // clears the 2x20 female header (~8.5 mm) facing the backer

/* [FPC adapter (on the backer)] */
adL     = 45;
adW     = 21;
adGap   = 2.0;  // board edge to the FPC slot; shrink if the ribbon is very short
adClr   = 0.3;
adRailW = 1.2;
adRailH = 2.0;
adHoles = [];   // optional [[x, y], ...] from the board's bottom-left -> M2 self-tapper bosses
adBossH = 2.0;

/* [RTL-SDR Blog V4] */
sdrL         = 69;   // MEASURE: end plate to end plate
sdrW         = 27;   // MEASURE
sdrT         = 13;   // MEASURE
sdrClr       = 0.3;
sdrCx        = 163;  // inner X of the dongle centreline (vertical, SMA up)
sdrSmaNutT   = 2.0;  // MEASURE: SMA nut on the end plate (0 if you remove it)
sdrEndGap    = 0.3;  // SMA nut to wall
sdrLift      = 1.2;  // air gap under the dongle
sdrRailH     = 7;
sdrRailW     = 2.0;
sdrStopT     = 2.0;
sdrPadW      = 5;
sdrUsbNotchW = 15;
sdrSmaOffX   = 0;    // MEASURE: SMA centre minus body centre across the width, + = right
sdrSmaOffZ   = 0;    // MEASURE: across the thickness, + = toward the front
sdrSmaLen    = 9.0;  // MEASURE: SMA length past the end plate (nut included)
smaHoleD     = 7.0;
smaCbD       = 12;   // outside counterbore so the coax nut sits deeper
smaCbDepth   = 1.2;
strapT       = 3;
strapW       = 10;

/* [I/O plate] */
ioSize   = [79, 26];
ioT      = 2.4;
ioCenter = [116, 17];  // inner coords
ioScrewX = 35.5;
ioWindow = [62, 18];
// [x, y, w, h, corner r, ear spacing (0 = none), ear hole dia, label]  - MEASURE your parts
ioPorts = [
    [-17, 0,  9.4, 3.6, 1.6,  0, 3.2, "5V"],    // panel-mount USB-C (power)
    [ 12, 0, 13.6, 6.2, 0.8, 30, 3.2, "FLAP"]   // panel-mount USB-A (split-flap)
];

/* [Vents and label] */
slotT     = 2.0;
slotPitch = 4.2;
vents = [                 // inner [x, y, w, h]
    [ 36,  5, 36, 21],    // intake under the Pi
    [  8, 90, 58, 24],    // exhaust above the Pi
    [118, 72, 20, 46],    // exhaust, middle
    [156, 64, 14, 58]     // under the RTL-SDR
];
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

bezelT      = faceT + pocketD;
zBackerBack = floorT + piStandoff + piPcbT + max(piCompH + topClr, gpioWireH);
zBezelBack  = zBackerBack + backerT;   // top of the shell walls
D           = zBezelBack + bezelT;     // overall depth
zPanelFront = D - faceT;
cbDepth     = zBackerBack + screwEngage - screwL;

panelCx    = W/2;
panelCy    = H/2;
pocketTopY = border + pocketH;
fpcCx      = panelCx + fpcOffX;
fpcY0      = pocketTopY - 0.5;
fpcCutW    = fpcW + 2;

corners      = [[cornerInset, cornerInset], [W - cornerInset, cornerInset],
                [cornerInset, H - cornerInset], [W - cornerInset, H - cornerInset]];
outerCorners = [[0, 0], [W, 0], [0, H], [W, H]];

adX0 = fpcCx - adL/2;      // adapter footprint (global)
adY1 = fpcY0 - adGap;
adY0 = adY1 - adW;

sdrY1      = innerH - sdrSmaNutT - sdrEndGap;   // inner coords from here down
sdrY0      = sdrY1 - sdrL;
sdrChL     = sdrCx - sdrW/2 - sdrClr;
sdrChR     = sdrCx + sdrW/2 + sdrClr;
sdrZ0      = floorT + sdrLift;
sdrZc      = sdrZ0 + sdrT/2;
sdrStopY   = sdrY0 - sdrClr - sdrStopT;
strapZ     = sdrZ0 + sdrT + 0.3;
strapY     = (sdrY0 + sdrY1)/2;
strapBossX = [sdrChL - sdrRailW - insM3[2]/2 + 0.5, sdrChR + sdrRailW + insM3[2]/2 - 0.5];
smaX       = wall + sdrCx + sdrSmaOffX;          // global
smaZ       = sdrZc + sdrSmaOffZ;
smaFree    = sdrSmaLen - sdrSmaNutT - sdrEndGap - (wall - smaCbDepth);

echo(str("Airspace Monitor v2: ", W, " x ", H, " x ", D, " mm"));
echo(str("Shell->bezel: 4x M3x", screwL, " SHCS, counterbore dia ", m3HeadD, " x ", cbDepth, " mm deep"));
echo(str("SMA thread free for the coax nut: ", smaFree, " mm (want >= 4)"));

assert(cbDepth >= 2, "screwL too long for the corner columns");
assert(sdrStopY > 2, "RTL-SDR too long for the shell");
assert(wall + hatPos[0] + hatHoles[1][0] + insM25[2]/2 < adX0 - adClr - adRailW,
       "HAT standoffs collide with the FPC adapter rails");
assert(piPos[1] + piW < hatPos[1] + hatHoles[0][1] - insM25[2]/2,
       "Pi overlaps the HAT standoffs");

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
        // SMA-end pads: the end plate bears on these, never the SMA nut
        for (x = [sdrChL, sdrChR - sdrPadW])
            translate([x, sdrY1, 0]) cube([sdrPadW, innerH - sdrY1 + e, railTop + e]);
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
    // SMA through the top wall, plus an outside counterbore for the coax nut
    translate([smaX, H - wall - 1, smaZ]) rotate([-90, 0, 0]) cylinder(d = smaHoleD, h = wall + 2);
    translate([smaX, H - smaCbDepth, smaZ]) rotate([-90, 0, 0]) cylinder(d = smaCbD, h = smaCbDepth + 1);
    // I/O window + its inserts (installed from outside)
    at_inner(ioCenter) translate([0, 0, -e]) linear_extrude(floorT + 2*e) rrectC(ioWindow, 2);
    for (s = [-1, 1])
        at_inner([ioCenter[0] + s*ioScrewX, ioCenter[1]]) insert_hole(insM3, 0, up = true);
    // vents
    for (v = vents) at_inner([v[0], v[1]]) vent_slots(v[2], v[3]);
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
        // FPC pass-through at the top edge
        translate([fpcCx - fpcCutW/2, fpcY0, zBezelBack - e]) cube([fpcCutW, 0.5 + fpcSlot, pocketD + e]);
        // seam groove
        translate([0, 0, zBezelBack - e]) linear_extrude(grooveD + e) ring(tongueOff, grooveW);
        // corner inserts
        for (c = corners) translate([c[0], c[1], 0]) insert_hole(insM3, zBackerBack, up = true);
    }
}

//-----------------------------------------------------------------------
// Backer plate (display module: HAT + FPC adapter)
//-----------------------------------------------------------------------
module adapter_mount() {
    if (len(adHoles) == 0) {
        // 3-sided locating frame, open toward the FPC slot (board goes on VHB)
        translate([0, 0, zBackerBack - adRailH]) linear_extrude(adRailH + e) difference() {
            translate([adX0 - adClr - adRailW, adY0 - adClr - adRailW])
                square([adL + 2*(adClr + adRailW), adW + 2*adClr + adRailW]);
            translate([adX0 - adClr, adY0 - adClr]) square([adL + 2*adClr, adW + 2*adClr + 5]);
        }
    } else {
        for (h = adHoles)
            translate([adX0 + h[0], adY0 + h[1], zBackerBack - adBossH]) cylinder(d = 5, h = adBossH + e);
    }
}

module backer() {
    difference() {
        union() {
            translate([0, 0, zBackerBack]) linear_extrude(backerT) outline(wall + backerClr);
            // HAT standoffs (point toward the back)
            for (h = hatHoles)
                at_inner([hatPos[0] + h[0], hatPos[1] + h[1]])
                    translate([0, 0, zBackerBack - hatStandoff]) cylinder(d = insM25[2], h = hatStandoff + e);
            adapter_mount();
        }
        // clear the bezel's corner bosses and drop the thin corner slivers
        for (i = [0 : 3]) hull() {
            translate([corners[i][0], corners[i][1], zBackerBack - 1])
                cylinder(d = insM3[2] + 0.6, h = backerT + 2);
            translate([outerCorners[i][0] - 1, outerCorners[i][1] - 1, zBackerBack - 1])
                cube([2, 2, backerT + 2]);
        }
        // FPC pass-through
        translate([fpcCx - fpcCutW/2, fpcY0, zBackerBack - 1]) cube([fpcCutW, 0.5 + fpcSlot, backerT + 2]);
        // bend relief on the slot's inner rear edge (where the ribbon turns toward the adapter)
        translate([fpcCx - fpcCutW/2, fpcY0, zBackerBack]) hull() {
            translate([0, -1.2, -e]) cube([fpcCutW, 1.2 + e, e]);
            translate([0, -e, -e]) cube([fpcCutW, e, 1.2 + e]);
        }
        // HAT inserts (from the standoff tips)
        for (h = hatHoles)
            at_inner([hatPos[0] + h[0], hatPos[1] + h[1]])
                insert_hole(insM25, zBackerBack - hatStandoff, up = true);
        // optional adapter pilot holes (M2 self-tappers)
        for (h = adHoles)
            translate([adX0 + h[0], adY0 + h[1], zBackerBack - adBossH - e])
                cylinder(d = 1.8, h = adBossH + backerT - 0.8);
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

// Local: outer face at z = 0 (print this side down), centred on the plate.
module io_plate() {
    difference() {
        linear_extrude(ioT) rrectC(ioSize, 3);
        for (p = ioPorts) {
            translate([p[0], p[1], -e]) linear_extrude(ioT + 2*e) rrectC([p[2], p[3]], p[4]);
            if (p[5] > 0)
                for (s = [-1, 1])
                    translate([p[0] + s*p[5]/2, p[1], -e]) cylinder(d = p[6], h = ioT + 2*e);
            if (p[7] != "")
                translate([p[0], p[1] + p[3]/2 + 2.0, -e]) mirror([1, 0, 0])
                    linear_extrude(0.4 + e)
                        text(p[7], size = 2.6, font = labelFont, halign = "center", valign = "bottom");
        }
        for (s = [-1, 1]) translate([s*ioScrewX, 0, -e]) cylinder(d = m3Clr, h = ioT + 2*e);
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
    linear_extrude(footW)
        polygon([[0, 0], [footD, 0], [footD, 3], Q, Pt, Pb, Pf, Pl, [0, Pl[1]]]);
}

//-----------------------------------------------------------------------
// Previews
//-----------------------------------------------------------------------
module strap_in_place()
    translate([wall + (strapBossX[0] + strapBossX[1])/2, wall + strapY, strapZ]) sdr_strap();

module io_in_place()
    translate([wall + ioCenter[0], wall + ioCenter[1], -ioT]) io_plate();

module hardware_ghosts() {
    // Pi 4: PCB, rough USB/Ethernet block, GPIO jumper envelope
    %translate([wall + piPos[0], wall + piPos[1], floorT + piStandoff]) {
        cube([piL, piW, piPcbT]);
        translate([piL - 21, 2, piPcbT]) cube([23.5, 52, piCompH]);
        translate([7, piW - 6, piPcbT]) cube([51, 5, gpioWireH]);
    }
    // RTL-SDR body + SMA
    %translate([wall + sdrCx - sdrW/2, wall + sdrY0, sdrZ0]) cube([sdrW, sdrL, sdrT]);
    %translate([smaX, wall + sdrY1, smaZ]) rotate([-90, 0, 0]) cylinder(d = 6.35, h = sdrSmaLen);
    // panel
    %translate([border + panelClr, border + panelClr, zPanelFront - panelT]) cube([panelW, panelH, panelT]);
    // driver HAT (header toward the backer)
    %translate([wall + hatPos[0], wall + hatPos[1], zBackerBack - hatStandoff - 1.6]) cube([hatL, hatW, 1.6]);
    // FPC adapter
    %translate([adX0, adY0, zBackerBack - 1.6]) cube([adL, adW, 1.6]);
}

module assembled() {
    color("SlateGray") shell();
    color("Tan")       backer();
    color("DimGray")   bezel();
    color("Silver")    strap_in_place();
    color("Silver")    io_in_place();
    if (show_hardware) hardware_ghosts();
}

module exploded() {
    color("SlateGray") shell();
    color("Silver")    translate([0, 0, 15]) strap_in_place();
    color("Silver")    translate([0, 0, -20]) io_in_place();
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
if (part == "assembly")         assembled();
else if (part == "exploded")    exploded();
else if (part == "on_stand")    on_stand();
else if (part == "shell")       shell();
else if (part == "bezel")       translate([W, 0, D]) rotate([0, 180, 0]) bezel();
else if (part == "backer")      translate([W, 0, zBezelBack]) rotate([0, 180, 0]) backer();
else if (part == "io_plate")    io_plate();
else if (part == "sdr_strap")   sdr_strap();
else if (part == "feet")        { foot(); translate([0, 50, 0]) foot(); }
else if (part == "small_parts") {
    io_plate();
    translate([0, 28, 0]) sdr_strap();
    translate([-75, 45, 0]) foot();
    translate([5, 45, 0]) foot();
}
