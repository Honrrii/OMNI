/**
 * space-bg.js
 * Halo Reach / Warframe-style reactive space background.
 *
 * HOW TO USE:
 *   1. Add <canvas id="space-canvas"></canvas> to your HTML root (before #root).
 *   2. Add <div class="space-grid"></div> and three
 *      <div class="space-scanline"></div> elements.
 *   3. Import and call initSpaceBg() from your App.jsx useEffect, or
 *      include this script in index.html as a module.
 *
 * In App.jsx (recommended):
 *   import { initSpaceBg } from './space-bg';
 *   useEffect(() => {
 *     const cleanup = initSpaceBg();
 *     return cleanup;
 *   }, []);
 */

export function initSpaceBg() {
  const canvas = document.getElementById('space-canvas');
  if (!canvas) return () => {};

  const ctx = canvas.getContext('2d');

  // ── Mouse parallax state ──────────────────────────────────────────
  let mouse = { x: 0.5, y: 0.5 };
  let smoothMouse = { x: 0.5, y: 0.5 };

  const onMouseMove = (e) => {
    mouse.x = e.clientX / window.innerWidth;
    mouse.y = e.clientY / window.innerHeight;
  };
  window.addEventListener('mousemove', onMouseMove, { passive: true });

  // ── Resize handling ───────────────────────────────────────────────
  let W, H;
  const resize = () => {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
    buildStars();
    buildNebulaClouds();
  };
  window.addEventListener('resize', resize, { passive: true });

  // ── Star layers (parallax depth 0..1) ────────────────────────────
  let stars = [];

  function buildStars() {
    stars = [];

    // Back layer — tiny, dim, barely moving (deep field)
    for (let i = 0; i < 480; i++) {
      stars.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: Math.random() * 0.7 + 0.2,
        a: Math.random() * 0.35 + 0.08,
        depth: 0.05 + Math.random() * 0.10,  // parallax factor
        twinkleSpeed: 0.4 + Math.random() * 0.8,
        twinklePhase: Math.random() * Math.PI * 2,
        color: pickStarColor(),
      });
    }

    // Mid layer — medium, moderate glow
    for (let i = 0; i < 200; i++) {
      stars.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: Math.random() * 1.2 + 0.5,
        a: Math.random() * 0.55 + 0.15,
        depth: 0.15 + Math.random() * 0.15,
        twinkleSpeed: 0.6 + Math.random() * 1.2,
        twinklePhase: Math.random() * Math.PI * 2,
        color: pickStarColor(),
      });
    }

    // Front layer — bright, larger, bigger parallax (foreground field)
    for (let i = 0; i < 55; i++) {
      stars.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: Math.random() * 2.0 + 1.0,
        a: Math.random() * 0.75 + 0.25,
        depth: 0.30 + Math.random() * 0.20,
        twinkleSpeed: 0.8 + Math.random() * 1.6,
        twinklePhase: Math.random() * Math.PI * 2,
        color: pickStarColor(),
        glint: Math.random() > 0.55, // some stars get a lens glint
      });
    }

    // Hero stars — very bright, large halos, significant parallax
    for (let i = 0; i < 12; i++) {
      stars.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: 2.5 + Math.random() * 2.0,
        a: 0.65 + Math.random() * 0.35,
        depth: 0.45 + Math.random() * 0.20,
        twinkleSpeed: 1.0 + Math.random() * 1.5,
        twinklePhase: Math.random() * Math.PI * 2,
        color: pickHeroStarColor(),
        hero: true,
        glint: true,
      });
    }
  }

  function pickStarColor() {
    const roll = Math.random();
    if (roll < 0.55) return '#e8f4ff';     // blue-white (O/B type)
    if (roll < 0.72) return '#fff8f0';     // yellow-white (F/G)
    if (roll < 0.83) return '#ffeedd';     // warm white
    if (roll < 0.91) return '#c8d8ff';     // blue
    if (roll < 0.96) return '#ffe0b0';     // orange
    return '#ffcccc';                       // rare red
  }

  function pickHeroStarColor() {
    const options = ['#d0e8ff', '#ffffff', '#e0d0ff', '#c8e0ff', '#f0e0ff'];
    return options[Math.floor(Math.random() * options.length)];
  }

  // ── Nebula cloud data ─────────────────────────────────────────────
  let clouds = [];

  function buildNebulaClouds() {
    clouds = [
      {
        cx: W * 0.72, cy: H * 0.14,
        rx: W * 0.28, ry: H * 0.22,
        color0: 'rgba(40,100,220,0)',
        color1: 'rgba(40,100,220,0.07)',
        depth: 0.04,
        rot: 0,
        rotSpeed: 0.00008,
      },
      {
        cx: W * 0.18, cy: H * 0.78,
        rx: W * 0.24, ry: H * 0.20,
        color0: 'rgba(90,20,160,0)',
        color1: 'rgba(90,20,160,0.055)',
        depth: 0.03,
        rot: 0.8,
        rotSpeed: -0.00006,
      },
      {
        cx: W * 0.50, cy: H * 0.50,
        rx: W * 0.40, ry: H * 0.35,
        color0: 'rgba(10,30,80,0)',
        color1: 'rgba(10,30,80,0.12)',
        depth: 0.02,
        rot: 0,
        rotSpeed: 0.00004,
      },
      {
        cx: W * 0.85, cy: H * 0.60,
        rx: W * 0.18, ry: H * 0.24,
        color0: 'rgba(0,180,180,0)',
        color1: 'rgba(0,180,180,0.04)',
        depth: 0.025,
        rot: 1.2,
        rotSpeed: 0.00005,
      },
    ];
  }

  // ── Planet / moon (Halo Reach style) ─────────────────────────────
  const PLANET = {
    // upper-right corner, partially off-screen
    cx: () => W * 0.88,
    cy: () => H * 0.08,
    r:  () => Math.min(W, H) * 0.20,
    depth: 0.012, // very subtle parallax — it's far away
  };

  function drawPlanet(px, py) {
    const r = PLANET.r();

    // Atmospheric halo
    const halo = ctx.createRadialGradient(px, py, r * 0.70, px, py, r * 1.55);
    halo.addColorStop(0,   'rgba(80,150,255,0.00)');
    halo.addColorStop(0.5, 'rgba(80,150,255,0.04)');
    halo.addColorStop(1,   'rgba(40,80,200,0.00)');
    ctx.beginPath();
    ctx.arc(px, py, r * 1.55, 0, Math.PI * 2);
    ctx.fillStyle = halo;
    ctx.fill();

    // Planet body
    const body = ctx.createRadialGradient(
      px - r * 0.30, py - r * 0.30, r * 0.05,
      px, py, r
    );
    body.addColorStop(0,   'rgba(200,225,255,0.75)');
    body.addColorStop(0.4, 'rgba(100,160,220,0.55)');
    body.addColorStop(0.75,'rgba(40,70,160,0.40)');
    body.addColorStop(1,   'rgba(10,20,60,0.00)');

    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fillStyle = body;
    ctx.fill();

    // Terminator / limb shadow (dark crescent on right)
    const shadow = ctx.createRadialGradient(
      px + r * 0.35, py, r * 0.15,
      px + r * 0.20, py, r * 1.05
    );
    shadow.addColorStop(0,   'rgba(0,0,0,0.00)');
    shadow.addColorStop(0.5, 'rgba(0,0,0,0.10)');
    shadow.addColorStop(1,   'rgba(0,5,20,0.50)');
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fillStyle = shadow;
    ctx.fill();

    // Thin bright limb on lit side
    const limb = ctx.createRadialGradient(
      px - r * 0.80, py - r * 0.80, r * 0.60,
      px - r * 0.80, py - r * 0.80, r * 1.10
    );
    limb.addColorStop(0,   'rgba(200,230,255,0.00)');
    limb.addColorStop(0.85,'rgba(200,230,255,0.00)');
    limb.addColorStop(0.92,'rgba(200,230,255,0.22)');
    limb.addColorStop(1,   'rgba(200,230,255,0.00)');
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fillStyle = limb;
    ctx.fill();
  }

  // ── Lens glint helper ─────────────────────────────────────────────
  function drawGlint(x, y, r, alpha) {
    // Cross flare
    const len = r * 5.5;
    const half = len / 2;
    ctx.save();
    ctx.globalAlpha = alpha * 0.28;
    ctx.strokeStyle = '#c8e4ff';
    ctx.lineWidth = 0.6;

    ctx.beginPath();
    ctx.moveTo(x - half, y);
    ctx.lineTo(x + half, y);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(x, y - half * 0.55);
    ctx.lineTo(x, y + half * 0.55);
    ctx.stroke();

    ctx.restore();
  }

  // ── Shooting star state ───────────────────────────────────────────
  const shooters = [];

  function spawnShooter() {
    shooters.push({
      x:     -100 + Math.random() * W * 0.5,
      y:      Math.random() * H * 0.5,
      vx:    12 + Math.random() * 14,
      vy:     4 + Math.random() * 8,
      len:   80 + Math.random() * 160,
      a:     0.7 + Math.random() * 0.3,
      life:  1,
      decay: 0.014 + Math.random() * 0.012,
    });
  }

  // Spawn first one slightly delayed
  let shooterTimer = 4000 + Math.random() * 5000;
  let lastTime = 0;

  // ── Main draw loop ────────────────────────────────────────────────
  let raf;

  function draw(timestamp) {
    const dt = Math.min(timestamp - lastTime, 50); // cap at 50ms
    lastTime = timestamp;

    // Smooth mouse
    const ease = 0.04;
    smoothMouse.x += (mouse.x - smoothMouse.x) * ease;
    smoothMouse.y += (mouse.y - smoothMouse.y) * ease;

    // Shooting star timer
    shooterTimer -= dt;
    if (shooterTimer <= 0) {
      spawnShooter();
      shooterTimer = 5500 + Math.random() * 8500;
    }

    ctx.clearRect(0, 0, W, H);

    // -- Nebula clouds
    for (const c of clouds) {
      c.rot += c.rotSpeed * dt;
      const dx = (smoothMouse.x - 0.5) * W * c.depth * 2;
      const dy = (smoothMouse.y - 0.5) * H * c.depth * 2;
      const px = c.cx + dx;
      const py = c.cy + dy;

      ctx.save();
      ctx.translate(px, py);
      ctx.rotate(c.rot);
      const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, Math.max(c.rx, c.ry));
      grad.addColorStop(0, c.color1);
      grad.addColorStop(1, c.color0);
      ctx.scale(c.rx / Math.max(c.rx, c.ry), c.ry / Math.max(c.rx, c.ry));
      ctx.beginPath();
      ctx.arc(0, 0, Math.max(c.rx, c.ry), 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.restore();
    }

    // -- Planet
    {
      const basePx = PLANET.cx();
      const basePy = PLANET.cy();
      const dx = (smoothMouse.x - 0.5) * W * PLANET.depth;
      const dy = (smoothMouse.y - 0.5) * H * PLANET.depth;
      drawPlanet(basePx + dx, basePy + dy);
    }

    // -- Stars
    const t = timestamp * 0.001;
    for (const s of stars) {
      const twinkle = 0.5 + 0.5 * Math.sin(t * s.twinkleSpeed + s.twinklePhase);
      const alpha = s.a * (0.65 + 0.35 * twinkle);

      // Parallax offset
      const dx = (smoothMouse.x - 0.5) * W * s.depth;
      const dy = (smoothMouse.y - 0.5) * H * s.depth;
      const sx = ((s.x + dx + W) % W);
      const sy = ((s.y + dy + H) % H);

      ctx.globalAlpha = alpha;

      if (s.hero) {
        // Soft glow halo
        const haloR = s.r * 4.5;
        const halo = ctx.createRadialGradient(sx, sy, 0, sx, sy, haloR);
        halo.addColorStop(0,   hexToRgba(s.color, alpha * 0.55));
        halo.addColorStop(1,   hexToRgba(s.color, 0));
        ctx.beginPath();
        ctx.arc(sx, sy, haloR, 0, Math.PI * 2);
        ctx.fillStyle = halo;
        ctx.globalAlpha = 1;
        ctx.fill();
      }

      // Core dot
      ctx.globalAlpha = alpha;
      ctx.beginPath();
      ctx.arc(sx, sy, s.r, 0, Math.PI * 2);
      ctx.fillStyle = s.color;
      ctx.fill();

      if (s.glint) {
        drawGlint(sx, sy, s.r, alpha);
      }
    }
    ctx.globalAlpha = 1;

    // -- Shooting stars
    for (let i = shooters.length - 1; i >= 0; i--) {
      const sh = shooters[i];
      sh.x   += sh.vx * dt * 0.08;
      sh.y   += sh.vy * dt * 0.08;
      sh.life -= sh.decay * (dt / 16);

      if (sh.life <= 0 || sh.x > W + 200) {
        shooters.splice(i, 1);
        continue;
      }

      const tailX = sh.x - Math.cos(Math.atan2(sh.vy, sh.vx)) * sh.len;
      const tailY = sh.y - Math.sin(Math.atan2(sh.vy, sh.vx)) * sh.len;

      const grad = ctx.createLinearGradient(tailX, tailY, sh.x, sh.y);
      grad.addColorStop(0,   'rgba(255,255,255,0.00)');
      grad.addColorStop(0.6, `rgba(160,210,255,${sh.life * sh.a * 0.45})`);
      grad.addColorStop(1,   `rgba(255,255,255,${sh.life * sh.a})`);

      ctx.beginPath();
      ctx.moveTo(tailX, tailY);
      ctx.lineTo(sh.x, sh.y);
      ctx.strokeStyle = grad;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Bright head
      ctx.beginPath();
      ctx.arc(sh.x, sh.y, 1.2, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(240,250,255,${sh.life * sh.a})`;
      ctx.fill();
    }

    raf = requestAnimationFrame(draw);
  }

  // Tiny hex-to-rgba converter
  function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha.toFixed(3)})`;
  }

  // ── Start ─────────────────────────────────────────────────────────
  resize();
  lastTime = performance.now();
  raf = requestAnimationFrame(draw);

  // Return cleanup fn for React useEffect
  return () => {
    cancelAnimationFrame(raf);
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('resize', resize);
  };
}


/* ── HTML injection helper (for non-React setups) ───────────────── */

/**
 * Call this if you're not using React.
 * It injects the canvas + divs then starts the background.
 */
export function injectSpaceBg() {
  if (!document.getElementById('space-canvas')) {
    const canvas = document.createElement('canvas');
    canvas.id = 'space-canvas';
    document.body.prepend(canvas);
  }

  if (!document.querySelector('.space-grid')) {
    const grid = document.createElement('div');
    grid.className = 'space-grid';
    document.body.prepend(grid);
  }

  for (let i = 0; i < 3; i++) {
    const sl = document.createElement('div');
    sl.className = 'space-scanline';
    document.body.prepend(sl);
  }

  return initSpaceBg();
}
