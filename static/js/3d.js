(function () {
  if (typeof THREE === 'undefined') return;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.z = 3.5;

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.domElement.className = 'three-canvas';
  renderer.domElement.style.position = 'fixed';
  renderer.domElement.style.top = '0';
  renderer.domElement.style.left = '0';
  renderer.domElement.style.zIndex = '0';
  renderer.domElement.style.pointerEvents = 'none';
  renderer.domElement.style.opacity = '0.95';
  document.body.appendChild(renderer.domElement);

  const ambient = new THREE.AmbientLight(0xffffff, 0.6);
  scene.add(ambient);
  const keyLight = new THREE.DirectionalLight(0xffffff, 1.0);
  keyLight.position.set(5, 3, 5);
  scene.add(keyLight);
  const rimLight = new THREE.PointLight(0x88ccff, 0.6);
  rimLight.position.set(-5, -3, -3);
  scene.add(rimLight);

  // Group for clapperboard
  const boardGroup = new THREE.Group();
  scene.add(boardGroup);

  // Clapperboard base (slightly rounded box)
  const baseWidth = 1.8;
  const baseHeight = 1.1;
  const baseDepth = 0.08;
  const baseGeo = new THREE.BoxGeometry(baseWidth, baseHeight, baseDepth);
  const baseMat = new THREE.MeshStandardMaterial({ color: 0x0b0b0b, metalness: 0.15, roughness: 0.4 });
  const base = new THREE.Mesh(baseGeo, baseMat);
  base.position.set(0, 0, 0);
  boardGroup.add(base);

  // Draw a play-circle decal on the base using canvas
  const decalCanvas = document.createElement('canvas');
  decalCanvas.width = 512;
  decalCanvas.height = 512;
  const dctx = decalCanvas.getContext('2d');
  // background transparent
  dctx.clearRect(0, 0, 512, 512);
  // white circle with blue triangle
  dctx.fillStyle = '#ffffff';
  dctx.beginPath();
  dctx.arc(256, 256, 160, 0, Math.PI * 2);
  dctx.fill();
  dctx.fillStyle = '#1e90ff';
  dctx.beginPath();
  dctx.moveTo(300, 256);
  dctx.lineTo(220, 310);
  dctx.lineTo(220, 202);
  dctx.closePath();
  dctx.fill();
  const decalTex = new THREE.CanvasTexture(decalCanvas);
  decalTex.needsUpdate = true;
  const decalMat = new THREE.MeshBasicMaterial({ map: decalTex, transparent: true });
  const decalPlane = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 0.6), decalMat);
  decalPlane.position.set(0.6, -0.0, baseDepth / 2 + 0.001);
  boardGroup.add(decalPlane);

  // Clapper (top hinged) - use canvas texture for diagonal stripes
  const clapCanvas = document.createElement('canvas');
  clapCanvas.width = 1024;
  clapCanvas.height = 256;
  const cctx = clapCanvas.getContext('2d');
  // fill black
  cctx.fillStyle = '#111111';
  cctx.fillRect(0, 0, 1024, 256);
  // draw diagonal white stripes
  cctx.strokeStyle = '#ffffff';
  cctx.lineWidth = 64;
  for (let x = -512; x < 1536; x += 160) {
    cctx.beginPath();
    cctx.moveTo(x, 0);
    cctx.lineTo(x + 128, 256);
    cctx.stroke();
  }
  const clapTex = new THREE.CanvasTexture(clapCanvas);
  clapTex.wrapS = clapTex.wrapT = THREE.RepeatWrapping;

  const clapGeo = new THREE.BoxGeometry(baseWidth + 0.02, 0.18, 0.04);
  const clapMat = new THREE.MeshStandardMaterial({ map: clapTex, metalness: 0.2, roughness: 0.5 });
  const clapper = new THREE.Mesh(clapGeo, clapMat);
  clapper.position.set(0, baseHeight / 2 - 0.08, baseDepth / 2 + 0.02);
  // pivot for hinge
  const hinge = new THREE.Group();
  hinge.position.set(0, baseHeight / 2 - 0.08, baseDepth / 2 + 0.02);
  hinge.add(clapper);
  boardGroup.add(hinge);

  // small metal hinge visuals
  const hingeGeo = new THREE.CylinderGeometry(0.02, 0.02, baseWidth, 8);
  const hingeMat = new THREE.MeshStandardMaterial({ color: 0x777777, metalness: 0.9, roughness: 0.25 });
  const hingePipe = new THREE.Mesh(hingeGeo, hingeMat);
  hingePipe.rotation.z = Math.PI / 2;
  hingePipe.position.set(0, baseHeight / 2 - 0.08, baseDepth / 2 + 0.01);
  boardGroup.add(hingePipe);

  // Starfield / particles behind globe
  const ptsGeom = new THREE.BufferGeometry();
  const ptsCount = 900;
  const positions = new Float32Array(ptsCount * 3);
  for (let i = 0; i < ptsCount; i++) {
    const r = 40 * Math.cbrt(Math.random());
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos((Math.random() * 2) - 1);
    positions[i * 3 + 0] = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = r * Math.cos(phi);
  }
  ptsGeom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const ptsMat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.04, opacity: 0.85, transparent: true });
  const points = new THREE.Points(ptsGeom, ptsMat);
  scene.add(points);

  // Resize handling
  function onResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }
  window.addEventListener('resize', onResize);

  // Simple mouse parallax
  let mouseX = 0, mouseY = 0;
  window.addEventListener('mousemove', (e) => {
    const nx = (e.clientX / window.innerWidth) - 0.5;
    const ny = (e.clientY / window.innerHeight) - 0.5;
    mouseX = nx * 0.6;
    mouseY = ny * 0.4;
  });

  // Animation loop
  function animate() {
    requestAnimationFrame(animate);
    // animate clapperboard
    const t = Date.now() * 0.0012;
    // slow group rotation responding to mouse
    boardGroup.rotation.x += (mouseY - boardGroup.rotation.x) * 0.02;
    boardGroup.rotation.y += (mouseX - boardGroup.rotation.y) * 0.02 + 0.002;
    boardGroup.position.y = Math.sin(t * 0.6) * 0.04;

    // hinge clap slight oscillation
    hinge.rotation.z = Math.sin(t * 1.3) * 0.25 - 0.6;

    // slow starfield rotation
    points.rotation.y += 0.0004;

    renderer.render(scene, camera);
  }
  animate();
})();
      }
    } else {
  // Gentle breathing idle oscillation for top arm
  hingePivot.rotation.z = defaultClapAngle + Math.sin(elapsedTime * 1.4) * 0.04;
}

// 4. Space Starfield & Dust Movement
starPoints.rotation.y = elapsedTime * 0.015;
starPoints.rotation.x = Math.sin(elapsedTime * 0.01) * 0.02;
dustPoints.rotation.y = -elapsedTime * 0.025;

// Render
renderer.render(scene, camera);
  }

animate();
}) ();

