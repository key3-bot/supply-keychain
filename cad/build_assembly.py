# FreeCAD 1.1 headless — pristine cart-double pendulum (iris-quality bar).
# Local-frame parts with mating clevis/hub geometry. Viewer does FK + animation.

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


def mesh_export(shape, path, deflection=0.10):
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


def torus_ring(major, minor, y0=0.0):
    """Thin decorative ring in XZ plane, axis = Y."""
    t = Part.makeTorus(major, minor)
    # default torus is XY plane (axis Z); rotate to axis Y
    t.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90)
    t.translate(App.Vector(0, y0, 0))
    return t


def bearing_608():
    """Centered on origin, axis = Y. Race + balls suggestion."""
    od = G.BEARING_OD / 2.0
    id_ = G.BEARING_ID / 2.0
    w = G.BEARING_W
    outer = cyl(od, w, 0, -w / 2.0, 0, "y")
    inner = cyl(id_ + 0.15, w + 0.4, 0, -w / 2.0 - 0.2, 0, "y")
    race = outer.cut(inner)
    # groove
    groove = cyl(od + 0.05, 1.4, 0, -0.7, 0, "y").cut(
        cyl(od - 1.1, 1.6, 0, -0.8, 0, "y")
    )
    # ball suggestions
    balls = []
    br = 1.7
    path_r = (od + id_) / 2.0
    for i in range(7):
        a = i * (2.0 * math.pi / 7.0)
        bx = path_r * math.cos(a)
        bz = path_r * math.sin(a)
        balls.append(Part.makeSphere(br, App.Vector(bx, 0, bz)))
    return fuse_all([race, groove] + balls)


def slip_ring():
    """SRC012-style capsule, axis Y, centered."""
    body = cyl(G.SLIP_OD / 2.0, G.SLIP_L, 0, -G.SLIP_L / 2.0, 0, "y")
    bands = []
    for t in (-0.38, -0.18, 0.0, 0.18, 0.38):
        y0 = t * G.SLIP_L - 0.45
        bands.append(cyl(G.SLIP_OD / 2.0 + 0.4, 0.9, 0, y0, 0, "y"))
    # end flanges
    bands.append(cyl(G.SLIP_OD / 2.0 + 0.8, 1.2, 0, -G.SLIP_L / 2.0, 0, "y"))
    bands.append(cyl(G.SLIP_OD / 2.0 + 0.8, 1.2, 0, G.SLIP_L / 2.0 - 1.2, 0, "y"))
    bore = cyl(G.SLIP_BORE / 2.0, G.SLIP_L + 4, 0, -G.SLIP_L / 2.0 - 2, 0, "y")
    return fuse_all([body] + bands).cut(bore)


def magnet():
    return cyl(G.MAGNET_D / 2.0, G.MAGNET_H, 0, -G.MAGNET_H / 2.0, 0, "y")


def collar():
    body = cyl(6.8, 5.0, 0, -2.5, 0, "y")
    body = body.cut(cyl(G.SHAFT_D / 2.0 + 0.05, 6.0, 0, -3.0, 0, "y"))
    # set screw dimple
    body = body.cut(cyl(1.2, 4.0, 0, -1.0, 4.0, "z"))
    return body


def shaft(length):
    return cyl(G.SHAFT_D / 2.0, length, 0, -length / 2.0, 0, "y")


def as5047p():
    """Board in XZ, thin +Y; chip faces −Y toward magnet."""
    bw, bh, bt = G.AS_BOARD  # X, Z, thickness-Y
    board = box(bw, bt, bh, -bw / 2.0, 0.0, -bh / 2.0)
    for hx, hz in G.AS_HOLES:
        board = board.cut(
            cyl(G.AS_HOLE_R, bt + 1.2, hx - bw / 2.0, -0.6, hz - bh / 2.0, "y")
        )
    chip = box(5.0, 1.0, 6.4, -2.5, bt, -3.2)
    pads = []
    for i in range(5):
        pads.append(box(1.2, 0.3, 1.8, -10 + i * 2.4, bt, -bh / 2.0 + 1.0))
        pads.append(box(1.2, 0.3, 1.8, -10 + i * 2.4, bt, bh / 2.0 - 2.8))
    keeper = cyl(3.8, 0.5, 0, bt + 1.0, 0, "y")
    return fuse_all([board, chip, keeper] + pads)


def amt102():
    body = cyl(G.AMT_R, G.AMT_BODY_H, 0, 0, 0, "y")
    # scalloped rim
    for i in range(8):
        a = i * (math.pi / 4.0)
        body = body.cut(
            cyl(2.2, G.AMT_BODY_H + 1, (G.AMT_R - 0.5) * math.cos(a), -0.5, (G.AMT_R - 0.5) * math.sin(a), "y")
        )
    base = cyl(G.AMT_R + 1.0, G.AMT_BASE_H, 0, -G.AMT_BASE_H, 0, "y")
    hub = cyl(5.5, 7.0, 0, -3.5, 0, "y")
    plate = box(36.0, 2.0, 36.0, -18.0, -G.AMT_BASE_H - 2.0, -18.0)
    for hx, hz in ((-13, -13), (13, -13), (-13, 13), (13, 13)):
        plate = plate.cut(cyl(1.7, 5, hx, -G.AMT_BASE_H - 2.5, hz, "y"))
    return fuse_all([body, base, hub, plate])


def teensy():
    tw, th, tt = G.TEENSY
    board = box(tw, th, tt, -tw / 2.0, -th / 2.0, 0)
    # USB
    usb = box(9.0, 7.5, 3.2, -tw / 2.0 - 0.5, -3.75, tt)
    # Ethernet
    eth = box(16.0, 14.0, 12.0, tw / 2.0 - 17.0, -7.0, tt)
    # MCU blob
    mcu = box(10.0, 10.0, 1.2, -5.0, -5.0, tt)
    pins = []
    for i in range(24):
        pins.append(box(0.6, 0.6, 6.0, -tw / 2.0 + 4 + i * 2.3, -th / 2.0 + 1.0, -6.0))
        pins.append(box(0.6, 0.6, 6.0, -tw / 2.0 + 4 + i * 2.3, th / 2.0 - 1.6, -6.0))
    return fuse_all([board, usb, eth, mcu] + pins)


def rounded_spar(length, radius, z0=0.0):
    """Cylinder spar along +Z from z0 to z0+length."""
    return cyl(radius, length, 0, 0, z0, "z")


def hub_disk(radius, width, y0=None):
    """Rotating hub, axis Y, centered (or y0 = min Y)."""
    if y0 is None:
        y0 = -width / 2.0
    disc = cyl(radius, width, 0, y0, 0, "y")
    # lighten
    for i in range(4):
        a = i * (math.pi / 2.0) + math.pi / 4.0
        rr = radius * 0.45
        disc = disc.cut(cyl(radius * 0.18, width + 1, rr * math.cos(a), y0 - 0.5, rr * math.sin(a), "y"))
    bore = cyl(G.SHAFT_D / 2.0 + 0.05, width + 2, 0, y0 - 1, 0, "y")
    return disc.cut(bore)


def clevis_fork(gap, tine_t, reach, height_r):
    """
    Distal clevis at z=0 facing +Z arm behind it.
    Two tines along Y with inner gap; rounded noses.
    gap = clear distance between inner faces
    tine_t = each tine thickness
    reach = how far tines extend in ±X and along Z past pivot (radius-ish)
    """
    span = gap + 2.0 * tine_t
    parts = []
    for sign in (-1.0, 1.0):
        y_inner = sign * (gap / 2.0)
        y0 = y_inner if sign > 0 else y_inner - tine_t
        # plate
        plate = box(reach * 2.0, tine_t, reach * 2.0, -reach, y0, -reach)
        # round the nose with cylinder fuse then common
        nose = cyl(reach, tine_t, 0, y0, 0, "y")
        tine = plate.fuse(nose)
        # bore
        tine = tine.cut(cyl(G.SHAFT_D / 2.0 + 0.08, tine_t + 2, 0, y0 - 1, 0, "y"))
        # bearing pocket (half-depth) on inner face
        if sign < 0:
            # +Y facing pocket on +Y face of − tine → at y = -gap/2
            pocket_y = -gap / 2.0 - 0.05
            tine = tine.cut(
                cyl(G.BEARING_OD / 2.0 + 0.05, 3.2, 0, pocket_y - 3.2, 0, "y")
            )
        else:
            pocket_y = gap / 2.0 + 0.05
            tine = tine.cut(
                cyl(G.BEARING_OD / 2.0 + 0.05, 3.2, 0, pocket_y, 0, "y")
            )
        parts.append(tine)
    # back bridge joining tines on −Z side (toward spar)
    bridge = box(reach * 1.2, span, 6.0, -reach * 0.6, -span / 2.0, -reach - 2.0)
    return fuse_all(parts + [bridge])


def rail():
    body = box(G.RAIL_LEN, G.RAIL_W, G.RAIL_H, -G.RAIL_LEN / 2.0, -G.RAIL_W / 2.0, 0)
    # top races
    for y in (-G.RAIL_W / 2.0 + 4.0, G.RAIL_W / 2.0 - 7.0):
        body = body.cut(box(G.RAIL_LEN + 2, 3.2, 2.4, -G.RAIL_LEN / 2.0 - 1, y, G.RAIL_H - 2.0))
    # center channel
    body = body.cut(box(G.RAIL_LEN + 2, 6.0, 3.0, -G.RAIL_LEN / 2.0 - 1, -3.0, G.RAIL_H - 4.5))
    feet = []
    for x in (-G.RAIL_LEN / 2.0 + 18, G.RAIL_LEN / 2.0 - 48):
        foot = box(36.0, G.RAIL_FOOT_W, 5.0, x, -G.RAIL_FOOT_W / 2.0, -5.0)
        # bolt holes
        for by in (-G.RAIL_FOOT_W / 2.0 + 8, G.RAIL_FOOT_W / 2.0 - 8):
            foot = foot.cut(cyl(2.2, 8, x + 18, by, -6.0))
        feet.append(foot)
    # end stops
    for x in (-G.RAIL_LEN / 2.0, G.RAIL_LEN / 2.0 - 6):
        feet.append(box(6.0, G.RAIL_W + 8, G.RAIL_H + 4, x, -(G.RAIL_W + 8) / 2.0, 0))
    return body.fuse(fuse_all(feet))


def cart():
    """
    Cart body + twin shoulder cheeks with bearing seats.
    Shoulder origin is at (0,0,SHOULDER_Z) in world when travel=0.
    Cheeks are part of the cart (fixed); rotating hub is on link1.
    """
    z0 = G.CART_Z0
    body = box(G.CART_L, G.CART_W, G.CART_H, -G.CART_L / 2.0, -G.CART_W / 2.0, z0)
    # rail tunnel
    body = body.cut(
        box(
            G.CART_L + 6,
            G.RAIL_W + 2.4,
            G.RAIL_H + 2.5,
            -G.CART_L / 2.0 - 3,
            -(G.RAIL_W + 2.4) / 2.0,
            z0 - 1.2,
        )
    )
    # underside rollers suggestion
    for x in (-G.CART_L / 2.0 + 18, G.CART_L / 2.0 - 18):
        for y in (-G.RAIL_W / 2.0 - 1.0, G.RAIL_W / 2.0 - 5.0):
            body = body.fuse(cyl(4.0, 6.0, x, y, z0 + 2.0, "y"))

    hub_w = G.SHOULDER_HUB_W
    span = G.cheek_span(hub_w)
    cheek_h = 34.0
    cheek_x = 22.0  # half-width of cheek plate in X
    # deck cut under cheeks for clearance
    body = body.cut(box(cheek_x * 2 + 4, span + 4, 8, -cheek_x - 2, -(span + 4) / 2.0, G.CART_TOP - 6))

    cheeks = []
    for sign in (-1.0, 1.0):
        y0 = sign * (hub_w / 2.0) if sign > 0 else -hub_w / 2.0 - G.CHEEK_T
        if sign < 0:
            y0 = -hub_w / 2.0 - G.CHEEK_T
        else:
            y0 = hub_w / 2.0
        cheek = box(cheek_x * 2, G.CHEEK_T, cheek_h, -cheek_x, y0, G.CART_TOP - 4.0)
        # round top
        cheek = cheek.fuse(cyl(cheek_x, G.CHEEK_T, 0, y0, G.SHOULDER_Z, "y"))
        # bearing bore through
        cheek = cheek.cut(
            cyl(G.BEARING_OD / 2.0 + 0.05, G.CHEEK_T + 2, 0, y0 - 1, G.SHOULDER_Z, "y")
        )
        # outer bearing recess
        if sign < 0:
            cheek = cheek.cut(
                cyl(G.BEARING_OD / 2.0 + 0.6, 2.2, 0, y0 - 0.1, G.SHOULDER_Z, "y")
            )
        else:
            cheek = cheek.cut(
                cyl(
                    G.BEARING_OD / 2.0 + 0.6,
                    2.2,
                    0,
                    y0 + G.CHEEK_T - 2.1,
                    G.SHOULDER_Z,
                    "y",
                )
            )
        cheeks.append(cheek)

    # cross brace between cheeks below pivot
    brace = box(12.0, hub_w, 8.0, -6.0, -hub_w / 2.0, G.CART_TOP - 2.0)

    # Teensy standoffs on +X deck
    standoffs = []
    for bx, by in ((16, 16), (16, -16), (52, 16), (52, -16)):
        standoffs.append(cyl(2.4, 5.0, bx, by, G.CART_TOP))
        body = body.cut(cyl(1.0, 6.0, bx, by, G.CART_TOP - 1))

    # AMT bracket on −X face
    bracket = box(8.0, 34.0, 28.0, -G.CART_L / 2.0 - 8.0, -17.0, z0 + 6.0)
    bracket = bracket.fuse(box(14.0, 34.0, 4.0, -G.CART_L / 2.0 - 8.0, -17.0, z0 + 30.0))
    for hz in (10.0, 24.0):
        bracket = bracket.cut(cyl(1.6, 12, -G.CART_L / 2.0 - 9.0, 0.0, z0 + hz, "x"))

    # cable passthrough
    body = body.cut(box(14.0, 20.0, 12.0, G.CART_L / 2.0 - 16.0, -10.0, G.CART_TOP - 14.0))

    # chamfer-ish top edges via cut cylinders — skip, keep clean fuse
    return fuse_all([body, brace, bracket] + cheeks + standoffs)


def link1():
    """
    Local frame: proximal shoulder hub at origin, length along +Z.
    Hub width = SHOULDER_HUB_W fits between cart cheeks.
    Distal clevis at z=LINK1_L holds elbow hub.
    """
    hub_w = G.SHOULDER_HUB_W
    hub = hub_disk(G.LINK1_HUB_R, hub_w)
    # clamp ears
    ear = box(8.0, hub_w, 10.0, G.LINK1_HUB_R - 3.0, -hub_w / 2.0, -5.0)
    ear = ear.cut(cyl(1.5, hub_w + 2, G.LINK1_HUB_R + 1.0, -hub_w / 2.0 - 1, 0, "y"))
    hub = hub.fuse(ear)

    spar_z0 = G.LINK1_HUB_R - 2.0
    spar_len = G.LINK1_L - spar_z0 - 8.0
    spar = rounded_spar(spar_len, G.LINK1_ARM_R, spar_z0)
    # taper sleeve near hub
    sleeve = cyl(G.LINK1_ARM_R + 2.2, 16.0, 0, 0, spar_z0, "z")
    spar = spar.fuse(sleeve)

    # wire tunnel
    spar = spar.cut(cyl(2.0, spar_len - 8.0, 0, 0, spar_z0 + 4.0, "z"))
    # lightening holes along spar (through X)
    for z in (G.LINK1_L * 0.28, G.LINK1_L * 0.48, G.LINK1_L * 0.68):
        spar = spar.cut(cyl(3.2, G.LINK1_ARM_R * 3, -G.LINK1_ARM_R * 1.5, 0, z, "x"))

    # distal clevis at z = LINK1_L
    fork = clevis_fork(
        gap=G.LINK1_CLEVIS_GAP,
        tine_t=G.LINK1_CLEVIS_T,
        reach=16.0,
        height_r=16.0,
    )
    fork.translate(App.Vector(0, 0, G.LINK1_L))

    # blend collar into clevis
    blend = cyl(G.LINK1_ARM_R + 1.5, 12.0, 0, 0, G.LINK1_L - 18.0, "z")

    return fuse_all([hub, spar, blend, fork])


def link2():
    """
    Local: proximal elbow hub at origin (width = ELBOW_HUB_W), tip mass at z=LINK2_L.
    Hub fits inside link1 distal clevis.
    """
    hub_w = G.ELBOW_HUB_W
    hub = hub_disk(G.LINK2_HUB_R, hub_w)
    spar_z0 = G.LINK2_HUB_R - 1.5
    spar_len = G.LINK2_L - spar_z0 - G.TIP_R
    spar = rounded_spar(spar_len, G.LINK2_ARM_R, spar_z0)
    sleeve = cyl(G.LINK2_ARM_R + 1.8, 12.0, 0, 0, spar_z0, "z")
    spar = spar.cut(cyl(1.7, spar_len - 6.0, 0, 0, spar_z0 + 3.0, "z"))
    for z in (G.LINK2_L * 0.35, G.LINK2_L * 0.55, G.LINK2_L * 0.72):
        spar = spar.cut(cyl(2.6, G.LINK2_ARM_R * 3, -G.LINK2_ARM_R * 1.5, 0, z, "x"))

    tip = cyl(G.TIP_R, G.TIP_H, 0, -G.TIP_H / 2.0, G.LINK2_L, "y")
    # flatten tip sides slightly
    tip = tip.fuse(Part.makeSphere(G.TIP_R * 0.95, App.Vector(0, 0, G.LINK2_L)))
    tip = tip.cut(cyl(G.SHAFT_D / 2.0 + 0.1, G.TIP_H + 2, 0, -G.TIP_H / 2.0 - 1, G.LINK2_L, "y"))
    # set screw
    tip = tip.fuse(cyl(G.LINK2_ARM_R + 0.8, 8.0, 0, 0, G.LINK2_L - G.TIP_R - 2.0, "z"))

    return fuse_all([hub, sleeve, spar, tip])


def joint_hardware(hub_w, slip_side=True):
    """
    Shaft + bearings + collar + magnet [+ slip ring] about origin, axis Y.
    Bearings sit in the cheek bores at y = ±(hub_w/2 + CHEEK_T/2).
    """
    span = G.cheek_span(hub_w)
    # bearings centered in each cheek
    y_b = hub_w / 2.0 + G.CHEEK_T / 2.0
    b1 = bearing_608()
    b1.translate(App.Vector(0, -y_b, 0))
    b2 = bearing_608()
    b2.translate(App.Vector(0, y_b, 0))

    shaft_len = span + 28.0 + (G.SLIP_L if slip_side else 10.0)
    sh = shaft(shaft_len)

    parts = [b1, b2, sh]
    # collar outside +Y cheek
    col = collar()
    col.translate(App.Vector(0, span / 2.0 + 3.5, 0))
    parts.append(col)

    # magnet on −Y stub (faces encoder)
    mag = magnet()
    mag.translate(App.Vector(0, -span / 2.0 - 5.0, 0))
    parts.append(mag)

    if slip_side:
        slip = slip_ring()
        slip.translate(App.Vector(0, span / 2.0 + 4.0 + G.SLIP_L / 2.0, 0))
        parts.append(slip)

    return fuse_all(parts)


def main():
    print("FreeCAD", App.Version(), flush=True)
    print("pristine fitted-joint pendulum", flush=True)
    doc = App.newDocument("PendulumAssembly")

    # Build solids
    parts = {}
    print("rail…", flush=True)
    parts["rail"] = rail()
    print("cart…", flush=True)
    parts["cart"] = cart()
    print("link1…", flush=True)
    parts["link1"] = link1()
    print("link2…", flush=True)
    parts["link2"] = link2()
    print("shoulder-joint…", flush=True)
    parts["shoulder-joint"] = joint_hardware(G.SHOULDER_HUB_W, slip_side=True)
    print("elbow-joint…", flush=True)
    parts["elbow-joint"] = joint_hardware(G.ELBOW_HUB_W, slip_side=True)
    print("as5047p…", flush=True)
    parts["as5047p"] = as5047p()
    print("amt102-v…", flush=True)
    parts["amt102-v"] = amt102()
    print("teensy-4.1…", flush=True)
    parts["teensy-4.1"] = teensy()

    colors = {
        "rail": (0.55, 0.60, 0.66),
        "cart": (0.88, 0.90, 0.93),
        "link1": (0.52, 0.58, 0.64),
        "link2": (0.62, 0.48, 0.38),
        "shoulder-joint": (0.45, 0.48, 0.52),
        "elbow-joint": (0.45, 0.48, 0.52),
        "as5047p": (0.07, 0.18, 0.12),
        "amt102-v": (0.12, 0.12, 0.12),
        "teensy-4.1": (0.10, 0.45, 0.22),
    }

    # Posed snapshot for FCStd only (not exported as viewer meshes)
    s = G.POSE_SHOULDER0
    e = G.POSE_ELBOW0
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
        "posed_shoulder_joint": parts["shoulder-joint"].copy().translate(App.Vector(*sh)),
        "posed_elbow_joint": parts["elbow-joint"].copy().translate(App.Vector(*el)),
        "posed_teensy": parts["teensy-4.1"]
        .copy()
        .translate(App.Vector(28.0, 0.0, G.CART_TOP + 5.0)),
        "posed_amt": parts["amt102-v"]
        .copy()
        .translate(App.Vector(-G.CART_L / 2.0 - 4.0, 20.0, G.CART_Z0 + 20.0)),
        "posed_as_a": parts["as5047p"]
        .copy()
        .translate(App.Vector(sh[0], sh[1] - G.cheek_span(G.SHOULDER_HUB_W) / 2.0 - 6.0, sh[2])),
        "posed_as_b": parts["as5047p"]
        .copy()
        .translate(App.Vector(el[0], el[1] - G.cheek_span(G.ELBOW_HUB_W) / 2.0 - 6.0, el[2])),
    }

    for name, shape in parts.items():
        solid_to_obj(doc, name.replace("-", "_"), shape, colors[name])
        mesh_export(shape, os.path.join(EXPORTS, name + ".stl"), 0.09)

    for name, shape in posed.items():
        solid_to_obj(doc, name, shape, (0.7, 0.7, 0.75))

    # Drop obsolete orphan meshes so the web root cannot serve them by accident
    for obsolete in (
        "wiring.stl",
        "tip-mass.stl",
        "slip-ring-12-wire-a.stl",
        "slip-ring-12-wire-b.stl",
        "as5047p-a.stl",
        "as5047p-b.stl",
        "elbow-joint.stl.bak",
    ):
        p = os.path.join(EXPORTS, obsolete)
        if os.path.isfile(p):
            os.remove(p)
            print("removed obsolete", p, flush=True)

    # Copy as5047p twice under stable names used optionally — single mesh is enough
    doc.saveAs(DOC_PATH)
    print("saved", DOC_PATH, flush=True)

    Path(os.path.join(EXPORTS, "pendulum-kinematics.json")).write_text(
        json.dumps(G.kinematics_json(), indent=2)
    )
    print("ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
