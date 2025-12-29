$fn=96;
thickness_mm = 4.2;
pts = [[-7.978, 13.0617], [-3.6502, 15.4202], [-6.0278, -1.0518], [0.8209, 1.7511], [1.078, -15.8737], [6.2181, -2.1053], [1.3703, -1.3648], [3.0039, 14.9981], [-2.7471, 15.5794], [-3.2984, 18.706], [-11.2661, 18.8964]];
hole = [0.0, 16.0, 2.6];
offset_r = 0.261;
engrave_depth = 0.9;
module shape2d(){
  // CGAL clean + controlled smooth/sharp
  offset(r=offset_r) offset(r=-offset_r)
    polygon(points=pts, paths=[[for(i=[0:len(pts)-1]) i]]);
}
module body(){
  linear_extrude(height=thickness_mm, convexity=10)
    shape2d();
}
module face_engrave(){
  // eyes
  translate([6.5, 4.8, thickness_mm-engrave_depth]) cylinder(h=engrave_depth+0.2, r=2.8189);
  translate([-6.5, 4.8, thickness_mm-engrave_depth]) cylinder(h=engrave_depth+0.2, r=2.8189);

  // mouth arc band (2D ring section extruded shallow)
  translate([0, -5.5, thickness_mm-engrave_depth])
    linear_extrude(height=engrave_depth+0.2)
      intersection(){
        // limit width
        square([9.9325, 9.9325], center=true);
        difference(){
          translate([0,-5.5]) circle(r=13.1785);
          translate([0,-5.5]) circle(r=11.5785);
        }
      };
}
difference(){
  body();
  // keychain hole (exactly 1)
  translate([hole[0], hole[1], -1]) cylinder(h=thickness_mm+2, r=hole[2]);
}