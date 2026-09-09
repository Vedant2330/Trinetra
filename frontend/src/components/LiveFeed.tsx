// LiveFeed — the real MJPEG pipeline (/api/stream.mjpg), plus a canvas
// overlay rendering the M4 VIDEO zones (normalized frame coordinates)
// on top of the annotated frames. Video zones ≠ geographic sectors
// (ADR-002 coordinate separation) — this overlay is VIDEO-space only.

import { useEffect, useRef, useState } from 'react';
import type { Store } from '../store';
import { Panel, Pill } from './ui';

export default function LiveFeed({ store, compact = false }: { store: Store; compact?: boolean }) {
  const { status, zones, selectedCamera } = store;
  const imgRef = useRef<HTMLImageElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [feedError, setFeedError] = useState(false);
  const [snapTick, setSnapTick] = useState(0);
  const active = status.active && status.session;
  const sessionSource = status.session?.source_id ?? null;
  const isCameraSelected = selectedCamera === null
    || selectedCamera === sessionSource;

  // MJPEG failed but session alive -> honest slow snapshot fallback
  // (/api/frame.jpg, 2s cadence) instead of a dead panel
  useEffect(() => {
    if (!feedError || !active || !isCameraSelected) return;
    const iv = setInterval(() => setSnapTick(t => t + 1), 2000);
    return () => clearInterval(iv);
  }, [feedError, active, isCameraSelected]);

  // zone overlay redraw on every zone list / frame-size change
  useEffect(() => {
    const img = imgRef.current, cv = canvasRef.current;
    if (!img || !cv) return;
    const draw = () => {
      if (!img.naturalWidth) return;
      cv.width = img.naturalWidth;
      cv.height = img.naturalHeight;
      const ctx = cv.getContext('2d');
      if (!ctx) return;
      ctx.clearRect(0, 0, cv.width, cv.height);
      const w = cv.width, h = cv.height;
      for (const z of zones) {
        if (!z.active) continue;
        if (z.source_id !== sessionSource) continue;   // only this camera's
        const color = z.zone_type === 'RESTRICTED' ? '#DC2626' : '#2563EB';
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.font = '14px monospace';
        if (z.kind === 'polygon' && z.geometry.points) {
          ctx.beginPath();
          z.geometry.points.forEach(([x, y], i) => {
            const px = x * w, py = y * h;
            if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
          });
          ctx.closePath();
          ctx.stroke();
          ctx.fillStyle = color + '22';
          ctx.fill();
        } else if (z.kind === 'line' && z.geometry.p1 && z.geometry.p2) {
          const { p1, p2 } = z.geometry;
          ctx.beginPath();
          ctx.moveTo(p1[0] * w, p1[1] * h);
          ctx.lineTo(p2[0] * w, p2[1] * h);
          ctx.stroke();
          ctx.fillStyle = color;
          ctx.fillText(`${z.name} (${z.geometry.direction_mode ?? 'both'})`,
            p1[0] * w + 6, p1[1] * h - 6);
        }
      }
    };
    draw();
    img.addEventListener('load', draw);
    return () => img.removeEventListener('load', draw);
  }, [zones, sessionSource, active]);

  const msrc = active && isCameraSelected ? '/api/stream.mjpg' : null;

  // a NEW session (or stop) clears the error so the stream re-attempts
  useEffect(() => {
    setFeedError(false);
  }, [msrc]);

  return (
    <Panel
      title="Live Feed — Annotated MJPEG"
      right={
        <div className="flex items-center gap-2 text-[11px] font-mono">
          {sessionSource && (
            <span className={isCameraSelected ? 'text-cc-accent' : 'text-cc-dim'}>
              {sessionSource}
            </span>
          )}
          {active ? (
            <Pill tone={status.session!.status === 'running' ? 'green'
              : status.session!.status === 'error' ? 'red' : 'amber'}>
              {status.session!.status.toUpperCase()}
            </Pill>
          ) : <Pill tone="dim">NO SESSION</Pill>}
        </div>
      }
      className="min-h-0"
    >
      <div className="relative w-full h-full bg-black flex items-center justify-center min-h-0">
        {msrc && !feedError ? (
          <>
            <img
              ref={imgRef}
              src={msrc}
              alt="live annotated feed"
              className="max-w-full max-h-full object-contain"
              onError={() => setFeedError(true)}
            />
            <canvas
              ref={canvasRef}
              className="absolute inset-0 w-full h-full object-contain pointer-events-none"
            />
          </>
        ) : feedError && active && isCameraSelected ? (
          <>
            <img
              src={`/api/frame.jpg?_=${snapTick}`}
              alt="latest annotated frame (snapshot mode)"
              className="max-w-full max-h-full object-contain"
            />
            <span className="absolute top-1 right-2 text-[9px] font-mono text-cc-amber bg-black/60 px-1.5 rounded">
              ○ STREAM LOST — SNAPSHOT MODE (2s)
            </span>
          </>
        ) : (
          <div className="text-cc-dim text-sm text-center px-6 font-mono">
            {feedError
              ? '○ FEED UNAVAILABLE — session ended or connection lost'
              : !active
                ? 'no active session — start one from the Sources page'
                : 'camera selected — switch selection to the live session source'}
          </div>
        )}
        {compact && active && (
          <div className="absolute bottom-1 left-2 text-[10px] font-mono text-white/70 bg-black/50 px-1.5 rounded">
            {status.session!.frames_processed}f · {status.session!.pipeline_fps.toFixed(1)}fps · {status.session!.active_tracks} tracks
          </div>
        )}
      </div>
    </Panel>
  );
}
