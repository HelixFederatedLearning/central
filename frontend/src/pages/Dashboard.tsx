// // src/pages/Dashboard.tsx
// import React, { useEffect, useMemo, useState } from "react";
// import { useFedEvents } from "../state/FedEventsProvider";
// import "./dashboard.css";

// export default function Dashboard() {
//   const {
//     events,
//     windowMinutes,
//     currentRound,
//     currentModel,
//     openCounts,
//     openedAtIso,
//   } = useFedEvents();

//   const [now, setNow] = useState(Date.now());

//   useEffect(() => {
//     const t = setInterval(() => setNow(Date.now()), 1000);
//     return () => clearInterval(t);
//   }, []);

//   const cycleEndsAt = useMemo(() => {
//     if (!openedAtIso || !windowMinutes) return null;
//     return new Date(openedAtIso).getTime() + windowMinutes * 60_000;
//   }, [openedAtIso, windowMinutes]);

//   const remainingMs = cycleEndsAt ? Math.max(0, cycleEndsAt - now) : null;

//   const remainingFmt = useMemo(() => {
//     if (remainingMs == null) return "—";
//     const s = Math.ceil(remainingMs / 1000);
//     const mm = String(Math.floor(s / 60)).padStart(2, "0");
//     const ss = String(s % 60).padStart(2, "0");
//     return `${mm}:${ss}`;
//   }, [remainingMs]);

//   const totalUpdates = openCounts.hospital + openCounts.patient;
//   const cycleHint =
//     totalUpdates >= 2
//       ? "≥2 updates — will aggregate this cycle"
//       : totalUpdates === 1
//       ? "1 update — will wait to next cycle"
//       : "Waiting for updates";

//   return (
//     <div className="dash-wrap">
//       <header className="dash-header">
//         <div>
//           <h1 className="dash-title">Federation Live Dashboard</h1>
//           <div className="dash-sub">
//             Current Model:&nbsp;
//             {currentModel ? (
//               <>
//                 <code>{currentModel.version}</code>{" "}
//                 <span className="muted">
//                   ({currentModel.id.slice(0, 8)}…)
//                 </span>
//               </>
//             ) : (
//               <span className="muted">none yet</span>
//             )}
//           </div>
//         </div>
//         <div className="dash-counters">
//           <div className="pill">
//             Hospitals: <b>{openCounts.hospital}</b>
//           </div>
//           <div className="pill">
//             Patients: <b>{openCounts.patient}</b>
//           </div>
//           <div className={`timer ${totalUpdates >= 2 ? "ok" : ""}`}>
//             {remainingFmt}
//           </div>
//         </div>
//       </header>

//       <div className="card-panel">
//         <div className="cycle-row">
//           <div>
//             <div className="lbl">Round</div>
//             <div className="mono">
//               {currentRound?.id ? currentRound.id : "—"}
//             </div>
//           </div>
//           <div>
//             <div className="lbl">Status</div>
//             <div className={`status ${currentRound?.status || "idle"}`}>
//               {currentRound?.status || "idle"}
//             </div>
//           </div>
//           <div className="grow">
//             <div className="lbl">Cycle</div>
//             <div className="mono">{cycleHint}</div>
//           </div>
//           <div>
//             <div className="lbl">Window</div>
//             <div className="mono">{windowMinutes ?? "—"} min</div>
//           </div>
//         </div>
//       </div>

//       <section className="grid">
//         <div className="card-panel">
//           <h3>Live Updates</h3>
//           <ul className="feed">
//             {events.length === 0 && (
//               <li className="muted">No events yet</li>
//             )}
//             {events.map((e, i) => (
//               <li key={i} className="feed-item">
//                 {e.type === "delta_received" && (
//                   <>
//                     <span className={`tag ${e.kind}`}>{e.kind}</span>
//                     &nbsp;<b>{e.client_id}</b> sent{" "}
//                     <b>{e.num_examples}</b> images
//                     <span className="time">
//                       {new Date(e.received_at).toLocaleTimeString()}
//                     </span>
//                   </>
//                 )}
//                 {e.type === "round_opened" && (
//                   <>
//                     <span className="tag opened">round</span>
//                     &nbsp;Round opened <b>{e.round_id}</b> (window{" "}
//                     {e.window_minutes} min)
//                     <span className="time">
//                       {new Date(e.opened_at).toLocaleTimeString()}
//                     </span>
//                   </>
//                 )}
//                 {e.type === "round_aggregated" && (
//                   <>
//                     <span className="tag agg">agg</span>
//                     &nbsp;Round <b>{e.round_id}</b> aggregated → model{" "}
//                     <code>{e.new_version}</code>
//                     <span className="time">
//                       {new Date(e.aggregated_at).toLocaleTimeString()}
//                     </span>
//                   </>
//                 )}
//                 {e.type === "current_model_updated" && (
//                   <>
//                     <span className="tag model">model</span>
//                     &nbsp;Current model updated to{" "}
//                     <code>{e.version}</code>
//                     <span className="time">
//                       {new Date(e.at).toLocaleTimeString()}
//                     </span>
//                   </>
//                 )}
//               </li>
//             ))}
//           </ul>
//         </div>

//         <div className="card-panel">
//           <h3>Round Snapshot</h3>
//           <div className="kv">
//             <div className="kv-row">
//               <div>Hospitals</div>
//               <div className="mono">{openCounts.hospital}</div>
//             </div>
//             <div className="kv-row">
//               <div>Patients</div>
//               <div className="mono">{openCounts.patient}</div>
//             </div>
//             <div className="kv-row">
//               <div>Total</div>
//               <div className="mono">{totalUpdates}</div>
//             </div>
//             <div className="kv-row">
//               <div>Ends in</div>
//               <div className={`mono ${totalUpdates >= 2 ? "ok" : ""}`}>
//                 {remainingFmt}
//               </div>
//             </div>
//           </div>
//           <p className="muted" style={{ marginTop: 12 }}>
//             Aggregation &amp; model updates run automatically on
//             the server. This dashboard only displays live progress.
//           </p>
//         </div>
//       </section>
//     </div>
//   );
// }
// src/pages/Dashboard.tsx
import React, { useEffect, useMemo, useState } from "react";
import { useFedEvents } from "../state/FedEventsProvider";
import "./dashboard.css";

// Helper: parse server timestamps.
// If there is no timezone in the string, assume UTC.
function parseServerTime(value: string | null | undefined): Date {
  if (!value) return new Date(NaN);
  const s = String(value);
  // has 'Z' or an explicit offset (+05:30, -0300, etc.)?
  if (/[zZ]|[+\-]\d\d:?\d\d$/.test(s)) {
    return new Date(s);
  }
  // otherwise assume it's UTC and append 'Z'
  return new Date(s + "Z");
}

function formatServerTime(value: string | null | undefined): string {
  const d = parseServerTime(value);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString();
}

export default function Dashboard() {
  const {
    events,
    windowMinutes,
    currentRound,
    currentModel,
    openCounts,
    openedAtIso,
  } = useFedEvents();

  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const cycleEndsAt = useMemo(() => {
    if (!openedAtIso || !windowMinutes) return null;
    return (
      parseServerTime(openedAtIso).getTime() + windowMinutes * 60_000
    );
  }, [openedAtIso, windowMinutes]);

  const remainingMs = cycleEndsAt ? Math.max(0, cycleEndsAt - now) : null;

  const remainingFmt = useMemo(() => {
    if (remainingMs == null) return "—";
    const s = Math.ceil(remainingMs / 1000);
    const mm = String(Math.floor(s / 60)).padStart(2, "0");
    const ss = String(s % 60).padStart(2, "0");
    return `${mm}:${ss}`;
  }, [remainingMs]);

  const totalUpdates = openCounts.hospital + openCounts.patient;
  const cycleHint =
    totalUpdates >= 2
      ? "≥2 updates — will aggregate this cycle"
      : totalUpdates === 1
      ? "1 update — will wait to next cycle"
      : "Waiting for updates";

  return (
    <div className="dash-wrap">
      <header className="dash-header">
        <div>
          <h1 className="dash-title">Federation Live Dashboard</h1>
          <div className="dash-sub">
            Current Model:&nbsp;
            {currentModel ? (
              <>
                <code>{currentModel.version}</code>{" "}
                <span className="muted">
                  ({currentModel.id.slice(0, 8)}…)
                </span>
              </>
            ) : (
              <span className="muted">none yet</span>
            )}
          </div>
        </div>
        <div className="dash-counters">
          <div className="pill">
            Hospitals: <b>{openCounts.hospital}</b>
          </div>
          <div className="pill">
            Patients: <b>{openCounts.patient}</b>
          </div>
          <div className={`timer ${totalUpdates >= 2 ? "ok" : ""}`}>
            {remainingFmt}
          </div>
        </div>
      </header>

      <div className="card-panel">
        <div className="cycle-row">
          <div>
            <div className="lbl">Round</div>
            <div className="mono">
              {currentRound?.id ? currentRound.id : "—"}
            </div>
          </div>
          <div>
            <div className="lbl">Status</div>
            <div className={`status ${currentRound?.status || "idle"}`}>
              {currentRound?.status || "idle"}
            </div>
          </div>
          <div className="grow">
            <div className="lbl">Cycle</div>
            <div className="mono">{cycleHint}</div>
          </div>
          <div>
            <div className="lbl">Window</div>
            <div className="mono">{windowMinutes ?? "—"} min</div>
          </div>
        </div>
      </div>

      <section className="grid">
        <div className="card-panel">
          <h3>Live Updates</h3>
          <ul className="feed">
            {events.length === 0 && (
              <li className="muted">No events yet</li>
            )}
            {events.map((e, i) => (
              <li key={i} className="feed-item">
                {e.type === "delta_received" && (
                  <>
                    <span className={`tag ${e.kind}`}>{e.kind}</span>
                    &nbsp;<b>{e.client_id}</b> sent{" "}
                    <b>{e.num_examples}</b> images
                    <span className="time">
                      {formatServerTime(e.received_at)}
                    </span>
                  </>
                )}
                {e.type === "round_opened" && (
                  <>
                    <span className="tag opened">round</span>
                    &nbsp;Round opened <b>{e.round_id}</b> (window{" "}
                    {e.window_minutes} min)
                    <span className="time">
                      {formatServerTime(e.opened_at)}
                    </span>
                  </>
                )}
                {e.type === "round_aggregated" && (
                  <>
                    <span className="tag agg">agg</span>
                    &nbsp;Round <b>{e.round_id}</b> aggregated → model{" "}
                    <code>{e.new_version}</code>
                    <span className="time">
                      {formatServerTime(e.aggregated_at)}
                    </span>
                  </>
                )}
                {e.type === "current_model_updated" && (
                  <>
                    <span className="tag model">model</span>
                    &nbsp;Current model updated to{" "}
                    <code>{e.version}</code>
                    <span className="time">
                      {formatServerTime(e.at)}
                    </span>
                  </>
                )}
              </li>
            ))}
          </ul>
        </div>

        <div className="card-panel">
          <h3>Round Snapshot</h3>
          <div className="kv">
            <div className="kv-row">
              <div>Hospitals</div>
              <div className="mono">{openCounts.hospital}</div>
            </div>
            <div className="kv-row">
              <div>Patients</div>
              <div className="mono">{openCounts.patient}</div>
            </div>
            <div className="kv-row">
              <div>Total</div>
              <div className="mono">{totalUpdates}</div>
            </div>
            <div className="kv-row">
              <div>Ends in</div>
              <div className={`mono ${totalUpdates >= 2 ? "ok" : ""}`}>
                {remainingFmt}
              </div>
            </div>
          </div>
          <p className="muted" style={{ marginTop: 12 }}>
            Aggregation &amp; model updates run automatically on
            the server. This dashboard only displays live progress.
          </p>
        </div>
      </section>
    </div>
  );
}
