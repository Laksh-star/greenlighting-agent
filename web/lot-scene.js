// Isometric studio-lot scene for the Greenlighting Agent.
// Pure rendering + picking; all data and HUD logic lives in lot.js.

import * as THREE from "three";

const COLORS = {
  sky: 0xdde4f3,
  ground: 0xdde4f3,
  pad: 0xf3f5fb,
  road: 0xc6cfe2,
  select: 0x3b6fe0,
  roadLine: 0xffffff,
  wall: 0xf4f1ea,
  wallTrim: 0xd9d4c8,
  door: 0x2c3650,
  go: 0x12a467,
  cond: 0xe9a01c,
  nogo: 0xe0503f,
  unknown: 0x8a94a8,
  vacant: 0xf2b632,
  idle: 0xaab3c4,
  working: 0x3b6fe0,
  tree: 0x55b98a,
  treeDark: 0x3f9e73,
  trunk: 0x9b7653,
  crate: 0xd9a871,
  crateDark: 0x39425a,
  office: 0xfafbfd,
  glass: 0x5a79b8,
};

const AGENT_HUES = [0x3b6fe0, 0x9b5de5, 0x12a467, 0xe9a01c, 0xe86a92, 0xe0503f];
const SLOT_COLUMNS = [-42, -20, 2, 24];
const SLOT_ROWS = [-11, -35, -59];
const OFFICE_POS = new THREE.Vector3(-40, 0, 25);
const CROSS_ROAD_X = 46;
const TRAILER_SCALE = 1.3;
const APRON_Z = 14;
const ELEVATION = THREE.MathUtils.degToRad(38);
const HOME_AZIMUTH = THREE.MathUtils.degToRad(28);

export function slotPosition(index) {
  const col = SLOT_COLUMNS[index % SLOT_COLUMNS.length];
  const row = SLOT_ROWS[Math.floor(index / SLOT_COLUMNS.length)] ?? SLOT_ROWS.at(-1);
  return new THREE.Vector3(col, 0, row);
}

export function createLot(canvas, agents, handlers = {}) {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(COLORS.sky);

  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -400, 600);
  const view = {
    target: new THREE.Vector3(-8, 0, -6),
    azimuth: HOME_AZIMUTH,
    height: 110,
  };
  const goal = { target: view.target.clone(), azimuth: view.azimuth, height: view.height };
  let insets = { top: 0, right: 0, bottom: 0, left: 0 };
  let size = { w: 1, h: 1 };
  let homeHeight = 110;

  // ---------- lights ----------
  scene.add(new THREE.HemisphereLight(0xffffff, 0xc9d2e6, 1.25));
  const sun = new THREE.DirectionalLight(0xfff6e8, 1.9);
  sun.position.set(-40, 100, 28);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -95;
  sun.shadow.camera.right = 95;
  sun.shadow.camera.top = 95;
  sun.shadow.camera.bottom = -95;
  sun.shadow.camera.near = 1;
  sun.shadow.camera.far = 260;
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.04;
  sun.shadow.radius = 5;
  scene.add(sun);

  // ---------- helpers ----------
  const materials = new Map();
  function mat(color, extra) {
    if (extra) return new THREE.MeshLambertMaterial({ color, ...extra });
    if (!materials.has(color)) materials.set(color, new THREE.MeshLambertMaterial({ color }));
    return materials.get(color);
  }

  function box(w, h, d, color, x = 0, y = 0, z = 0, parent, extra) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(color, extra));
    mesh.position.set(x, y + h / 2, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    if (parent) parent.add(mesh);
    return mesh;
  }

  function cyl(rTop, rBottom, h, color, x, y, z, parent, segments = 20, extra) {
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(rTop, rBottom, h, segments), mat(color, extra));
    mesh.position.set(x, y + h / 2, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    if (parent) parent.add(mesh);
    return mesh;
  }

  // Ground decals are unlit so colours are exact; one shadow catcher handles shadows.
  function flat(w, d, color, x, z, y = 0.02, parent = scene, opacity = 1) {
    const mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(w, d),
      new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity, depthWrite: opacity >= 1 })
    );
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.set(x, y, z);
    parent.add(mesh);
    return mesh;
  }

  function textTexture(text, { fg = "#171c26", bg = null, font = 700, pad = 26, size = 72 } = {}) {
    const c = document.createElement("canvas");
    const ctx = c.getContext("2d");
    const fontSpec = `${font} ${size}px Inter, system-ui, -apple-system, "Segoe UI", sans-serif`;
    ctx.font = fontSpec;
    const w = Math.ceil(ctx.measureText(text).width) + pad * 2;
    const h = size + pad * 1.3;
    c.width = w;
    c.height = h;
    if (bg) {
      ctx.fillStyle = bg;
      ctx.beginPath();
      ctx.roundRect(0, 0, w, h, h / 2.6);
      ctx.fill();
    }
    ctx.font = fontSpec;
    ctx.fillStyle = fg;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, w / 2, h / 2 + size * 0.04);
    const texture = new THREE.CanvasTexture(c);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 4;
    return { texture, aspect: w / h };
  }

  function label(text, height, options) {
    const { texture, aspect } = textTexture(text, options);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false, transparent: true }));
    sprite.scale.set(height * aspect, height, 1);
    sprite.renderOrder = 10;
    return sprite;
  }

  function decal(text, height, color) {
    const { texture, aspect } = textTexture(text, { fg: color, pad: 6, size: 96 });
    const mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(height * aspect, height),
      new THREE.MeshBasicMaterial({ map: texture, transparent: true })
    );
    return mesh;
  }

  function verdictColor(verdict) {
    return COLORS[verdict] ?? COLORS.unknown;
  }

  const pickables = [];
  function register(group, data) {
    group.userData = { ...data, root: true };
    pickables.push(group);
  }
  function unregister(group) {
    const index = pickables.indexOf(group);
    if (index >= 0) pickables.splice(index, 1);
  }

  // ---------- ground, roads, static dressing ----------
  flat(900, 900, COLORS.ground, 0, 0, 0);
  flat(900, 8, COLORS.road, 0, 5); // main road
  flat(8, 900, COLORS.road, CROSS_ROAD_X, 0, 0.021); // cross road
  for (let x = -300; x <= 300; x += 7) {
    if (Math.abs(x - CROSS_ROAD_X) > 5) flat(3, 0.35, COLORS.roadLine, x, 5, 0.03);
  }
  for (let z = -300; z <= 300; z += 7) {
    if (Math.abs(z - 5) > 5) flat(0.35, 3, COLORS.roadLine, CROSS_ROAD_X, z, 0.03);
  }
  const backlot = flat(96, 70, COLORS.pad, -9, -36, 0.015);
  flat(96, 32, COLORS.pad, -9, 27, 0.015);

  const shadowCatcher = new THREE.Mesh(
    new THREE.PlaneGeometry(900, 900),
    new THREE.ShadowMaterial({ color: 0x3a4a7a, opacity: 0.2, depthWrite: false })
  );
  shadowCatcher.renderOrder = 2;
  shadowCatcher.rotation.x = -Math.PI / 2;
  shadowCatcher.position.y = 0.08;
  shadowCatcher.receiveShadow = true;
  scene.add(shadowCatcher);

  function tree(x, z, scale = 1) {
    const g = new THREE.Group();
    cyl(0.34, 0.42, 2.2, COLORS.trunk, 0, 0, 0, g, 8);
    const crown = new THREE.Mesh(new THREE.SphereGeometry(1.7, 16, 12), mat(COLORS.tree));
    crown.position.y = 3.6;
    crown.scale.y = 1.25;
    crown.castShadow = true;
    g.add(crown);
    g.position.set(x, 0, z);
    g.scale.setScalar(scale);
    scene.add(g);
    return g;
  }
  [
    [-64, -42, 1.1], [-64, -24, 0.9], [-64, -8, 1], [-64, 16, 1.15], [-64, 34, 0.9],
    [58, -40, 1.2], [56, -18, 0.9], [56, 18, 1], [58, 38, 1.15],
    [-46, 50, 1.05], [-24, 50, 0.9], [-2, 50, 1.1], [20, 50, 0.95],
    [78, -60, 1.3], [84, -6, 1], [76, 56, 1.2], [-86, -30, 1.2], [-84, 26, 1], [-30, 66, 1.1], [30, 68, 1],
  ].forEach(([x, z, s]) => tree(x, z, s));
  const backTrees = new THREE.Group();
  scene.add(backTrees);
  [[-50, 1.1], [-28, 0.9], [-6, 1.15], [16, 1], [36, 0.9]].forEach(([x, s]) => {
    backTrees.add(tree(x, 0, s));
  });

  function crateStack(x, z, parent, dark = false) {
    const g = new THREE.Group();
    const c = dark ? COLORS.crateDark : COLORS.crate;
    box(1.5, 1.1, 1.5, c, 0, 0, 0, g);
    box(1.5, 1.1, 1.5, c, 1.65, 0, 0, g);
    box(1.5, 1.1, 1.5, c, 0.8, 1.1, 0, g);
    box(3.4, 0.16, 1.9, 0xb9895a, 0.82, -0.08, 0, g);
    g.position.set(x, 0.08, z);
    parent.add(g);
    return g;
  }

  // Water tower: the lot's landmark.
  (function waterTower() {
    const g = new THREE.Group();
    for (const [x, z] of [[-1.6, -1.6], [1.6, -1.6], [-1.6, 1.6], [1.6, 1.6]]) {
      const leg = cyl(0.16, 0.2, 9, 0x8a94a8, x, 0, z, g, 8);
      leg.rotation.z = -x * 0.045;
      leg.rotation.x = z * 0.045;
    }
    cyl(2.9, 2.9, 3.8, 0xfafbfd, 0, 8.6, 0, g, 28);
    cyl(2.96, 2.96, 0.8, COLORS.go, 0, 9.9, 0, g, 28);
    cyl(0.15, 3.2, 1.7, 0x39425a, 0, 12.4, 0, g, 28);
    g.position.set(31, 0, 20);
    scene.add(g);
  })();

  // Grip truck that drives the main road.
  function buildTruck() {
    const g = new THREE.Group();
    box(6.2, 3, 2.8, 0xfafbfd, -1.2, 1, 0, g);
    box(6.24, 0.6, 2.84, COLORS.go, -1.2, 1.5, 0, g);
    box(2.2, 2.2, 2.6, COLORS.go, 3.2, 0.8, 0, g);
    box(0.9, 0.9, 2.3, 0x24304a, 3.9, 1.9, 0, g);
    box(8, 0.4, 2.2, 0x39425a, 0, 0.55, 0, g);
    for (const x of [-3, -1.6, 3.1]) {
      for (const z of [-1.25, 1.25]) {
        const wheel = cyl(0.62, 0.62, 0.5, 0x1f2636, x, 0, z, g, 16);
        wheel.rotation.x = Math.PI / 2;
        wheel.position.y = 0.62;
      }
    }
    return g;
  }
  const truck = buildTruck();
  truck.position.set(-140, 0, 6.8);
  scene.add(truck);

  // ---------- greenlight office (master orchestrator) ----------
  const office = new THREE.Group();
  const lamps = {};
  (function buildOffice() {
    box(13, 0.5, 11, COLORS.wallTrim, 0, 0, 0, office);
    box(12, 9, 10, COLORS.office, 0, 0.5, 0, office);
    for (const y of [2.3, 5, 7.7]) {
      box(12.06, 1.3, 8.2, COLORS.glass, 0, y, 0, office);
      box(10.2, 1.3, 10.06, COLORS.glass, 0, y, 0, office);
    }
    box(12.6, 0.5, 10.6, COLORS.go, 0, 9.5, 0, office);
    box(3.2, 2.6, 0.3, COLORS.door, 0, 0.5, 5.05, office);
    box(4.2, 0.3, 2, COLORS.go, 0, 3.2, 5.8, office);
    // Signal head on the roof.
    const head = new THREE.Group();
    cyl(0.22, 0.22, 1.6, 0x39425a, 0, 0, 0, head, 10);
    box(2.2, 5.4, 1.5, 0x1f2636, 0, 1.6, 0, head);
    const lampGeo = new THREE.SphereGeometry(0.72, 20, 14);
    [["nogo", 5.8], ["cond", 4.3], ["go", 2.8]].forEach(([key, y]) => {
      const material = new THREE.MeshLambertMaterial({ color: 0x4a5368, emissive: 0x000000 });
      for (const z of [0.62, -0.62]) {
        const lamp = new THREE.Mesh(lampGeo, material);
        lamp.position.set(0, y, z);
        lamp.scale.z = 0.55;
        head.add(lamp);
      }
      lamps[key] = material;
    });
    head.position.set(0, 10, 0);
    head.rotation.y = HOME_AZIMUTH;
    office.add(head);
    const tag = label("Greenlight Office", 1.9, { bg: "#171c26", fg: "#ffffff", font: 600 });
    tag.position.set(0, 19, 0);
    office.add(tag);
    office.position.copy(OFFICE_POS);
    scene.add(office);
    register(office, { kind: "office" });
  })();

  let signal = null;
  function setSignal(state) {
    signal = state;
    for (const key of Object.keys(lamps)) {
      const on = state === key;
      lamps[key].color.setHex(on ? COLORS[key] : 0x4a5368);
      lamps[key].emissive.setHex(on ? COLORS[key] : 0x000000);
    }
  }

  // ---------- agent trailers ----------
  const trailers = new Map();
  agents.forEach((agent, i) => {
    const g = new THREE.Group();
    const hue = AGENT_HUES[i % AGENT_HUES.length];
    box(7, 2.9, 2.9, 0xfafbfd, 0, 0.7, 0, g);
    box(7.05, 0.55, 2.95, hue, 0, 1.5, 0, g);
    box(7.2, 0.2, 3.1, 0xdfe3ec, 0, 3.6, 0, g);
    box(1, 1.9, 0.12, COLORS.door, -1.8, 0.7, 1.46, g);
    box(1.7, 0.9, 0.12, COLORS.glass, 0.9, 2.1, 1.46, g);
    box(3.4, 0.14, 1.5, hue, -0.8, 3.05, 2.2, g);
    box(1.4, 0.22, 1.2, 0x8a94a8, -1.8, 0.25, 2.1, g);
    for (const x of [-2.3, 2.3]) {
      for (const z of [-1.3, 1.3]) {
        const wheel = cyl(0.48, 0.48, 0.36, 0x1f2636, x, 0, z, g, 14);
        wheel.rotation.x = Math.PI / 2;
        wheel.position.y = 0.48;
      }
    }
    cyl(0.07, 0.07, 1.4, 0x8a94a8, 3, 3.8, 0, g, 8);
    const lampMaterial = new THREE.MeshLambertMaterial({ color: COLORS.idle, emissive: 0x000000 });
    const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.42, 16, 12), lampMaterial);
    lamp.position.set(3, 5.4, 0);
    g.add(lamp);
    const tag = label(agent.short, 1.7, { bg: "#ffffff", fg: "#171c26", font: 600 });
    tag.position.set(-0.4, 6.3, 0);
    g.add(tag);
    const col = i % 3;
    const row = Math.floor(i / 3);
    g.scale.setScalar(TRAILER_SCALE);
    g.position.set(-18 + col * 13, 0, 21 + row * 10);
    scene.add(g);
    register(g, { kind: "agent", id: agent.key });
    trailers.set(agent.key, { group: g, lamp, lampMaterial, state: "idle" });
  });

  function setAgentState(key, state) {
    const trailer = trailers.get(key);
    if (!trailer) return;
    trailer.state = state;
    const hex = state === "done" ? COLORS.go : state === "working" ? COLORS.working : COLORS.idle;
    trailer.lampMaterial.color.setHex(hex);
    trailer.lampMaterial.emissive.setHex(state === "idle" ? 0x000000 : hex);
    trailer.lamp.scale.setScalar(1);
  }

  // ---------- couriers (golf carts) ----------
  const couriers = [];
  function buildCart(hue) {
    const g = new THREE.Group();
    box(2.3, 0.6, 1.3, 0xfafbfd, 0, 0.4, 0, g);
    box(0.8, 0.7, 1.2, hue, -0.7, 1, 0, g);
    for (const [x, z] of [[-1, -0.55], [-1, 0.55], [0.9, -0.55], [0.9, 0.55]]) {
      cyl(0.05, 0.05, 1.3, 0x39425a, x, 1, z, g, 6);
    }
    box(2.4, 0.12, 1.4, hue, 0, 2.3, 0, g);
    for (const x of [-0.75, 0.75]) {
      for (const z of [-0.66, 0.66]) {
        const wheel = cyl(0.32, 0.32, 0.22, 0x1f2636, x, 0, z, g, 12);
        wheel.rotation.x = Math.PI / 2;
        wheel.position.y = 0.32;
      }
    }
    return g;
  }

  function dispatchCourier(key) {
    const trailer = trailers.get(key);
    if (!trailer || reducedMotion) return;
    const start = trailer.group.position.clone();
    const index = agents.findIndex((agent) => agent.key === key);
    const lane = APRON_Z + (index % 3) * 0.9;
    const path = [
      new THREE.Vector3(start.x - 2.4, 0, start.z + 3.8),
      new THREE.Vector3(start.x - 6.5, 0, start.z + 3.8),
      new THREE.Vector3(start.x - 6.5, 0, lane),
      new THREE.Vector3(OFFICE_POS.x + 9.5, 0, lane),
      new THREE.Vector3(OFFICE_POS.x + 9.5, 0, OFFICE_POS.z + 8.5),
      new THREE.Vector3(OFFICE_POS.x + 2, 0, OFFICE_POS.z + 8.5),
    ];
    const cart = buildCart(AGENT_HUES[index % AGENT_HUES.length]);
    cart.scale.setScalar(1.25);
    cart.position.copy(path[0]);
    scene.add(cart);
    couriers.push({ cart, path, segment: 0, progress: 0 });
  }

  // ---------- stages (projects) ----------
  const stages = new Map();
  const vacants = [];
  let selectedId = null;

  const ringMaterial = new THREE.MeshBasicMaterial({
    color: COLORS.select,
    transparent: true,
    opacity: 0.9,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const ringSquare = new THREE.Mesh(new THREE.RingGeometry(0.94, 1, 4, 1), ringMaterial);
  ringSquare.rotation.z = Math.PI / 4;
  const ring = new THREE.Group();
  ring.add(ringSquare);
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.1;
  ring.visible = false;
  ringSquare.renderOrder = 3;
  scene.add(ring);

  const dotCanvas = document.createElement("canvas");
  dotCanvas.width = dotCanvas.height = 64;
  const dotCtx = dotCanvas.getContext("2d");
  dotCtx.fillStyle = "#ffffff";
  dotCtx.beginPath();
  dotCtx.arc(32, 32, 28, 0, Math.PI * 2);
  dotCtx.fill();
  const dotTexture = new THREE.CanvasTexture(dotCanvas);

  function stageSize(budget) {
    const millions = Math.max(Number(budget) || 0, 1e6) / 1e6;
    const t = THREE.MathUtils.clamp(Math.log10(millions) / 2.3, 0, 1);
    return { w: 9 + t * 4, d: 11 + t * 4, h: 4.8 + t * 3 };
  }

  function buildStage(project) {
    const { w, d, h } = stageSize(project.budget);
    const color = verdictColor(project.verdict);
    const g = new THREE.Group();
    const body = new THREE.Group();
    g.add(body);

    flat(w + 4.5, d + 6, 0xffffff, 0, 1, 0.04, g, 0.85);
    box(w + 0.4, 0.35, d + 0.4, COLORS.wallTrim, 0, 0, 0, body);
    box(w, h, d, COLORS.wall, 0, 0.35, 0, body);
    // Barrel-vault roof in the verdict colour.
    const roof = new THREE.Mesh(new THREE.CylinderGeometry(w / 2 + 0.25, w / 2 + 0.25, d + 0.7, 28), mat(color));
    roof.rotation.x = Math.PI / 2;
    roof.scale.y = 1;
    roof.scale.x = 1;
    const vault = new THREE.Group();
    vault.add(roof);
    vault.scale.y = 0.34;
    vault.position.y = h + 0.35;
    roof.castShadow = true;
    body.add(vault);
    box(w + 0.7, 0.36, d + 0.9, color, 0, h + 0.2, 0, body);
    // Elephant door and personnel door on the front face.
    box(w * 0.46 + 0.5, h * 0.74 + 0.25, 0.24, color, -w * 0.12, 0.35, d / 2 + 0.02, body);
    box(w * 0.46, h * 0.74, 0.3, COLORS.door, -w * 0.12, 0.35, d / 2 + 0.03, body);
    box(1, 2, 0.24, COLORS.door, w * 0.34, 0.35, d / 2 + 0.02, body);
    // Stage number on the camera-facing side wall and on the front.
    const side = decal(project.slotLabel, h * 0.52, "#39425a");
    side.rotation.y = Math.PI / 2;
    side.position.set(w / 2 + 0.03, h * 0.56, 0);
    body.add(side);
    const front = decal(project.slotLabel, 1.3, "#39425a");
    front.position.set(w * 0.34, 3.5, d / 2 + 0.04);
    body.add(front);
    crateStack(w / 2 + 1.3, d / 2 + 1.2, g, project.verdict === "nogo");
    if (project.verdict !== "nogo") crateStack(-w / 2 + 0.6, d / 2 + 2.6, g, true);

    // Map pin floating above the roof.
    const pin = new THREE.Group();
    const pinMaterial = new THREE.MeshLambertMaterial({ color, emissive: color, emissiveIntensity: 0.25 });
    const ball = new THREE.Mesh(new THREE.SphereGeometry(1.15, 22, 16), pinMaterial);
    ball.position.y = 2.3;
    const tip = new THREE.Mesh(new THREE.ConeGeometry(0.94, 2, 22), pinMaterial);
    tip.rotation.x = Math.PI;
    tip.position.y = 1;
    const dot = new THREE.Sprite(new THREE.SpriteMaterial({ map: dotTexture, depthTest: false, transparent: true }));
    dot.position.y = 2.3;
    dot.scale.set(0.95, 0.95, 1);
    dot.renderOrder = 9;
    pin.add(ball, tip, dot);
    ball.castShadow = true;
    const pinBase = h + 0.35 + w * 0.18 + 0.9;
    pin.position.y = pinBase;
    g.add(pin);

    g.position.copy(slotPosition(project.slot));
    scene.add(g);
    register(g, { kind: "stage", id: project.id });
    return { group: g, body, pin, pinBase, size: { w, d, h }, born: performance.now(), project };
  }

  function buildVacant(slot) {
    const g = new THREE.Group();
    const w = 11;
    const d = 13;
    const y = 0.05;
    const strip = (sw, sd, x, z) => flat(sw, sd, COLORS.vacant, x, z, y, g);
    for (let i = -2; i <= 2; i += 1) {
      strip(1.3, 0.3, i * 2.3, -d / 2);
      strip(1.3, 0.3, i * 2.3, d / 2);
    }
    for (let i = -2; i <= 2; i += 1) {
      strip(0.3, 1.3, -w / 2, i * 2.7);
      strip(0.3, 1.3, w / 2, i * 2.7);
    }
    strip(2.6, 0.45, 0, 0);
    strip(0.45, 2.6, 0, 0);
    const hit = flat(w, d, 0xffffff, 0, 0, 0.03, g, 0.35);
    g.position.copy(slotPosition(slot));
    scene.add(g);
    register(g, { kind: "vacant", slot });
    return g;
  }

  function disposeGroup(group) {
    unregister(group);
    scene.remove(group);
    group.traverse((node) => {
      if (node.geometry) node.geometry.dispose();
      if (node.material?.map && node.material.map !== dotTexture) {
        node.material.map.dispose();
        node.material.dispose();
      }
    });
  }

  function setProjects(projects) {
    const keep = new Set();
    for (const project of projects) {
      const signature = `${project.slot}|${project.verdict}|${project.budget}|${project.slotLabel}`;
      keep.add(project.id);
      const existing = stages.get(project.id);
      if (existing && existing.signature === signature) continue;
      if (existing) disposeGroup(existing.group);
      const stage = buildStage(project);
      stage.signature = signature;
      stages.set(project.id, stage);
    }
    for (const [id, stage] of stages) {
      if (!keep.has(id)) {
        disposeGroup(stage.group);
        stages.delete(id);
      }
    }
    vacants.splice(0).forEach(disposeGroup);
    const rows = projects.length > 8 ? 3 : 2;
    for (let slot = projects.length; slot < rows * SLOT_COLUMNS.length; slot += 1) {
      vacants.push(buildVacant(slot));
    }
    const deep = rows === 3;
    backlot.scale.y = deep ? 1 : 46 / 70;
    backlot.position.z = deep ? -36 : -24;
    backTrees.position.z = deep ? -78 : -54;
    select(selectedId && stages.has(selectedId) ? selectedId : null);
    fitHome();
  }

  function select(id, { focus = false } = {}) {
    selectedId = id;
    const stage = id ? stages.get(id) : null;
    ring.visible = Boolean(stage);
    if (!stage) return;
    const { w, d } = stage.size;
    ring.position.x = stage.group.position.x;
    ring.position.z = stage.group.position.z + 1;
    ring.scale.set((w + 6.5) * 0.72, (d + 8) * 0.72, 1);
    if (focus) goal.target.copy(stage.group.position);
  }

  // ---------- camera ----------
  // Fit the lot's bounding box into the part of the canvas the HUD leaves free.
  function fitHome() {
    const freeW = Math.max(size.w - insets.left - insets.right, 240);
    const freeH = Math.max(size.h - insets.top - insets.bottom, 200);
    const deep = stages.size > 8;
    const bounds = { x0: -52, x1: 34, z0: deep ? -68 : -44, z1: 38, y1: 12 };
    const az = goal.azimuth;
    const right = new THREE.Vector3(Math.cos(az), 0, -Math.sin(az));
    const up = new THREE.Vector3(-Math.sin(az) * Math.sin(ELEVATION), Math.cos(ELEVATION), -Math.cos(az) * Math.sin(ELEVATION));
    const forward = new THREE.Vector3(-Math.sin(az), 0, -Math.cos(az));
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    const corner = new THREE.Vector3();
    for (const x of [bounds.x0, bounds.x1]) {
      for (const z of [bounds.z0, bounds.z1]) {
        for (const y of [0, bounds.y1]) {
          corner.set(x, y, z);
          minX = Math.min(minX, corner.dot(right));
          maxX = Math.max(maxX, corner.dot(right));
          minY = Math.min(minY, corner.dot(up));
          maxY = Math.max(maxY, corner.dot(up));
        }
      }
    }
    homeHeight = size.h * Math.max((maxX - minX) / freeW, (maxY - minY) / freeH) * 1.02;
    homeTarget
      .set(0, 0, 0)
      .addScaledVector(right, (minX + maxX) / 2)
      .addScaledVector(forward, (minY + maxY) / 2 / Math.sin(ELEVATION));
    if (!userMoved) {
      goal.height = homeHeight;
      goal.target.copy(homeTarget);
    }
  }
  const homeTarget = new THREE.Vector3(-10, 0, -4);
  let userMoved = false;

  function applyCamera() {
    const unit = view.height / size.h;
    const dx = insets.left + (size.w - insets.left - insets.right) / 2 - size.w / 2;
    const dy = insets.top + (size.h - insets.top - insets.bottom) / 2 - size.h / 2;
    camera.left = (-size.w / 2 - dx) * unit;
    camera.right = (size.w / 2 - dx) * unit;
    camera.top = (size.h / 2 + dy) * unit;
    camera.bottom = (-size.h / 2 + dy) * unit;
    const distance = 220;
    const horizontal = Math.cos(ELEVATION) * distance;
    camera.position.set(
      view.target.x + Math.sin(view.azimuth) * horizontal,
      Math.sin(ELEVATION) * distance,
      view.target.z + Math.cos(view.azimuth) * horizontal
    );
    camera.lookAt(view.target);
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld();
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    size = { w: Math.max(rect.width, 1), h: Math.max(rect.height, 1) };
    renderer.setSize(size.w, size.h, false);
    fitHome();
  }

  function setInsets(next) {
    insets = next;
    fitHome();
  }

  function control(action) {
    if (action === "in") goal.height = Math.max(goal.height / 1.25, 34);
    if (action === "out") goal.height = Math.min(goal.height * 1.25, 240);
    if (action === "left" || action === "right") {
      // Re-frame the whole lot for the new viewing side.
      goal.azimuth += action === "left" ? -Math.PI / 2 : Math.PI / 2;
      userMoved = false;
      fitHome();
      return;
    }
    if (action === "home") {
      userMoved = false;
      goal.azimuth = Math.round((goal.azimuth - HOME_AZIMUTH) / (Math.PI * 2)) * Math.PI * 2 + HOME_AZIMUTH;
      fitHome();
      return;
    }
    userMoved = true;
  }

  // ---------- pointer: pan, zoom, hover, pick ----------
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let drag = null;
  let hovered = null;

  function pick(event) {
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(pickables, true);
    for (const hit of hits) {
      let node = hit.object;
      while (node && !node.userData.root) node = node.parent;
      if (node) return node;
    }
    return null;
  }

  canvas.addEventListener("pointerdown", (event) => {
    drag = { x: event.clientX, y: event.clientY, moved: false };
    canvas.setPointerCapture(event.pointerId);
  });

  canvas.addEventListener("pointermove", (event) => {
    if (drag) {
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 5) return;
      drag.moved = true;
      drag.x = event.clientX;
      drag.y = event.clientY;
      canvas.classList.add("is-dragging");
      const unit = view.height / size.h;
      const right = new THREE.Vector3(Math.cos(view.azimuth), 0, -Math.sin(view.azimuth));
      const forward = new THREE.Vector3(-Math.sin(view.azimuth), 0, -Math.cos(view.azimuth));
      goal.target.addScaledVector(right, -dx * unit);
      goal.target.addScaledVector(forward, (dy * unit) / Math.sin(ELEVATION));
      goal.target.x = THREE.MathUtils.clamp(goal.target.x, -110, 90);
      goal.target.z = THREE.MathUtils.clamp(goal.target.z, -110, 90);
      view.target.copy(goal.target);
      userMoved = true;
      handlers.onHover?.(null);
      return;
    }
    const node = pick(event);
    if (node !== hovered) {
      hovered = node;
      canvas.classList.toggle("is-hot", Boolean(node));
    }
    handlers.onHover?.(node ? node.userData : null, event.clientX, event.clientY);
  });

  canvas.addEventListener("pointerup", (event) => {
    const wasDrag = drag?.moved;
    drag = null;
    canvas.classList.remove("is-dragging");
    if (wasDrag) return;
    const node = pick(event);
    if (node) handlers.onPick?.(node.userData);
  });

  canvas.addEventListener("pointerleave", () => {
    hovered = null;
    canvas.classList.remove("is-hot");
    handlers.onHover?.(null);
  });

  canvas.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      goal.height = THREE.MathUtils.clamp(goal.height * Math.exp(event.deltaY * 0.001), 34, 240);
      userMoved = true;
    },
    { passive: false }
  );

  // ---------- frame loop ----------
  let last = performance.now();
  function frame(now) {
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    const t = now / 1000;
    const k = reducedMotion ? 1 : 1 - Math.exp(-dt * 7);
    view.target.lerp(goal.target, k);
    view.azimuth += (goal.azimuth - view.azimuth) * k;
    view.height += (goal.height - view.height) * k;
    applyCamera();

    for (const stage of stages.values()) {
      const age = (now - stage.born) / 650;
      const rise = reducedMotion || age >= 1 ? 1 : 1 - Math.pow(1 - age, 3);
      stage.body.scale.y = Math.max(rise, 0.001);
      const isSelected = stage.project.id === selectedId;
      const bob = reducedMotion ? 0 : Math.sin(t * 2.2 + stage.project.slot) * 0.35;
      stage.pin.position.y = stage.pinBase * rise + bob + (isSelected ? 0.8 : 0);
      const pinScale = isSelected ? 1.35 : 1;
      stage.pin.scale.setScalar(stage.pin.scale.x + (pinScale - stage.pin.scale.x) * 0.2);
    }

    if (ring.visible && !reducedMotion) ringMaterial.opacity = 0.65 + Math.sin(t * 3) * 0.25;

    for (const trailer of trailers.values()) {
      if (trailer.state === "working" && !reducedMotion) {
        trailer.lamp.scale.setScalar(1 + Math.sin(t * 9) * 0.28);
      }
    }

    if (signal === "thinking") {
      const order = ["nogo", "cond", "go"];
      const active = order[Math.floor(t * 4) % 3];
      for (const key of order) {
        const on = key === active;
        lamps[key].color.setHex(on ? COLORS[key] : 0x4a5368);
        lamps[key].emissive.setHex(on ? COLORS[key] : 0x000000);
      }
    }

    for (let i = couriers.length - 1; i >= 0; i -= 1) {
      const courier = couriers[i];
      const from = courier.path[courier.segment];
      const to = courier.path[courier.segment + 1];
      const length = from.distanceTo(to);
      courier.progress += (dt * 22) / Math.max(length, 0.001);
      if (courier.progress >= 1) {
        courier.segment += 1;
        courier.progress = 0;
        if (courier.segment >= courier.path.length - 1) {
          disposeGroup(courier.cart);
          couriers.splice(i, 1);
          continue;
        }
      }
      const a = courier.path[courier.segment];
      const b = courier.path[courier.segment + 1];
      courier.cart.position.lerpVectors(a, b, courier.progress);
      courier.cart.rotation.y = Math.atan2(-(b.z - a.z), b.x - a.x);
    }

    if (!reducedMotion) {
      truck.position.x += dt * 9;
      if (truck.position.x > 150) truck.position.x = -150;
    }

    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }

  new ResizeObserver(resize).observe(canvas);
  resize();
  setProjects([]);
  view.height = goal.height;
  view.target.copy(goal.target);
  requestAnimationFrame(frame);

  return {
    setProjects,
    select,
    setAgentState,
    dispatchCourier,
    setSignal,
    setInsets,
    control,
  };
}
