// =============================================================================
//  splitflap_enclosure.scad  -  parametric 3D-printed enclosure for a
//  Scott Bezek splitflap v2 display built on one combined acrylic front panel
// =============================================================================
//
//  HOW IT GOES TOGETHER
//   SHELL  An open-front box printed in segments, back face on the bed, no
//          supports. Segments join with a tongue-and-groove in the top and
//          bottom walls plus M3-bolted lugs along the back wall.
//   PANEL  Your acrylic, with the modules bolted to it as usual, drops into a
//          shallow pocket in the shell's front rim and rests on a narrow seat
//          ledge. No extra holes are needed in the acrylic.
//   BEZEL  A thin frame that overlaps the acrylic edge and fastens to the rim
//          (M3 screws into heat-set inserts, or magnets). Remove the bezel and
//          the panel + modules lift straight out of the front for service.
//          The bezel is split at different places than the shell, so every
//          bezel piece bridges (and stiffens) a shell seam.
//   BOARDS The Chainlink Drivers and the Chainlink Buddy screw onto standoffs
//          on the inside of the back wall, behind the modules. Board sizes and
//          mounting holes come from the Chainlink gerbers. A board may span a
//          shell seam (unscrew it before separating those segments).
//   PORTS  Pass-through holes in the right wall for the USB-C and barrel-jack
//          cables, placed to line up with the Buddy's connectors.
//
//  COORDINATES  X = width (left -> right seen from the front), Y = height,
//               Z = depth (Z = 0 is the outside of the back wall, Z = D the
//               front). OpenSCAD's top view is the front of the display.
//
//  WORKFLOW
//   1. Set the panel size and the "space behind the panel" values.
//   2. part = "assembly", preview (F5), read the console for sizes, board
//      positions, hardware and ribbon-cable runs.
//   3. Print the test parts first: "joint_test", "corner_test", "port_test"
//      and "standoff_test" (index 0 = Driver, 1 = Buddy).
//   4. Export every "shell_segment" and "bezel_piece" (index = 0, 1, 2 ...).
//      Shell segments print back-down; bezel pieces are already flipped so
//      the visible face prints on the bed.
// =============================================================================

/* [What to render] */
part = "bezel_piece"; // [assembly, shell_segment, bezel_piece, joint_test, corner_test, port_test, standoff_test]
// Shell segment / bezel piece to export (0 = leftmost, seen from the front). standoff_test: 0 = Driver, 1 = Buddy
index = 3; // [0:1:9]
// Assembly view only: spread the parts apart (mm)
explode = 0; // [0:5:100]
show_panel = true;
show_module_envelope = true;
show_boards = true;

/* [Printer] */
bed_x = 250;
bed_y = 250;
bed_z = 250;
// Keep every part at least this far inside the bed limits
bed_margin = 5;

/* [Front panel (acrylic)] */
panel_w = 692;
panel_h = 164;
panel_t = 3;
// Clearance between the acrylic edge and its pocket (per side)
panel_gap = 0.5;
// + puts the acrylic face in front of the rim, - sinks it below the rim
panel_proud = 0;

/* [Space behind the panel - measure these] */
// Acrylic top/bottom edge -> nearest module part behind the panel
margin_tb = 4;
// Acrylic left/right edge -> nearest module part behind the panel
margin_side = 4;
// The seat ledge stops this far short of the modules
ledge_clearance = 1;
ledge_max = 10;
// Back face of the acrylic -> rearmost point of a module (motor, wires, connectors)
module_depth = 90;
// Room behind the modules: Chainlink boards on their standoffs, wiring, joint lugs
rear_clearance = 30;

/* [Shell] */
// 0 = automatic (fewest segments that fit the bed)
segments = 0;
// Optional explicit seam positions, mm from the shell's left outer edge, e.g. [240, 480]
custom_seams = [];
wall = 4;
back_t = 4;
// Solid front rim the bezel fastens to (also sets the visible frame width)
rim_w = 10;
// Front-to-back thickness of the seat the acrylic rests on
ledge_t = 4;
corner_r = 2;

/* [Shell joints] */
// Bolted lugs per seam along the back wall (2 or more puts one in each back corner)
joint_bolts = 3;
joint_hardware = "insert"; // [insert, nut]
lug_size = 10;
// Lug length on each side of a seam
lug_len = 8;
tongues = true;
tongue_w = 1.6;
tongue_len = 3;
tongue_clear = 0.2;

/* [Bezel] */
bezel_t = 3;
// How far the bezel covers the acrylic edge (stay clear of the flap windows)
bezel_overlap_tb = 5;
bezel_overlap_side = 5;
// Lip on the back of the bezel that presses the acrylic onto its seat
bezel_preload = 0.3;
bezel_fastener = "screw"; // [screw, magnet]
// Fasteners along each long rail (top and bottom)
bezel_screws_tb = 8;
// Fasteners on each end rail (keep it even: the finger notches sit mid-height)
bezel_screws_side = 2;
bezel_end_inset = 25;
// No rim fastener closer than this to any shell or bezel seam
seam_keepout = 10;
// Optional explicit bezel seams (default: the middle of each shell segment)
custom_bezel_seams = [];
// Total gap left at each bezel butt joint
bezel_seam_gap = 0.2;
bezel_chamfer = 1;
countersink = true;

/* [Hardware] */
screw_clear_d = 3.4;
// Hole for your M3 heat-set inserts (check the insert maker's spec)
insert_hole_d = 4.1;
insert_depth = 5.5;
csk_d = 6.4;
nut_af = 5.5;
nut_t = 2.4;
magnet_d = 6;
magnet_h = 2;
magnet_clear = 0.15;

/* [Back wall] */
vents = true;
vent_w = 3;
vent_len = 60;
vent_pitch = 8;
// Vent band centre, as a fraction of the enclosure height
vent_y_frac = 0.42;
vent_seam_clear = 25;
// Extra cutouts: [segment (-1 = last), x offset from segment centre, y, width, height, corner radius]
back_cutouts = [];
keyholes = false;
keyhole_inset = 80;
keyhole_from_top = 45;
keyhole_head_d = 8.5;
keyhole_shank_d = 4.2;
keyhole_slot = 10;
// Extra M3-insert standoffs on the inside of the back wall: [segment, x offset from centre, y, height]
standoffs = [];
// Hidden under the bezel: lets a fingernail get behind the acrylic edge
finger_notches = true;
notch_w = 20;
notch_reach = 4;

/* [Electronics - mounting] */
// Gap between the back wall and the underside of each PCB
board_standoff_h = 6;
board_standoff_d = 8;
board_hardware = "insert"; // [insert, self_tap]
// Pilot hole when screwing M3 straight into the plastic
self_tap_hole_d = 2.6;
pcb_t = 1.6;
// Tallest parts above each PCB with plugs and ribbons connected (checked against rear_clearance)
driver_parts_h = 16;
buddy_parts_h = 16;

/* [Electronics - Chainlink Drivers] */
num_drivers = 2;
// Board centres in mm from the left outer edge, left to right (empty = each centred in an equal share of the width)
driver_x = [];
// Board centre height as a fraction of the enclosure height (0.72 keeps clear of the middle joint lug)
driver_y_frac = 0.72;
// 180 = channel A on the left seen from the front (Scott's module order). 0 = motor connectors up, channel A on the right
driver_rot = 180; // [0, 90, 180, 270]

/* [Electronics - Chainlink Buddy] */
include_buddy = true;
// Gap between the Buddy and the right wall: room for the USB-C plug
buddy_wall_clear = 35;
// Gap below the Buddy: room for the barrel plug and its cable bend
buddy_floor_clear = 40;
// 0 = T-Display USB-C facing the right wall, barrel jack facing down
buddy_rot = 0; // [0, 90, 180, 270]
// Explicit centre [x, y] in mm (empty = automatic: far right)
buddy_pos = [];

/* [Cable ports - right wall] */
ports = true;
// USB-C pass-through slot: width along the wall, height front-to-back. Must pass your plug's overmold
usb_hole_w = 14;
usb_hole_h = 9;
// Must pass your barrel plug's overmold
barrel_hole_d = 12;
// USB-C centre above the Buddy PCB (T-Display sitting in female headers)
tdisplay_usb_h = 11.7;
// Barrel jack centre above the Buddy PCB
barrel_jack_h = 6.3;
// Plug + strain relief length, used to place a port when its jack doesn't face the wall
usb_plug_len = 30;
barrel_plug_len = 28;
// Manual port positions [y, z]: y up from the bottom, z forward from the back (empty = automatic)
usb_port = [];
barrel_port = [];
// Pointed top on the round hole so it prints cleanly without supports
teardrop_ports = true;

/* [Hidden] */
$fa = 4;
$fs = 0.4;

// ---- Board data, read from the Chainlink gerbers ---------------------------
// mm, origin = lower-left corner of the board outline, component side up
// (as the gerbers show it). Mounting holes are 3.2 mm (M3).
DRV_SIZE       = [198.12, 30.48];
DRV_HOLES      = [[3.302, 3.302], [3.302, 27.178], [99.06, 3.302],
                  [194.818, 3.302], [194.818, 27.178]];
DRV_IN         = [186.69, 15.24];   // J19 "Input" 2x4 header
DRV_OUT        = [11.43, 15.24];    // J20 "Output" 2x4 header
DRV_MOTOR_X    = [28.02, 47.07, 66.12, 132.16, 151.21, 170.26];   // JST-XH, channels F..A
DRV_SENSOR_X   = [27.94, 46.99, 66.04, 132.08, 151.13, 170.18];
BUD_SIZE       = [74.93, 49.53];
BUD_R          = 3.81;
BUD_HOLES      = [[3.81, 3.81], [3.81, 45.72], [71.12, 3.81], [71.12, 45.72]];
BUD_OUT        = [12.7, 33.02];     // J1 "Output" 2x4 header
BUD_PWR        = [12.7, 15.24];     // J2 power screw terminal
BUD_TD         = [22.94, 16.67, 51.49, 25.09];   // T-Display outline [x, y, w, h]
BUD_USB        = [74.43, 29.215];   // T-Display USB-C ...
BUD_USB_DIR    = [1, 0];            // ... faces +X
BUD_BARREL     = [26.035, -0.54];   // barrel jack opening ...
BUD_BARREL_DIR = [0, -1];           // ... faces -Y

// ================================================================ derived ====
c0       = rim_w + panel_gap;            // shell outer edge -> acrylic edge
W        = panel_w + 2 * c0;             // outer width
H        = panel_h + 2 * c0;             // outer height
recess   = panel_t - panel_proud;        // pocket depth
D        = back_t + rear_clearance + module_depth + recess;   // outer depth
zf       = D - recess;                   // seat plane = back face of acrylic
ledge_tb   = max(0, min(margin_tb   - ledge_clearance, ledge_max));
ledge_side = max(0, min(margin_side - ledge_clearance, ledge_max));
in_tb    = c0 + ledge_tb;                // inset of the opening inside the seat
in_side  = c0 + ledge_side;
z_ledge  = zf - ledge_t;
ch       = max(in_tb, in_side) - wall;   // height of the self-supporting underside
z_ch     = z_ledge - ch;
lip_h    = max(0, bezel_preload - panel_proud);
ox       = c0 + bezel_overlap_side;      // bezel window inset
oy       = c0 + bezel_overlap_tb;
rim_c    = rim_w / 2;                    // centre line of the rim fasteners
lug_z    = back_t + lug_size / 2;
tl       = tongues ? tongue_len : 0;
rear_top = back_t + rear_clearance;      // where the back of the modules sits

n_auto   = ceil(W / (bed_x - bed_margin - tl));
n_seg    = len(custom_seams) > 0 ? len(custom_seams) + 1
         : (segments > 0 ? segments : n_auto);
seams    = len(custom_seams) > 0 ? concat([0], custom_seams, [W])
         : [for (i = [0:1:n_seg]) i * W / n_seg];
inner_seams = [for (i = [1:1:n_seg - 1]) seams[i]];

bz_inner = len(custom_bezel_seams) > 0 ? custom_bezel_seams
         : (n_seg == 1 ? [] : [for (i = [0:1:n_seg - 1]) (seams[i] + seams[i + 1]) / 2]);
bz       = concat([0], bz_inner, [W]);
n_bz     = len(bz) - 1;
all_seams = concat(inner_seams, bz_inner);

function seg_index(k)  = k < 0 ? n_seg + k : k;
function seg_centre(k) = (seams[seg_index(k)] + seams[seg_index(k) + 1]) / 2;

// push a position out of the keep-out zone around any seam
function nudge(x, ss, d, i = 0) =
    i >= len(ss) ? x :
    let(dx = x - ss[i])
    nudge(abs(dx) < d ? ss[i] + (dx >= 0 ? d : -d) : x, ss, d, i + 1);

tb_xs = bezel_screws_tb < 1 ? [] :
    [for (k = [0:1:bezel_screws_tb - 1])
        nudge(bezel_screws_tb == 1 ? W / 2
              : bezel_end_inset + k * (W - 2 * bezel_end_inset) / (bezel_screws_tb - 1),
              all_seams, seam_keepout)];
side_ys = bezel_screws_side < 1 ? [] :
    [for (k = [0:1:bezel_screws_side - 1])
        bezel_screws_side == 1 ? H / 2
        : c0 + bezel_end_inset + k * (H - 2 * c0 - 2 * bezel_end_inset) / (bezel_screws_side - 1)];
bezel_pts = concat(
    [for (x = tb_xs) [x, rim_c]],
    [for (x = tb_xs) [x, H - rim_c]],
    [for (y = side_ys) [rim_c, y]],
    [for (y = side_ys) [W - rim_c, y]]);

lug_ys = joint_bolts < 1 ? [] :
    [for (j = [0:1:joint_bolts - 1])
        joint_bolts == 1 ? H / 2
        : wall + lug_size / 2 + j * (H - 2 * wall - lug_size) / (joint_bolts - 1)];

// --- electronics ------------------------------------------------------------
function rot2(p, r) = r == 90 ? [-p[1], p[0]] : r == 180 ? [-p[0], -p[1]]
                    : r == 270 ? [p[1], -p[0]] : p;
function rsize(s, r) = (r == 90 || r == 270) ? [s[1], s[0]] : s;
// board-local point -> enclosure XY (board centred on c, rotated r degrees CCW)
function bpt(c, s, r, p) = c + rot2(p - s / 2, r);
function clampv(v, lo, hi) = min(max(v, lo), hi);

n_drv  = len(driver_x) > 0 ? len(driver_x) : max(0, num_drivers);
drv_c  = [for (k = [0:1:n_drv - 1])
             [len(driver_x) > 0 ? driver_x[k] : W * (2 * k + 1) / (2 * n_drv), H * driver_y_frac]];
bud_sz = rsize(BUD_SIZE, buddy_rot);
bud_c  = len(buddy_pos) == 2 ? buddy_pos
       : [W - wall - buddy_wall_clear - bud_sz[0] / 2, wall + buddy_floor_clear + bud_sz[1] / 2];

// every board as [centre, size, rotation, holes, name]
boards_all = concat(
    [for (k = [0:1:n_drv - 1]) [drv_c[k], DRV_SIZE, driver_rot, DRV_HOLES, str("Driver ", k)]],
    include_buddy ? [[bud_c, BUD_SIZE, buddy_rot, BUD_HOLES, "Buddy"]] : []);
function bb_lo(b) = b[0] - rsize(b[1], b[2]) / 2;
function bb_hi(b) = b[0] + rsize(b[1], b[2]) / 2;
function overlap(a0, a1, b0, b1) = a0[0] < b1[0] && b0[0] < a1[0] && a0[1] < b1[1] && b0[1] < a1[1];

board_pts   = [for (b = boards_all) for (h = b[3]) bpt(b[0], b[1], b[2], h)];
user_so_pts = [for (s = standoffs) [seg_centre(s[0]) + s[1], s[2]]];
so_pts      = concat(board_pts, user_so_pts);
so_r        = board_standoff_d / 2 + 2;          // standoff footprint incl. flared base
board_top_z = back_t + board_standoff_h + pcb_t;

// chain order: the first Driver is the one whose channel A drives the leftmost module
chain   = driver_rot == 0 ? [for (k = [n_drv - 1:-1:0]) k] : [for (k = [0:1:n_drv - 1]) k];
function d_in(k)  = bpt(drv_c[k], DRV_SIZE, driver_rot, DRV_IN);
function d_out(k) = bpt(drv_c[k], DRV_SIZE, driver_rot, DRV_OUT);
bud_out = bpt(bud_c, BUD_SIZE, buddy_rot, BUD_OUT);

// cable ports: in line with a connector that faces the right wall, otherwise
// level with the end of its plug
usb_p = bpt(bud_c, BUD_SIZE, buddy_rot, BUD_USB);
usb_f = rot2(BUD_USB_DIR, buddy_rot);
bar_p = bpt(bud_c, BUD_SIZE, buddy_rot, BUD_BARREL);
bar_f = rot2(BUD_BARREL_DIR, buddy_rot);
function port_y(p, f, plug, half) =
    clampv(f[0] > 0.5 ? p[1] : p[1] + f[1] * plug, wall + half + 2, H - wall - half - 2);
usb_yz = len(usb_port) == 2 ? usb_port
       : [port_y(usb_p, usb_f, usb_plug_len, usb_hole_w / 2), board_top_z + tdisplay_usb_h];
bar_yz = len(barrel_port) == 2 ? barrel_port
       : [port_y(bar_p, bar_f, barrel_plug_len, barrel_hole_d / 2), board_top_z + barrel_jack_h];
ports_on  = ports && (include_buddy || (len(usb_port) == 2 && len(barrel_port) == 2));
bar_top   = barrel_hole_d / 2 * (teardrop_ports ? sqrt(2) : 1);

// ============================================================ checks/info ====
assert(rim_w >= wall, "rim_w must be at least wall");
assert(H <= bed_y - bed_margin, str("Enclosure height ", H, " mm doesn't fit the bed"));
assert(D <= bed_z - bed_margin, str("Enclosure depth ", D, " mm doesn't fit the bed height"));
assert(rear_clearance >= lug_size + 2, "rear_clearance must leave room for the joint lugs (lug_size + 2)");
assert(joint_hardware == "nut" || lug_len >= insert_depth + 1.5, "lug_len too short for the inserts");
for (i = [0:1:n_seg - 1])
    assert(seams[i + 1] - seams[i] + (i < n_seg - 1 ? tl : 0) <= bed_x - bed_margin,
           str("Shell segment ", i, " is too wide for the bed - add segments"));
for (j = [0:1:n_bz - 1])
    assert(bz[j + 1] - bz[j] <= bed_x - bed_margin,
           str("Bezel piece ", j, " is too wide for the bed - adjust custom_bezel_seams"));

// boards: inside the walls, clear of the joint lugs, clear of each other
for (b = boards_all) {
    lo = bb_lo(b);
    hi = bb_hi(b);
    assert(lo[0] >= wall + 1 && hi[0] <= W - wall - 1 && lo[1] >= wall + 1 && hi[1] <= H - wall - 1,
           str(b[4], " doesn't fit inside the walls - move it or change its rotation"));
    if (board_standoff_h - 2.5 < lug_size)       // 2.5 mm: solder joints under the PCB
        for (s = inner_seams, ly = lug_ys)
            assert(!overlap(lo - [1, 1], hi + [1, 1],
                            [s - lug_len, ly - lug_size / 2], [s + lug_len, ly + lug_size / 2]),
                   str(b[4], " sits on the joint lug at x = ", s, ", y = ", ly,
                       " - move it up or down, or raise board_standoff_h above ", lug_size + 2.5));
}
for (i = [0:1:len(boards_all) - 1], j = [0:1:len(boards_all) - 1])
    if (i < j)
        assert(!overlap(bb_lo(boards_all[i]) - [2, 2], bb_hi(boards_all[i]) + [2, 2],
                        bb_lo(boards_all[j]), bb_hi(boards_all[j])),
               str(boards_all[i][4], " overlaps ", boards_all[j][4], " - move one of them"));
for (p = so_pts, s = inner_seams)
    assert(abs(p[0] - s) >= so_r + 0.5,
           str("A standoff at x = ", p[0], " lands on the shell seam at x = ", s, " - shift that board sideways"));

if (ports_on) {
    assert(usb_yz[1] - usb_hole_h / 2 >= back_t + 1 && bar_yz[1] - barrel_hole_d / 2 >= back_t + 1,
           "A cable port cuts into the back wall - raise its z");
    assert(abs(usb_yz[0] - bar_yz[0]) >= usb_hole_w / 2 + barrel_hole_d / 2 + 3
           || abs(usb_yz[1] - bar_yz[1]) >= usb_hole_h / 2 + barrel_hole_d / 2 + 3,
           "The two cable ports overlap - move one with usb_port / barrel_port");
}

n_rim   = len(bezel_pts);
n_joint = max(0, n_seg - 1) * joint_bolts;

echo(str("Enclosure outside: ", W, " x ", H, " x ", D, " mm (+ ", bezel_t, " mm bezel)"));
echo(str("Shell: ", n_seg, " segments, seams at x = ", inner_seams));
echo(str("Bezel: ", n_bz, " pieces, seams at x = ", bz_inner));
echo(str("Seat ledge behind the acrylic: ", ledge_tb, " mm top/bottom, ", ledge_side, " mm sides"));
if (bezel_fastener == "screw")
    echo(str("Bezel hardware: ", n_rim, " x M3 heat-set inserts + ", n_rim, " x M3x8 ",
             countersink ? "countersunk" : "button-head", " screws"));
else
    echo(str("Bezel hardware: ", 2 * n_rim, " x ", magnet_d, "x", magnet_h, " mm magnets (",
             n_rim, " in the rim, ", n_rim, " in the bezel - keep the polarity consistent)"));
echo(str("Joint hardware: ", n_joint,
         joint_hardware == "insert" ? " x M3x12 screws + M3 heat-set inserts" : " x M3x16 screws + M3 nuts"));
if (n_drv > 0)
    echo(str("Chainlink Drivers (rotation ", driver_rot, "): centres ", drv_c));
if (include_buddy)
    echo(str("Chainlink Buddy (rotation ", buddy_rot, "): centre ", bud_c));
if (len(board_pts) > 0)
    echo(str("Board hardware: ", len(board_pts), board_hardware == "insert"
             ? " x M3 heat-set inserts + M3x6 screws" : " x M3x8 screws (self-tapping into the standoffs)"));
if (len(standoffs) > 0) echo(str("Extra standoffs: ", len(standoffs), " x M3 heat-set inserts"));
if (ports_on)
    echo(str("Right-wall ports [y, z]: USB-C ", usb_yz, ", barrel ", bar_yz));
if (n_drv > 0 && include_buddy)
    echo(str("Ribbon run (straight line, add slack): Buddy -> Driver ", chain[0], " = ",
             round(norm(d_in(chain[0]) - bud_out)), " mm"));
for (j = [0:1:n_drv - 2])
    echo(str("Ribbon run (straight line, add slack): Driver ", chain[j], " -> Driver ", chain[j + 1], " = ",
             round(norm(d_in(chain[j + 1]) - d_out(chain[j]))), " mm"));

if (ledge_tb < 1.5 || ledge_side < 1.5)
    echo("WARNING: the seat ledge is under 1.5 mm on at least one edge - the acrylic has little to rest on. More frame margin on the panel helps.");
if (finger_notches && bezel_screws_side % 2 == 1)
    echo("WARNING: an odd bezel_screws_side puts a side fastener in the finger notch.");
if (bezel_fastener == "magnet" && bezel_t < magnet_h + magnet_clear + 0.8)
    echo("WARNING: bezel_t is thin for the magnet pockets.");
if (bezel_fastener == "magnet" && magnet_d + 2 * magnet_clear > rim_w - 2)
    echo("WARNING: magnets are too wide for rim_w.");
if (bezel_fastener == "screw" && insert_hole_d > rim_w - 3)
    echo("WARNING: inserts are too wide for rim_w.");
for (j = [0:1:n_bz - 1])
    if (len([for (p = bezel_pts) if (p[0] > bz[j] && p[0] < bz[j + 1]) 1]) < 2)
        echo(str("WARNING: bezel piece ", j, " has fewer than 2 fasteners - raise bezel_screws_tb."));
for (i = [0:1:n_seg - 1])
    if (len([for (p = bezel_pts) if (p[0] > seams[i] && p[0] < seams[i + 1]) 1]) < 2)
        echo(str("WARNING: shell segment ", i, " has fewer than 2 rim fasteners - raise bezel_screws_tb."));
need_rear = board_standoff_h + pcb_t + 1
          + max(n_drv > 0 ? driver_parts_h : 0, include_buddy ? buddy_parts_h : 0);
if (len(boards_all) > 0 && need_rear > rear_clearance)
    echo(str("WARNING: the boards need rear_clearance >= ", need_rear, " mm to stay clear of the modules."));
if (ports_on && (usb_yz[1] + usb_hole_h / 2 > rear_top - 1 || bar_yz[1] + bar_top > rear_top - 1))
    echo("WARNING: a cable port reaches past the back of the modules - raise rear_clearance or lower the port.");
if (board_standoff_h < 4)
    echo("WARNING: board_standoff_h under 4 mm - the solder joints under the boards may touch the back wall.");

// ================================================================ helpers ====
module rrect(w, h, r) {
    if (r > 0) offset(r = r) offset(delta = -r) square([w, h]);
    else square([w, h]);
}

module rrect_c(w, h, r) {
    rr = min(r, min(w, h) / 2 - 0.01);
    if (rr > 0) offset(r = rr) offset(delta = -rr) square([w, h], center = true);
    else square([w, h], center = true);
}

// box inset from the shell's outer rectangle by ix (left/right) and iy (top/bottom)
module rect_slab(ix, iy, z0, h) {
    translate([ix, iy, z0]) cube([W - 2 * ix, H - 2 * iy, h]);
}

// cylinder along +X, starting at the current origin
module xcyl(d, h, fn = 0) {
    rotate([0, 90, 0]) cylinder(d = d, h = h, $fn = fn);
}

// ================================================================== shell ====
// Front rim + seat ledge, with a 45-degree (or steeper) underside so it
// prints without supports when the segment stands on its back.
module front_rim() {
    difference() {
        rect_slab(wall - 0.01, wall - 0.01, z_ch, D - z_ch);
        rect_slab(rim_w, rim_w, zf, D);                    // acrylic pocket
        rect_slab(in_side, in_tb, z_ledge - 0.01, D);      // opening inside the seat
        hull() {
            rect_slab(in_side, in_tb, z_ledge - 0.02, 0.02);
            rect_slab(wall, wall, z_ch - 0.02, 0.01);
        }
    }
}

module rim_fastener_cut(p) {
    if (bezel_fastener == "magnet")
        translate([p[0], p[1], D - magnet_h - magnet_clear])
            cylinder(d = magnet_d + 2 * magnet_clear, h = magnet_h + magnet_clear + 1);
    else
        translate([p[0], p[1], D - insert_depth])
            cylinder(d = insert_hole_d, h = insert_depth + 1);
}

// Scallop in the rim, reaching 2 mm behind the acrylic edge (hidden by the bezel)
module finger_notch(side) {
    r  = recess + 2;
    x0 = rim_w - notch_reach;
    nl = in_side - x0 + 0.01;
    xs = side == 0 ? x0 : W - x0 - nl;
    hull() for (dy = [-1, 1])
        translate([xs, H / 2 + dy * max(0, notch_w / 2 - r), D]) xcyl(2 * r, nl, 32);
}

// a vent slot is skipped wherever it would cut into a standoff
function vent_free(x, vy) =
    len([for (p = so_pts)
            if (abs(p[0] - x) < vent_w / 2 + so_r + 1 && abs(p[1] - vy) < vent_len / 2 + so_r + 1) 1]) == 0;

module vent_cuts() {
    vy = H * vent_y_frac;
    for (i = [0:1:n_seg - 1]) {
        a = seams[i] + vent_seam_clear;
        b = seams[i + 1] - vent_seam_clear;
        n = floor((b - a - vent_w) / vent_pitch) + 1;
        if (n > 0) for (k = [0:1:n - 1]) {
            x = (a + b) / 2 + (k - (n - 1) / 2) * vent_pitch;
            if (vent_free(x, vy))
                translate([x, vy, -1])
                    linear_extrude(height = back_t + 2)
                        hull() for (s = [-1, 1])
                            translate([0, s * (vent_len - vent_w) / 2]) circle(d = vent_w, $fn = 16);
        }
    }
}

module back_cutout(c) {
    translate([seg_centre(c[0]) + c[1], c[2], -1])
        linear_extrude(height = back_t + 2) rrect_c(c[3], c[4], c[5]);
}

module keyhole(kx) {
    ky = H - keyhole_from_top;
    translate([0, 0, -1]) linear_extrude(height = back_t + 2) {
        translate([kx, ky]) circle(d = keyhole_head_d, $fn = 32);
        hull() for (dy = [0, keyhole_slot])
            translate([kx, ky + dy]) circle(d = keyhole_shank_d, $fn = 24);
    }
}

// --- board standoffs ----------------------------------------------------------
// z0 = surface the standoff grows from, floor_t = material under that surface
module board_standoff(p, z0) {
    translate([p[0], p[1], z0 - 0.01]) {
        cylinder(d = board_standoff_d, h = board_standoff_h + 0.01);
        cylinder(d1 = board_standoff_d + 4, d2 = board_standoff_d, h = 2);   // flared base
    }
}

module board_standoff_hole(p, z0, floor_t) {
    hd  = board_hardware == "insert" ? insert_hole_d : self_tap_hole_d;
    dep = min(board_hardware == "insert" ? insert_depth : 8, board_standoff_h + floor_t - 1);
    translate([p[0], p[1], z0 + board_standoff_h - dep]) cylinder(d = hd, h = dep + 1);
}

// --- right-wall cable ports ---------------------------------------------------
// 2D shapes in the wall plane: local +Y = enclosure Y, local -X = enclosure +Z
module port_2d_round(d) {
    hull() {
        circle(d = d);
        if (teardrop_ports) translate([-d / 2 * sqrt(2), 0]) square(0.01, center = true);
    }
}

module port_2d_slot(w, h) {
    r = min(2, h / 2 - 0.1);
    offset(r = r) square([h - 2 * r, w - 2 * r], center = true);
}

module wall_port(yz) {
    translate([W - wall - 1, yz[0], yz[1]]) rotate([0, 90, 0])
        linear_extrude(height = wall + 2) children();
}

// The whole shell as one piece; segments are cut from it.
module shell_body() {
    difference() {
        union() {
            difference() {
                linear_extrude(height = D) rrect(W, H, corner_r);
                rect_slab(wall, wall, back_t, D);
            }
            front_rim();
            for (p = board_pts) board_standoff(p, back_t);
            for (s = standoffs)
                translate([seg_centre(s[0]) + s[1], s[2], back_t - 0.01])
                    cylinder(d = 8, h = s[3] + 0.01);
        }
        for (p = bezel_pts) rim_fastener_cut(p);
        for (p = board_pts) board_standoff_hole(p, back_t, back_t);
        for (s = standoffs)
            translate([seg_centre(s[0]) + s[1], s[2], back_t + s[3] - insert_depth])
                cylinder(d = insert_hole_d, h = insert_depth + 1);
        if (finger_notches) for (side = [0, 1]) finger_notch(side);
        if (vents) vent_cuts();
        for (c = back_cutouts) back_cutout(c);
        if (keyholes) for (kx = [keyhole_inset, W - keyhole_inset]) keyhole(kx);
        if (ports_on) {
            wall_port(usb_yz) port_2d_slot(usb_hole_w, usb_hole_h);
            wall_port(bar_yz) port_2d_round(barrel_hole_d);
        }
    }
}

// --- segment joints ---------------------------------------------------------
// side = -1: lug on the left segment (screw head side)
// side = +1: lug on the right segment (insert or nut side)
module lugs(s, side) {
    for (y = lug_ys)
        translate([side > 0 ? s : s - lug_len, y - lug_size / 2 - 0.01, back_t - 0.01])
            cube([lug_len, lug_size + 0.02, lug_size + 0.01]);
}

module lug_holes(s, side) {
    for (y = lug_ys) {
        if (side < 0) {
            translate([s - lug_len - 1, y, lug_z]) xcyl(screw_clear_d, lug_len + 2, 24);
        } else if (joint_hardware == "nut") {
            translate([s - 1, y, lug_z]) xcyl(screw_clear_d, lug_len + 2, 24);
            // hex pocket with a point on top, so it bridges cleanly
            translate([s + lug_len - nut_t - 0.4, y, lug_z])
                xcyl((nut_af + 0.2) / cos(30), nut_t + 1.4, 6);
        } else {
            // insert is pressed in from the seam face before assembly
            translate([s - 1, y, lug_z]) xcyl(insert_hole_d, insert_depth + 1, 24);
        }
    }
}

module tongue(s) {
    for (yc = [wall / 2, H - wall / 2])
        translate([s - 0.01, yc - tongue_w / 2, 0])
            cube([tongue_len + 0.01, tongue_w, D - 3]);
}

module groove(s) {
    for (yc = [wall / 2, H - wall / 2])
        translate([s - 0.01, yc - tongue_w / 2 - tongue_clear, -1])
            cube([tongue_len + 2 * tongue_clear + 0.01, tongue_w + 2 * tongue_clear,
                  D - 3 + tongue_clear + 1]);
}

module shell_segment(i) {
    s0 = seams[i];
    s1 = seams[i + 1];
    difference() {
        union() {
            intersection() {
                shell_body();
                translate([s0, -1, -1]) cube([s1 - s0, H + 2, D + 2]);
            }
            if (i > 0) lugs(s0, 1);
            if (i < n_seg - 1) {
                lugs(s1, -1);
                if (tongues) tongue(s1);
            }
        }
        if (i > 0) {
            lug_holes(s0, 1);
            if (tongues) groove(s0);
        }
        if (i < n_seg - 1) lug_holes(s1, -1);
    }
}

// ================================================================== bezel ====
// Local Z: 0 = back face (sits on the rim), bezel_t = visible front face.
module bezel_fastener_cut(p) {
    if (bezel_fastener == "magnet") {
        translate([p[0], p[1], -1])
            cylinder(d = magnet_d + 2 * magnet_clear, h = 1 + magnet_h + magnet_clear);
    } else {
        translate([p[0], p[1], -lip_h - 1]) cylinder(d = screw_clear_d, h = bezel_t + lip_h + 2);
        if (countersink) {
            csk_h = (csk_d - screw_clear_d) / 2;
            translate([p[0], p[1], bezel_t - csk_h])
                cylinder(d1 = screw_clear_d, d2 = csk_d, h = csk_h + 0.01);
            translate([p[0], p[1], bezel_t]) cylinder(d = csk_d, h = 1);
        }
    }
}

module bezel_full() {
    difference() {
        union() {
            linear_extrude(height = bezel_t) rrect(W, H, corner_r);
            if (lip_h > 0) difference() {           // clamp lip, touches only the acrylic
                rect_slab(c0 + 0.5, c0 + 0.5, -lip_h, lip_h + 0.01);
                rect_slab(ox, oy, -lip_h - 1, lip_h + 2);
            }
        }
        rect_slab(ox, oy, -lip_h - 1, bezel_t + lip_h + 2);        // window
        if (bezel_chamfer > 0) hull() {                            // window chamfer
            rect_slab(ox, oy, bezel_t - bezel_chamfer, 0.01);
            rect_slab(ox - bezel_chamfer - 0.5, oy - bezel_chamfer - 0.5, bezel_t + 0.5, 0.01);
        }
        for (p = bezel_pts) bezel_fastener_cut(p);
    }
}

module bezel_piece(j) {
    g0 = j > 0 ? bezel_seam_gap / 2 : 0;
    g1 = j < n_bz - 1 ? bezel_seam_gap / 2 : 0;
    intersection() {
        bezel_full();
        translate([bz[j] + g0, -1, -lip_h - 1])
            cube([bz[j + 1] - bz[j] - g0 - g1, H + 2, bezel_t + lip_h + 2]);
    }
}

// flipped so the visible face is on the bed
module bezel_piece_print(j) {
    translate([0, H, bezel_t]) rotate([180, 0, 0]) translate([-bz[j], 0, 0]) bezel_piece(j);
}

// ======================================================== board models ====
// Rough stand-ins for the assembly view only (PCB + the bulky connectors).
module parts_boxes(list) {
    for (q = list) translate([q[0], q[1], pcb_t]) cube([q[2], q[3], q[4]]);
}

module driver_model() {
    color("SeaGreen") difference() {
        cube([DRV_SIZE[0], DRV_SIZE[1], pcb_t]);
        for (h = DRV_HOLES) translate([h[0], h[1], -1]) cylinder(d = 3.2, h = pcb_t + 2, $fn = 16);
    }
    color("Black") parts_boxes(concat(
        [[DRV_OUT[0] - 4.5, DRV_OUT[1] - 8.5, 9, 17, 9],       // J20 output
         [DRV_IN[0] - 4.5, DRV_IN[1] - 8.5, 9, 17, 9],         // J19 input
         [83.82, 20.1, 30.48, 8, 10]],                         // power terminals
        [for (x = DRV_MOTOR_X)  [x - 7.45, 23.8, 14.9, 5.75, 7]],
        [for (x = DRV_SENSOR_X) [x - 3.8, 7.6, 7.6, 2.6, 8.5]]));
}

module buddy_model() {
    td_z = tdisplay_usb_h - 3.2;          // underside of the T-Display above the Buddy PCB
    color("SeaGreen") difference() {
        linear_extrude(height = pcb_t) rrect(BUD_SIZE[0], BUD_SIZE[1], BUD_R);
        for (h = BUD_HOLES) translate([h[0], h[1], -1]) cylinder(d = 3.2, h = pcb_t + 2, $fn = 16);
    }
    color("Black") parts_boxes([
        [BUD_OUT[0] - 4.5, BUD_OUT[1] - 8.5, 9, 17, 9],                  // J1 output
        [BUD_PWR[0] - 4, BUD_PWR[1] - 7.62, 8, 15.24, 10],               // J2 power
        [BUD_TD[0] + 6.27, 39.37, 30.48, 2.54, td_z],                    // T-Display sockets
        [BUD_TD[0] + 6.27, 16.51, 30.48, 2.54, td_z],
        [BUD_BARREL[0] - 4.5, BUD_BARREL[1], 9, 14.4, 11]]);             // barrel jack
    color("DarkSlateGray") translate([BUD_TD[0], BUD_TD[1], pcb_t + td_z]) cube([BUD_TD[2], BUD_TD[3], 1.6]);
    color("Black") translate([BUD_TD[0] + 8, BUD_TD[1] + 3, pcb_t + td_z + 1.6]) cube([34, BUD_TD[3] - 6, 1.6]);
    color("Silver") translate([BUD_USB[0] - 7.3, BUD_USB[1] - 4.5, pcb_t + tdisplay_usb_h - 1.6])
        cube([7.3, 9, 3.2]);
}

module board_model(b) {
    c = b[0];
    s = b[1];
    translate([c[0], c[1], back_t + board_standoff_h]) rotate([0, 0, b[2]])
        translate([-s[0] / 2, -s[1] / 2, 0]) {
            if (b[4] == "Buddy") buddy_model();
            else driver_model();
        }
}

// ============================================================= test parts ====
// Short slices of the first seam: tongue/groove and lug fit
module joint_test() {
    if (n_seg < 2) {
        echo("joint_test needs at least 2 shell segments");
    } else {
        s = seams[1];
        zcap = back_t + lug_size + 4;
        translate([-(s - 20), 0, 0]) intersection() {
            shell_segment(0);
            translate([s - 20, -1, -1]) cube([20 + tl + 1, H + 2, zcap + 1]);
        }
        translate([-(s - 20) + 15, 0, 0]) intersection() {
            shell_segment(1);
            translate([s, -1, -1]) cube([20, H + 2, zcap + 1]);
        }
    }
}

// Front-left corner of the shell (pocket, seat, insert, notch) + matching bezel corner
module corner_test() {
    zc = z_ch - 2;
    cx = 50;
    cy = H / 2 + notch_w / 2 + 6;
    translate([0, 0, -zc]) intersection() {
        shell_segment(0);
        translate([-1, -1, zc]) cube([cx + 1, cy + 1, D]);
    }
    translate([cx + 10, 0, 0]) intersection() {
        bezel_piece_print(0);
        translate([-1, -1, -1]) cube([cx + 1, cy + 1, bezel_t + lip_h + 2]);
    }
}

// The bit of the right wall with both cable ports (prints back-down, like the real part)
module port_test() {
    y0 = max(0, min(usb_yz[0] - usb_hole_w / 2, bar_yz[0] - barrel_hole_d / 2) - 8);
    y1 = min(H, max(usb_yz[0] + usb_hole_w / 2, bar_yz[0] + barrel_hole_d / 2) + 8);
    z1 = max(usb_yz[1] + usb_hole_h / 2, bar_yz[1] + bar_top) + 5;
    translate([-(W - 15), -y0, 0]) intersection() {
        shell_segment(n_seg - 1);
        translate([W - 15, y0, -1]) cube([16, y1 - y0, z1 + 1]);
    }
}

// A thin frame with one board's standoff pattern: check hole spacing and inserts
module standoff_test(k) {
    s  = k == 0 ? DRV_SIZE : BUD_SIZE;
    hs = k == 0 ? DRV_HOLES : BUD_HOLES;
    plate = 2;
    difference() {
        union() {
            translate([-3, -3, 0]) cube([s[0] + 6, s[1] + 6, plate]);
            for (h = hs) board_standoff(h, plate);
        }
        for (h = hs) board_standoff_hole(h, plate, plate);
        translate([12, 12, -1]) cube([s[0] - 24, s[1] - 24, plate + 2]);
    }
}

// =============================================================== assembly ====
module assembly() {
    rotate([90, 0, 0]) {                     // stand it up, front facing -Y
        for (i = [0:1:n_seg - 1])
            translate([i * explode, 0, 0])
                color(i % 2 == 0 ? "SteelBlue" : "LightSteelBlue") shell_segment(i);
        if (show_boards) for (b = boards_all) board_model(b);
        if (show_panel)
            translate([explode * (n_seg - 1) / 2, 0, explode])
                color([0.75, 0.88, 1, 0.45])
                    translate([c0, c0, zf]) cube([panel_w, panel_h, panel_t]);
        for (j = [0:1:n_bz - 1])
            translate([j * explode, 0, D + 2 * explode])
                color(j % 2 == 0 ? "DimGray" : "Gray") bezel_piece(j);
        if (show_module_envelope)
            %translate([c0 + margin_side, c0 + margin_tb, zf - module_depth])
                cube([panel_w - 2 * margin_side, panel_h - 2 * margin_tb, module_depth]);
    }
}

// ================================================================= output ====
if (part == "assembly") {
    assembly();
} else if (part == "shell_segment") {
    assert(index < n_seg, str("index must be below ", n_seg));
    translate([-seams[index], 0, 0]) shell_segment(index);
} else if (part == "bezel_piece") {
    assert(index < n_bz, str("index must be below ", n_bz));
    bezel_piece_print(index);
} else if (part == "joint_test") {
    joint_test();
} else if (part == "corner_test") {
    corner_test();
} else if (part == "port_test") {
    assert(ports_on, "port_test needs ports = true (and the Buddy, or manual port positions)");
    port_test();
} else if (part == "standoff_test") {
    assert(index <= 1, "standoff_test: index 0 = Driver, 1 = Buddy");
    standoff_test(index);
}
