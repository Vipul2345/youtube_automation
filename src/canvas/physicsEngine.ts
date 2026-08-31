import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createCanvas, Canvas, CanvasRenderingContext2D } from 'canvas';
import ffmpegPath from '@ffmpeg-installer/ffmpeg';
import { logger } from '../utils/logger.js';

export type ShapeType = 'circle' | 'square' | 'triangle' | 'pentagon' | 'hexagon' | 'star';

export interface PhysicsBody {
  id: number;
  type: ShapeType;
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  mass: number;
  angle: number;
  angularVelocity: number;
  color: string;
  strokeColor: string;
}

const NEON_PALETTE = [
  { fill: 'rgba(0, 240, 255, 0.75)', stroke: '#00F0FF' },   // Electric Cyan
  { fill: 'rgba(255, 0, 127, 0.75)', stroke: '#FF007F' },   // Neon Magenta
  { fill: 'rgba(255, 230, 0, 0.75)', stroke: '#FFE600' },   // Bright Yellow
  { fill: 'rgba(0, 255, 102, 0.75)', stroke: '#00FF66' },   // Neon Lime Green
  { fill: 'rgba(157, 0, 255, 0.75)', stroke: '#9D00FF' },   // Deep Purple
  { fill: 'rgba(255, 102, 0, 0.75)', stroke: '#FF6600' }    // Bright Orange
];

/**
 * Initializes a pool of physical geometric bodies with random positions and velocities.
 */
export function createPhysicsWorld(count: number = 16, width: number = 1080, height: number = 1920): PhysicsBody[] {
  const shapes: ShapeType[] = ['circle', 'square', 'triangle', 'pentagon', 'hexagon', 'star'];
  const bodies: PhysicsBody[] = [];

  for (let i = 0; i < count; i++) {
    const type = shapes[i % shapes.length];
    const radius = 45 + Math.random() * 35; // Size between 45px and 80px
    const palette = NEON_PALETTE[i % NEON_PALETTE.length];

    bodies.push({
      id: i,
      type,
      x: 100 + Math.random() * (width - 200),
      y: 100 + Math.random() * (height - 200),
      vx: (Math.random() - 0.5) * 350, // Velocity in px/sec
      vy: (Math.random() - 0.5) * 350,
      radius,
      mass: Math.PI * radius * radius,
      angle: Math.random() * Math.PI * 2,
      angularVelocity: (Math.random() - 0.5) * 2.5,
      color: palette.fill,
      strokeColor: palette.stroke
    });
  }

  return bodies;
}

/**
 * Updates physics simulation for 1 frame step (dt in seconds).
 * Enforces:
 * 1. Side wall elastic bounce (Left & Right)
 * 2. Top & Bottom toroidal wrap-around
 * 3. Pairwise elastic 2D body collisions with repulsion
 */
export function updatePhysicsWorld(bodies: PhysicsBody[], width: number, height: number, dt: number): void {
  // 1. Move bodies & update rotation
  for (const b of bodies) {
    b.x += b.vx * dt;
    b.y += b.vy * dt;
    b.angle += b.angularVelocity * dt;

    // 2. Side Walls Elastic Bounce (Left & Right)
    if (b.x - b.radius < 0) {
      b.x = b.radius;
      b.vx = -b.vx * 0.98;
    } else if (b.x + b.radius > width) {
      b.x = width - b.radius;
      b.vx = -b.vx * 0.98;
    }

    // 3. Top & Bottom Toroidal Wrap-Around
    if (b.y + b.radius < -20) {
      b.y = height + b.radius;
    } else if (b.y - b.radius > height + 20) {
      b.y = -b.radius;
    }
  }

  // 4. Pairwise Elastic Collisions with Repulsion Impulse
  for (let i = 0; i < bodies.length; i++) {
    for (let j = i + 1; j < bodies.length; j++) {
      const b1 = bodies[i];
      const b2 = bodies[j];

      const dx = b2.x - b1.x;
      const dy = b2.y - b1.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const minDist = b1.radius + b2.radius;

      if (dist < minDist && dist > 0.0001) {
        // Normal collision vector
        const nx = dx / dist;
        const ny = dy / dist;

        // Relative velocity
        const rvx = b2.vx - b1.vx;
        const rvy = b2.vy - b1.vy;
        const velAlongNormal = rvx * nx + rvy * ny;

        // Only resolve if moving towards each other
        if (velAlongNormal < 0) {
          const restitution = 0.95; // Elasticity
          const impulseScalar = (-(1 + restitution) * velAlongNormal) / ((1 / b1.mass) + (1 / b2.mass));

          const ix = impulseScalar * nx;
          const iy = impulseScalar * ny;

          b1.vx -= (1 / b1.mass) * ix;
          b1.vy -= (1 / b1.mass) * iy;
          b2.vx += (1 / b2.mass) * ix;
          b2.vy += (1 / b2.mass) * iy;

          // Add torque / spin on collision
          b1.angularVelocity += (Math.random() - 0.5) * 1.5;
          b2.angularVelocity += (Math.random() - 0.5) * 1.5;
        }

        // Separate overlapping bodies to prevent sticking
        const overlap = minDist - dist;
        const separationX = nx * overlap * 0.5;
        const separationY = ny * overlap * 0.5;

        b1.x -= separationX;
        b1.y -= separationY;
        b2.x += separationX;
        b2.y += separationY;
      }
    }
  }
}

/**
 * Draws a regular polygon (triangle, square, pentagon, hexagon) or star on canvas.
 */
function drawPolygon(ctx: CanvasRenderingContext2D, sides: number, radius: number) {
  ctx.beginPath();
  for (let i = 0; i < sides; i++) {
    const a = (i * 2 * Math.PI) / sides - Math.PI / 2;
    const px = Math.cos(a) * radius;
    const py = Math.sin(a) * radius;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
}

function drawStar(ctx: CanvasRenderingContext2D, points: number, outerRadius: number, innerRadius: number) {
  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const r = i % 2 === 0 ? outerRadius : innerRadius;
    const a = (i * Math.PI) / points - Math.PI / 2;
    const px = Math.cos(a) * r;
    const py = Math.sin(a) * r;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
}

/**
 * Render 1 frame of physics world onto 2D canvas.
 */
export function renderPhysicsFrame(ctx: CanvasRenderingContext2D, bodies: PhysicsBody[], width: number, height: number): void {
  // Dark Slate Background
  ctx.fillStyle = '#0a0f1d';
  ctx.fillRect(0, 0, width, height);

  // Subtle floating background grid
  ctx.strokeStyle = 'rgba(0, 240, 255, 0.08)';
  ctx.lineWidth = 1;
  const gridSize = 120;
  for (let x = 0; x < width; x += gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 0; y < height; y += gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  // Draw Physics Bodies
  for (const b of bodies) {
    ctx.save();
    ctx.translate(b.x, b.y);
    ctx.rotate(b.angle);

    ctx.fillStyle = b.color;
    ctx.strokeStyle = b.strokeColor;
    ctx.lineWidth = 4;

    switch (b.type) {
      case 'circle':
        ctx.beginPath();
        ctx.arc(0, 0, b.radius, 0, Math.PI * 2);
        ctx.closePath();
        break;
      case 'square':
        drawPolygon(ctx, 4, b.radius);
        break;
      case 'triangle':
        drawPolygon(ctx, 3, b.radius);
        break;
      case 'pentagon':
        drawPolygon(ctx, 5, b.radius);
        break;
      case 'hexagon':
        drawPolygon(ctx, 6, b.radius);
        break;
      case 'star':
        drawStar(ctx, 5, b.radius, b.radius * 0.5);
        break;
    }

    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }
}

/**
 * Generates an MP4 background video by simulating and streaming 2D physics frames directly to FFmpeg.
 */
export async function generatePhysicsBackgroundVideo(
  durationSeconds: number,
  width: number = 1080,
  height: number = 1920,
  outputPath: string
): Promise<string> {
  const fps = 30;
  const totalFrames = Math.ceil(durationSeconds * fps);
  const dt = 1 / fps;

  logger.info(`=======================================================`);
  logger.info(`GENERATING 2D PHYSICS SIMULATION VIDEO (${totalFrames} FRAMES)`);
  logger.info(`Shapes: Triangles, Squares, Circles, Pentagons, Hexagons, Stars`);
  logger.info(`Physics: Side Bounce + Top/Bottom Wrap-Around + 2D Repulsion`);
  logger.info(`Output: ${outputPath}`);
  logger.info(`=======================================================`);

  const canvas = createCanvas(width, height);
  const ctx = canvas.getContext('2d');
  const world = createPhysicsWorld(18, width, height);

  const ffmpegProc = spawn(ffmpegPath.path, [
    '-y',
    '-f', 'rawvideo',
    '-vcodec', 'rawvideo',
    '-s', `${width}x${height}`,
    '-pix_fmt', 'bgra',
    '-r', `${fps}`,
    '-i', 'pipe:0',
    '-c:v', 'libx264',
    '-preset', 'ultrafast',
    '-crf', '22',
    '-pix_fmt', 'yuv420p',
    outputPath
  ]);

  return new Promise((resolve, reject) => {
    let frameIndex = 0;

    function writeFrame() {
      let canWrite = true;
      while (frameIndex < totalFrames && canWrite) {
        updatePhysicsWorld(world, width, height, dt);
        renderPhysicsFrame(ctx, world, width, height);

        const buffer = canvas.toBuffer('raw');
        canWrite = ffmpegProc.stdin.write(buffer);
        frameIndex++;
      }

      if (frameIndex < totalFrames) {
        ffmpegProc.stdin.once('drain', writeFrame);
      } else {
        ffmpegProc.stdin.end();
      }
    }

    ffmpegProc.on('close', (code) => {
      if (code === 0) {
        logger.success(`Physics simulation video rendered successfully: ${outputPath}`);
        resolve(outputPath);
      } else {
        reject(new Error(`FFmpeg exited with code ${code} during physics video rendering.`));
      }
    });

    ffmpegProc.on('error', reject);

    writeFrame();
  });
}
