"use strict";

// Marching tetrahedra on the supplied density volume. Rendering never evolves psi.
window.DensitySurface3D = class {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.triangles = [];
    this.zoom = 1;
    this.home();
    let last = null;
    canvas.addEventListener("pointerdown", (e) => {
      last = [e.clientX, e.clientY];
      canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener("pointermove", (e) => {
      if (!last) return;
      this.yaw += (e.clientX - last[0]) * 0.009;
      this.pitch = Math.max(
        -1.4,
        Math.min(1.4, this.pitch + (e.clientY - last[1]) * 0.009),
      );
      last = [e.clientX, e.clientY];
      this.draw();
    });
    for (const event of ["pointerup", "pointercancel", "lostpointercapture"])
      canvas.addEventListener(event, () => {
        last = null;
      });
    canvas.addEventListener("keydown", (e) => {
      if (!e.key.startsWith("Arrow")) return;
      e.preventDefault();
      this.yaw +=
        e.key === "ArrowRight" ? 0.12 : e.key === "ArrowLeft" ? -0.12 : 0;
      this.pitch = Math.max(
        -1.4,
        Math.min(
          1.4,
          this.pitch +
            (e.key === "ArrowDown" ? 0.12 : e.key === "ArrowUp" ? -0.12 : 0),
        ),
      );
      this.draw();
    });
  }
  home() {
    this.yaw = -0.65;
    this.pitch = 0.38;
    this.draw();
  }
  update(snapshot, fraction) {
    const {
      volume: v,
      volume_n: n,
      volume_centers: centers,
      config: c,
    } = snapshot;
    const peak = v.reduce((a, b) => Math.max(a, b), 0),
      level = peak * fraction;
    this.triangles = [];
    const offsets = [
      [0, 0, 0],
      [1, 0, 0],
      [1, 1, 0],
      [0, 1, 0],
      [0, 0, 1],
      [1, 0, 1],
      [1, 1, 1],
      [0, 1, 1],
    ];
    const tetra = [
      [0, 5, 1, 6],
      [0, 1, 2, 6],
      [0, 2, 3, 6],
      [0, 3, 7, 6],
      [0, 7, 4, 6],
      [0, 4, 5, 6],
    ];
    const cross = (a, b) => [
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0],
    ];
    const sub = (a, b) => a.map((x, i) => x - b[i]);
    const add = (a, b, d, inside) => {
      let normal = cross(sub(b, a), sub(d, a));
      if (normal.reduce((sum, x, i) => sum + x * (inside[i] - a[i]), 0) > 0)
        normal = normal.map((x) => -x);
      const length = Math.hypot(...normal);
      if (length > 1e-12)
        this.triangles.push({
          p: [a, b, d],
          normal: normal.map((x) => x / length),
        });
    };
    for (let x = 0; x < n - 1; x++)
      for (let y = 0; y < n - 1; y++)
        for (let z = 0; z < n - 1; z++) {
          const vals = offsets.map(
            (o) => v[((x + o[0]) * n + y + o[1]) * n + z + o[2]],
          );
          if (Math.max(...vals) < level || Math.min(...vals) >= level) continue;
          const pts = offsets.map((o) =>
            [centers[x + o[0]], centers[y + o[1]], centers[z + o[2]]].map(
              (a) => a / c.length,
            ),
          );
          const edge = (a, b) => {
            const t = (level - vals[a]) / (vals[b] - vals[a]);
            return pts[a].map((p, i) => p + t * (pts[b][i] - p));
          };
          for (const t of tetra) {
            const hi = t.filter((i) => vals[i] >= level),
              lo = t.filter((i) => vals[i] < level);
            if (!hi.length || !lo.length) continue;
            if (hi.length === 1)
              add(...lo.map((j) => edge(hi[0], j)), pts[hi[0]]);
            else if (lo.length === 1)
              add(...hi.map((j) => edge(lo[0], j)), pts[hi[0]]);
            else {
              const [a, b, d, e] = [
                edge(hi[0], lo[0]),
                edge(hi[0], lo[1]),
                edge(hi[1], lo[0]),
                edge(hi[1], lo[1]),
              ];
              add(a, b, d, pts[hi[0]]);
              add(b, e, d, pts[hi[0]]);
            }
          }
        }
    this.level = level;
    this.draw();
  }
  rotate(p) {
    // Physical z is up; y points into the scene in the home orientation.
    const [x, y, z] = [p[0], p[2], p[1]],
      cy = Math.cos(this.yaw),
      sy = Math.sin(this.yaw),
      cp = Math.cos(this.pitch),
      sp = Math.sin(this.pitch);
    const xx = cy * x + sy * z,
      zz = -sy * x + cy * z;
    return [xx, cp * y - sp * zz, sp * y + cp * zz];
  }
  draw() {
    if (!this.ctx) return;
    const ctx = this.ctx,
      w = this.canvas.width,
      h = this.canvas.height,
      scale = h * 0.6 * this.zoom;
    ctx.fillStyle = "#0e2028";
    ctx.fillRect(0, 0, w, h);
    const project = (p) => {
      const q = this.rotate(p);
      return [w / 2 + q[0] * scale, h / 2 - q[1] * scale, q[2]];
    };
    ctx.strokeStyle = "#34505b";
    ctx.lineWidth = 1;
    const corners = [];
    for (let x of [-0.5, 0.5])
      for (let y of [-0.5, 0.5])
        for (let z of [-0.5, 0.5]) corners.push([x, y, z]);
    corners.forEach((p, i) =>
      corners.forEach((q, j) => {
        if (j <= i || p.filter((a, k) => a !== q[k]).length !== 1) return;
        const a = project(p),
          b = project(q);
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
        ctx.stroke();
      }),
    );
    const faces = this.triangles.map((t) => ({
      p: t.p.map(project),
      n: this.rotate(t.normal),
    }));
    faces.sort(
      (a, b) =>
        a.p.reduce((s, p) => s + p[2], 0) - b.p.reduce((s, p) => s + p[2], 0),
    );
    for (const face of faces) {
      const light =
        0.35 +
        0.65 *
          Math.max(0, face.n[0] * -0.3 + face.n[1] * 0.5 + face.n[2] * 0.8124);
      ctx.fillStyle = `rgb(${Math.round(60 * light)},${Math.round(204 * light)},${Math.round(205 * light)})`;
      ctx.beginPath();
      face.p.forEach((p, i) =>
        i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]),
      );
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = ctx.fillStyle;
      ctx.lineWidth = 0.45;
      ctx.stroke();
    }
    const origin = project([-0.5, -0.5, -0.5]);
    [
      [0.58, -0.5, -0.5],
      [-0.5, 0.58, -0.5],
      [-0.5, -0.5, 0.58],
    ].forEach((p, i) => {
      const b = project(p);
      ctx.strokeStyle = ["#7ba8ff", "#69e1d5", "#e9be72"][i];
      ctx.fillStyle = ctx.strokeStyle;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(...origin.slice(0, 2));
      ctx.lineTo(...b.slice(0, 2));
      ctx.stroke();
      ctx.font = "18px sans-serif";
      ctx.fillText("xyz"[i], b[0] + 5, b[1]);
    });
  }
};
