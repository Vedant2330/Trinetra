// LiveFeed — the real MJPEG pipeline (/api/stream.mjpg). V3/C2: the
// zone overlay is drawn SERVER-side and burned into this stream (the
// single-renderer rule — the same JPEG serves the stream AND evidence
// snapshots), so the old client-canvas draw is REMOVED. The Virtual
// Fence layer toggle (LayerToggles) controls the server layer only.

import { useEffect, useState } from 'react';
import type { Store } from '../store';
import { Panel, Pill } from './ui';

export default function LiveFeed({ store, compact = false }: { store: Store; compact?: boolean }) {
  const { status, selectedCamera } = store;
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
          <img
            src={msrc}
            alt="live annotated feed"
            className="max-w-full max-h-full object-contain"
            onError={() => setFeedError(true)}
          />
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
                ? 'no active session — start one from the Live View page'
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
