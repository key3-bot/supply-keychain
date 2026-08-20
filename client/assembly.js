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
};

/** Fitted pendulum (mm, CAD Z-up). Angle 0 = hang down. */
const PEND = {
  shoulder: { x: 0, y: 0, z: 66 }, // CART_TOP(50)+16
  cartTop: 50,
  cartZ0: 16,
  cartL: 110,
  link1L: 170,
  link2L: 115,
  shoulderHubW: 14,
  elbowHubW: 12,
  cheekT: 7,
  travelAmp: 70,
  shoulderAmp: THREE.MathUtils.degToRad(42),
  elbowAmp: THREE.MathUtils.degToRad(55),
  shoulderBias: THREE.MathUtils.degToRad(10),
  elbowBias: THREE.MathUtils.degToRad(-28),
  // encoder board offset along −Y from joint origin
  asY: (hubW) => -(hubW / 2 + 7 + 6),
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

const camera = new THREE.PerspectiveCamera(40, 1, 0.5, 8000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
root.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.98;
controls.minDistance = 40;
controls.maxDistance = 1200;

scene.add(new THREE.AmbientLight(0xffffff, 0.7));
const key = new THREE.DirectionalLight(0xfff4d6, 1.05);
key.position.set(200, 280, 160);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
scene.add(key);
const fill = new THREE.DirectionalLight(0xb9e8ef, 0.48);
fill.position.set(-180, 90, -140);
scene.add(fill);
const rim = new THREE.DirectionalLight(0xffffff, 0.25);
rim.position.set(40, -120, 80);
scene.add(rim);

const ground = new THREE.Mesh(
  new THREE.CircleGeometry(700, 72),
  new THREE.ShadowMaterial({ opacity: 0.14 })
);
ground.rotation.x = -Math.PI / 2;
ground.position.y = -320;
ground.receiveShadow = true;
scene.add(ground);

function metal(color, extra = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.32, metalness: 0.72, ...extra });
}

const mats = {
  rail: metal(0x8e9aa8, { roughness: 0.4, metalness: 0.65 }),
  cart: metal(0xdde3ec, { roughness: 0.35, metalness: 0.55 }),
  link1: metal(0x7a8796, { roughness: 0.28, metalness: 0.82 }),
  link2: metal(0x9a7358, { roughness: 0.34, metalness: 0.7 }),
  joint: metal(0x5c636b, { roughness: 0.25, metalness: 0.9 }),
  gold: metal(0xc9a227, { roughness: 0.3, metalness: 0.85 }),
  pcb: new THREE.MeshStandardMaterial({ color: 0x1a7a38, roughness: 0.45, metalness: 0.12 }),
  pcb2: new THREE.MeshStandardMaterial({ color: 0x143024, roughness: 0.5, metalness: 0.08 }),
  plastic: new THREE.MeshStandardMaterial({ color: 0x222222, roughness: 0.42, metalness: 0.18 }),
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

/** CAD Z-up (x,y,z) → Three Y-up (x, z, −y) */
function cadToThree(x, y, z = 0) {
  return new THREE.Vector3(x, z, -y);
}

function clearParts() {
  state.parts.forEach((p) => scene.remove(p));
  state.parts = [];
  state.iris = null;
  state.pend = null;
}

function addRoot(id, obj, home, explodeDir) {
  obj.userData = {
    id,
    home: home.clone(),
    explodeDir: explodeDir.clone(),
  };
  obj.position.copy(home);
  obj.traverse((child) => {
    if (child.isMesh) {
      child.castShadow = true;
      child.receiveShadow = true;
      if (!child.userData.id) child.userData.id = id;
    }
  });
  scene.add(obj);
  state.parts.push(obj);
  return obj;
}

function tag(obj, id) {
  obj.userData.id = id;
  obj.traverse((c) => {
    if (c.isMesh) c.userData.id = id;
  });
  return obj;
}

/** STL is CAD Z-up → apply Rx(−90) so CAD +Z becomes Three +Y. */
function cadMesh(mesh) {
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
    const home = cadToThree(
      IRIS.rPivot * Math.cos(a),
      IRIS.rPivot * Math.sin(a),
      IRIS.bladeZ + i * IRIS.bladePitch
    );
    blade.userData.home.copy(home);
    blade.position.copy(home).addScaledVector(blade.userData.explodeDir, state.explode);
    blade.rotation.set(0, bladeAngle(i, theta), 0);
  });
  if (iris.rotor) iris.rotor.rotation.y = theta - IRIS.thetaClosed;
}

/**
 * Pendulum FK.
 * After cadMesh Rx(−90): mesh local +Z (link length) → group +Y.
 * Angle 0 hang down = group rot.z = π so +Y points world −Y.
 * Joint axis CAD +Y → after Rx(−90) is world −Z; we rotate about group Z
 * which is CAD Y after the mesh conversion when pivots are empty Groups
 * without the Rx — empty Groups keep identity, meshes inside have Rx.
 *
 * Hierarchy:
 *   cartRoot (translate X)
 *     shoulder (at shoulder CAD point)  rot.z = π + shoulderAngle
 *       shoulderJoint, asA, link1
 *       elbow (at local 0, link1L, 0)   rot.z = elbowAngle
 *         elbowJoint, asB, link2
 */
function pendulumAngles(phase) {
  const travel = PEND.travelAmp * Math.sin(phase * 0.85);
  const shoulder = PEND.shoulderBias + PEND.shoulderAmp * Math.sin(phase);
  const elbow = PEND.elbowBias + PEND.elbowAmp * Math.sin(phase * 1.32 + 0.35);
  return { travel, shoulder, elbow };
}

function setPendulumPose(phase) {
  const pend = state.pend;
  if (!pend) return;
  const { travel, shoulder, elbow } = pendulumAngles(phase);
  const ex = state.explode;

  pend.cartRoot.position.set(travel, 0, 0);
  pend.cartRoot.position.addScaledVector(pend.cartExplode, ex);

  // Shoulder in cart frame (CAD → Three)
  const sh = cadToThree(PEND.shoulder.x, PEND.shoulder.y, PEND.shoulder.z);
  pend.shoulder.position.copy(sh);
  pend.shoulder.position.addScaledVector(pend.shoulderExplode, ex);
  // Hang: mesh +Y (after Rx-90 from CAD +Z) → world −Y via rot.z = π + a
  pend.shoulder.rotation.set(0, 0, Math.PI + shoulder);

  pend.elbow.position.set(0, PEND.link1L, 0);
  pend.elbow.position.addScaledVector(pend.elbowExplode, ex);
  pend.elbow.rotation.set(0, 0, elbow);
}

function setExplode(t) {
  state.explode = t;
  if (state.mode === "iris") {
    state.parts.forEach((p) => {
      p.position.copy(p.userData.home).addScaledVector(p.userData.explodeDir, t);
    });
    setIrisPose(state.aperture);
  } else if (state.mode === "pendulum") {
    // Non-articulated roots (rail) explode; articulated via setPendulumPose
    if (state.pend?.rail) {
      state.pend.rail.position
        .copy(state.pend.rail.userData.home)
        .addScaledVector(state.pend.rail.userData.explodeDir, t);
    }
    setPendulumPose(state._phase || 0);
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
        const cid = child.userData.id || p.userData.id;
        const on = cid === id && id !== "frame";
        child.material.emissive = new THREE.Color(on ? 0xc48a00 : 0x000000);
        child.material.emissiveIntensity = on ? 0.28 : 0;
      }
    });
  });
  if (!hint) return;
  const labels = {
    "teensy-4.1": "Teensy 4.1 — cart deck controller",
    as5047p: "AS5047P — absolute joint encoder + magnet",
    "amt102-v": "AMT102-V — cart travel encoder",
    frame: "Rail / cart / fitted links",
    "shoulder-joint": "Shoulder — 608s in cart cheeks, hub in the gap, slip ring + magnet",
    "elbow-joint": "Elbow — 608s in link1 clevis, link2 hub seated in the fork",
    "iris-stator": "Stator cup — 12 pivot pins",
    "iris-rotor": "Drive ring — 12 pins in blade slots",
    "iris-cover": "Retaining cover",
    "iris-blade": "12 notched blades — pin-clear",
  };
  const idle =
    state.mode === "iris"
      ? "Drag to orbit · iris is dilating"
      : "Drag to orbit · fitted joints · live swing";
  hint.textContent = labels[id] || idle;
}

function frameIris() {
  camera.position.set(92, 78, 96);
  controls.target.set(0, 5, 0);
}

function framePendulum() {
  // Full hang: shoulder ~y66, tip ~ y66-285 ≈ -220
  camera.position.set(340, 90, 380);
  controls.target.set(0, -70, 0);
  controls.update();
}

async function buildPendulum() {
  clearParts();

  const urls = {
    rail: "cad/rail.stl",
    cart: "cad/cart.stl",
    link1: "cad/link1.stl",
    link2: "cad/link2.stl",
    shoulder: "cad/shoulder-joint.stl",
    elbow: "cad/elbow-joint.stl",
    as5047p: "cad/as5047p.stl",
    amt: "cad/amt102-v.stl",
    teensy: "cad/teensy-4.1.stl",
  };

  const [
    railM,
    cartM,
    link1M,
    link2M,
    shoulderM,
    elbowM,
    asM,
    amtM,
    teensyM,
  ] = await Promise.all([
    loadStl(urls.rail, mats.rail.clone()),
    loadStl(urls.cart, mats.cart.clone()),
    loadStl(urls.link1, mats.link1.clone()),
    loadStl(urls.link2, mats.link2.clone()),
    loadStl(urls.shoulder, mats.joint.clone()),
    loadStl(urls.elbow, mats.joint.clone()),
    loadStl(urls.as5047p, mats.pcb2.clone()),
    loadStl(urls.amt, mats.plastic.clone()),
    loadStl(urls.teensy, mats.pcb.clone()),
  ]);

  // Static rail
  const rail = tag(cadMesh(railM), "frame");
  addRoot("frame", rail, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, -24, 0));

  // Cart root (travels)
  const cartRoot = new THREE.Group();
  tag(cartRoot, "frame");

  const cart = tag(cadMesh(cartM), "frame");
  cartRoot.add(cart);

  const teensy = tag(cadMesh(teensyM), "teensy-4.1");
  teensy.position.copy(cadToThree(28, 0, PEND.cartTop + 5));
  cartRoot.add(teensy);

  const amt = tag(cadMesh(amtM), "amt102-v");
  amt.position.copy(cadToThree(-PEND.cartL / 2 - 4, 20, PEND.cartZ0 + 20));
  cartRoot.add(amt);

  // Shoulder pivot group
  const shoulder = new THREE.Group();
  tag(shoulder, "shoulder-joint");

  const shoulderJoint = tag(cadMesh(shoulderM), "shoulder-joint");
  shoulder.add(shoulderJoint);

  const asA = tag(cadMesh(asM.clone()), "as5047p");
  asA.position.copy(cadToThree(0, PEND.asY(PEND.shoulderHubW), 0));
  shoulder.add(asA);

  const link1 = tag(cadMesh(link1M), "frame");
  shoulder.add(link1);

  // Elbow pivot at distal end of link1 (local +Y after convert = CAD +Z)
  const elbow = new THREE.Group();
  tag(elbow, "elbow-joint");
  elbow.position.set(0, PEND.link1L, 0);
  shoulder.add(elbow);

  const elbowJoint = tag(cadMesh(elbowM), "elbow-joint");
  elbow.add(elbowJoint);

  const asB = tag(cadMesh(asM.clone()), "as5047p");
  asB.position.copy(cadToThree(0, PEND.asY(PEND.elbowHubW), 0));
  elbow.add(asB);

  const link2 = tag(cadMesh(link2M), "frame");
  elbow.add(link2);

  cartRoot.add(shoulder);
  addRoot("frame", cartRoot, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 14, 0));

  // Register pickable leaves for highlight (still parented under cartRoot)
  state.parts.push(teensy, amt, shoulderJoint, elbowJoint, asA, asB, link1, link2);

  state.pend = {
    rail,
    cartRoot,
    shoulder,
    elbow,
    cartExplode: new THREE.Vector3(0, 14, 0),
    shoulderExplode: new THREE.Vector3(-18, 22, 28),
    elbowExplode: new THREE.Vector3(28, -40, -22),
  };

  state._phase = 0.2;
  setPendulumPose(state._phase);
  framePendulum();
  highlight("shoulder-joint");
  if (hint) hint.textContent = "Fitted clevis joints · live swing · click a part";
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
  addRoot("iris-stator", stator, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, -16, 0));

  const rotor = new THREE.Group();
  rotorMesh.rotation.x = -Math.PI / 2;
  rotor.add(rotorMesh);
  addRoot("iris-rotor", rotor, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 18, 0));

  const cover = new THREE.Group();
  coverMesh.rotation.x = -Math.PI / 2;
  cover.add(coverMesh);
  addRoot("iris-cover", cover, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 32, 0));

  const blades = [];
  for (let i = 0; i < IRIS.n; i += 1) {
    const group = new THREE.Group();
    const mesh = bladeMesh.clone();
    mesh.material = mats.blade.clone();
    mesh.material.color.offsetHSL(0, 0, (i % 3) * 0.03);
    mesh.rotation.x = -Math.PI / 2;
    group.add(mesh);
    const a = (i * Math.PI * 2) / IRIS.n;
    const home = cadToThree(
      IRIS.rPivot * Math.cos(a),
      IRIS.rPivot * Math.sin(a),
      IRIS.bladeZ + i * IRIS.bladePitch
    );
    addRoot("iris-blade", group, home, new THREE.Vector3(Math.cos(a) * 8, 10, -Math.sin(a) * 8));
    blades.push(group);
  }

  const well = new THREE.Mesh(
    new THREE.CircleGeometry(34, 64),
    new THREE.MeshStandardMaterial({ color: 0x101418, roughness: 0.9, metalness: 0.05 })
  );
  well.rotation.x = -Math.PI / 2;
  well.position.y = 0.4;
  addRoot("iris-stator", well, new THREE.Vector3(0, 0.4, 0), new THREE.Vector3(0, -16, 0));

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
    state.playing = true;
    if (playBtn) playBtn.textContent = "Pause";
    if (mode === "iris") await buildIris();
    else await buildPendulum();
  } catch (err) {
    console.error(err);
    if (hint) hint.textContent = "CAD mesh load failed — hard-refresh?";
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
  if (!id || id === "frame") return;
  highlight(id);
  if (typeof window.selectKey === "function" && state.mode === "pendulum") {
    const catalogId =
      id === "shoulder-joint" || id === "elbow-joint" ? "slip-ring-12-wire" : id;
    window.selectKey(catalogId);
  }
}

function resize() {
  const w = root.clientWidth;
  const h = Math.max(420, Math.round(w * 0.58));
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
    const u = Number(swingInput.value);
    state.swing = u;
    // Map slider 0..1 → phase
    state._phase = u * Math.PI * 2;
    setPendulumPose(state._phase);
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
      state._phase = t * 0.85;
      const u = 0.5 + 0.5 * Math.sin(state._phase);
      state.swing = u;
      if (swingInput) swingInput.value = String(u.toFixed(3));
      setPendulumPose(state._phase);
    }
  }
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
tick();
