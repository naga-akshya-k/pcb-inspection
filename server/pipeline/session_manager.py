"""
INSPECTRA — Central PCB Inspection Session & Event Broker Engine
Industry 4.0 Traceability + Industry 5.0 Human-in-the-Loop State Management
"""

import os
import time
import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class QualityGateRecord:
    blur_variance: float = 0.0
    mean_brightness: float = 0.0
    status: str = "PASS"  # PASS, BLUR_WARNING, EXPOSURE_WARNING, REJECTED
    message: str = "OPTICAL_QUALITY_PASS"


@dataclass
class AlignmentRecord:
    method: str = "ORB_RANSAC"
    inlier_ratio: float = 1.0
    quality_score: float = 1.0
    status: str = "PASS"
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DefectItem:
    defect_id: str
    component_id: str
    defect_type: str  # MISSING, TOMBSTONE, TILT, HEIGHT_ANOMALY, OVERHANG, POLARITY_REVERSED, SOLDER_BRIDGE, UNKNOWN_ANOMALY
    severity: str     # CRITICAL, HIGH, MEDIUM, LOW, PROCESS_INDICATOR
    confidence: float = 0.95
    uncertainty: float = 0.05
    evidence: str = ""
    recommended_action: str = "INSPECT"
    bbox_px: List[int] = field(default_factory=lambda: [0, 0, 0, 0])


@dataclass
class HumanReviewRecord:
    adjudicated: bool = False
    operator_id: Optional[str] = None
    operator_decision: Optional[str] = None  # ACCEPT_OVERRIDE, REJECT_CONFIRM, REWORK_REQUEST, ESCALATE, COMMENT_ONLY
    override_applied: bool = False
    operator_comment: Optional[str] = None
    escalated_to: Optional[str] = None
    timestamp_utc: Optional[str] = None


@dataclass
class PCBInspectionSession:
    session_id: str
    pcb_id: str
    serial_number: str
    product_code: str = "INSPECTRA-REV-4"
    batch_lot: str = "LOT-2026-W41"
    production_line: str = "SMT-LINE-01"
    station_id: str = "AOI-OPTICAL-01"
    operator_id: str = "OP-INDUSTRIAL"
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    calibration_version: str = "CAL-2026.10-01"
    golden_reference_id: str = "GOLDEN-MASTER-01"
    golden_reference_sha256: str = ""
    
    # Visual assets
    image_url: Optional[str] = None
    overlay_image_b64: Optional[str] = None
    depth_heatmap_b64: Optional[str] = None
    golden_image_b64: Optional[str] = None
    
    # Pipeline stages
    quality_gate: Dict[str, Any] = field(default_factory=dict)
    alignment: Dict[str, Any] = field(default_factory=dict)
    modalities: Dict[str, Any] = field(default_factory=dict)
    
    # Results
    components: List[Dict[str, Any]] = field(default_factory=list)
    metrology: List[Dict[str, Any]] = field(default_factory=list)
    defects: List[Dict[str, Any]] = field(default_factory=list)
    substrate_leveling: Dict[str, Any] = field(default_factory=dict)
    
    # Verdicts & Human-in-the-Loop
    ai_verdict: str = "READY"  # PASS, REVIEW, REWORK, FAIL
    health_index: float = 1.0
    defective_components: int = 0
    total_components: int = 12
    ai_confidence: float = 0.98
    ai_explanation: str = "Awaiting inspection"
    
    human_review: Dict[str, Any] = field(default_factory=lambda: asdict(HumanReviewRecord()))
    final_verdict: str = "READY"
    
    # Traceability
    processing_time_ms: float = 0.0
    audit_record_id: Optional[str] = None
    cfx_message_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class InspectionSessionManager:
    """
    Central in-memory and persistent manager for all PCBInspectionSessions.
    Provides real-time broadcasting queue for Server-Sent Events (SSE).
    """

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._sessions: Dict[str, PCBInspectionSession] = {}
        self._history_order: List[str] = []
        self._active_pcb_id: Optional[str] = None
        self._counter = 1248
        self._subscribers: List[asyncio.Queue] = []
        self._init_default_session()

    def _init_default_session(self):
        default_pcb_id = "PCB-001248"
        sess = PCBInspectionSession(
            session_id=f"SES-{uuid.uuid4().hex[:8].upper()}",
            pcb_id=default_pcb_id,
            serial_number="TB005",
            ai_verdict="PASS",
            final_verdict="PASS",
            health_index=1.0,
            defective_components=0,
            total_components=12,
            ai_explanation="Baseline Golden Master sample: 100% nominal component placement, zero IPC violations.",
            image_url="/evaluation/test_boards/TB005.png"
        )
        self._sessions[default_pcb_id] = sess
        self._history_order.append(default_pcb_id)
        self._active_pcb_id = default_pcb_id

    def generate_pcb_id(self, serial: str = "") -> str:
        self._counter += 1
        return f"PCB-{self._counter:06d}"

    def register_session(self, session: PCBInspectionSession) -> PCBInspectionSession:
        self._sessions[session.pcb_id] = session
        if session.pcb_id in self._history_order:
            self._history_order.remove(session.pcb_id)
        self._history_order.insert(0, session.pcb_id)
        
        if len(self._history_order) > self.max_history:
            oldest_id = self._history_order.pop()
            if oldest_id != self._active_pcb_id and oldest_id in self._sessions:
                del self._sessions[oldest_id]

        self._active_pcb_id = session.pcb_id
        self.broadcast_event("inspection_completed", session.to_dict())
        return session

    def set_active_pcb(self, pcb_id: str) -> Optional[PCBInspectionSession]:
        session = self.get_session(pcb_id)
        if session:
            self._active_pcb_id = session.pcb_id
            self.broadcast_event("board_selected", session.to_dict())
            return session
        return None

    def get_session(self, pcb_id_or_serial: str) -> Optional[PCBInspectionSession]:
        if not pcb_id_or_serial:
            return None
        # Try direct pcb_id match
        if pcb_id_or_serial in self._sessions:
            return self._sessions[pcb_id_or_serial]
        # Try serial match
        for s in self._sessions.values():
            if s.serial_number == pcb_id_or_serial or s.session_id == pcb_id_or_serial:
                return s
        return None

    def get_active_session(self) -> PCBInspectionSession:
        if self._active_pcb_id and self._active_pcb_id in self._sessions:
            return self._sessions[self._active_pcb_id]
        # Fallback to first session
        if self._history_order:
            return self._sessions[self._history_order[0]]
        self._init_default_session()
        return self._sessions[self._active_pcb_id]

    def list_history(self, limit: int = 30) -> List[Dict[str, Any]]:
        history_list = []
        for pid in self._history_order[:limit]:
            if pid in self._sessions:
                s = self._sessions[pid]
                history_list.append({
                    "pcb_id": s.pcb_id,
                    "serial_number": s.serial_number,
                    "timestamp_utc": s.timestamp_utc,
                    "ai_verdict": s.ai_verdict,
                    "final_verdict": s.final_verdict,
                    "health_index": s.health_index,
                    "defective_components": s.defective_components,
                    "total_components": s.total_components,
                    "is_active": (s.pcb_id == self._active_pcb_id),
                    "human_reviewed": bool(s.human_review.get("adjudicated", False))
                })
        return history_list

    def record_human_adjudication(
        self,
        pcb_id: str,
        decision: str,  # ACCEPT_OVERRIDE, REJECT_CONFIRM, REWORK_REQUEST, ESCALATE, COMMENT_ONLY
        operator_comment: str = "",
        operator_id: str = "OP-INDUSTRIAL",
        escalated_to: str = ""
    ) -> Optional[PCBInspectionSession]:
        session = self.get_session(pcb_id)
        if not session:
            return None

        now_iso = datetime.now(timezone.utc).isoformat()
        is_override = decision in ["ACCEPT_OVERRIDE", "REJECT_CONFIRM", "REWORK_REQUEST"]
        
        # Determine final verdict based on human adjudication
        if decision == "ACCEPT_OVERRIDE":
            final_v = "PASS"
        elif decision == "REJECT_CONFIRM":
            final_v = "FAIL"
        elif decision == "REWORK_REQUEST":
            final_v = "REWORK"
        elif decision == "ESCALATE":
            final_v = "REVIEW"
        else:
            final_v = session.ai_verdict

        session.human_review = {
            "adjudicated": True,
            "operator_id": operator_id,
            "operator_decision": decision,
            "override_applied": is_override and (final_v != session.ai_verdict),
            "operator_comment": operator_comment.strip(),
            "escalated_to": escalated_to.strip() if decision == "ESCALATE" else None,
            "timestamp_utc": now_iso
        }
        session.final_verdict = final_v

        self.broadcast_event("human_review_updated", session.to_dict())
        return session

    # --- Real-Time Server-Sent Events (SSE) Broker ---
    async def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        msg = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        dead_queues = []
        for q in self._subscribers:
            try:
                q.put_nowait(msg)
            except (asyncio.QueueFull, Exception):
                dead_queues.append(q)
        for dq in dead_queues:
            self.unsubscribe(dq)


# Global Singleton Session Manager
session_manager = InspectionSessionManager()
