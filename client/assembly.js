import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

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

const mats = {
  rail: metal(0x9aa7b5),
  cart: metal(0xd8dee8),
  alu: metal(0x7f8b99),
  alu2: metal(0xa3adb8),
  gold: metal(0xc9a227),
  pcb: new THREE.MeshStandardMaterial({ color: 0x1f7a3a, roughness: 0.55, metalness: 0.1 }),
  pcb2: new THREE.MeshStandardMaterial({ color: 0x163024, roughness: 0.5, metalness: 0.08 }),
  plastic: new THREE.MeshStandardMaterial({ color: 0x2b2b2b, roughness: 0.4, metalness: 0.15 }),
};

function metal(color) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.32, metalness: 0.72 });
}

const parts = [];

function addPart(id, mesh, home, explodeDir) {
  mesh.userData = { id, home: home.clone(), explodeDir: explodeDir.clone() };
  mesh.position.copy(home);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  scene.add(mesh);
  parts.push(mesh);
  return mesh;
}

function box(w, h, d, mat) {
  return new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
}

function cyl(r, h, mat, seg = 32) {
  return new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, seg), mat);
}

const rail = box(400, 10, 22, mats.rail);
addPart("frame", rail, new THREE.Vector3(0, 5, 0), new THREE.Vector3(0, -20, 0));

const cart = box(80, 22, 52, mats.cart);
addPart("frame", cart, new THREE.Vector3(0, 21, 0), new THREE.Vector3(0, 8, 0));

const teensy = box(61, 4, 18, mats.pcb);
addPart("teensy-4.1", teensy, new THREE.Vector3(16, 35, 0), new THREE.Vector3(40, 50, 20));

const amt = cyl(14.5, 10, mats.plastic);
amt.rotation.x = Math.PI / 2;
addPart("amt102-v", amt, new THREE.Vector3(-28, 21, 32), new THREE.Vector3(-50, 10, 40));

function slipRing() {
  const g = new THREE.Group();
  const body = cyl(6, 20, mats.gold);
  g.add(body);
  for (const y of [-6, 0, 6]) {
    const ring = cyl(6.7, 1.2, mats.gold);
    ring.position.y = y;
    g.add(ring);
  }
  return g;
}

const slip1 = slipRing();
addPart("slip-ring-12-wire", slip1, new THREE.Vector3(0, 42, 0), new THREE.Vector3(-30, 30, -40));

const enc1 = box(20, 2, 20, mats.pcb2);
addPart("as5047p", enc1, new THREE.Vector3(16, 42, 0), new THREE.Vector3(50, 40, -20));

const link1 = box(16, 180, 8, mats.alu);
addPart("frame", link1, new THREE.Vector3(0, 142, 0), new THREE.Vector3(0, 70, 0));

const slip2 = slipRing();
addPart("slip-ring-12-wire", slip2, new THREE.Vector3(0, 232, 0), new THREE.Vector3(30, 90, 30));

const enc2 = box(20, 2, 20, mats.pcb2);
addPart("as5047p", enc2, new THREE.Vector3(14, 232, 0), new THREE.Vector3(55, 100, 10));

const link2 = box(12, 120, 6, mats.alu2);
link2.rotation.z = THREE.MathUtils.degToRad(-22);
addPart("frame", link2, new THREE.Vector3(22, 286, 0), new THREE.Vector3(20, 130, 0));

const tip = cyl(7, 8, mats.gold, 24);
addPart("frame", tip, new THREE.Vector3(44, 340, 0), new THREE.Vector3(30, 150, 0));

let selected = "teensy-4.1";
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

function setExplode(t) {
  parts.forEach((p) => {
    p.position.copy(p.userData.home).addScaledVector(p.userData.explodeDir, t);
  });
}

function highlight(id) {
  selected = id;
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
      "teensy-4.1": "Teensy 4.1 — cart brain",
      "slip-ring-12-wire": "12-wire slip ring — joint wiring",
      as5047p: "AS5047P — joint angle",
      "amt102-v": "AMT102-V — cart travel",
      frame: "Rail / links — mechanical follow-on",
    };
    hint.textContent = labels[id] || "Drag to orbit · click a part";
  }
}

function pick(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
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
highlight("teensy-4.1");

function tick() {
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
tick();
