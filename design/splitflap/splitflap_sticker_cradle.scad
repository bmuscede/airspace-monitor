// ============================================================
//  Splitflap letter-sticker cradle
//  For Scott Bezek's splitflap (v2). Holds two flaps exactly as
//  they hang on the spool: pin edges meeting at the seam, top flap
//  face up, bottom flap = the previous top flap flipped down.
//  One sticker spans both flaps, then gets cut along the seam.
//
//  Per letter:
//    1. TOP pocket: new blank, face up.  BOTTOM pocket: last top
//       flap, flipped down over the seam (blank back facing up).
//       Slide both so the pin edges butt together at the seam.
//    2. Apply the letter across both flaps, using the cap line,
//       baseline and centre ticks.
//    3. Cut the vinyl along the seam (blade runs into the channel).
//    4. Bottom flap is finished -> "done" stack, in order.
//       Flip the top flap down into the bottom pocket. New blank on top.
//  Closing the loop: start with the character AFTER the blank, using a
//  fresh flap in the bottom pocket (its face-down side is the blank's
//  top half). After the last character, leave the top flap as-is; its
//  empty back is the blank's bottom half. Don't flip it down.
// ============================================================

/* [Flaps - measure yours] */
flap_w = 54.0;       // width across the pins
flap_h = 42.8;       // half a CR80 card (85.6 / 2)
flap_t = 0.76;       // 30 mil PVC

/* [Letters] */
letter_h      = 76.2;  // cap height of your stickers (3" = 76.2)
letter_offset = 0;     // shift letter centre up (+) / down (-) from the seam

/* [Cradle] */
lanes        = 4;      // side-by-side cradles; 4 fit on a 250 mm bed
fit_w        = 0.3;    // total clearance across the pocket
fit_h        = 0.4;    // total clearance along both flaps (lets you butt the seam)
pocket_depth = 0.6;    // MUST be < flap_t so the flaps stand proud
base_t       = 4.0;
end_margin   = 24;     // room beyond the flaps for a tape hinge + labels
side_margin  = 7;
lane_gap     = 5;      // web between lanes
corner_r     = 4;

/* [Knife channel at the seam] */
knife_w = 1.2;
knife_d = 1.5;         // depth below the pocket floor

/* [Guides] */
line_w      = 0.8;
line_d      = 0.6;
centre_tick = 8;

/* [Finger scoops] */
scoop_r        = 8;
scoop_depth    = 2.5;  // depth at the centre of the dish
scoop_undercut = 2.5;  // how far the dish reaches under each flap's free edge
scoop_x        = 13;   // offset from lane centre (keeps the centre tick clear)

/* [Labels] */
labels      = true;
label_size  = 3.5;
label_depth = 0.6;
label_font  = "Liberation Sans:style=Bold";

/* [Hidden] */
$fn = 96;
eps = 0.01;

pw    = flap_w + fit_w;          // pocket width
ph    = 2 * flap_h + fit_h;      // pocket length (both flaps, seam at y = 0)
pitch = pw + lane_gap;
W     = lanes * pw + (lanes - 1) * lane_gap + 2 * side_margin;
L     = ph + 2 * end_margin;
top_z = base_t;

assert(pocket_depth < flap_t, "pocket_depth must be less than flap_t so the flaps stand proud");
assert(letter_h / 2 + abs(letter_offset) < flap_h, "letter does not fit on the flaps");

echo(str("Cradle footprint: ", W, " x ", L, " mm"));
if (W > 250 || L > 250) echo("WARNING: larger than an A1 bed (250 x 250)");

function lane_x(i) = (i - (lanes - 1) / 2) * pitch;

module rounded_rect(size, r) {
    offset(r = r) offset(delta = -r) square(size, center = true);
}

// 2D footprint of every pocket
module pockets_2d() {
    for (i = [0 : lanes - 1])
        translate([lane_x(i), 0]) square([pw, ph], center = true);
}

module label(s, txt) {
    translate([0, s * (ph / 2 + end_margin - label_size - 2), top_z - label_depth])
        linear_extrude(label_depth + eps)
            text(txt, size = label_size, font = label_font,
                 halign = "center", valign = "center");
}

module cradle() {
    difference() {
        linear_extrude(base_t) rounded_rect([W, L], corner_r);

        // Flap pockets
        translate([0, 0, top_z - pocket_depth])
            linear_extrude(pocket_depth + eps) pockets_2d();

        // Knife channel along the seam; runs the full width so the
        // blade can start and finish in the rim
        translate([0, 0, top_z - pocket_depth - knife_d])
            linear_extrude(pocket_depth + knife_d + eps)
                square([W + 2 * eps, knife_w], center = true);

        // Cap line and baseline, rim only (never grooves the pocket floor)
        for (y = [letter_offset + letter_h / 2, letter_offset - letter_h / 2])
            translate([0, 0, top_z - line_d])
                linear_extrude(line_d + eps)
                    difference() {
                        translate([0, y]) square([W + 2 * eps, line_w], center = true);
                        pockets_2d();
                    }

        // Centre ticks beyond both ends of each pocket
        for (i = [0 : lanes - 1], s = [-1, 1])
            translate([lane_x(i), s * (ph / 2 + centre_tick / 2), top_z - line_d])
                linear_extrude(line_d + eps)
                    square([line_w, centre_tick + eps], center = true);

        // Finger scoops under each flap's free (rounded-corner) edge
        for (i = [0 : lanes - 1], s = [-1, 1])
            translate([lane_x(i) + scoop_x, s * (ph / 2 + scoop_r - scoop_undercut), top_z])
                scale([1, 1, scoop_depth / scoop_r]) sphere(r = scoop_r);

        // Process reminders
        if (labels) {
            label( 1, "TOP: NEW BLANK");
            label(-1, "BOTTOM: LAST TOP, FLIPPED");
        }
    }
}

cradle();
