import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

const root = document.getElementById("cad-root");
const hint = document.getElementById("cad-hint");
const explodeInput = document.getElementById("cad-explode");
const resetBtn = document.getElementById("cad-reset");

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf3f6fb);

const camera = new THREE.PerspectiveCamera(42, 1, 1, 2000);
camera.position.set(280, 210, 320);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
root.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.target.set(0, 90, 0);
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

function metal(color) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.32, metalness: 0.72 });
}

const mats = {
  rail: metal(0x9aa7b5),
  cart: metal(0xd8dee8),
  alu: metal(0x7f8b99),
  alu2: metal(0xa3adb8),
  gold: metal(0xc9a227),
  pcb: new THREE.MeshStandardMaterial({ color: 0x1f7a3a, roughness: 0.45, metalness: 0.12 }),
  pcb2: new THREE.MeshStandardMaterial({ color: 0x163024, roughness: 0.5, metalness: 0.08 }),
  plastic: new THREE.MeshStandardMaterial({ color: 0x2b2b2b, roughness: 0.4, metalness: 0.15 }),
};

const parts = [];
const loader = new STLLoader();

function addPart(id, mesh, home, explodeDir) {
  mesh.userData = { id, home: home.clone(), explodeDir: explodeDir.clone() };
  mesh.position.copy(home);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  scene.add(mesh);
  parts.push(mesh);
  return mesh;
}

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

function setExplode(t) {
  parts.forEach((p) => {
    p.position.copy(p.userData.home).addScaledVector(p.userData.explodeDir, t);
  });
}

function highlight(id) {
  parts.forEach((p) => {
    p.traverse((child) => {
      if (child.material && child.material.emissive) {
        const on = p.userData.id === id && id !== "frame";
        child.material.emissive = new THREE.Color(on ? 0xc48a00 : 0x000000);
        child.material.emissiveIntensity = on ? 0.28 : 0;
      }
    });
  });
  if (hint) {
    const labels = {
      "teensy-4.1": "Teensy 4.1 — vendor STEP",
      "slip-ring-12-wire": "SRC012-12 slip ring — Ø12 × 19.5 mm",
      as5047p: "AS5047P-TS_EK_AB — 28 × 22 mm",
      "amt102-v": "AMT102-V — Ø31 × 28.77 mm",
      frame: "Rail / links — mechanical follow-on",
    };
    hint.textContent = labels[id] || "Drag to orbit · click a part";
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
  const hits = raycaster.intersectObjects(parts, true);
  if (!hits.length) return;
  let obj = hits[0].object;
  while (obj && !obj.userData.id) obj = obj.parent;
  const id = obj && obj.userData.id;
  if (!id || id === "frame") return;
  highlight(id);
  if (typeof window.selectKey === "function") window.selectKey(id);
}

function resize() {
  const w = root.clientWidth;
  const h = Math.max(360, Math.round(w * 0.52));
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

async function build() {
  const files = [
    ["cad/rail.stl", "frame", mats.rail, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, -20, 0)],
    ["cad/cart.stl", "frame", mats.cart, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 8, 0)],
    ["cad/link1.stl", "frame", mats.alu, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 70, 0)],
    ["cad/link2.stl", "frame", mats.alu2, new THREE.Vector3(0, 0, 0), new THREE.Vector3(20, 130, 0)],
    ["cad/teensy-4.1.stl", "teensy-4.1", mats.pcb, new THREE.Vector3(0, 0, 0), new THREE.Vector3(40, 50, 20)],
    ["cad/slip-ring-12-wire-a.stl", "slip-ring-12-wire", mats.gold, new THREE.Vector3(0, 0, 0), new THREE.Vector3(-30, 30, -40)],
    ["cad/slip-ring-12-wire-b.stl", "slip-ring-12-wire", mats.gold, new THREE.Vector3(0, 0, 0), new THREE.Vector3(30, 90, 30)],
    ["cad/as5047p-a.stl", "as5047p", mats.pcb2, new THREE.Vector3(0, 0, 0), new THREE.Vector3(50, 40, -20)],
    ["cad/as5047p-b.stl", "as5047p", mats.pcb2, new THREE.Vector3(0, 0, 0), new THREE.Vector3(55, 100, 10)],
    ["cad/amt102-v.stl", "amt102-v", mats.plastic, new THREE.Vector3(0, 0, 0), new THREE.Vector3(-50, 10, 40)],
  ];

  for (const [url, id, mat, home, explode] of files) {
    const mesh = await loadStl(url, mat.clone());
    // FreeCAD/STL is Z-up. Rotate into the existing Y-up viewer.
    mesh.rotation.x = -Math.PI / 2;
    addPart(id, mesh, home, explode);
  }

  highlight("teensy-4.1");
}

explodeInput.addEventListener("input", () => setExplode(Number(explodeInput.value)));
resetBtn.addEventListener("click", () => {
  explodeInput.value = "0";
  setExplode(0);
  camera.position.set(280, 210, 320);
  controls.target.set(0, 90, 0);
});
renderer.domElement.addEventListener("pointerdown", pick);
window.addEventListener("resize", resize);
window.highlightCad = highlight;

resize();
if (hint) hint.textContent = "Loading FreeCAD meshes…";
build().catch((err) => {
  console.error(err);
  if (hint) hint.textContent = "CAD mesh load failed";
});

function tick() {
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
tick();
