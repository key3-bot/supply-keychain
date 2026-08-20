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

const root = document.getElementById("cad-root");
const hint = document.getElementById("cad-hint");
const explodeInput = document.getElementById("cad-explode");
const apertureInput = document.getElementById("cad-aperture");
const playBtn = document.getElementById("cad-play");
const resetBtn = document.getElementById("cad-reset");
const irisOnly = [...document.querySelectorAll(".iris-only")];
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
controls.maxPolarAngle = Math.PI * 0.49;

scene.add(new THREE.AmbientLight(0xffffff, 0.72));
const key = new THREE.DirectionalLight(0xfff4d6, 1.05);
key.position.set(180, 260, 140);
key.castShadow = true;
scene.add(key);
const fill = new THREE.DirectionalLight(0xb9e8ef, 0.45);
fill.position.set(-160, 80, -120);
scene.add(fill);

const ground = new THREE.Mesh(
  new THREE.CircleGeometry(420, 64),
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
  playing: true,
  parts: [],
  iris: null,
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

function cadToThree(x, y, z = 0) {
  return new THREE.Vector3(x, z, -y);
}

function clearParts() {
  state.parts.forEach((p) => scene.remove(p));
  state.parts = [];
  state.iris = null;
}

function addPart(id, obj, home, explodeDir) {
  obj.userData = { id, home: home.clone(), explodeDir: explodeDir.clone() };
  obj.position.copy(home);
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
  // FreeCAD Z rotation maps to Three.js +Y after the STL's Rx(-90°) convert.
  // Non-crossing pack: no rigid tilt. Tiny Z pitch keeps solids from intersecting.
  iris.blades.forEach((blade, i) => {
    const a = (i * Math.PI * 2) / IRIS.n;
    const px = IRIS.rPivot * Math.cos(a);
    const py = IRIS.rPivot * Math.sin(a);
    const home = cadToThree(px, py, IRIS.bladeZ + i * IRIS.bladePitch);
    blade.userData.home.copy(home);
    blade.position.copy(home).addScaledVector(blade.userData.explodeDir, state.explode);
    // Parent yaw aims +X at the drive pin. Child mesh is pre-tilted about CAD X.
    blade.rotation.set(0, bladeAngle(i, theta), 0);
  });
  if (iris.rotor) {
    iris.rotor.rotation.y = theta - IRIS.thetaClosed;
  }
}

function setExplode(t) {
  state.explode = t;
  state.parts.forEach((p) => {
    p.position.copy(p.userData.home).addScaledVector(p.userData.explodeDir, t);
  });
  if (state.mode === "iris") setIrisPose(state.aperture);
}

function setModeUi(mode) {
  modeBtns.forEach((btn) => btn.classList.toggle("active", btn.dataset.mode === mode));
  irisOnly.forEach((el) => el.classList.toggle("hidden", mode !== "iris"));
}

function highlight(id) {
  state.parts.forEach((p) => {
    p.traverse((child) => {
      if (child.material && child.material.emissive) {
        const on = p.userData.id === id && id !== "frame";
        child.material.emissive = new THREE.Color(on ? 0xc48a00 : 0x000000);
        child.material.emissiveIntensity = on ? 0.28 : 0;
      }
    });
  });
  if (!hint) return;
  const labels = {
    "teensy-4.1": "Teensy 4.1 — vendor STEP on cart top",
    "slip-ring-12-wire": "SRC012-12 slip ring — Ø12.4 × 19.5 mm",
    as5047p: "AS5047P-TS_EK_AB — 28 × 22 mm absolute joint encoder",
    "amt102-v": "AMT102-V — Ø31 cart encoder on side bracket",
    frame: "Rail / cart / hollow links / tip mass",
    "shoulder-joint": "Shoulder — 608 bearings, Ø8 shaft, magnet + collar",
    "elbow-joint": "Elbow — 608 bearings, Ø8 shaft, magnet + slip ring",
    wiring: "Harness — Teensy → slip rings → encoders through link tunnels",
    "iris-stator": "Stator cup — 12 pivot pins, wall captures the pack",
    "iris-rotor": "Drive ring — 12 pins in blade slots",
    "iris-cover": "Retaining cover — holds leaves in the cup",
    "iris-blade": "12 notched blades — pin-clear through the stroke",
  };
  hint.textContent = labels[id] || (state.mode === "iris" ? "Drag to orbit · iris is dilating" : "Drag to orbit · click a part");
}

function frameIris() {
  camera.position.set(92, 78, 96);
  controls.target.set(0, 5, 0);
}

function framePendulum() {
  // Assembly hangs below the cart; look at mid-hang volume.
  camera.position.set(260, 120, 300);
  controls.target.set(20, -40, 0);
}

async function buildPendulum() {
  clearParts();
  // FreeCAD exports are already posed in world mm (Z-up). STL Rx(-90°) → Three Y-up.
  // Teensy STEP mesh is from the older cart height; lift ~6 mm onto the new cart top.
  const files = [
    ["cad/rail.stl", "frame", mats.rail, [0, 0, 0], [0, -18, 0]],
    ["cad/cart.stl", "frame", mats.cart, [0, 0, 0], [0, 10, 0]],
    ["cad/link1.stl", "frame", mats.alu, [0, 0, 0], [30, -40, 0]],
    ["cad/link2.stl", "frame", mats.alu2, [0, 0, 0], [50, -90, 0]],
    ["cad/tip-mass.stl", "frame", mats.tip, [0, 0, 0], [40, -120, 0]],
    ["cad/shoulder-joint.stl", "shoulder-joint", mats.steel, [0, 0, 0], [-20, 25, 30]],
    ["cad/elbow-joint.stl", "elbow-joint", mats.steel, [0, 0, 0], [40, -50, -25]],
    ["cad/slip-ring-12-wire-a.stl", "slip-ring-12-wire", mats.gold, [0, 0, 0], [-35, 20, 20]],
    ["cad/slip-ring-12-wire-b.stl", "slip-ring-12-wire", mats.gold, [0, 0, 0], [55, -40, -20]],
    ["cad/as5047p-a.stl", "as5047p", mats.pcb2, [0, 0, 0], [-40, -25, 15]],
    ["cad/as5047p-b.stl", "as5047p", mats.pcb2, [0, 0, 0], [60, -55, -30]],
    ["cad/amt102-v.stl", "amt102-v", mats.plastic, [0, 0, 0], [-70, 15, 25]],
    ["cad/teensy-4.1.stl", "teensy-4.1", mats.pcb, [0, 6, 0], [45, 35, 15]],
    ["cad/wiring.stl", "wiring", mats.wire, [0, 0, 0], [25, -20, -40]],
  ];
  for (const [url, id, mat, homeT, explodeT] of files) {
    const mesh = await loadStl(url, mat.clone());
    // CAD Z-up → Three Y-up. home/explode are already in Three space (x,y,z).
    mesh.rotation.x = -Math.PI / 2;
    addPart(
      id,
      mesh,
      new THREE.Vector3(homeT[0], homeT[1], homeT[2]),
      new THREE.Vector3(explodeT[0], explodeT[1], explodeT[2])
    );
  }
  framePendulum();
  highlight("shoulder-joint");
  if (hint) hint.textContent = "Real joint stack · click a part · explode to separate";
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
    // CAD Z-up → Three Y-up, then lean about the slot axis (CAD +X).
    // Same tilt on every leaf → continuous cyclic overlap around the ring.
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
      state.playing = false;
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
    // Map joint stacks back to catalog keys when possible.
    const catalogId =
      id === "shoulder-joint" || id === "elbow-joint"
        ? "slip-ring-12-wire"
        : id;
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
apertureInput.addEventListener("input", () => {
  state.playing = false;
  if (playBtn) playBtn.textContent = "Play";
  state.aperture = Number(apertureInput.value);
  setIrisPose(state.aperture);
});
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
setMode("iris");

function tick() {
  if (state.mode === "iris" && state.playing && state.iris) {
    const t = 0.5 + 0.5 * Math.sin(clock.getElapsedTime() * 0.7);
    state.aperture = t;
    apertureInput.value = String(t.toFixed(3));
    setIrisPose(t);
  }
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
tick();
