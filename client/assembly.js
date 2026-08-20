import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

const IRIS = {
  n: 12,
  rPivot: 32,
  rDrive: 40,
  thetaClosed: THREE.MathUtils.degToRad(10),
  thetaOpen: THREE.MathUtils.degToRad(40),
  bladeZ: 3.9,
  bladePitch: 0.11,
  bladeTilt: 0,
};

// Pristine pendulum kinematics (mm, CAD Z-up). Angle 0 = hanging down.
const PEND = {
  shoulder: { x: 0, y: 0, z: 54 },
  cartTop: 46,
  cartZ0: 14,
  cartL: 96,
  link1L: 180,
  link2L: 120,
  travelAmp: 55,
  shoulderAmp: THREE.MathUtils.degToRad(38),
  elbowAmp: THREE.MathUtils.degToRad(48),
  shoulderBias: THREE.MathUtils.degToRad(8),
  elbowBias: THREE.MathUtils.degToRad(-22),
};

const root = document.getElementById("cad-root");
const hint = document.getElementById("cad-hint");
const explodeInput = document.getElementById("cad-explode");
const apertureInput = document.getElementById("cad-aperture");
const swingInput = document.getElementById("cad-swing");
const playBtn = document.getElementById("cad-play");
const resetBtn = document.getElementById("cad-reset");
const irisOnly = [...document.querySelectorAll(".iris-only")];
const pendOnly = [...document.querySelectorAll(".pend-only")];
const modeBtns = [...document.querySelectorAll(".cad-mode")];

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf3f6fb);

const camera = new THREE.PerspectiveCamera(42, 1, 1, 2000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
root.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.495;

scene.add(new THREE.AmbientLight(0xffffff, 0.72));
const key = new THREE.DirectionalLight(0xfff4d6, 1.05);
key.position.set(180, 260, 140);
key.castShadow = true;
scene.add(key);
const fill = new THREE.DirectionalLight(0xb9e8ef, 0.45);
fill.position.set(-160, 80, -120);
scene.add(fill);

const ground = new THREE.Mesh(
  new THREE.CircleGeometry(480, 64),
  new THREE.ShadowMaterial({ opacity: 0.12 })
);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

function metal(color, extra = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.32, metalness: 0.72, ...extra });
}

const mats = {
  rail: metal(0x9aa7b5),
  cart: metal(0xd8dee8),
  alu: metal(0x7f8b99),
  alu2: metal(0xa3adb8),
  gold: metal(0xc9a227),
  steel: metal(0x6e7680, { roughness: 0.28, metalness: 0.85 }),
  wire: new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.7, metalness: 0.15 }),
  tip: metal(0xb83a2f, { roughness: 0.35, metalness: 0.55 }),
  pcb: new THREE.MeshStandardMaterial({ color: 0x1f7a3a, roughness: 0.45, metalness: 0.12 }),
  pcb2: new THREE.MeshStandardMaterial({ color: 0x163024, roughness: 0.5, metalness: 0.08 }),
  plastic: new THREE.MeshStandardMaterial({ color: 0x2b2b2b, roughness: 0.4, metalness: 0.15 }),
  stator: metal(0x3a414a, { roughness: 0.38, metalness: 0.78 }),
  rotor: metal(0xc9a227, { roughness: 0.28, metalness: 0.82 }),
  cover: new THREE.MeshStandardMaterial({
    color: 0x2c3238,
    roughness: 0.22,
    metalness: 0.55,
    transparent: true,
    opacity: 0.42,
    depthWrite: true,
  }),
  blade: metal(0x9aa4b0, { roughness: 0.22, metalness: 0.88 }),
};

const loader = new STLLoader();
const clock = new THREE.Clock();

const state = {
  mode: "iris",
  explode: 0,
  aperture: 0.35,
  swing: 0.35,
  playing: true,
  parts: [],
  iris: null,
  pend: null,
};

function loadStl(url, material) {
  return new Promise((resolve, reject) => {
    loader.load(
      url,
      (geom) => {
        geom.computeVertexNormals();
        resolve(new THREE.Mesh(geom, material));
      },
      undefined,
      reject
    );
  });
}

/** CAD Z-up (x,y,z) → Three Y-up (x,z,-y) */
function cadToThree(x, y, z = 0) {
  return new THREE.Vector3(x, z, -y);
}

function clearParts() {
  state.parts.forEach((p) => scene.remove(p));
  state.parts = [];
  state.iris = null;
  state.pend = null;
}

function addPart(id, obj, home, explodeDir) {
  obj.userData = {
    id,
    home: home.clone(),
    explodeDir: explodeDir.clone(),
    basePos: obj.position.clone(),
  };
  obj.traverse((child) => {
    if (child.isMesh) {
      child.castShadow = true;
      child.receiveShadow = true;
    }
  });
  scene.add(obj);
  state.parts.push(obj);
  return obj;
}

function markPickable(root, id) {
  root.userData.id = id;
  root.traverse((c) => {
    if (c.isMesh) c.userData.id = id;
  });
}

function cadMesh(mesh) {
  // STL is CAD Z-up. Rx(-90) → Three Y-up.
  mesh.rotation.x = -Math.PI / 2;
  return mesh;
}

function rotorAngle(t) {
  return THREE.MathUtils.lerp(IRIS.thetaClosed, IRIS.thetaOpen, t);
}

function bladeAngle(i, theta) {
  const a = (i * Math.PI * 2) / IRIS.n;
  const px = IRIS.rPivot * Math.cos(a);
  const py = IRIS.rPivot * Math.sin(a);
  const dx = IRIS.rDrive * Math.cos(a + theta);
  const dy = IRIS.rDrive * Math.sin(a + theta);
  return Math.atan2(dy - py, dx - px);
}

function setIrisPose(t) {
  const iris = state.iris;
  if (!iris) return;
  const theta = rotorAngle(t);
  iris.blades.forEach((blade, i) => {
    const a = (i * Math.PI * 2) / IRIS.n;
    const px = IRIS.rPivot * Math.cos(a);
    const py = IRIS.rPivot * Math.sin(a);
    const home = cadToThree(px, py, IRIS.bladeZ + i * IRIS.bladePitch);
    blade.userData.home.copy(home);
    blade.position.copy(home).addScaledVector(blade.userData.explodeDir, state.explode);
    blade.rotation.set(0, bladeAngle(i, theta), 0);
  });
  if (iris.rotor) iris.rotor.rotation.y = theta - IRIS.thetaClosed;
}

function pendulumAngles(t) {
  // Smooth swing + cart travel. t in [0,1] or free-running phase via sin.
  const phase = t * Math.PI * 2;
  const travel = PEND.travelAmp * Math.sin(phase * 0.85);
  const shoulder = PEND.shoulderBias + PEND.shoulderAmp * Math.sin(phase);
  const elbow = PEND.elbowBias + PEND.elbowAmp * Math.sin(phase * 1.35 + 0.4);
  return { travel, shoulder, elbow };
}

function setPendulumPose(t) {
  const pend = state.pend;
  if (!pend) return;
  const { travel, shoulder, elbow } = pendulumAngles(t);
  const ex = state.explode;

  // Cart slides on rail (Three X).
  pend.cartRoot.position.set(travel, 0, 0);
  pend.cartRoot.position.addScaledVector(pend.cartExplode, ex);

  // Shoulder above cart. CAD joint axis = Y → Three -Z after Rx(-90).
  // Hang map: mesh CAD +Z becomes group +Y after Rx(-90); rot.z = PI + a sends +Y to hang dir.
  pend.shoulder.position.copy(cadToThree(PEND.shoulder.x, PEND.shoulder.y, PEND.shoulder.z));
  pend.shoulder.position.addScaledVector(pend.shoulderExplode, ex);
  pend.shoulder.rotation.set(0, 0, Math.PI + shoulder);

  // Elbow is relative bend at end of link1 (local +Y after convert = distal).
  pend.elbow.position.set(0, PEND.link1L, 0);
  pend.elbow.position.addScaledVector(pend.elbowExplode, ex);
  pend.elbow.rotation.set(0, 0, elbow);

  // Static wiring follows cart a bit
  if (pend.wiring) {
    pend.wiring.position.set(travel * 0.35, 0, 0);
    pend.wiring.position.addScaledVector(pend.wiringExplode, ex);
  }
}

function setExplode(t) {
  state.explode = t;
  if (state.mode === "iris") {
    state.parts.forEach((p) => {
      p.position.copy(p.userData.home).addScaledVector(p.userData.explodeDir, t);
    });
    setIrisPose(state.aperture);
  } else if (state.mode === "pendulum") {
    setPendulumPose(state.swing);
  }
}

function setModeUi(mode) {
  modeBtns.forEach((btn) => btn.classList.toggle("active", btn.dataset.mode === mode));
  irisOnly.forEach((el) => el.classList.toggle("hidden", mode !== "iris"));
  pendOnly.forEach((el) => el.classList.toggle("hidden", mode !== "pendulum"));
}

function highlight(id) {
  state.parts.forEach((p) => {
    p.traverse((child) => {
      if (child.material && child.material.emissive) {
        const on = p.userData.id === id && id !== "frame" && id !== "wiring";
        child.material.emissive = new THREE.Color(on ? 0xc48a00 : 0x000000);
        child.material.emissiveIntensity = on ? 0.28 : 0;
      }
    });
  });
  if (!hint) return;
  const labels = {
    "teensy-4.1": "Teensy 4.1 — on cart deck",
    "slip-ring-12-wire": "SRC012-12 slip ring — Ø12.4 × 19.5 mm at joint",
    as5047p: "AS5047P — absolute joint encoder + magnet",
    "amt102-v": "AMT102-V — cart travel encoder",
    frame: "Rail / cart / hollow links / tip mass",
    "shoulder-joint": "Shoulder joint — 608 bearings, Ø8 shaft, collar",
    "elbow-joint": "Elbow joint — 608 bearings, Ø8 shaft, slip ring",
    wiring: "Harness loom (static rest-pose guide)",
    "iris-stator": "Stator cup — 12 pivot pins",
    "iris-rotor": "Drive ring — 12 pins in blade slots",
    "iris-cover": "Retaining cover",
    "iris-blade": "12 notched blades — pin-clear",
  };
  const idle =
    state.mode === "iris"
      ? "Drag to orbit · iris is dilating"
      : "Drag to orbit · pendulum swinging · click a part";
  hint.textContent = labels[id] || idle;
}

function frameIris() {
  camera.position.set(92, 78, 96);
  controls.target.set(0, 5, 0);
}

function framePendulum() {
  // Cart near y~50, hang down toward y~-150
  camera.position.set(280, 160, 320);
  controls.target.set(0, -20, 0);
}

async function buildPendulum() {
  clearParts();

  const [
    railM,
    cartM,
    link1M,
    link2M,
    tipM,
    shoulderM,
    elbowM,
    slipA,
    slipB,
    asA,
    asB,
    amtM,
    teensyM,
    wireM,
  ] = await Promise.all([
    loadStl("cad/rail.stl", mats.rail.clone()),
    loadStl("cad/cart.stl", mats.cart.clone()),
    loadStl("cad/link1.stl", mats.alu.clone()),
    loadStl("cad/link2.stl", mats.alu2.clone()),
    loadStl("cad/tip-mass.stl", mats.tip.clone()),
    loadStl("cad/shoulder-joint.stl", mats.steel.clone()),
    loadStl("cad/elbow-joint.stl", mats.steel.clone()),
    loadStl("cad/slip-ring-12-wire-a.stl", mats.gold.clone()),
    loadStl("cad/slip-ring-12-wire-b.stl", mats.gold.clone()),
    loadStl("cad/as5047p-a.stl", mats.pcb2.clone()),
    loadStl("cad/as5047p-b.stl", mats.pcb2.clone()),
    loadStl("cad/amt102-v.stl", mats.plastic.clone()),
    loadStl("cad/teensy-4.1.stl", mats.pcb.clone()).catch(() =>
      loadStl("cad/teensy-4.1-step.stl", mats.pcb.clone())
    ),
    loadStl("cad/wiring.stl", mats.wire.clone()),
  ]);

  // --- static rail ---
  const rail = cadMesh(railM);
  addPart("frame", rail, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, -20, 0));

  // --- cart root (travels in X) ---
  const cartRoot = new THREE.Group();
  const cart = cadMesh(cartM);
  cartRoot.add(cart);

  const teensy = cadMesh(teensyM);
  // Local teensy sits on deck: CAD (18,0,CART_TOP+4) → after parent cart at 0
  teensy.position.copy(cadToThree(18, 0, PEND.cartTop + 4));
  cartRoot.add(teensy);
  markPickable(teensy, "teensy-4.1");

  const amt = cadMesh(amtM);
  amt.position.copy(cadToThree(-PEND.cartL / 2 - 6, 18, PEND.cartZ0 + 18));
  cartRoot.add(amt);
  markPickable(amt, "amt102-v");

  // Shoulder pivot on cart
  const shoulder = new THREE.Group();
  const shoulderJoint = cadMesh(shoulderM);
  shoulder.add(shoulderJoint);
  markPickable(shoulderJoint, "shoulder-joint");

  const slipRingA = cadMesh(slipA);
  // local slip is on Y; offset to +Y side of joint
  slipRingA.position.copy(cadToThree(0, 16, 0));
  shoulder.add(slipRingA);
  markPickable(slipRingA, "slip-ring-12-wire");

  const encA = cadMesh(asA);
  encA.position.copy(cadToThree(0, -18, 0));
  shoulder.add(encA);
  markPickable(encA, "as5047p");

  // Link1 hangs from shoulder (mesh CAD +Z → group +Y via Rx-90; rot.z flips to hang)
  const link1 = cadMesh(link1M);
  shoulder.add(link1);
  markPickable(link1, "frame");

  // Elbow at distal end of link1 (local +Y = CAD +Z after convert)
  const elbow = new THREE.Group();
  elbow.position.set(0, PEND.link1L, 0);
  shoulder.add(elbow);

  const elbowJoint = cadMesh(elbowM);
  elbow.add(elbowJoint);
  markPickable(elbowJoint, "elbow-joint");

  const slipRingB = cadMesh(slipB);
  slipRingB.position.copy(cadToThree(0, 16, 0));
  elbow.add(slipRingB);
  markPickable(slipRingB, "slip-ring-12-wire");

  const encB = cadMesh(asB);
  encB.position.copy(cadToThree(0, -18, 0));
  elbow.add(encB);
  markPickable(encB, "as5047p");

  const link2 = cadMesh(link2M);
  elbow.add(link2);
  markPickable(link2, "frame");

  const tip = cadMesh(tipM);
  elbow.add(tip);
  markPickable(tip, "frame");

  cartRoot.add(shoulder);
  addPart("frame", cartRoot, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 12, 0));
  // Register pickable children with catalog ids
  addPart("teensy-4.1", teensy, teensy.position.clone(), new THREE.Vector3(40, 30, 10));
  addPart("amt102-v", amt, amt.position.clone(), new THREE.Vector3(-60, 20, 20));
  addPart("shoulder-joint", shoulderJoint, new THREE.Vector3(0, 0, 0), new THREE.Vector3(-20, 25, 20));
  addPart("elbow-joint", elbowJoint, new THREE.Vector3(0, 0, 0), new THREE.Vector3(30, -40, -20));
  addPart("slip-ring-12-wire", slipRingA, new THREE.Vector3(0, 0, 0), new THREE.Vector3(-30, 20, 15));
  addPart("slip-ring-12-wire", slipRingB, new THREE.Vector3(0, 0, 0), new THREE.Vector3(40, -30, -15));
  addPart("as5047p", encA, new THREE.Vector3(0, 0, 0), new THREE.Vector3(-35, -20, 10));
  addPart("as5047p", encB, new THREE.Vector3(0, 0, 0), new THREE.Vector3(45, -45, -20));

  // Rest-pose wiring guide (world-baked); only drifts with cart a little
  const wiring = cadMesh(wireM);
  addPart("wiring", wiring, new THREE.Vector3(0, 0, 0), new THREE.Vector3(20, -15, -30));

  state.pend = {
    cartRoot,
    shoulder,
    elbow,
    wiring,
    cartExplode: new THREE.Vector3(0, 12, 0),
    shoulderExplode: new THREE.Vector3(-15, 20, 25),
    elbowExplode: new THREE.Vector3(25, -35, -20),
    wiringExplode: new THREE.Vector3(20, -15, -30),
  };

  // Remove duplicate top-level addPart side effects on nested meshes' homes —
  // nested parts stay parented; explode is handled in setPendulumPose.
  state.parts = state.parts.filter((p) => {
    // keep only scene roots we added via scene.add in addPart
    return p.parent === scene;
  });
  // Re-add nested pick targets without reparenting — they're already under cartRoot
  // Ensure cartRoot is the only articulated root besides rail/wiring
  // (teensy etc. were addPart'd which scene.add'd them — fix by reparenting)
  [teensy, amt, shoulderJoint, elbowJoint, slipRingA, slipRingB, encA, encB].forEach((m) => {
    // if addPart stole them to scene, put back
    if (m.parent === scene) {
      // find intended parent
    }
  });

  // Rebuild parenting cleanly: remove stolen nodes from scene roots list
  // and ensure hierarchy is correct.
  const ensureChild = (parent, child) => {
    if (child.parent !== parent) parent.add(child);
  };
  ensureChild(cartRoot, cart);
  ensureChild(cartRoot, teensy);
  ensureChild(cartRoot, amt);
  ensureChild(cartRoot, shoulder);
  ensureChild(shoulder, shoulderJoint);
  ensureChild(shoulder, slipRingA);
  ensureChild(shoulder, encA);
  ensureChild(shoulder, link1);
  ensureChild(shoulder, elbow);
  ensureChild(elbow, elbowJoint);
  ensureChild(elbow, slipRingB);
  ensureChild(elbow, encB);
  ensureChild(elbow, link2);
  ensureChild(elbow, tip);

  // parts list for explode/highlight: rail, cartRoot, wiring + tagged meshes
  state.parts = [rail, cartRoot, wiring, teensy, amt, shoulderJoint, elbowJoint, slipRingA, slipRingB, encA, encB, link1, link2, tip];
  state.parts.forEach((p) => {
    if (!p.userData.home) {
      p.userData.home = p.position.clone();
      p.userData.explodeDir = new THREE.Vector3(0, 0, 0);
    }
    if (!p.userData.id) p.userData.id = "frame";
  });
  teensy.userData.id = "teensy-4.1";
  amt.userData.id = "amt102-v";
  shoulderJoint.userData.id = "shoulder-joint";
  elbowJoint.userData.id = "elbow-joint";
  slipRingA.userData.id = "slip-ring-12-wire";
  slipRingB.userData.id = "slip-ring-12-wire";
  encA.userData.id = "as5047p";
  encB.userData.id = "as5047p";
  wiring.userData.id = "wiring";
  rail.userData.id = "frame";
  cartRoot.userData.id = "frame";
  link1.userData.id = "frame";
  link2.userData.id = "frame";
  tip.userData.id = "frame";

  setPendulumPose(state.swing);
  framePendulum();
  highlight("shoulder-joint");
  if (hint) hint.textContent = "Pendulum swinging · joints at the top of the hang";
  if (playBtn) playBtn.textContent = state.playing ? "Pause" : "Play";
}

async function buildIris() {
  clearParts();
  const [statorMesh, rotorMesh, coverMesh, bladeMesh] = await Promise.all([
    loadStl("cad/iris-stator.stl", mats.stator.clone()),
    loadStl("cad/iris-rotor.stl", mats.rotor.clone()),
    loadStl("cad/iris-cover.stl", mats.cover.clone()),
    loadStl("cad/iris-blade.stl", mats.blade.clone()),
  ]);

  const stator = new THREE.Group();
  statorMesh.rotation.x = -Math.PI / 2;
  stator.add(statorMesh);
  addPart("iris-stator", stator, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, -16, 0));

  const rotor = new THREE.Group();
  rotorMesh.rotation.x = -Math.PI / 2;
  rotor.add(rotorMesh);
  addPart("iris-rotor", rotor, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 18, 0));

  const cover = new THREE.Group();
  coverMesh.rotation.x = -Math.PI / 2;
  cover.add(coverMesh);
  addPart("iris-cover", cover, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 32, 0));

  const blades = [];
  for (let i = 0; i < IRIS.n; i += 1) {
    const group = new THREE.Group();
    const mesh = bladeMesh.clone();
    mesh.material = mats.blade.clone();
    mesh.material.color.offsetHSL(0, 0, (i % 3) * 0.03);
    mesh.rotation.x = -Math.PI / 2;
    group.add(mesh);
    const a = (i * Math.PI * 2) / IRIS.n;
    const home = cadToThree(IRIS.rPivot * Math.cos(a), IRIS.rPivot * Math.sin(a), IRIS.bladeZ + i * IRIS.bladePitch);
    addPart("iris-blade", group, home, new THREE.Vector3(Math.cos(a) * 8, 10, -Math.sin(a) * 8));
    blades.push(group);
  }

  const well = new THREE.Mesh(
    new THREE.CircleGeometry(34, 64),
    new THREE.MeshStandardMaterial({ color: 0x101418, roughness: 0.9, metalness: 0.05 })
  );
  well.rotation.x = -Math.PI / 2;
  well.position.y = 0.4;
  addPart("iris-stator", well, new THREE.Vector3(0, 0.4, 0), new THREE.Vector3(0, -16, 0));

  state.iris = { blades, rotor, stator, cover };
  setIrisPose(state.aperture);
  frameIris();
  highlight("iris-blade");
}

async function setMode(mode) {
  state.mode = mode;
  setModeUi(mode);
  explodeInput.value = "0";
  state.explode = 0;
  if (hint) hint.textContent = "Loading CAD…";
  try {
    if (mode === "iris") {
      state.playing = true;
      if (playBtn) playBtn.textContent = "Pause";
      await buildIris();
    } else {
      state.playing = true;
      if (playBtn) playBtn.textContent = "Pause";
      await buildPendulum();
    }
  } catch (err) {
    console.error(err);
    if (hint) hint.textContent = "CAD mesh load failed";
  }
}

function pick(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  const pointer = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1
  );
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(state.parts, true);
  if (!hits.length) return;
  let obj = hits[0].object;
  while (obj && !obj.userData.id) obj = obj.parent;
  const id = obj && obj.userData.id;
  if (!id || id === "frame" || id === "wiring") return;
  highlight(id);
  if (typeof window.selectKey === "function" && state.mode === "pendulum") {
    const catalogId =
      id === "shoulder-joint" || id === "elbow-joint" ? "slip-ring-12-wire" : id;
    window.selectKey(catalogId);
  }
}

function resize() {
  const w = root.clientWidth;
  const h = Math.max(360, Math.round(w * 0.52));
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

explodeInput.addEventListener("input", () => setExplode(Number(explodeInput.value)));
if (apertureInput) {
  apertureInput.addEventListener("input", () => {
    state.playing = false;
    if (playBtn) playBtn.textContent = "Play";
    state.aperture = Number(apertureInput.value);
    setIrisPose(state.aperture);
  });
}
if (swingInput) {
  swingInput.addEventListener("input", () => {
    state.playing = false;
    if (playBtn) playBtn.textContent = "Play";
    state.swing = Number(swingInput.value);
    setPendulumPose(state.swing);
  });
}
playBtn.addEventListener("click", () => {
  state.playing = !state.playing;
  playBtn.textContent = state.playing ? "Pause" : "Play";
});
resetBtn.addEventListener("click", () => {
  explodeInput.value = "0";
  setExplode(0);
  if (state.mode === "iris") frameIris();
  else framePendulum();
});
modeBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.mode !== state.mode) setMode(btn.dataset.mode);
  });
});
renderer.domElement.addEventListener("pointerdown", pick);
window.addEventListener("resize", resize);
window.highlightCad = highlight;
window.setCadMode = setMode;

resize();
setMode("pendulum");

function tick() {
  const t = clock.getElapsedTime();
  if (state.playing) {
    if (state.mode === "iris" && state.iris) {
      const u = 0.5 + 0.5 * Math.sin(t * 0.7);
      state.aperture = u;
      if (apertureInput) apertureInput.value = String(u.toFixed(3));
      setIrisPose(u);
    } else if (state.mode === "pendulum" && state.pend) {
      // continuous phase, also mirror onto slider 0..1
      const u = 0.5 + 0.5 * Math.sin(t * 0.55);
      state.swing = u;
      if (swingInput) swingInput.value = String(u.toFixed(3));
      setPendulumPose(t * 0.09); // free-running phase (not limited to 0..1)
    }
  }
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
tick();
