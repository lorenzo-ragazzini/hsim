from __future__ import annotations
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import threading
import time
import re
import json

@dataclass
class Entry:
    time: float
    kind: str  # "message" or "event"
    subtype: str  # "send","receive","read","trigger","execute","queue_in","dequeue"
    src: str
    dst: str
    label: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

class SequenceRecorder:
    """
    Lightweight recorder for inter-agent messages and event executions.
    Stores an ordered list of entries and can export a Mermaid sequence diagram.
    """
    def __init__(self):
        self._entries: List[Entry] = []
        self._lock = threading.RLock()
        self.active = True
        # map hex id -> assigned queue index for stable names
        self._queue_id_map: Dict[str, int] = {}
        self._queue_counter: int = 0
        # monotonic event id counter for scheduler events
        self._event_counter: int = 0
        # message id mapping for stable message identifiers
        self._message_id_map: Dict[str, int] = {}
        self._message_counter: int = 0

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

    def entries(self) -> List[Entry]:
        with self._lock:
            return list(self._entries)

    def record(self, entry: Entry) -> None:
        if not self.active:
            return
        with self._lock:
            self._entries.append(entry)

    # Message helpers
    def record_message_send(self, message, receiver) -> None:
        try:
            src = getattr(message.sender, "name", str(message.sender)) if message.sender is not None else "Anonymous"
            dst = getattr(receiver, "name", str(receiver)) if receiver is not None else "Anonymous"
            label = self._fmt_label(message)
            # extract hex id for message and assign stable message id
            try:
                mrepr = str(message)
                mhex = None
                m = re.search(r"0x[0-9a-fA-F]+", mrepr)
                if m:
                    mhex = m.group(0)
                if mhex:
                    midx = self._message_id_map.get(mhex)
                    if midx is None:
                        self._message_counter += 1
                        midx = self._message_counter
                        self._message_id_map[mhex] = midx
                    message_id = f"msg_{midx}"
                else:
                    message_id = None
            except Exception:
                message_id = None
            raw = {"message": message}
            if message_id:
                raw["message_id"] = message_id
            self.record(Entry(time=message.env.now, kind="message", subtype="send", src=src, dst=dst, label=label, raw=raw))
        except Exception:
            pass

    def record_message_received(self, message) -> None:
        try:
            src = getattr(message.sender, "name", str(message.sender)) if message.sender is not None else "Anonymous"
            dst = getattr(message.receiver, "name", str(message.receiver)) if message.receiver is not None else "Anonymous"
            label = self._fmt_label(message)
            # preserve/assign message id
            try:
                mrepr = str(message)
                mhex = None
                m = re.search(r"0x[0-9a-fA-F]+", mrepr)
                if m:
                    mhex = m.group(0)
                if mhex:
                    midx = self._message_id_map.get(mhex)
                    if midx is None:
                        self._message_counter += 1
                        midx = self._message_counter
                        self._message_id_map[mhex] = midx
                    message_id = f"msg_{midx}"
                else:
                    message_id = None
            except Exception:
                message_id = None
            raw = {"message": message}
            if message_id:
                raw["message_id"] = message_id
            self.record(Entry(time=message.env.now, kind="message", subtype="receive", src=src, dst=dst, label=label, raw=raw))
        except Exception:
            pass

    def record_message_read(self, message) -> None:
        try:
            src = getattr(message.sender, "name", str(message.sender)) if message.sender is not None else "Anonymous"
            dst = getattr(message.receiver, "name", str(message.receiver)) if message.receiver is not None else "Anonymous"
            label = self._fmt_label(message)
            # preserve/assign message id
            try:
                mrepr = str(message)
                mhex = None
                m = re.search(r"0x[0-9a-fA-F]+", mrepr)
                if m:
                    mhex = m.group(0)
                if mhex:
                    midx = self._message_id_map.get(mhex)
                    if midx is None:
                        self._message_counter += 1
                        midx = self._message_counter
                        self._message_id_map[mhex] = midx
                    message_id = f"msg_{midx}"
                else:
                    message_id = None
            except Exception:
                message_id = None
            raw = {"message": message}
            if message_id:
                raw["message_id"] = message_id
            self.record(Entry(time=message.env.now, kind="message", subtype="read", src=src, dst=dst, label=label, raw=raw))
        except Exception:
            pass

    # Event helpers
    def record_event_trigger(self, event) -> None:
        try:
            # assign a stable recorder id for this event (so trigger/execute can be correlated)
            self._event_counter += 1
            eid = f"E{self._event_counter}"
            try:
                setattr(event, "_recorder_id", eid)
            except Exception:
                pass

            # detect a probable causal event: prefer the last executed event entry if any
            cause_eid = None
            with self._lock:
                for prev in reversed(self._entries):
                    if prev.kind == "event" and prev.subtype == "execute":
                        prev_raw = prev.raw or {}
                        if "event_id" in prev_raw:
                            cause_eid = prev_raw.get("event_id")
                            break
                    if prev.kind == "message":
                        # stop at message boundary (external cause)
                        break

            owner, action_name = self._extract_action_owner(event)
            src = "Scheduler"
            dst = owner
            label = f"trigger {action_name}"
            raw = {"event": event, "event_id": eid, "cause_event_id": cause_eid}
            self.record(Entry(time=event.env.now, kind="event", subtype="trigger", src=src, dst=dst, label=label, raw=raw))
        except Exception:
            pass

    def record_event_execute(self, event) -> None:
        try:
            # reuse recorder id if assigned at trigger time, otherwise create one now
            eid = getattr(event, "_recorder_id", None)
            if eid is None:
                self._event_counter += 1
                eid = f"E{self._event_counter}"
                try:
                    setattr(event, "_recorder_id", eid)
                except Exception:
                    pass

            # try to reuse cause recorded at trigger time if any
            cause_eid = getattr(event, "_recorder_cause", None)
            # fallback: look into the last trigger entry for this event (if present)
            if cause_eid is None:
                with self._lock:
                    for prev in reversed(self._entries):
                        if prev.kind == "event" and prev.subtype == "trigger":
                            prev_raw = prev.raw or {}
                            if prev_raw.get("event") is event and "cause_event_id" in prev_raw:
                                cause_eid = prev_raw.get("cause_event_id")
                                break

            owner, action_name = self._extract_action_owner(event)
            src = "Scheduler"
            dst = owner
            label = f"execute {action_name}"
            raw = {"event": event, "event_id": eid, "cause_event_id": cause_eid}
            self.record(Entry(time=event.env.now, kind="event", subtype="execute", src=src, dst=dst, label=label, raw=raw))
        except Exception:
            pass

    def _extract_action_owner(self, event):
        """
        Try to determine a human-friendly owner name and action name for the event.
        """
        action = event.action
        action_name = ""
        owner_name = "Anonymous"
        try:
            # If the action is a list, pick first
            if isinstance(action, (list, tuple)):
                action = action[0] if len(action) > 0 else action
            # If it's a bound method
            owner = getattr(action, "__self__", None)
            name = getattr(action, "__name__", None)
            if owner is not None:
                owner_name = getattr(owner, "name", owner.__class__.__name__)
            elif len(event.arguments) > 0:
                possibly_owner = event.arguments[0]
                owner_name = getattr(possibly_owner, "name", str(possibly_owner))
            else:
                owner_name = "Scheduler"
            action_name = name if name else repr(action)
        except Exception:
            action_name = repr(action)
        return owner_name, action_name

    def _fmt_label(self, message):
        try:
            return str(message.content)
        except Exception:
            return ""

    def export_mermaid(self, path: Optional[str] = None, include_events: bool = True, include_payload: bool = False) -> str:
        """
        Generate a Mermaid sequenceDiagram text. If path is provided, write to file.
        Returns the generated string.

        Rules:
        - Messages rendered as queue/agent -> queue/agent.
        - Skip Scheduler 'trigger' entries; use 'execute' entries resolved to real owners.
        - Precompute and sanitize participants; never emit raw Message/object reprs as participants.
        """
        with self._lock:
            entries = list(self._entries)

        # helper to detect message-object reprs (avoid emitting them as participants)
        msg_repr_re = re.compile(r"hsim\.core\.core\.msg\.Message_object_at_0x[0-9a-fA-F]+")
        # build map from message repr -> (sender_name, receiver_name) and message id (if present)
        msg_map: Dict[str, tuple] = {}
        msg_id_map: Dict[str, str] = {}
        for e in entries:
            if e.kind == "message":
                msg = (e.raw or {}).get("message")
                if msg is not None:
                    try:
                        msg_map[str(msg)] = (getattr(msg.sender, "name", str(msg.sender)) if msg.sender is not None else "Anonymous",
                                            getattr(msg.receiver, "name", str(msg.receiver)) if msg.receiver is not None else "Anonymous")
                        # capture message_id if recorded
                        mid = (e.raw or {}).get("message_id")
                        if mid:
                            msg_id_map[str(msg)] = mid
                    except Exception:
                        pass

        # First pass: collect logical participants (resolved)
        participants_set: List[str] = []
        for idx, e in enumerate(entries):
            if e.kind == "message":
                # prefer using the actual Message object's sender/receiver when available
                msg = (e.raw or {}).get("message")
                if msg is not None:
                    try:
                        src = getattr(msg.sender, "name", str(msg.sender)) if msg.sender is not None else "Anonymous"
                        dst = getattr(msg.receiver, "name", str(msg.receiver)) if msg.receiver is not None else "Anonymous"
                    except Exception:
                        src, dst = e.src, e.dst
                else:
                    # if raw message is not present, try to remap if e.src/e.dst is a message repr
                    src, dst = e.src, e.dst
                    if msg_repr_re.search(str(src)) and str(src) in msg_map:
                        src = msg_map[str(src)][0]
                    if msg_repr_re.search(str(dst)) and str(dst) in msg_map:
                        dst = msg_map[str(dst)][1]
                # avoid adding raw message reprs as participants
                # remap any message-object-like names to actual sender/receiver
                src_str = str(src)
                dst_str = str(dst)
                if msg_repr_re.search(src_str) and src_str in msg_map:
                    src = msg_map[src_str][0]
                    src_str = str(src)
                if msg_repr_re.search(dst_str) and dst_str in msg_map:
                    dst = msg_map[dst_str][1]
                    dst_str = str(dst)
                # Only include agent/queue-like names (exclude raw Message/class names or bare "Message")
                if src_str != "Message" and not msg_repr_re.search(src_str) and src_str not in ("Scheduler", "Anonymous") and src_str not in participants_set:
                    participants_set.append(src)
                if dst_str != "Message" and not msg_repr_re.search(dst_str) and dst_str not in ("Scheduler", "Anonymous") and dst_str not in participants_set:
                    participants_set.append(dst)
            elif e.kind == "event":
                if e.subtype == "trigger":
                    continue
                ev = (e.raw or {}).get("event")
                owner_obj, src_state, dst_state = self._resolve_event_owner(ev)
                resolved_owner_name = None
                if owner_obj is not None:
                    # if owner_obj is a Message-like object, map to sender name using msg_map
                    owner_key = str(owner_obj)
                    if msg_repr_re.search(owner_key) and owner_key in msg_map:
                        resolved_owner_name = msg_map[owner_key][0]
                    else:
                        name_attr = getattr(owner_obj, "name", None)
                        resolved_owner_name = name_attr if name_attr else str(owner_obj)
                    if resolved_owner_name:
                        # exclude bare or class-like Message names
                        if resolved_owner_name != "Message" and resolved_owner_name not in ("Scheduler", "Anonymous") and resolved_owner_name not in participants_set and "Message" not in resolved_owner_name:
                            participants_set.append(resolved_owner_name)
                else:
                    # attempt to attribute to previous message producer
                    producer = self._find_causal_producer(idx, entries)
                    if producer:
                        # if producer is a message repr, remap to sender
                        if msg_repr_re.search(str(producer)) and str(producer) in msg_map:
                            producer = msg_map[str(producer)][0]
                        if producer:
                            prod_str = str(producer)
                            if msg_repr_re.search(prod_str) and prod_str in msg_map:
                                producer = msg_map[prod_str][0]
                                prod_str = str(producer)
                            if prod_str != "Message" and not msg_repr_re.search(prod_str) and producer not in ("Scheduler","Anonymous") and prod_str not in participants_set:
                                participants_set.append(producer)

        # Build normalized + sanitized mapping and ensure unique sanitized identifiers
        normalized_map: Dict[str, str] = {}
        sanitized_map: Dict[str, str] = {}
        used_sanitized: Dict[str, int] = {}
        for orig in participants_set:
            # normalize queue hex ids, otherwise keep orig
            norm = self._normalize_participant_name(orig, entries)
            normalized_map[orig] = norm
            s = self._sanitize(norm)
            # ensure uniqueness
            count = used_sanitized.get(s, 0)
            if count:
                s_unique = f"{s}_{count}"
            else:
                s_unique = s
            used_sanitized[s] = count + 1
            sanitized_map[orig] = s_unique

        # Emit participants as a header block (no mid-inserts)
        lines = ["sequenceDiagram"]
        for orig in participants_set:
            lines.append(f"    participant {sanitized_map[orig]}")

        # Second pass: emit arrows
        for idx, e in enumerate(entries):
            time_label = f" [{e.time}]"
            label = e.label if include_payload else (e.label.split(":", 1)[0] if e.label else "")
            if e.kind == "message":
                msg = (e.raw or {}).get("message")
                if msg is not None:
                    try:
                        src = getattr(msg.sender, "name", str(msg.sender)) if msg.sender is not None else "Anonymous"
                        dst = getattr(msg.receiver, "name", str(msg.receiver)) if msg.receiver is not None else "Anonymous"
                    except Exception:
                        src, dst = e.src, e.dst
                    # append stable message id and original hex (if present) to label
                    mid = (e.raw or {}).get("message_id") or msg_id_map.get(str(msg))
                    try:
                        mrepr = str(msg)
                        mh = re.search(r"0x[0-9a-fA-F]+", mrepr)
                        mhex = mh.group(0) if mh else None
                    except Exception:
                        mhex = None
                    if mid and mhex:
                        label = f"{label} [{mid},{mhex}]"
                    elif mid:
                        label = f"{label} [{mid}]"
                    elif mhex:
                        label = f"{label} [{mhex}]"
                else:
                    src, dst = e.src, e.dst
                    if msg_repr_re.search(str(src)) and str(src) in msg_map:
                        src = msg_map[str(src)][0]
                    if msg_repr_re.search(str(dst)) and str(dst) in msg_map:
                        dst = msg_map[str(dst)][1]
                # remap message reprs to sender/receiver if present in msg_map
                if msg_repr_re.search(str(src)) and str(src) in msg_map:
                    src = msg_map[str(src)][0]
                if msg_repr_re.search(str(dst)) and str(dst) in msg_map:
                    dst = msg_map[str(dst)][1]
                # map through normalized/sanitized; if missing, skip
                if src in sanitized_map and dst in sanitized_map:
                    lines.append(f"    {sanitized_map[src]}->>{sanitized_map[dst]}: {self._escape(label)}{time_label}")
                else:
                    # skip if participants were filtered out (Scheduler/Anonymous)
                    continue
            elif e.kind == "event":
                if e.subtype == "trigger":
                    continue
                ev = (e.raw or {}).get("event")
                owner_obj, src_state, dst_state = self._resolve_event_owner(ev)
                resolved_owner_name = None
                if owner_obj is not None:
                    owner_key = str(owner_obj)
                    if msg_repr_re.search(owner_key) and owner_key in msg_map:
                        resolved_owner_name = msg_map[owner_key][0]
                    else:
                        resolved_owner_name = (getattr(owner_obj, "name", None) or owner_obj.__class__.__name__ or str(owner_obj))
                if resolved_owner_name:
                    sanitized = sanitized_map.get(resolved_owner_name)
                    if not sanitized:
                        # if the resolved owner wasn't precomputed (rare), add it now consistently
                        s = self._sanitize(self._normalize_participant_name(resolved_owner_name, entries))
                        cnt = used_sanitized.get(s, 0)
                        s_unique = f"{s}_{cnt}" if cnt else s
                        used_sanitized[s] = cnt + 1
                        sanitized = s_unique
                        lines.insert(1, f"    participant {sanitized}")
                        sanitized_map[resolved_owner_name] = sanitized
                    trans_label = f"{src_state}->{dst_state}" if src_state and dst_state else label
                    lines.append(f"    {sanitized}->>{sanitized}: {self._escape(trans_label)}{time_label}")
                else:
                    producer = self._find_causal_producer(idx, entries)
                    if producer:
                        if msg_repr_re.search(str(producer)) and str(producer) in msg_map:
                            producer = msg_map[str(producer)][0]
                        if producer and producer in sanitized_map:
                            lines.append(f"    {sanitized_map[producer]}->>{sanitized_map[producer]}: {self._escape(label)}{time_label}")
                        else:
                            continue
                    else:
                        continue
            else:
                continue

        diagram = "\n".join(lines)
        if path:
            try:
                with open(path, "w", encoding="utf8") as fh:
                    fh.write(diagram)
            except Exception:
                pass
        return diagram

    def export_scheduler_graph(self, mmd_path: Optional[str] = None, json_path: Optional[str] = None, time_bucket: Optional[float] = None) -> str:
        """
        Export scheduler-focused event graph as a Mermaid flowchart (LR) and optional JSON.
        - Considers only event entries with subtype 'execute' (avoids trigger duplicates).
        - Builds a time spine (T0..Tn) from unique timestamps and pins events to their time nodes.
        - Creates causal edges by scanning backwards and linking preceding execute events encountered
          before a message boundary. This produces a readable causality graph; later we can
          improve cause detection by enriching entries at recording time.
        Returns the Mermaid flowchart string. Writes mmd_path and json_path if provided.
        """
        with self._lock:
            entries = list(self._entries)

        # collect execute events
        exec_entries = []
        for idx, e in enumerate(entries):
            if e.kind == "event" and e.subtype == "execute":
                exec_entries.append((idx, e))

        if not exec_entries:
            return ""

        # unique sorted time buckets (use raw times unless time_bucket provided)
        times = sorted({e.time for _, e in exec_entries})
        if time_bucket and time_bucket > 0:
            # bucket times
            buckets = {}
            for t in times:
                b = int(t // time_bucket)
                buckets.setdefault(b, []).append(t)
            spine_times = [min(v) for k, v in sorted(buckets.items())]
        else:
            spine_times = times

        # map time -> Tnode name
        time_nodes = {t: f"T{idx}" for idx, t in enumerate(spine_times)}

        # build event nodes and map entry idx -> eid (prefer recorder-assigned event ids)
        nodes = []
        eid_map = {}
        for i, (idx, e) in enumerate(exec_entries, start=1):
            # prefer explicit event_id captured at record time, otherwise synthesize one
            raw_e = e.raw or {}
            recorded_id = raw_e.get("event_id")
            eid = recorded_id if recorded_id else f"E{i}"
            eid_map[idx] = eid
            # resolve owner and states
            ev = raw_e.get("event")
            owner_obj, src_state, dst_state = self._resolve_event_owner(ev)
            owner = None
            if owner_obj is not None:
                name_attr = getattr(owner_obj, "name", None)
                owner = name_attr if name_attr else str(owner_obj)
            label_parts = []
            if owner:
                label_parts.append(owner)
            # include state transition if present
            if src_state and dst_state:
                label_parts.append(f"{src_state}→{dst_state}")
            # include payload/label
            if e.label:
                label_parts.append(e.label)
            label = " — ".join(label_parts) if label_parts else e.label or ""
            nodes.append({"id": eid, "time": e.time, "label": label, "owner": owner, "src_state": src_state, "dst_state": dst_state, "index": idx})

        # build causal edges:
        #  - prefer explicit cause_event_id recorded on each entry
        #  - fallback to backward-scan heuristic (stop at message boundary)
        edges = []
        # set of known event ids for quick lookup
        known_event_ids = set(eid_map.values())
        for j, (idx, e) in enumerate(exec_entries):
            eid = eid_map[idx]
            raw_e = e.raw or {}
            cause_id = raw_e.get("cause_event_id")
            if cause_id and cause_id in known_event_ids:
                edges.append({"source": cause_id, "target": eid, "type": "triggers"})
                continue
            # fallback: scan back and collect prior execute events until a message boundary
            causes = []
            for k in range(idx - 1, -1, -1):
                prev = entries[k]
                if prev.kind == "event" and prev.subtype == "execute":
                    if k in eid_map:
                        causes.append(eid_map[k])
                if prev.kind == "message":
                    # stop scanning at message boundary (assume message is external cause)
                    break
            for c in reversed(causes):
                edges.append({"source": c, "target": eid, "type": "triggers"})

        # build Mermaid flowchart
        lines = ["flowchart LR", "    %% --- Time axis spine (invisible nodes) ---"]
        # create time spine nodes
        for idx, t in enumerate(spine_times):
            tnode = f"T{idx}"
            lines.append(f"    {tnode}([\"t={t}\"]) -.-> ")
        # pin events to spine: choose the closest spine time (exact match or nearest)
        lines.append("\n    %% --- Events pinned to their timestamp ---")
        for n in nodes:
            # find nearest spine time
            t = n["time"]
            if t in time_nodes:
                tnode = time_nodes[t]
            else:
                # nearest by absolute diff
                nearest = min(spine_times, key=lambda x: abs(x - t))
                tnode = time_nodes[nearest]
            # escape label
            lbl = n["label"].replace('"', '\\"') if n["label"] else n["id"]
            lines.append(f"    {tnode} --- {n['id']}[\"{lbl}\"]")
        # causal edges
        lines.append("\n    %% --- Causal / trigger edges ---")
        for ed in edges:
            lines.append(f"    {ed['source']} -->|{ed['type']}| {ed['target']}")
        # style spine
        lines.append("\n    %% --- Style the spine differently ---")
        for idx, t in enumerate(spine_times):
            tnode = f"T{idx}"
            lines.append(f"    style {tnode} fill:#e0e0e0,stroke:#999,color:#555")

        mmd = "\n".join(lines)

        # optionally write mmd and json
        if mmd_path:
            try:
                with open(mmd_path, "w", encoding="utf8") as fh:
                    fh.write(mmd)
            except Exception:
                pass
        if json_path:
            try:
                payload = {"nodes": nodes, "edges": edges, "spine_times": spine_times}
                with open(json_path, "w", encoding="utf8") as fh:
                    json.dump(payload, fh, indent=2)
            except Exception:
                pass

        return mmd

    def _sanitize(self, name: str) -> str:
        # Keep only letters, digits and underscore
        if not name:
            return "X"
        s = re.sub(r"[^A-Za-z0-9_]", "_", name)
        # ensure it doesn't start with a digit (mermaid tolerates but keep nice)
        if re.match(r"^[0-9]", s):
            s = "_" + s
        return s

    def _escape(self, text: str) -> str:
        return text.replace("\n", " ").replace(":", "\\:") if text else ""

    def _find_obj_for_participant(self, name: str, entries: List[Entry]):
        """
        Locate an actual Python object corresponding to a participant string by:
        1) matching exact str(obj) to the participant name (covers existing behavior)
        2) if not found and name looks like a generic class name (e.g. "Queue"), pick the
           first object of that class found in entries that does not yet have an assigned hex mapping.
        """
        # 1) exact match against recorded message/event raws
        repr_map: Dict[str, object] = {}
        class_buckets: Dict[str, List[object]] = {}
        for e in entries:
            raw = e.raw or {}
            msg = raw.get("message")
            if msg is not None:
                try:
                    sender = getattr(msg, "sender", None)
                    receiver = getattr(msg, "receiver", None)
                    if sender is not None:
                        repr_map[str(sender)] = sender
                        class_buckets.setdefault(sender.__class__.__name__, []).append(sender)
                        if str(sender) == name:
                            return sender
                    if receiver is not None:
                        repr_map[str(receiver)] = receiver
                        class_buckets.setdefault(receiver.__class__.__name__, []).append(receiver)
                        if str(receiver) == name:
                            return receiver
                except Exception:
                    pass
            ev = raw.get("event")
            if ev is not None:
                try:
                    owner, _ = self._extract_action_owner(ev)
                    # _extract_action_owner may return owner name instead of object; skip if not object
                    if hasattr(owner, "__class__"):
                        repr_map[str(owner)] = owner
                        class_buckets.setdefault(owner.__class__.__name__, []).append(owner)
                        if str(owner) == name:
                            return owner
                except Exception:
                    pass

        # 2) If participant name contains a hex id, but exact match failed (rare), try to find any
        # object whose repr contains that hex.
        m = re.search(r"0x[0-9a-fA-F]+", name)
        if m:
            hexid = m.group(0)
            for repr_str, obj in repr_map.items():
                if hexid in repr_str:
                    return obj

        # 3) If name is a simple class name like "Queue" and no exact match found, pick first
        # candidate of that class that is not already mapped to a hex id (to avoid collisions).
        simple_name = name.split("_", 1)[0]  # e.g., "Queue" from "Queue_1" or plain "Queue"
        candidates = class_buckets.get(simple_name, [])
        if candidates:
            for cand in candidates:
                # prefer objects with distinct hex in their repr
                try:
                    repr_c = str(cand)
                    if re.search(r"0x[0-9a-fA-F]+", repr_c):
                        return cand
                except Exception:
                    return cand
            return candidates[0]

        # nothing found
        return None

    def _normalize_participant_name(self, name: str, entries: List[Entry]) -> str:
        """
        Normalize queue-like participant names to a deterministic form:
        - Extract the hex object id if present (e.g. 0x7b01b0e4d580) and use it as uniqueness key.
        - Assign a stable integer index per unique hex id and return "Queue_<N>_(dir)" where dir is
          obtained from queue._desBlock if the underlying object can be found.
        - If no hex id is present, return the original name.
        """
        m = re.search(r"0x[0-9a-fA-F]+", name)
        if not m:
            return name
        hexid = m.group(0)
        idx = self._queue_id_map.get(hexid)
        if idx is None:
            self._queue_counter += 1
            idx = self._queue_counter
            self._queue_id_map[hexid] = idx

        # attempt to find underlying object to read _desBlock
        obj = self._find_obj_for_participant(name, entries)
        dir_part = None
        if obj is not None:
            dir_part = getattr(obj, "_desBlock", None)
        if dir_part:
            return f"queue_{idx}_({dir_part})__{hexid}"
        return f"queue_{idx}__{hexid}"

    def _resolve_event_owner(self, event_obj):
        """
        Resolve owner object for an event (prefer Transition-bound owners).
        Returns (owner_obj, source_state_name, target_state_name) or (None, None, None).
        """
        if event_obj is None:
            return None, None, None
        try:
            action = getattr(event_obj, "action", None)
            if isinstance(action, (list, tuple)):
                action = action[0] if len(action) > 0 else action
            # bound method -> __self__ is the owner
            owner = getattr(action, "__self__", None)
            # if owner looks like a Transition (has _fsm, source, target)
            if owner is not None and hasattr(owner, "_fsm") and hasattr(owner, "source") and hasattr(owner, "target"):
                transition = owner
                fsm_agent = getattr(transition._fsm, "_agent", None)
                src_state = getattr(transition.source, "name", str(transition.source))
                dst_state = getattr(transition.target, "name", str(transition.target))
                return (fsm_agent or transition._fsm), src_state, dst_state
            # if action itself is a Transition-like callable
            if hasattr(action, "_fsm") and hasattr(action, "source") and hasattr(action, "target"):
                transition = action
                fsm_agent = getattr(transition._fsm, "_agent", None)
                src_state = getattr(transition.source, "name", str(transition.source))
                dst_state = getattr(transition.target, "name", str(transition.target))
                return (fsm_agent or transition._fsm), src_state, dst_state
            # if bound to an agent or other object, return that
            if owner is not None:
                return owner, None, None
            # try inspect event arguments for an agent-like object
            args = getattr(event_obj, "arguments", []) or []
            for a in args:
                if hasattr(a, "name") or hasattr(a, "_desBlock"):
                    return a, None, None
        except Exception:
            pass
        return None, None, None

    def _find_causal_producer(self, index: int, entries: List[Entry]):
        """
        Simple backward scan to find a preceding message entry to attribute an event.
        Returns the src name of the producer or None.
        """
        for i in range(index - 1, -1, -1):
            e = entries[i]
            if e.kind == "message":
                return e.src
        return None

# Singleton recorder
_recorder_singleton: Optional[SequenceRecorder] = None

def get_recorder() -> SequenceRecorder:
    global _recorder_singleton
    if _recorder_singleton is None:
        _recorder_singleton = SequenceRecorder()
    return _recorder_singleton