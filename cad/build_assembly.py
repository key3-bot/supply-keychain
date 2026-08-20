# FreeCAD 1.1 — buildable cart-double pendulum (side-hang, fitted joints).
# Local-frame STLs; viewer FK. Units mm.

import json
import math
import os
import sys
from pathlib import Path

import FreeCAD as App
import Mesh
import Part

try:
    import MeshPart
except Exception:
    MeshPart = None

ROOT = os.environ.get("CAD_ROOT", "/home/node/supply-keychain/cad")
sys.path.insert(0, ROOT)
import pendulum_geom as G

EXPORTS = os.path.join(ROOT, "exports")
DOC_PATH = os.path.join(ROOT, "cart-double-pendulum.FCStd")
os.makedirs(EXPORTS, exist_ok=True)


def solid_to_obj(doc, name, shape, color):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    if hasattr(obj, "ViewObject") and obj.ViewObject:
        obj.ViewObject.ShapeColor = color
    return obj


def mesh_export(shape, path, deflection=0.09):
    if MeshPart is not None:
        try:
            mesh = MeshPart.meshFromShape(
                Shape=shape,
                LinearDeflection=deflection,
                AngularDeflection=0.45,
                Relative=False,
            )
            mesh.write(path)
            print("wrote", path, "facets", mesh.CountFacets, flush=True)
            return
        except Exception as exc:
            print("MeshPart failed, tessellate:", exc, flush=True)
    mesh = Mesh.Mesh()
    mesh.addFacets(shape.tessellate(deflection))
    mesh.write(path)
    print("wrote", path, "facets", mesh.CountFacets, "(tessellate)", flush=True)


def fuse_all(shapes):
    out = None
    for s in shapes:
        if s is None:
            continue
        try:
            if s.isNull():
                continue
        except Exception:
            pass
        out = s if out is None else out.fuse(s)
    if out is None:
        raise RuntimeError("fuse_all empty")
    try:
        out = out.removeSplitter()
    except Exception:
        pass
    return out


def cyl(r, h, x=0, y=0, z=0, axis="z"):
    if axis == "z":
        return Part.makeCylinder(r, h, App.Vector(x, y, z))
    if axis == "y":
        c = Part.makeCylinder(r, h, App.Vector(0, 0, 0), App.Vector(0, 1, 0))
        c.translate(App.Vector(x, y, z))
        return c
    if axis == "x":
        c = Part.makeCylinder(r, h, App.Vector(0, 0, 0), App.Vector(1, 0, 0))
        c.translate(App.Vector(x, y, z))
        return c
    raise ValueError(axis)


def box(dx, dy, dz, x=0, y=0, z=0):
    return Part.makeBox(dx, dy, dz, App.Vector(x, y, z))


def bearing_608():
    od, id_, w = G.BEARING_OD / 2.0, G.BEARING_ID / 2.0, G.BEARING_W
    outer = cyl(od, w, 0, -w / 2.0, 0, "y")
    inner = cyl(id_ + 0.1, w + 0.4, 0, -w / 2.0 - 0.2, 0, "y")
    race = outer.cut(inner)
    groove = cyl(od + 0.05, 1.3, 0, -0.65, 0, "y").cut(
        cyl(od - 1.0, 1.5, 0, -0.75, 0, "y")
    )
    balls = []
    path_r = (od + id_) * 0.5
    for i in range(8):
        a = i * (2 * math.pi / 8)
        balls.append(
            Part.makeSphere(1.55, App.Vector(path_r * math.cos(a), 0, path_r * math.sin(a)))
        )
    return fuse_all([race, groove] + balls)


def slip_ring():
    body = cyl(G.SLIP_OD / 2.0, G.SLIP_L, 0, -G.SLIP_L / 2.0, 0, "y")
    bands = []
    for t in (-0.36, -0.18, 0.0, 0.18, 0.36):
        bands.append(cyl(G.SLIP_OD / 2.0 + 0.35, 0.85, 0, t * G.SLIP_L - 0.4, 0, "y"))
    bands.append(cyl(G.SLIP_OD / 2.0 + 0.75, 1.1, 0, -G.SLIP_L / 2.0, 0, "y"))
    bands.append(cyl(G.SLIP_OD / 2.0 + 0.75, 1.1, 0, G.SLIP_L / 2.0 - 1.1, 0, "y"))
    bore = cyl(G.SLIP_BORE / 2.0, G.SLIP_L + 4, 0, -G.SLIP_L / 2.0 - 2, 0, "y")
    return fuse_all([body] + bands).cut(bore)


def magnet():
    return cyl(G.MAGNET_D / 2.0, G.MAGNET_H, 0, -G.MAGNET_H / 2.0, 0, "y")


def collar():
    body = cyl(6.5, 5.0, 0, -2.5, 0, "y").cut(
        cyl(G.SHAFT_D / 2.0 + 0.05, 6, 0, -3, 0, "y")
    )
    body = body.cut(cyl(1.15, 3.5, 0, -1.0, 3.5, "z"))
    return body


def shaft(length):
    return cyl(G.SHAFT_D / 2.0, length, 0, -length / 2.0, 0, "y")


def as5047p():
    bw, bh, bt = G.AS_BOARD
    board = box(bw, bt, bh, -bw / 2.0, 0.0, -bh / 2.0)
    for hx, hz in G.AS_HOLES:
        board = board.cut(
            cyl(G.AS_HOLE_R, bt + 1.2, hx - bw / 2.0, -0.6, hz - bh / 2.0, "y")
        )
    chip = box(5.0, 1.0, 6.4, -2.5, bt, -3.2)
    keeper = cyl(3.6, 0.5, 0, bt + 1.0, 0, "y")
    return board.fuse(chip).fuse(keeper)


def amt102():
    body = cyl(G.AMT_R, G.AMT_BODY_H, 0, 0, 0, "y")
    for i in range(8):
        a = i * math.pi / 4
        body = body.cut(
            cyl(
                2.0,
                G.AMT_BODY_H + 1,
                (G.AMT_R - 0.4) * math.cos(a),
                -0.5,
                (G.AMT_R - 0.4) * math.sin(a),
                "y",
            )
        )
    base = cyl(G.AMT_R + 0.8, G.AMT_BASE_H, 0, -G.AMT_BASE_H, 0, "y")
    hub = cyl(5.5, 7.0, 0, -3.5, 0, "y")
    plate = box(36, 2, 36, -18, -G.AMT_BASE_H - 2, -18)
    for hx, hz in ((-13, -13), (13, -13), (-13, 13), (13, 13)):
        plate = plate.cut(cyl(1.7, 5, hx, -G.AMT_BASE_H - 2.5, hz, "y"))
    return fuse_all([body, base, hub, plate])


def teensy():
    tw, th, tt = G.TEENSY
    board = box(tw, th, tt, -tw / 2, -th / 2, 0)
    usb = box(9, 7.5, 3.2, -tw / 2 - 0.5, -3.75, tt)
    eth = box(16, 14, 12, tw / 2 - 17, -7, tt)
    mcu = box(10, 10, 1.2, -5, -5, tt)
    return fuse_all([board, usb, eth, mcu])


def hub_disk(radius, width):
    """Rotating hub, axis Y, centered on origin."""
    y0 = -width / 2.0
    disc = cyl(radius, width, 0, y0, 0, "y")
    for i in range(5):
        a = i * (2 * math.pi / 5) + 0.3
        rr = radius * 0.52
        disc = disc.cut(
            cyl(radius * 0.16, width + 1, rr * math.cos(a), y0 - 0.5, rr * math.sin(a), "y")
        )
    # shaft bore (press / clamp on shaft)
    disc = disc.cut(cyl(G.SHAFT_D / 2.0 + 0.04, width + 2, 0, y0 - 1, 0, "y"))
    # clamp slot + bolt
    disc = disc.cut(box(radius + 2, 2.0, radius + 2, 0, -1.0, -1.0))
    disc = disc.cut(cyl(1.5, width + 2, radius * 0.65, y0 - 1, 0, "y"))
    return disc


def rail():
    body = box(G.RAIL_LEN, G.RAIL_W, G.RAIL_H, -G.RAIL_LEN / 2, -G.RAIL_W / 2, 0)
    for y in (-G.RAIL_W / 2 + 4, G.RAIL_W / 2 - 7):
        body = body.cut(
            box(G.RAIL_LEN + 2, 3.0, 2.2, -G.RAIL_LEN / 2 - 1, y, G.RAIL_H - 1.8)
        )
    body = body.cut(
        box(G.RAIL_LEN + 2, 5.5, 2.8, -G.RAIL_LEN / 2 - 1, -2.75, G.RAIL_H - 4.0)
    )
    feet = []
    for x in (-G.RAIL_LEN / 2 + 18, G.RAIL_LEN / 2 - 48):
        foot = box(36, G.RAIL_FOOT_W, 5, x, -G.RAIL_FOOT_W / 2, -5)
        for by in (-G.RAIL_FOOT_W / 2 + 8, G.RAIL_FOOT_W / 2 - 8):
            foot = foot.cut(cyl(2.2, 8, x + 18, by, -6))
        feet.append(foot)
    for x in (-G.RAIL_LEN / 2, G.RAIL_LEN / 2 - 6):
        feet.append(box(6, G.RAIL_W + 8, G.RAIL_H + 4, x, -(G.RAIL_W + 8) / 2, 0))
    return body.fuse(fuse_all(feet))


def cart():
    """
    Cart + outboard shoulder cheeks on +Y face.
    Shoulder pivot at world (0, SHOULDER_Y, SHOULDER_Z) when travel=0.
    Cheeks are centered on that pivot — arms hang in plane y=SHOULDER_Y.
    """
    z0 = G.CART_Z0
    body = box(G.CART_L, G.CART_W, G.CART_H, -G.CART_L / 2, -G.CART_W / 2, z0)
    # rail tunnel
    body = body.cut(
        box(
            G.CART_L + 6,
            G.RAIL_W + 2.5,
            G.RAIL_H + 2.5,
            -G.CART_L / 2 - 3,
            -(G.RAIL_W + 2.5) / 2,
            z0 - 1.2,
        )
    )
    # rollers
    for x in (-G.CART_L / 2 + 20, G.CART_L / 2 - 20):
        for y in (-G.RAIL_W / 2 - 1, G.RAIL_W / 2 - 5):
            body = body.fuse(cyl(4.0, 6.0, x, y, z0 + 2, "y"))

    hub_w = G.SHOULDER_HUB_W
    span = G.cheek_span(hub_w)
    # Pivot in world cart frame
    py, pz = G.SHOULDER_Y, G.SHOULDER_Z
    cheek_r = 18.0  # cheek plate outer radius about pivot
    cheek_x = 20.0

    # Side bracket block from cart +Y face out to cheeks
    bracket = box(
        40.0,
        G.SIDE_BRACKET + 2.0,
        28.0,
        -20.0,
        G.CART_W / 2.0 - 2.0,
        G.CART_TOP - 10.0,
    )
    # gussets
    gusset = box(8.0, G.SIDE_BRACKET + 2.0, 20.0, -24.0, G.CART_W / 2.0 - 2.0, G.CART_TOP - 10.0)
    gusset2 = box(8.0, G.SIDE_BRACKET + 2.0, 20.0, 16.0, G.CART_W / 2.0 - 2.0, G.CART_TOP - 10.0)

    # Two cheeks centered on pivot, spanning hub gap
    # Inner faces at y = py ± hub_w/2
    cheeks = []
    for sign in (-1.0, 1.0):
        # sign=-1: −Y cheek (toward cart), sign=+1: +Y cheek (outboard)
        y_inner = py + sign * (hub_w / 2.0)
        if sign < 0:
            y0 = y_inner - G.CHEEK_T  # extends toward −Y from inner face
        else:
            y0 = y_inner
        plate = box(cheek_x * 2, G.CHEEK_T, cheek_r * 2 + 8, -cheek_x, y0, pz - cheek_r - 4)
        plate = plate.fuse(cyl(cheek_r, G.CHEEK_T, 0, y0, pz, "y"))
        # bearing bore
        plate = plate.cut(cyl(G.BEARING_OD / 2.0 + 0.04, G.CHEEK_T + 2, 0, y0 - 1, pz, "y"))
        # outer recess for bearing flange
        if sign < 0:
            plate = plate.cut(
                cyl(G.BEARING_OD / 2.0 + 0.5, 2.0, 0, y0 - 0.05, pz, "y")
            )
        else:
            plate = plate.cut(
                cyl(G.BEARING_OD / 2.0 + 0.5, 2.0, 0, y0 + G.CHEEK_T - 1.95, pz, "y")
            )
        cheeks.append(plate)

    # web between cheeks under pivot (does not block hang — hang is −Z outboard)
    web = box(16.0, hub_w, 10.0, -8.0, py - hub_w / 2.0, pz - cheek_r - 2.0)

    # Teensy standoffs on deck (away from shoulder side)
    standoffs = []
    for bx, by in ((-20, -18), (-20, 8), (20, -18), (20, 8)):
        standoffs.append(cyl(2.4, 5.0, bx, by, G.CART_TOP))
        body = body.cut(cyl(1.0, 6.0, bx, by, G.CART_TOP - 1))

    # AMT on −X face
    bracket_amt = box(8, 34, 28, -G.CART_L / 2 - 8, -17, z0 + 6)
    bracket_amt = bracket_amt.fuse(
        box(12, 34, 4, -G.CART_L / 2 - 8, -17, z0 + 30)
    )

    # cable exit toward shoulder
    body = body.cut(
        box(16, 14, 12, 10, G.CART_W / 2 - 16, G.CART_TOP - 14)
    )

    return fuse_all(
        [body, bracket, gusset, gusset2, web, bracket_amt] + cheeks + standoffs
    )


def link1():
    """
    Local: proximal hub at origin (width=SHOULDER_HUB_W), length +Z to distal clevis.
    Hub seats between cart cheeks. Clevis seats link2 hub.
    """
    hub_w = G.SHOULDER_HUB_W
    hub = hub_disk(G.LINK1_HUB_R, hub_w)

    # spar from hub out to clevis
    z0 = G.LINK1_HUB_R - 1.0
    spar_len = G.LINK1_L - z0
    spar = cyl(G.LINK1_ARM_R, spar_len - G.LINK1_CLEVIS_R * 0.35, 0, 0, z0, "z")
    sleeve = cyl(G.LINK1_ARM_R + 2.5, 18.0, 0, 0, z0, "z")
    # wire tunnel
    spar = spar.cut(cyl(2.2, spar_len - 24, 0, 0, z0 + 8, "z"))
    for z in (G.LINK1_L * 0.30, G.LINK1_L * 0.50, G.LINK1_L * 0.68):
        spar = spar.cut(cyl(3.4, G.LINK1_ARM_R * 3, -G.LINK1_ARM_R * 1.5, 0, z, "x"))

    # Distal clevis at z = LINK1_L — fork opens along Y, pin axis Y
    gap = G.LINK1_CLEVIS_GAP
    t = G.LINK1_CLEVIS_T
    R = G.LINK1_CLEVIS_R
    zc = G.LINK1_L
    tines = []
    for sign in (-1.0, 1.0):
        y_inner = sign * (gap / 2.0)
        y0 = y_inner if sign > 0 else y_inner - t
        # rectangular body + round nose, centered on pivot
        plate = box(R * 2, t, R * 2 + 6, -R, y0, zc - R - 3)
        nose = cyl(R, t, 0, y0, zc, "y")
        tine = plate.fuse(nose)
        # pin bore
        tine = tine.cut(cyl(G.SHAFT_D / 2.0 + 0.06, t + 2, 0, y0 - 1, zc, "y"))
        # bearing pocket from inner face
        if sign < 0:
            tine = tine.cut(
                cyl(G.BEARING_OD / 2.0 + 0.05, min(t - 1.0, G.BEARING_W * 0.55), 0, y_inner - min(t - 1.0, G.BEARING_W * 0.55), zc, "y")
            )
        else:
            tine = tine.cut(
                cyl(G.BEARING_OD / 2.0 + 0.05, min(t - 1.0, G.BEARING_W * 0.55), 0, y_inner, zc, "y")
            )
        tines.append(tine)

    # back spine joining tines on the spar side (−Z from pivot)
    span = gap + 2 * t
    spine = box(R * 1.1, span, 10.0, -R * 0.55, -span / 2.0, zc - R - 8.0)
    # blend from spar into spine
    blend = cyl(G.LINK1_ARM_R + 1.8, 14.0, 0, 0, zc - R - 16.0, "z")

    return fuse_all([hub, sleeve, spar, blend, spine] + tines)


def link2():
    """
    Local: proximal hub at origin (width=ELBOW_HUB_W) seats in link1 clevis.
    Spar + tip mass along +Z. This *is* the second arm — hub is the joint half.
    """
    hub_w = G.ELBOW_HUB_W
    hub = hub_disk(G.LINK2_HUB_R, hub_w)

    z0 = G.LINK2_HUB_R - 1.0
    spar_len = G.LINK2_L - z0 - G.TIP_R * 0.3
    spar = cyl(G.LINK2_ARM_R, spar_len, 0, 0, z0, "z")
    sleeve = cyl(G.LINK2_ARM_R + 2.0, 14.0, 0, 0, z0, "z")
    spar = spar.cut(cyl(1.8, spar_len - 10, 0, 0, z0 + 5, "z"))
    for z in (G.LINK2_L * 0.34, G.LINK2_L * 0.55, G.LINK2_L * 0.72):
        spar = spar.cut(cyl(2.8, G.LINK2_ARM_R * 3, -G.LINK2_ARM_R * 1.5, 0, z, "x"))

    # tip mass centered on distal end, fused through spar
    tip = Part.makeSphere(G.TIP_R, App.Vector(0, 0, G.LINK2_L))
    tip = tip.fuse(cyl(G.TIP_R * 0.85, G.TIP_H * 0.55, 0, -G.TIP_H * 0.275, G.LINK2_L, "y"))
    collar = cyl(G.LINK2_ARM_R + 1.2, 10.0, 0, 0, G.LINK2_L - G.TIP_R - 2.0, "z")

    return fuse_all([hub, sleeve, spar, collar, tip])


def joint_hardware(hub_w, for_elbow=False):
    """
    Shaft + bearings + collar + magnet + slip ring about joint origin, axis Y.
    Bearings centered in each cheek/tine.
    Local frame = joint origin (same as link proximal / clevis center).
    """
    # Bearing centers: middle of each cheek
    y_b = hub_w / 2.0 + G.CHEEK_T / 2.0
    b1 = bearing_608()
    b1.translate(App.Vector(0, -y_b, 0))
    b2 = bearing_608()
    b2.translate(App.Vector(0, y_b, 0))

    span = G.cheek_span(hub_w)
    # shaft long enough for slip ring on +Y and magnet on −Y
    shaft_len = span + G.SLIP_L + 18.0
    sh = shaft(shaft_len)

    col = collar()
    col.translate(App.Vector(0, span / 2.0 + 3.0, 0))

    mag = magnet()
    mag.translate(App.Vector(0, -span / 2.0 - 4.5, 0))

    slip = slip_ring()
    slip.translate(App.Vector(0, span / 2.0 + 5.0 + G.SLIP_L / 2.0, 0))

    return fuse_all([b1, b2, sh, col, mag, slip])


def main():
    print("FreeCAD", App.Version(), flush=True)
    print("side-hang buildable pendulum", flush=True)
    # clearance self-check
    k = G.kinematics_json()
    print("clearance", k["clearanceChecks"], "shoulder", k["shoulder"], flush=True)

    doc = App.newDocument("PendulumAssembly")
    parts = {}
    steps = [
        ("rail", rail),
        ("cart", cart),
        ("link1", link1),
        ("link2", link2),
        ("shoulder-joint", lambda: joint_hardware(G.SHOULDER_HUB_W)),
        ("elbow-joint", lambda: joint_hardware(G.ELBOW_HUB_W, for_elbow=True)),
        ("as5047p", as5047p),
        ("amt102-v", amt102),
        ("teensy-4.1", teensy),
    ]
    for name, fn in steps:
        print(name, "…", flush=True)
        parts[name] = fn()

    colors = {
        "rail": (0.55, 0.60, 0.66),
        "cart": (0.88, 0.90, 0.93),
        "link1": (0.50, 0.56, 0.62),
        "link2": (0.72, 0.48, 0.32),
        "shoulder-joint": (0.42, 0.45, 0.50),
        "elbow-joint": (0.42, 0.45, 0.50),
        "as5047p": (0.07, 0.18, 0.12),
        "amt102-v": (0.12, 0.12, 0.12),
        "teensy-4.1": (0.10, 0.45, 0.22),
    }

    s, e = G.POSE_SHOULDER0, G.POSE_ELBOW0
    sh = G.shoulder_origin(0)
    el = G.elbow_origin(0, s)

    def place_hanging(shape, origin, abs_angle):
        theta = math.degrees(math.pi - abs_angle)
        out = shape.copy()
        out.rotate(App.Vector(0, 0, 0), App.Vector(0, 1, 0), theta)
        out.translate(App.Vector(*origin))
        return out

    posed = {
        "posed_link1": place_hanging(parts["link1"], sh, s),
        "posed_link2": place_hanging(parts["link2"], el, s + e),
        "posed_shoulder_hw": parts["shoulder-joint"].copy().translate(App.Vector(*sh)),
        "posed_elbow_hw": parts["elbow-joint"].copy().translate(App.Vector(*el)),
        "posed_teensy": parts["teensy-4.1"]
        .copy()
        .translate(App.Vector(0.0, -8.0, G.CART_TOP + 5.0)),
        "posed_amt": parts["amt102-v"]
        .copy()
        .translate(App.Vector(-G.CART_L / 2.0 - 4.0, 0.0, G.CART_Z0 + 20.0)),
        "posed_as_s": parts["as5047p"]
        .copy()
        .translate(
            App.Vector(
                sh[0],
                sh[1] - G.cheek_span(G.SHOULDER_HUB_W) / 2.0 - 7.0,
                sh[2],
            )
        ),
        "posed_as_e": parts["as5047p"]
        .copy()
        .translate(
            App.Vector(
                el[0],
                el[1] - G.cheek_span(G.ELBOW_HUB_W) / 2.0 - 7.0,
                el[2],
            )
        ),
    }

    for name, shape in parts.items():
        solid_to_obj(doc, name.replace("-", "_"), shape, colors[name])
        mesh_export(shape, os.path.join(EXPORTS, name + ".stl"), 0.09)

    for name, shape in posed.items():
        solid_to_obj(doc, name, shape, (0.72, 0.72, 0.78))

    # purge orphans from prior revisions
    for obsolete in (
        "wiring.stl",
        "tip-mass.stl",
        "slip-ring-12-wire-a.stl",
        "slip-ring-12-wire-b.stl",
        "as5047p-a.stl",
        "as5047p-b.stl",
        "teensy-4.1-step.stl",
    ):
        p = os.path.join(EXPORTS, obsolete)
        if os.path.isfile(p):
            os.remove(p)
            print("removed", p, flush=True)

    doc.saveAs(DOC_PATH)
    Path(os.path.join(EXPORTS, "pendulum-kinematics.json")).write_text(
        json.dumps(k, indent=2)
    )
    print("saved", DOC_PATH, flush=True)
    print("ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
