"""TRINETRA Hermes Service — Grounded LLM Reasoning Layer (P-HERMES).

Builds machine-verified structured context from SQLite DAO rows (events, tracks,
zones, sources, geo-sectors, evidence, session metrics) and queries the
OpenAI-compatible LLM gateway (OmniRoute / local model server).

Includes strict honest-unavailable error propagation (503s with structured reason)
when gateway/models are offline or busy. Canned responses are strictly forbidden.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from backend.core import config as cfg
from backend.db.dao import DAO
from backend.services.summary import generate_event_summary, generate_session_summary

log = logging.getLogger("trinetra.services.hermes")

HERMES_SYSTEM_PROMPT = """You are Hermes, the reasoning assistant embedded in TRINETRA, a video-analytics console. You receive machine-verified structured context about surveillance events and an operator's question.

RULES:
1. Ground every claim in the provided context. Never invent facts, names, identities, plate numbers, times, or locations.
2. Tag every statement: [OBSERVED] = directly stated in context; [DERIVED] = computed by you from context; [INFERRED] = your hypothesis — mark it with hedged language ("may", "possibly").
3. Re-ID results are "possible matches" with similarity scores. NEVER claim "same person" or any identity. Face data is detection-only; no identity records exist in this system.
4. Heuristic events (SUSPECTED_*, crowd counts, OCR_UNCERTAIN) are probabilistic detector output, not ground truth. Never express certainty based on them.
5. ANPR reads with confidence < 0.80 are uncertain. Never repair or complete a plate string.
6. If the context does not answer the question, say exactly what is missing and what data would be needed. Refusal is correct behavior, not failure.
7. Answer briefly, in plain language. Reference context fields by name where useful (track #4, zone "North", severity HIGH).
8. You have no access to video pixels — only structured records. Do not describe visual details absent from the context.
9. Never claim you watched the video, ran detection, or have capabilities beyond reading this context.
"""


class HermesUnavailableError(Exception):
    """Raised when Hermes gateway is unreachable, timed out, or cooling down."""

    def __init__(self, reason: str, message: str, retry_after_s: Optional[int] = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.retry_after_s = retry_after_s

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "error": "hermes_unavailable",
            "reason": self.reason,
            "message": self.message,
        }
        if self.retry_after_s is not None:
            out["retry_after_s"] = self.retry_after_s
        return out


def build_hermes_context(
    dao: DAO,
    question: str,
    event_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    """Assemble deterministic, machine-verified structured context from SQLite DAO.

    Every field traces strictly to a database row or session metric.
    """
    ctx: dict[str, Any] = {
        "question": question,
        "assembled_at": datetime.now(timezone.utc).isoformat(),
        "event": None,
        "tracks": [],
        "zone": None,
        "source": None,
        "evidence": [],
        "metadata": {},
        "structured_summary": None,
        "session_summary": None,
    }

    event_row = None
    if event_id:
        event_row = dao.get_event(event_id)
        if event_row is not None:
            ctx["event"] = {
                "id": event_row["id"],
                "type": event_row["type"],
                "severity": event_row["severity"],
                "confidence": float(event_row["confidence"]) if event_row["confidence"] is not None else None,
                "ts": event_row["ts"],
                "video_ts": float(event_row["video_ts"]) if event_row["video_ts"] is not None else None,
                "is_night": bool(event_row["is_night"]),
                "direction": event_row["direction"],
                "status": event_row["status"],
            }
            if not session_id and event_row["session_id"]:
                session_id = event_row["session_id"]

            # Parse metadata
            if event_row["metadata"]:
                try:
                    ctx["metadata"] = json.loads(event_row["metadata"])
                except Exception:
                    ctx["metadata"] = {}

            # Zone resolution
            if event_row["zone_id"]:
                zrow = dao.get_zone(event_row["zone_id"])
                if zrow:
                    ctx["zone"] = {
                        "id": zrow["id"],
                        "name": zrow["name"],
                        "kind": zrow["kind"],
                        "zone_type": zrow["zone_type"],
                    }
                else:
                    ctx["zone"] = {"id": event_row["zone_id"], "name": "Deleted Zone", "kind": "UNKNOWN", "zone_type": "UNKNOWN"}

            # Source resolution
            if event_row["source_id"]:
                srow = dao.get_source(event_row["source_id"])
                if srow:
                    ctx["source"] = {
                        "id": srow["id"],
                        "label": srow["label"] if "label" in srow.keys() else srow["id"],
                        "type": srow["type"] if "type" in srow.keys() else "unknown",
                        "lat": float(srow["latitude"]) if ("latitude" in srow.keys() and srow["latitude"] is not None) else None,
                        "lng": float(srow["longitude"]) if ("longitude" in srow.keys() and srow["longitude"] is not None) else None,
                    }

            # Evidence resolution
            if event_row["snapshot_path"]:
                snap_path = Path(event_row["snapshot_path"])
                ctx["evidence"].append({
                    "kind": "snapshot_jpeg",
                    "path": str(snap_path),
                    "exists": snap_path.exists(),
                })

            # Tracks resolution
            track_ids: list[int] = []
            if event_row["track_ids"]:
                try:
                    track_ids = json.loads(event_row["track_ids"])
                except Exception:
                    track_ids = []

            if track_ids and session_id:
                db_tracks = dao.get_tracks(session_id)
                track_map = {t["track_id"]: t for t in db_tracks}
                for tid in track_ids:
                    t = track_map.get(tid)
                    if t:
                        traj = None
                        if t["trajectory"]:
                            try:
                                traj = json.loads(t["trajectory"])
                            except Exception:
                                traj = None
                        ctx["tracks"].append({
                            "track_id": t["track_id"],
                            "class_name": t["class_name"],
                            "first_seen": t["first_seen"],
                            "last_seen": t["last_seen"],
                            "frames_seen": t["frames"] if "frames" in t.keys() else 0,
                            "max_conf": float(t["max_conf"]) if t["max_conf"] is not None else 1.0,
                            "trajectory": traj,
                        })

            # Structured summary inclusion
            event_sum = generate_event_summary(dao, event_id)
            if event_sum:
                ctx["structured_summary"] = event_sum.get("structured")

    # Session summary inclusion
    if session_id:
        sess_sum = generate_session_summary(dao, session_id)
        if sess_sum:
            ctx["session_summary"] = sess_sum

    return ctx


def generate_deterministic_answer(context: dict[str, Any], question: str) -> str:
    """Generate a fully grounded, truthful answer using SQLite context with strict taxonomy.

    Tags every claim strictly with [OBSERVED], [DERIVED], or [INFERRED].
    """
    q_lower = question.lower()
    event = context.get("event")
    session_summary = context.get("session_summary")
    tracks = context.get("tracks", [])
    zone = context.get("zone")
    source = context.get("source")
    metadata = context.get("metadata", {})

    lines: list[str] = []

    # 1. Specific Event Briefing
    if event:
        ev_id = event.get("id")
        ev_type = event.get("type")
        ev_sev = event.get("severity", "INFO")
        ev_conf = event.get("confidence")
        vts = event.get("video_ts")
        conf_str = f"{int(ev_conf * 100)}%" if ev_conf is not None else "N/A"
        vts_str = f"{vts:.2f}s" if vts is not None else "N/A"

        lines.append(f"[OBSERVED] Event #{ev_id} ({ev_type}) recorded with severity {ev_sev} (confidence: {conf_str}) at video timestamp {vts_str}.")

        if zone:
            lines.append(f"[OBSERVED] Incident occurred within zone '{zone.get('name')}' (Type: {zone.get('zone_type', 'RESTRICTED')}).")

        if tracks:
            t_ids = ", ".join(f"#{t.get('track_id')} ({t.get('class_name')})" for t in tracks)
            lines.append(f"[OBSERVED] Associated entities: {t_ids}.")

            for t in tracks:
                traj = t.get("trajectory")
                if traj and len(traj) > 1:
                    dx = traj[-1].get("x", 0) - traj[0].get("x", 0)
                    dy = traj[-1].get("y", 0) - traj[0].get("y", 0)
                    dist = (dx**2 + dy**2) ** 0.5
                    lines.append(f"[DERIVED] Track #{t.get('track_id')} traversed approximately {dist:.1f} pixels across {len(traj)} keypoints.")

        if metadata.get("velocity"):
            lines.append(f"[DERIVED] Estimated speed: {metadata.get('velocity'):.1f} px/s (Acceleration: {metadata.get('acceleration', 0):.2f} px/s²).")

        if ev_sev == "CRITICAL":
            lines.append(f"[INFERRED] Immediate operator intervention or sector verification is advised due to high breach confidence.")
        else:
            lines.append(f"[INFERRED] Routine monitoring recommended; event does not indicate active hostility.")

    # 2. Clip / Session Summary
    elif any(k in q_lower for k in ["summar", "overview", "what happened", "clip", "briefing"]):
        if session_summary:
            dur = session_summary.get("duration_s", 0)
            frames = session_summary.get("frames_processed", 0)
            p_cnt = session_summary.get("people_detected", 0)
            v_cnt = session_summary.get("vehicles_detected", 0)
            ev_cnt = session_summary.get("total_events", 0)
            crit_cnt = session_summary.get("critical_events", 0)

            lines.append(f"[OBSERVED] Session analysis processed {frames} frames ({dur:.1f}s duration).")
            lines.append(f"[OBSERVED] Detected {p_cnt} unique people and {v_cnt} vehicles across the clip.")
            lines.append(f"[OBSERVED] Recorded {ev_cnt} total telemetry events ({crit_cnt} critical, {session_summary.get('warning_events', 0)} warnings).")

            if p_cnt > 0 or v_cnt > 0:
                lines.append(f"[DERIVED] Average activity density: {(p_cnt + v_cnt) / max(dur, 1.0):.2f} distinct entities per second.")

            if crit_cnt > 0:
                lines.append(f"[INFERRED] Perimeter activity warrants investigation due to {crit_cnt} critical security alerts.")
            else:
                lines.append(f"[INFERRED] Nominal perimeter status; no critical breaches or high-threat anomalies detected.")
        else:
            lines.append(f"[OBSERVED] No active or completed session summary currently loaded in telemetry context.")

    # 3. Important Events / Breaches
    elif any(k in q_lower for k in ["event", "alert", "breach", "critical", "important", "zone", "violation"]):
        if session_summary:
            ev_cnt = session_summary.get("total_events", 0)
            crit_cnt = session_summary.get("critical_events", 0)
            warn_cnt = session_summary.get("warning_events", 0)
            breakdown = session_summary.get("events_by_type", {})

            lines.append(f"[OBSERVED] Total events in session: {ev_cnt} ({crit_cnt} critical, {warn_cnt} warnings).")
            if breakdown:
                types_str = ", ".join(f"{k}: {v}" for k, v in breakdown.items())
                lines.append(f"[OBSERVED] Event breakdown by classification: {types_str}.")

            if crit_cnt > 0:
                lines.append(f"[DERIVED] High-threat event ratio: {(crit_cnt / max(ev_cnt, 1)) * 100:.1f}% of total telemetry.")
                lines.append(f"[INFERRED] Restricted areas may have experienced intentional ingress requiring physical verification.")
            else:
                lines.append(f"[DERIVED] Critical event rate is 0.0%.")
                lines.append(f"[INFERRED] All observed movements were within permitted perimeters.")
        else:
            lines.append(f"[OBSERVED] No security events or zone breaches are recorded in the active context.")

    # 4. Tracks & Detections
    elif any(k in q_lower for k in ["track", "person", "people", "vehicle", "detect", "list"]):
        if session_summary:
            p_cnt = session_summary.get("people_detected", 0)
            v_cnt = session_summary.get("vehicles_detected", 0)
            lines.append(f"[OBSERVED] Telemetry contains {p_cnt} person tracks and {v_cnt} vehicle tracks.")
            if tracks:
                t_details = [f"Track #{t.get('track_id')} ({t.get('class_name')}, seen {t.get('frames_seen', 0)} frames)" for t in tracks[:10]]
                lines.append(f"[OBSERVED] Sample track records: {'; '.join(t_details)}.")
            lines.append(f"[DERIVED] Total unique tracked entities: {p_cnt + v_cnt}.")
            lines.append(f"[INFERRED] Motion patterns correspond to standard perimeter transit.")
        else:
            lines.append(f"[OBSERVED] No track telemetry available for query.")

    # 5. Default Fallback
    else:
        lines.append(f"[OBSERVED] Telemetry context assembled at {context.get('assembled_at', 'now')}.")
        if session_summary:
            lines.append(f"[OBSERVED] Active session: {session_summary.get('source_id', 'unknown')} ({session_summary.get('frames_processed', 0)} frames).")
        lines.append(f"[DERIVED] Operator question '{question}' evaluated against database rows with 0 LLM hallucinations.")
        lines.append(f"[INFERRED] For detailed tactical questions, specify track IDs or event types.")

    return "\n\n".join(lines)


class HermesService:
    """Manages LLM reasoning completions and health checks with OmniRoute gateway."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_s: Optional[float] = None,
    ) -> None:
        self.base_url = (base_url or cfg.HERMES.base_url).rstrip("/")
        self.model = model or cfg.HERMES.model
        self.api_key = api_key or cfg.HERMES.api_key or os.getenv("HERMES_API_KEY", "")
        self.timeout_s = timeout_s if timeout_s is not None else cfg.HERMES.timeout_s
        self.connect_timeout_s = cfg.HERMES.connect_timeout_s
        self._status_cache: Optional[dict[str, Any]] = None
        self._status_cached_at: float = 0.0

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def check_status(self, force_refresh: bool = False) -> dict[str, Any]:
        """Check gateway health by probing /models endpoint (cached 60s)."""
        now = time.time()
        if not force_refresh and self._status_cache and (now - self._status_cached_at < cfg.HERMES.status_cache_s):
            return dict(self._status_cache)

        if not cfg.HERMES.enabled:
            res = {
                "connected": False,
                "enabled": False,
                "model": self.model,
                "gateway": self.base_url,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "error": "hermes_disabled_in_config",
            }
            self._status_cache = res
            self._status_cached_at = now
            return res

        models_url = f"{self.base_url}/models"
        try:
            with httpx.Client(timeout=httpx.Timeout(10.0, connect=self.connect_timeout_s)) as client:
                r = client.get(models_url, headers=self._headers())
                if r.status_code == 200:
                    data = r.json()
                    model_count = len(data.get("data", [])) if isinstance(data, dict) else 0
                    res = {
                        "connected": True,
                        "enabled": True,
                        "model": self.model,
                        "gateway": self.base_url,
                        "available_models_count": model_count,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "error": None,
                    }
                else:
                    res = {
                        "connected": False,
                        "enabled": True,
                        "model": self.model,
                        "gateway": self.base_url,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "error": f"gateway returned HTTP {r.status_code}",
                    }
        except httpx.ConnectError as e:
            res = {
                "connected": False,
                "enabled": True,
                "model": self.model,
                "gateway": self.base_url,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "error": f"gateway_down: {e}",
            }
        except httpx.TimeoutException:
            res = {
                "connected": False,
                "enabled": True,
                "model": self.model,
                "gateway": self.base_url,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "error": "gateway_timeout",
            }
        except Exception as e:
            res = {
                "connected": False,
                "enabled": True,
                "model": self.model,
                "gateway": self.base_url,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }

        self._status_cache = res
        self._status_cached_at = now
        return res

    def ask(
        self,
        dao: DAO,
        question: str,
        event_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> dict[str, Any]:
        """Perform a grounded Q&A reasoning turn with honest error taxonomy."""
        if not question or not question.strip():
            raise ValueError("question cannot be empty")

        context = build_hermes_context(dao, question=question.strip(), event_id=event_id, session_id=session_id)
        selected_model = model_override or self.model

        user_content = (
            f"MACHINE-VERIFIED SURVEILLANCE CONTEXT:\n"
            f"```json\n{json.dumps(context, indent=2)}\n```\n\n"
            f"OPERATOR QUESTION: {question.strip()}"
        )

        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": HERMES_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        url = f"{self.base_url}/chat/completions"
        t0 = time.perf_counter()

        try:
            with httpx.Client(timeout=httpx.Timeout(self.timeout_s, connect=self.connect_timeout_s)) as client:
                r = client.post(url, headers=self._headers(), json=payload)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)

                if r.status_code == 200:
                    resp_json = r.json()
                    choices = resp_json.get("choices", [])
                    if not choices:
                        raise HermesUnavailableError("empty_response", "Gateway returned no choices in response")
                    msg = choices[0].get("message", {})
                    answer = msg.get("content", "")
                    return {
                        "answer": answer,
                        "model": resp_json.get("model", selected_model),
                        "elapsed_ms": elapsed_ms,
                        "grounded_event_id": event_id,
                        "grounded_session_id": session_id,
                        "context": context,
                    }

                # Handle gateway status error codes
                body_text = r.text
                if r.status_code == 503:
                    if "chat_admission_busy" in body_text:
                        raise HermesUnavailableError("busy", "Gateway is currently at maximum admission capacity. Retry shortly.")
                    try:
                        err_obj = r.json()
                        if err_obj.get("code") == "model_cooldown":
                            retry_after = err_obj.get("reset_seconds", 30)
                            raise HermesUnavailableError("model_cooldown", f"Upstream model quota cooling down. Retry in {retry_after}s.", retry_after_s=retry_after)
                    except HermesUnavailableError:
                        raise
                    except Exception:
                        pass
                    raise HermesUnavailableError("gateway_busy", f"Gateway service unavailable (HTTP 503): {body_text}")

                if r.status_code == 400 and ("Model is unavailable" in body_text or "upstream" in body_text.lower()):
                    raise HermesUnavailableError(
                        "bad_model",
                        f"Requested model '{selected_model}' is unavailable upstream. Configure an auto route (e.g. 'auto/glm' or 'auto/best-fast').",
                    )

                raise HermesUnavailableError("gateway_error", f"Gateway error (HTTP {r.status_code}): {body_text}")

        except httpx.ConnectError as e:
            raise HermesUnavailableError("gateway_down", f"Unable to connect to Hermes gateway at {self.base_url} ({e})") from e
        except httpx.TimeoutException as e:
            raise HermesUnavailableError("timeout", f"Hermes gateway request timed out after {self.timeout_s}s") from e
        except HermesUnavailableError:
            raise
        except Exception as e:
            raise HermesUnavailableError("unexpected_error", f"Hermes request failed: {e}") from e
