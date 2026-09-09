// SourcePicker — operator input-source selection (V2 dispatch §8–§11):
//   A) USB/WEBCAM: enumerate via POST /api/sources/webcam/scan (opens
//      ONLY real cameras), pick one → session starts on WebcamSource.
//   B) VIDEO FILE: drop zone / file picker → REAL upload via
//      POST /api/sources/upload (probe-validated server-side) →
//      metadata (name/size/fps/frames/resolution) → START ANALYSIS
//      enters the actual TRINETRA pipeline. No fake previews.

import { useRef, useState } from 'react';
import { api } from '../api';
import type { Store } from '../store';
import type { UploadInfo } from '../types';
import { Panel, Pill, StatusDot } from './ui';

type Mode = 'idle' | 'scanning' | 'uploading' | 'ready';

export default function SourcePicker({ store }: { store: Store }) {
  const [mode, setMode] = useState<Mode>('idle');
  const [cameras, setCameras] = useState<{ index: number; id: string; status: string }[]>([]);
  const [scanNote, setScanNote] = useState<string | null>(null);
  const [upload, setUpload] = useState<UploadInfo | null>(null);
  const [uploadPct, setUploadPct] = useState(0);
  const [pickedName, setPickedName] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);

  const scan = async () => {
    setMode('scanning'); setErr(null); setScanNote(null);
    try {
      const r = await api.webcamScan();
      setCameras(r.cameras);
      setScanNote(r.count === 0
        ? 'No camera available — none opened on this machine'
        : `${r.count} camera(s) responded`);
    } catch (e) {
      setErr(String((e as Error).message));
      setCameras([]);
    } finally { setMode('idle'); }
  };

  const startFileUpload = async (file: File) => {
    setErr(null); setUpload(null); setPickedName(file.name);
    setMode('uploading'); setUploadPct(0);
    try {
      const info = await api.uploadVideo(file, setUploadPct);
      setUpload(info);
      setMode('ready');
    } catch (e) {
      setErr(String((e as Error).message));
      setMode('idle');
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void startFileUpload(f);
  };

  const startSession = async (kind: 'file' | 'webcam', payload: { path?: string; index?: number }) => {
    setBusy(true); setErr(null);
    try {
      await api.sessionStart({ type: kind, ...payload });
      await store.refreshAll();
      store.setPage('dashboard');
    } catch (e) {
      setErr(String((e as Error).message));
    } finally { setBusy(false); }
  };

  const stop = async () => {
    setBusy(true); setErr(null);
    try {
      await api.sessionStop();
      await store.refreshAll();
    } catch (e) { setErr(String((e as Error).message)); }
    finally { setBusy(false); }
  };

  const active = store.status.active;

  return (
    <Panel
      title="Input Source"
      right={active
        ? <Pill tone="green">SESSION RUNNING</Pill>
        : <Pill tone="dim">NO SESSION</Pill>}
      className="min-h-0"
      scroll
    >
      <div className="p-3 space-y-3">
        {active && (
          <button
            disabled={busy}
            onClick={() => void stop()}
            className="w-full text-[11px] font-mono px-3 py-2 border border-cc-red/60 text-cc-red rounded hover:bg-cc-red/10"
          >
            STOP CURRENT SESSION ({store.status.session!.source_id})
          </button>
        )}

        {/* ── USB CAMERA ── */}
        <div className="border border-cc-line rounded p-2.5 bg-cc-panel2/40">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[11px] font-semibold text-cc-text">USB CAMERA</span>
            <button
              disabled={mode === 'scanning' || active}
              onClick={() => void scan()}
              className="ml-auto text-[10px] font-mono px-2 py-1 border border-cc-blue/50 text-cc-blue rounded-sm hover:bg-cc-blue/10 disabled:opacity-40"
            >
              {mode === 'scanning' ? 'SCANNING…' : 'SCAN CAMERAS'}
            </button>
          </div>
          {scanNote && <div className="text-[10px] font-mono text-cc-dim mb-1.5">{scanNote}</div>}
          {cameras.length > 0 && (
            <div className="space-y-1">
              {cameras.map(c => (
                <button
                  key={c.index}
                  disabled={busy || active}
                  onClick={() => void startSession('webcam', { index: c.index })}
                  className="w-full flex items-center gap-2 px-2 py-1.5 border border-cc-line rounded hover:bg-cc-panel2 text-left disabled:opacity-40"
                >
                  <StatusDot ok title={c.status} />
                  <span className="text-[11px] font-mono">{c.id}</span>
                  <span className="ml-auto text-[10px] font-mono text-cc-accent">START →</span>
                </button>
              ))}
            </div>
          )}
          {scanNote && cameras.length === 0 && (
            <div className="text-[10px] font-mono text-cc-amber">no camera available</div>
          )}
        </div>

        {/* ── VIDEO FILE ── */}
        <div className="border border-cc-line rounded p-2.5 bg-cc-panel2/40">
          <div className="text-[11px] font-semibold text-cc-text mb-2">VIDEO FILE</div>
          <div
            ref={dropRef}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInput.current?.click()}
            className={`border-2 border-dashed rounded px-3 py-5 text-center cursor-pointer transition-colors ${
              dragOver ? 'border-cc-blue bg-cc-blue/5' : 'border-cc-line hover:border-cc-dim'
            }`}
          >
            <div className="text-[11px] font-mono text-cc-dim">
              drop a video here or click to choose
            </div>
            <div className="text-[9px] font-mono text-cc-dim/60 mt-0.5">
              .mp4 / .mov — up to 500 MB, probe-validated server-side
            </div>
          </div>
          <input
            ref={fileInput}
            type="file"
            accept=".mp4,.mov,.m4v,video/mp4,video/quicktime"
            className="hidden"
            onChange={e => {
              const f = e.target.files?.[0];
              if (f) void startFileUpload(f);
            }}
          />
          {pickedName && (
            <div className="mt-2 text-[10px] font-mono text-cc-dim truncate">
              {pickedName}
            </div>
          )}
          {mode === 'uploading' && (
            <div className="mt-2 h-1.5 bg-cc-line rounded overflow-hidden">
              <div className="h-full bg-cc-blue transition-all" style={{ width: `${uploadPct}%` }} />
            </div>
          )}
          {upload && (
            <div className="mt-2 space-y-1.5">
              <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] font-mono">
                <span className="text-cc-dim">size</span><span>{(upload.size_bytes / 1e6).toFixed(1)} MB</span>
                <span className="text-cc-dim">resolution</span><span>{upload.width}×{upload.height}</span>
                <span className="text-cc-dim">fps</span><span>{upload.fps}</span>
                <span className="text-cc-dim">frames</span><span>{upload.frame_count}</span>
              </div>
              <button
                disabled={busy || active}
                onClick={() => void startSession('file', { path: upload.path })}
                className="w-full text-[11px] font-mono px-3 py-2 border border-cc-accent/60 text-cc-accent rounded hover:bg-cc-accent/10 disabled:opacity-40 font-semibold"
              >
                {busy ? 'STARTING…' : 'START ANALYSIS'}
              </button>
            </div>
          )}
        </div>

        {err && (
          <div className="text-[10px] font-mono text-cc-red bg-cc-red/5 border border-cc-red/30 rounded px-2 py-1.5">
            {err}
          </div>
        )}
      </div>
    </Panel>
  );
}
