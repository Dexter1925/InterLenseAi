import { useEffect, useRef } from "react";

interface Point3D {
  x: number;
  y: number;
  z: number;
}

export default function ParticleGlobe() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = canvas.clientWidth);
    let height = (canvas.height = canvas.clientHeight);

    // Create a sphere of particles
    const particles: Point3D[] = [];
    const particleCount = 120;
    const radius = Math.min(width, height) * 0.28 || 120;

    for (let i = 0; i < particleCount; i++) {
      const theta = Math.acos(Math.random() * 2 - 1);
      const phi = Math.random() * Math.PI * 2;

      particles.push({
        x: radius * Math.sin(theta) * Math.cos(phi),
        y: radius * Math.sin(theta) * Math.sin(phi),
        z: radius * Math.cos(theta),
      });
    }

    let angleY = 0.002;
    let angleX = 0.001;

    let mouseX = 0;
    let mouseY = 0;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left - width / 2;
      const y = e.clientY - rect.top - height / 2;
      mouseX = x * 0.0001;
      mouseY = y * 0.0001;
    };

    window.addEventListener("mousemove", handleMouseMove);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = canvas.clientWidth;
      height = canvas.height = canvas.clientHeight;
    };
    window.addEventListener("resize", handleResize);

    const rotateX = (point: Point3D, angle: number): Point3D => {
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      return {
        x: point.x,
        y: point.y * cos - point.z * sin,
        z: point.y * sin + point.z * cos,
      };
    };

    const rotateY = (point: Point3D, angle: number): Point3D => {
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      return {
        x: point.x * cos + point.z * sin,
        y: point.y,
        z: -point.x * sin + point.z * cos,
      };
    };

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Deep space atmospheric glow in center
      const gradient = ctx.createRadialGradient(
        width / 2,
        height / 2,
        0,
        width / 2,
        height / 2,
        radius * 1.5
      );
      gradient.addColorStop(0, "rgba(87, 27, 193, 0.1)");
      gradient.addColorStop(0.5, "rgba(47, 217, 244, 0.03)");
      gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);

      // Draw connections
      ctx.strokeStyle = "rgba(47, 217, 244, 0.04)";
      ctx.lineWidth = 0.5;

      const currentAngleY = angleY + mouseX;
      const currentAngleX = angleX + mouseY;

      // Rotate all particles
      for (let i = 0; i < particles.length; i++) {
        particles[i] = rotateY(particles[i], currentAngleY);
        particles[i] = rotateX(particles[i], currentAngleX);
      }

      // Draw particle points
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        // 3D Perspective projection
        const k = 300; // perspective factor
        const distance = k / (k + p.z);
        const screenX = width / 2 + p.x * distance;
        const screenY = height / 2 + p.y * distance;

        // Depth cueing (opacity based on Z-depth)
        const alpha = Math.max(0.1, Math.min(1, (p.z + radius) / (radius * 2)));

        ctx.fillStyle = `rgba(173, 198, 255, ${alpha * 0.8})`;

        // Glow effect for front particles
        if (p.z > 0) {
          ctx.shadowBlur = 10;
          ctx.shadowColor = "#2fd9f4";
        } else {
          ctx.shadowBlur = 0;
        }

        ctx.beginPath();
        ctx.arc(screenX, screenY, Math.max(1, 2.5 * distance), 0, Math.PI * 2);
        ctx.fill();

        // Connect nearby particles
        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dx = p.x - p2.x;
          const dy = p.y - p2.y;
          const dz = p.z - p2.z;
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

          if (dist < radius * 0.45) {
            const screenX2 = width / 2 + p2.x * (k / (k + p2.z));
            const screenY2 = height / 2 + p2.y * (k / (k + p2.z));

            const connectionAlpha = (1 - dist / (radius * 0.45)) * 0.15 * alpha;
            ctx.strokeStyle = `rgba(47, 217, 244, ${connectionAlpha})`;
            ctx.shadowBlur = 0;
            ctx.beginPath();
            ctx.moveTo(screenX, screenY);
            ctx.lineTo(screenX2, screenY2);
            ctx.stroke();
          }
        }
      }

      // Draw subtle orbital rings
      ctx.shadowBlur = 0;
      ctx.strokeStyle = "rgba(173, 198, 255, 0.05)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.ellipse(width / 2, height / 2, radius * 1.1, radius * 0.3, Math.PI / 6, 0, Math.PI * 2);
      ctx.stroke();

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ background: "transparent" }}
    />
  );
}
