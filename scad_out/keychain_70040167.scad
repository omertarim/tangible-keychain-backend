$fn=96;
thickness_mm = 4.2;
pts = [[-10.6973, 11.3851], [-2.9162, 14.0926], [-8.8221, -1.4438], [1.3202, 1.7226], [0.1521, -14.6299], [9.8967, -0.7372], [1.8694, -1.1026], [5.452, 14.5243], [-2.7458, 14.1257], [-3.3457, 17.212], [-14.9345, 16.1543]];
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
  translate([6.5, 4.8, thickness_mm-engrave_depth]) cylinder(h=engrave_depth+0.2, r=1.7034);
  translate([-6.5, 4.8, thickness_mm-engrave_depth]) cylinder(h=engrave_depth+0.2, r=1.7034);

  // mouth arc band (2D ring section extruded shallow)
  translate([0, -7.5, thickness_mm-engrave_depth])
    linear_extrude(height=engrave_depth+0.2)
      intersection(){
        // limit width
        square([13.9165, 13.9165], center=true);
        difference(){
          translate([0,5.5]) circle(r=11.6503);
          translate([0,5.5]) circle(r=10.0503);
        }
      };
}
difference(){
  body();
  // keychain hole (exactly 1)
  translate([hole[0], hole[1], -1]) cylinder(h=thickness_mm+2, r=hole[2]);
}