// Cart-double pendulum desktop assembly
// Units: millimeters. Open in OpenSCAD or any SCAD-compatible CAD.
// Matches the interactive viewer on the Supply Keychain page.

$fn = 48;

rail_len = 400;
rail_w = 22;
rail_h = 10;

cart_l = 80;
cart_w = 52;
cart_h = 22;

link1_l = 180;
link1_w = 16;
link1_t = 8;

link2_l = 120;
link2_w = 12;
link2_t = 6;

module rail() {
  color("#9aa7b5")
    translate([0, 0, rail_h/2])
      cube([rail_len, rail_w, rail_h], center=true);
}

module cart() {
  color("#d8dee8")
    translate([0, 0, rail_h + cart_h/2])
      cube([cart_l, cart_w, cart_h], center=true);
}

module teensy() {
  color("#1f7a3a")
    translate([18, 0, rail_h + cart_h + 2])
      cube([61, 18, 4], center=true);
}

module amt102() {
  color("#2b2b2b")
    translate([-28, cart_w/2 + 6, rail_h + cart_h/2])
      rotate([90, 0, 0])
        cylinder(h=10, d=29, center=true);
}

module slip_ring() {
  color("#c9a227") {
    cylinder(h=20, d=12, center=true);
    for (z = [-6, 0, 6])
      translate([0, 0, z])
        cylinder(h=1.2, d=13.4, center=true);
  }
}

module as5047p() {
  color("#163024")
    cube([20, 20, 2], center=true);
}

module link1() {
  color("#7f8b99")
    translate([0, 0, link1_l/2])
      cube([link1_w, link1_t, link1_l], center=true);
}

module link2() {
  color("#a3adb8")
    translate([0, 0, link2_l/2])
      cube([link2_w, link2_t, link2_l], center=true);
}

module assembly() {
  rail();
  cart();
  teensy();
  amt102();

  translate([0, 0, rail_h + cart_h]) {
    slip_ring();
    translate([14, 0, 0]) as5047p();
    translate([0, 0, 10]) {
      link1();
      translate([0, 0, link1_l]) {
        slip_ring();
        translate([12, 0, 0]) as5047p();
        rotate([0, 25, 0])
          link2();
      }
    }
  }
}

assembly();
