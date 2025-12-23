// scad/keychain_template.scad
$fn = 160;

// --------------------
// Parameters (overridden by -D)
// --------------------
base_form = "circle";              // circle | rounded_polygon | heart | droplet | bolt | wave | sun | star | flame | spike
size_mm = 38;
thickness_mm = 4.0;

rounded_polygon_sides = 8;
fillet_mm = 2.0;

twist_deg = 0;

// Organic edge (some shapes use this subtly)
noise_amp_mm = 0.0;                // 0.. ~2.5
noise_seed = 1337;

// symmetry count (used by wavy circle/wave/sun/star/spike)
sym_n = 7;

// Holes: [[x,y,r], ...]
holes = [];

// --------------------
// Helpers
// --------------------
function clamp(x,a,b) = x < a ? a : (x > b ? b : x);
function ph(seed) = (seed % 360);

module holes_2d(holes=[]) {
    for (h = holes) translate([h[0], h[1]]) circle(r=h[2]);
}

// Generic wavy circle for “organic” look
module wavy_circle_2d(d=38, amp=1.0, n=7, seed=1337, steps=240) {
    r0 = d/2;
    phase = ph(seed);
    pts = [
        for (i=[0:steps-1])
            let(
                t = 360*i/steps,
                wob = amp * (0.70*sin(n*t + phase) + 0.30*sin((n*2+1)*t + phase*0.37)),
                rr = r0 + wob
            )
            [ rr*cos(t), rr*sin(t) ]
    ];
    polygon(points=pts);
}

// Rounded polygon base (soft corners)
module rounded_poly_2d(d=38, sides=8, fillet=2.0) {
    r = d/2;
    pts = [ for (i=[0:sides-1]) [ r*cos(360*i/sides), r*sin(360*i/sides) ] ];
    offset(r=fillet) offset(delta=-fillet) polygon(points=pts);
}

// HEART (iconic)
module heart_2d(d=38) {
    // Heart built in ~40 units width, then scaled
    s = d / 40;
    scale([s,s]) union() {
        translate([-10, 8]) circle(r=12);
        translate([ 10, 8]) circle(r=12);
        polygon(points=[[ -22, 8], [ 22, 8], [ 0, -26]]);
    }
}

// DROPLET (teardrop)
module droplet_2d(d=38) {
    // top round + bottom point
    s = d / 40;
    scale([s,s]) union() {
        translate([0, 8]) circle(r=14);
        polygon(points=[[ -14, 8], [ 14, 8], [ 0, -26]]);
    }
}

// BOLT (lightning)
module bolt_2d(d=38) {
    // simple lightning polygon (scaled)
    s = d / 40;
    scale([s,s]) polygon(points=[
        [-6, 18], [ 8, 18], [ 0, 2],
        [10, 2], [-8, -22], [-2, -4],
        [-12, -4]
    ]);
}

// WAVE (calm)
module wave_2d(d=38, amp=1.0, n=6, seed=1337) {
    // Rounded “pebble” base with a gentle wavy offset on one axis
    // Implemented as wavy circle but with lower amp; looks calm & smooth
    wavy_circle_2d(d=d, amp=amp, n=n, seed=seed, steps=220);
}

// SUN (joy)
module sun_2d(d=38, rays=10, seed=1337) {
    // radial spikes but rounded-ish: alternate radii
    r0 = d/2 * 0.78;
    r1 = d/2 * 1.00;
    steps = rays * 2;
    phase = ph(seed);
    pts = [
        for (i=[0:steps-1])
            let(
                t = 360*i/steps + phase,
                rr = (i % 2 == 0) ? r1 : r0
            )
            [ rr*cos(t), rr*sin(t) ]
    ];
    offset(r=fillet_mm) offset(delta=-fillet_mm) polygon(points=pts);
}

// STAR (surprise)
module star_2d(d=38, pointsN=10, seed=1337) {
    // 5-point star by default (pointsN=10 means 5 outer+inner)
    r1 = d/2 * 1.00;
    r0 = d/2 * 0.45;
    steps = pointsN;
    phase = ph(seed);
    pts = [
        for (i=[0:steps-1])
            let(
                t = 360*i/steps + phase,
                rr = (i % 2 == 0) ? r1 : r0
            )
            [ rr*cos(t), rr*sin(t) ]
    ];
    offset(r=fillet_mm) offset(delta=-fillet_mm) polygon(points=pts);
}

// FLAME (anger)
module flame_2d(d=38, seed=1337) {
    // stylized flame silhouette
    s = d / 40;
    scale([s,s]) polygon(points=[
        [0, 20],
        [8, 10],
        [6, 2],
        [12, -4],
        [6, -18],
        [0, -26],
        [-6, -18],
        [-12, -4],
        [-6, 2],
        [-8, 10]
    ]);
    // soften corners
    // (offset done at caller)
}

// SPIKE (fear)
module spike_2d(d=38, spikes=9, seed=1337) {
    // similar to sun but sharper spikes
    r0 = d/2 * 0.65;
    r1 = d/2 * 1.05;
    steps = spikes * 2;
    phase = ph(seed);
    pts = [
        for (i=[0:steps-1])
            let(
                t = 360*i/steps + phase,
                rr = (i % 2 == 0) ? r1 : r0
            )
            [ rr*cos(t), rr*sin(t) ]
    ];
    polygon(points=pts);
}

// --------------------
// Base selector
// --------------------
module base_2d() {
    amp = clamp(noise_amp_mm, 0, 3);
    n   = max(3, sym_n);

    if (base_form == "circle") {
        if (amp > 0.001) wavy_circle_2d(d=size_mm, amp=amp, n=n, seed=noise_seed);
        else circle(d=size_mm);
    }
    else if (base_form == "rounded_polygon") {
        rounded_poly_2d(d=size_mm, sides=max(3,rounded_polygon_sides), fillet=fillet_mm);
    }
    else if (base_form == "heart") {
        heart_2d(d=size_mm);
    }
    else if (base_form == "droplet") {
        droplet_2d(d=size_mm);
    }
    else if (base_form == "bolt") {
        // lightning should be slightly softened
        offset(r=fillet_mm) offset(delta=-fillet_mm) bolt_2d(d=size_mm);
    }
    else if (base_form == "wave") {
        // calm wave: low amp looks good
        wave_2d(d=size_mm, amp=max(0.3, amp), n=n, seed=noise_seed);
    }
    else if (base_form == "sun") {
        sun_2d(d=size_mm, rays=max(7,n), seed=noise_seed);
    }
    else if (base_form == "star") {
        star_2d(d=size_mm, pointsN=10, seed=noise_seed);
    }
    else if (base_form == "flame") {
        offset(r=fillet_mm) offset(delta=-fillet_mm) flame_2d(d=size_mm, seed=noise_seed);
    }
    else if (base_form == "spike") {
        // keep sharp: only tiny fillet if you want
        spike_2d(d=size_mm, spikes=max(7,n), seed=noise_seed);
    }
    else {
        // default fallback
        circle(d=size_mm);
    }
}

// --------------------
// Model
// --------------------
difference() {
    linear_extrude(height=thickness_mm, twist=twist_deg, convexity=10)
        base_2d();

    if (len(holes) > 0) {
        translate([0,0,-1])
            linear_extrude(height=thickness_mm+2, convexity=10)
                holes_2d(holes);
    }
}
