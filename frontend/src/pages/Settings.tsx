// Settings — system configuration panels (V3): General, Analytics Thresholds,
// Re-ID Configuration, Notification Settings. Every field maps to a real
// backend config key; changes persist via PATCH /api/config (to implement).

import { useState } from 'react';
import { Panel, Pill } from '../components/ui';

interface GeneralConfig {
  session_timeout_s: number;
  max_concurrent_sessions: number;
  default_device: 'cpu' | 'mps' | 'cuda';
  log_level: 'debug' | 'info' | 'warn' | 'error';
  data_retention_days: number;
  snapshot_dir: string;
}

interface AnalyticsConfig {
  fence_confirm_frames: number;
  fence_grace_frames: number;
  trajectory_history_len: number;
  crowd_density_threshold: number;
  running_speed_threshold: number;
  loitering_time_s: number;
  night_start_hour: number;
  night_end_hour: number;
}

interface ReidConfig {
  enabled: boolean;
  similarity_threshold: number;
  min_observations: number;
  max_gallery_size: number;
  sync_interval_s: number;
}

interface NotificationConfig {
  email_enabled: boolean;
  webhook_enabled: boolean;
  webhook_url: string;
  severity_filter: string[];
  cooldown_s: number;
}

const DEFAULTS = {
  general: {
    session_timeout_s: 3600,
    max_concurrent_sessions: 1,
    default_device: 'cpu' as const,
    log_level: 'info' as const,
    data_retention_days: 30,
    snapshot_dir: 'snapshots/',
  },
  analytics: {
    fence_confirm_frames: 3,
    fence_grace_frames: 10,
    trajectory_history_len: 60,
    crowd_density_threshold: 10,
    running_speed_threshold: 2.5,
    loitering_time_s: 30,
    night_start_hour: 22,
    night_end_hour: 6,
  },
  reid: {
    enabled: false,
    similarity_threshold: 0.6,
    min_observations: 3,
    max_gallery_size: 1000,
    sync_interval_s: 5,
  },
  notifications: {
    email_enabled: false,
    webhook_enabled: false,
    webhook_url: '',
    severity_filter: ['HIGH', 'MEDIUM'],
    cooldown_s: 60,
  },
};

export default function Settings() {
  const [general, setGeneral] = useState<GeneralConfig>(DEFAULTS.general);
  const [analytics, setAnalytics] = useState<AnalyticsConfig>(DEFAULTS.analytics);
  const [reid, setReid] = useState<ReidConfig>(DEFAULTS.reid);
  const [notifications, setNotifications] = useState<NotificationConfig>(DEFAULTS.notifications);
  const [activeTab, setActiveTab] = useState<'general' | 'analytics' | 'reid' | 'notifications'>('general');
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const TABS = [
    { id: 'general', label: 'General', glyph: '⚙' },
    { id: 'analytics', label: 'Analytics', glyph: '∿' },
    { id: 'reid', label: 'Re-ID', glyph: '⌕' },
    { id: 'notifications', label: 'Notifications', glyph: '🔔' },
  ] as const;

  const save = async (section: string, _data: unknown) => {
    setSaving(prev => ({ ...prev, [section]: true }));
    setErr(null);
    setSuccess(null);
    try {
      // TODO: wire to PATCH /api/config when backend implements it
      await new Promise(r => setTimeout(r, 300)); // simulate API
      setSuccess(`${section} saved (stub — wire to backend)`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(prev => ({ ...prev, [section]: false }));
    }
  };

  const renderGeneral = () => (
    <Panel title="General Settings" className="min-h-0" scroll>
      <div className="p-3 space-y-4">
        <FieldGroup label="Session">
          <Input
            label="Session Timeout (s)"
            type="number"
            value={String(general.session_timeout_s)}
            onChange={e => setGeneral(prev => ({ ...prev, session_timeout_s: Number(e.target.value) }))}
            hint="auto-stop idle sessions"
          />
          <Input
            label="Max Concurrent Sessions"
            type="number"
            value={String(general.max_concurrent_sessions)}
            onChange={e => setGeneral(prev => ({ ...prev, max_concurrent_sessions: Number(e.target.value) }))}
            hint="hard limit enforced by backend"
          />
          <Select
            label="Default Device"
            value={general.default_device}
            options={['cpu', 'mps', 'cuda']}
            onChange={e => setGeneral(prev => ({ ...prev, default_device: e.target.value as 'cpu' | 'mps' | 'cuda' }))}
          />
        </FieldGroup>

        <FieldGroup label="Logging & Storage">
          <Select
            label="Log Level"
            value={general.log_level}
            options={['debug', 'info', 'warn', 'error']}
            onChange={e => setGeneral(prev => ({ ...prev, log_level: e.target.value as GeneralConfig['log_level'] }))}
          />
          <Input
            label="Data Retention (days)"
            type="number"
            value={String(general.data_retention_days)}
            onChange={e => setGeneral(prev => ({ ...prev, data_retention_days: Number(e.target.value) }))}
            hint="events older than this are purged"
          />
          <Input
            label="Snapshot Directory"
            value={general.snapshot_dir}
            onChange={e => setGeneral(prev => ({ ...prev, snapshot_dir: e.target.value }))}
            hint="relative to project root"
          />
        </FieldGroup>

        <div className="flex gap-2 pt-2">
          <button
            disabled={saving.general}
            onClick={() => save('general', general)}
            className="px-3 py-1.5 border border-cc-blue/60 text-cc-blue rounded-sm hover:bg-cc-blue/10 disabled:opacity-40 text-[11px] font-mono"
          >
            {saving.general ? 'SAVING…' : 'SAVE GENERAL'}
          </button>
        </div>
      </div>
    </Panel>
  );

  const renderAnalytics = () => (
    <Panel title="Analytics Thresholds" className="min-h-0" scroll>
      <div className="p-3 space-y-4">
        <FieldGroup label="Virtual Fence">
          <Input
            label="Confirm Frames"
            type="number"
            value={String(analytics.fence_confirm_frames)}
            onChange={e => setAnalytics({ ...analytics, fence_confirm_frames: Number(e.target.value) })}
            hint="consecutive frames inside zone before entry event"
          />
          <Input
            label="Grace Frames"
            type="number"
            value={String(analytics.fence_grace_frames)}
            onChange={e => setAnalytics({ ...analytics, fence_grace_frames: Number(e.target.value) })}
            hint="frames allowed outside before exit event"
          />
        </FieldGroup>

        <FieldGroup label="Trajectory & Behavior">
          <Input
            label="Trajectory History Length"
            type="number"
            value={String(analytics.trajectory_history_len)}
            onChange={e => setAnalytics({ ...analytics, trajectory_history_len: Number(e.target.value) })}
            hint="retained foot points per track"
          />
          <Input
            label="Crowd Density Threshold"
            type="number"
            value={String(analytics.crowd_density_threshold)}
            onChange={e => setAnalytics({ ...analytics, crowd_density_threshold: Number(e.target.value) })}
            hint="people per zone to trigger CROWD_DENSITY"
          />
          <Input
            label="Running Speed Threshold (m/s)"
            type="number"
            step="0.1"
            value={String(analytics.running_speed_threshold)}
            onChange={e => setAnalytics({ ...analytics, running_speed_threshold: Number(e.target.value) })}
            hint="speed above which SUSPECTED_RUNNING fires"
          />
          <Input
            label="Loitering Time (s)"
            type="number"
            value={String(analytics.loitering_time_s)}
            onChange={e => setAnalytics({ ...analytics, loitering_time_s: Number(e.target.value) })}
            hint="dwell time in zone before LOITERING"
          />
        </FieldGroup>

        <FieldGroup label="Night Hours (local clock)">
          <div className="flex gap-4">
            <Input
              label="Night Start Hour"
              type="number"
              min="0" max="23"
              value={String(analytics.night_start_hour)}
              onChange={e => setAnalytics({ ...analytics, night_start_hour: Number(e.target.value) })}
            />
            <Input
              label="Night End Hour"
              type="number"
              min="0" max="23"
              value={String(analytics.night_end_hour)}
              onChange={e => setAnalytics({ ...analytics, night_end_hour: Number(e.target.value) })}
            />
          </div>
        </FieldGroup>

        <div className="flex gap-2 pt-2">
          <button
            disabled={saving.analytics}
            onClick={() => save('analytics', analytics)}
            className="px-3 py-1.5 border border-cc-blue/60 text-cc-blue rounded-sm hover:bg-cc-blue/10 disabled:opacity-40 text-[11px] font-mono"
          >
            {saving.analytics ? 'SAVING…' : 'SAVE ANALYTICS'}
          </button>
        </div>
      </div>
    </Panel>
  );

  const renderReid = () => (
    <Panel title="Re-ID Configuration" className="min-h-0" scroll>
      <div className="p-3 space-y-4">
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={reid.enabled}
              onChange={e => setReid({ ...reid, enabled: e.target.checked })}
              className="w-4 h-4 accent-cc-blue border-cc-line rounded"
            />
            <span className="text-[11px] font-mono text-cc-text">Enable Cross-Camera Re-ID</span>
          </label>
          {reid.enabled ? <Pill tone="green">ENABLED</Pill> : <Pill tone="dim">DISABLED</Pill>}
        </div>

        {!reid.enabled ? (
          <div className="text-[11px] font-mono text-cc-dim opacity-60">
            Re-ID requires the OSNet model present at models/osnet_x1_0_msmt17.pt
          </div>
        ) : (
          <>
            <FieldGroup label="Matching">
              <Input
                label="Similarity Threshold"
                type="number"
                step="0.01"
                min="0" max="1"
                value={String(reid.similarity_threshold)}
                onChange={e => setReid(prev => ({ ...prev, similarity_threshold: Number(e.target.value) }))}
                hint="cosine similarity gate for gallery match"
              />
              <Input
                label="Min Observations"
                type="number"
                value={String(reid.min_observations)}
                onChange={e => setReid(prev => ({ ...prev, min_observations: Number(e.target.value) }))}
                hint="track embeddings before global ID assigned"
              />
              <Input
                label="Max Gallery Size"
                type="number"
                value={String(reid.max_gallery_size)}
                onChange={e => setReid(prev => ({ ...prev, max_gallery_size: Number(e.target.value) }))}
                hint="max global identities in gallery"
              />
            </FieldGroup>

            <FieldGroup label="Sync">
              <Input
                label="Sync Interval (s)"
                type="number"
                value={String(reid.sync_interval_s)}
                onChange={e => setReid(prev => ({ ...prev, sync_interval_s: Number(e.target.value) }))}
                hint="gallery merge cadence across cameras"
              />
            </FieldGroup>
          </>
        )}

        <div className="flex gap-2 pt-2">
          <button
            disabled={saving.reid}
            onClick={() => save('reid', reid)}
            className="px-3 py-1.5 border border-cc-blue/60 text-cc-blue rounded-sm hover:bg-cc-blue/10 disabled:opacity-40 text-[11px] font-mono"
          >
            {saving.reid ? 'SAVING…' : 'SAVE RE-ID'}
          </button>
        </div>
      </div>
    </Panel>
  );

  const renderNotifications = () => (
    <Panel title="Notification Settings" className="min-h-0" scroll>
      <div className="p-3 space-y-4">
        <FieldGroup label="Email">
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={notifications.email_enabled}
                onChange={e => setNotifications({ ...notifications, email_enabled: e.target.checked })}
                className="w-4 h-4 accent-cc-blue border-cc-line rounded"
              />
              <span className="text-[11px] font-mono">Enable Email Alerts</span>
            </label>
          </div>
        </FieldGroup>

        <FieldGroup label="Webhook">
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={notifications.webhook_enabled}
                onChange={e => setNotifications({ ...notifications, webhook_enabled: e.target.checked })}
                className="w-4 h-4 accent-cc-blue border-cc-line rounded"
              />
              <span className="text-[11px] font-mono">Enable Webhook</span>
            </label>
          </div>
          <Input
            label="Webhook URL"
            value={notifications.webhook_url}
            onChange={e => setNotifications({ ...notifications, webhook_url: e.target.value })}
            hint="POST JSON payload on each event"
            disabled={!notifications.webhook_enabled}
          />
        </FieldGroup>

        <FieldGroup label="Filtering">
          <div className="flex flex-wrap gap-1.5">
            {['HIGH', 'MEDIUM', 'LOW', 'INFO'].map(sev => (
              <label key={sev} className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={notifications.severity_filter.includes(sev)}
                  onChange={e => setNotifications({
                    ...notifications,
                    severity_filter: e.target.checked
                      ? [...notifications.severity_filter, sev]
                      : notifications.severity_filter.filter(s => s !== sev)
                  })}
                  className="w-3.5 h-3.5 accent-cc-blue border-cc-line rounded"
                />
                <span className="text-[10px] font-mono">{sev}</span>
              </label>
            ))}
          </div>
          <Input
            label="Cooldown (s)"
            type="number"
            value={String(notifications.cooldown_s)}
            onChange={e => setNotifications({ ...notifications, cooldown_s: Number(e.target.value) })}
            hint="minimum interval between notifications for same camera"
          />
        </FieldGroup>

        <div className="flex gap-2 pt-2">
          <button
            disabled={saving.notifications}
            onClick={() => save('notifications', notifications)}
            className="px-3 py-1.5 border border-cc-blue/60 text-cc-blue rounded-sm hover:bg-cc-blue/10 disabled:opacity-40 text-[11px] font-mono"
          >
            {saving.notifications ? 'SAVING…' : 'SAVE NOTIFICATIONS'}
          </button>
        </div>
      </div>
    </Panel>
  );

  return (
    <div className="h-full min-h-0 grid grid-cols-[240px_minmax(0,1fr)] gap-1.5">
      {/* Tab navigation */}
      <Panel className="min-h-0">
        <div className="p-2 space-y-1">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`w-full flex items-center gap-2 px-2.5 py-2 text-left text-[11px] font-mono rounded-sm transition-colors ${
                activeTab === t.id
                  ? 'bg-cc-panel2 border-l-2 border-l-cc-blue text-cc-text'
                  : 'text-cc-dim hover:text-cc-text hover:bg-cc-panel2/60'
              }`}
            >
              <span className="text-cc-accent/80">{t.glyph}</span>
              {t.label}
            </button>
          ))}
        </div>
      </Panel>

      {/* Tab content */}
      <div className="min-h-0">
        {activeTab === 'general' && renderGeneral()}
        {activeTab === 'analytics' && renderAnalytics()}
        {activeTab === 'reid' && renderReid()}
        {activeTab === 'notifications' && renderNotifications()}
        {(err || success) && (
          <div className={`fixed bottom-4 right-4 text-[11px] font-mono px-3 py-2 rounded border ${
            err ? 'text-cc-red border-cc-red/40 bg-cc-red/5' : 'text-cc-accent border-cc-accent/40 bg-cc-accent/5'
          }`}>
            {err || success}
          </div>
        )}
      </div>
    </div>
  );
}

function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <div className="text-[9px] uppercase tracking-wider text-cc-dim font-sans font-medium">
        {label}
      </div>
      <div className="space-y-2 border-l border-cc-line/40 pl-3 ml-1">
        {children}
      </div>
    </div>
  );
}

function Input({
  label,
  type = 'text',
  value,
  onChange,
  hint,
  disabled,
  min,
  max,
  step,
}: {
  label: string;
  type?: string;
  value: string | number;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  hint?: string;
  disabled?: boolean;
  min?: number | string;
  max?: number | string;
  step?: number | string;
}) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <label className="text-[10px] font-mono text-cc-dim flex items-center gap-1.5">
        {label}
        {hint && <span className="text-[9px] text-cc-dim/70">({hint})</span>}
      </label>
      <input
        type={type}
        value={String(value)}
        onChange={onChange}
        disabled={disabled}
        min={min}
        max={max}
        step={step}
        className="w-full bg-cc-bg border border-cc-line rounded px-2 py-1 text-[10px] font-mono text-cc-text placeholder-cc-dim/50 focus:outline-none focus:border-cc-accent disabled:opacity-50 disabled:cursor-not-allowed"
      />
    </div>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  hint?: string;
}) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <label className="text-[10px] font-mono text-cc-dim flex items-center gap-1.5">
        {label}
        {hint && <span className="text-[9px] text-cc-dim/70">({hint})</span>}
      </label>
      <select
        value={value}
        onChange={onChange}
        className="w-full bg-cc-bg border border-cc-line rounded px-2 py-1 text-[10px] font-mono text-cc-text focus:outline-none focus:border-cc-accent"
      >
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}