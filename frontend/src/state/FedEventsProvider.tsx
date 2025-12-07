// // frontend/src/state/FedEventsProvider.tsx
// import React, {
//   createContext,
//   useContext,
//   useEffect,
//   useRef,
//   useState,
//   ReactNode,
// } from "react";
// import {
//   getCurrentModel,
//   getSettings,
//   listRounds,
//   openEventsStream,
// } from "../lib/api";

// export type DeltaReceivedEvt = {
//   type: "delta_received";
//   round_id: string;
//   client_id: string;
//   kind: "hospital" | "patient";
//   num_examples: number;
//   received_at: string;
// };

// export type RoundOpenedEvt = {
//   type: "round_opened";
//   round_id: string;
//   opened_at: string;
//   window_minutes: number;
// };

// export type RoundAggregatedEvt = {
//   type: "round_aggregated";
//   round_id: string;
//   aggregated_at: string;
//   new_model_id: string;
//   new_version: string;
// };

// export type ModelUpdatedEvt = {
//   type: "current_model_updated";
//   model_id: string;
//   version: string;
//   at: string;
// };

// export type AnyEvt =
//   | DeltaReceivedEvt
//   | RoundOpenedEvt
//   | RoundAggregatedEvt
//   | ModelUpdatedEvt;

// export type RoundLite = {
//   id: string;
//   status: "open" | "closed" | "aggregated" | string;
//   created_at?: string;
//   closed_at?: string | null;
//   num_hospital?: number | null;
//   num_patient?: number | null;
//   window_start?: string | null;
// };

// type FedEventsState = {
//   events: AnyEvt[];
//   windowMinutes: number | null;
//   currentRound: RoundLite | null;
//   currentModel: { id: string; version: string } | null;
//   openCounts: { hospital: number; patient: number };
//   openedAtIso: string | null;
// };

// const FedEventsContext = createContext<FedEventsState | undefined>(undefined);

// // This should match backend Settings.MIN_TOTAL
// const MIN_TOTAL = 2;

// export function FedEventsProvider({ children }: { children: ReactNode }) {
//   const [events, setEvents] = useState<AnyEvt[]>([]);
//   const [windowMinutes, setWindowMinutes] = useState<number | null>(null);
//   const [currentRound, setCurrentRound] = useState<RoundLite | null>(null);
//   const [currentModel, setCurrentModel] = useState<
//     { id: string; version: string } | null
//   >(null);
//   const [openCounts, setOpenCounts] = useState({
//     hospital: 0,
//     patient: 0,
//   });
//   const [openedAtIso, setOpenedAtIso] = useState<string | null>(null);

//   const esRef = useRef<EventSource | null>(null);

//   // 1) Bootstrap: settings, current round, current model
//   useEffect(() => {
//     (async () => {
//       try {
//         const [settings, rounds, model] = await Promise.all([
//           getSettings(),
//           listRounds(),
//           getCurrentModel(),
//         ]);

//         if ((settings as any)?.window_minutes) {
//           setWindowMinutes((settings as any).window_minutes);
//         }

//         const rows = (rounds as RoundLite[]) || [];
//         const open = rows.find((r) => r.status === "open") || null;
//         setCurrentRound(open || rows[0] || null);

//         if (open) {
//           const hosp = open.num_hospital ?? 0;
//           const pat = open.num_patient ?? 0;
//           const total = hosp + pat;

//           setOpenCounts({
//             hospital: hosp,
//             patient: pat,
//           });

//           // Only start window if we already had enough deltas
//           if (total >= MIN_TOTAL) {
//             const startIso =
//               (open.window_start as string | undefined) ||
//               open.created_at ||
//               null;
//             setOpenedAtIso(startIso);
//           } else {
//             setOpenedAtIso(null);
//           }
//         } else {
//           setOpenCounts({ hospital: 0, patient: 0 });
//           setOpenedAtIso(null);
//         }

//         if (model && (model as any).id) {
//           setCurrentModel({
//             id: (model as any).id,
//             version: (model as any).version,
//           });
//         }
//       } catch (e) {
//         console.warn("[FedEventsProvider] bootstrap failed:", e);
//       }
//     })();
//   }, []);

//   // 2) SSE connection: listen to /v1/events and keep state live
//   useEffect(() => {
//     const es = openEventsStream((msg) => {
//       try {
//         const data = JSON.parse(msg.data) as AnyEvt;
//         if (!data || typeof data !== "object" || !("type" in data)) return;

//         // Prepend to live feed (no persistence across refresh)
//         setEvents((prev) => [data, ...prev].slice(0, 200));

//         if (data.type === "round_opened") {
//           // New round: reset counts and DO NOT start window yet.
//           setCurrentRound({
//             id: data.round_id,
//             status: "open",
//             created_at: data.opened_at,
//           });
//           setOpenCounts({ hospital: 0, patient: 0 });
//           setOpenedAtIso(null);
//           setWindowMinutes(data.window_minutes);
//         }

//         if (data.type === "delta_received") {
//           // Ensure we track the active round id
//           setCurrentRound((prev) =>
//             prev && prev.id === data.round_id
//               ? prev
//               : { id: data.round_id, status: "open" }
//           );

//           // Update counts; only start window when total reaches MIN_TOTAL
//           setOpenCounts((c) => {
//             const next = {
//               hospital: c.hospital + (data.kind === "hospital" ? 1 : 0),
//               patient: c.patient + (data.kind === "patient" ? 1 : 0),
//             };
//             const prevTotal = c.hospital + c.patient;
//             const nextTotal = next.hospital + next.patient;

//             if (prevTotal < MIN_TOTAL && nextTotal >= MIN_TOTAL) {
//               // First time we cross the threshold → start countdown now
//               setOpenedAtIso((iso) => iso ?? data.received_at);
//             }

//             return next;
//           });
//         }

//         if (data.type === "round_aggregated") {
//           // Round finished; stop countdown & reset counts
//           setCurrentRound((prev) => {
//             if (!prev || prev.id !== data.round_id) return prev;
//             return {
//               ...prev,
//               status: "aggregated",
//               closed_at: data.aggregated_at,
//             };
//           });
//           setOpenedAtIso(null);
//           setOpenCounts({ hospital: 0, patient: 0 });
//         }

//         if (data.type === "current_model_updated") {
//           setCurrentModel({
//             id: data.model_id,
//             version: data.version,
//           });
//         }
//       } catch {
//         // ignore keep-alive heartbeats & malformed lines
//       }
//     });

//     esRef.current = es;
//     return () => {
//       es.close();
//       esRef.current = null;
//     };
//   }, []);

//   const value: FedEventsState = {
//     events,
//     windowMinutes,
//     currentRound,
//     currentModel,
//     openCounts,
//     openedAtIso,
//   };

//   return (
//     <FedEventsContext.Provider value={value}>
//       {children}
//     </FedEventsContext.Provider>
//   );
// }

// export function useFedEvents(): FedEventsState {
//   const ctx = useContext(FedEventsContext);
//   if (!ctx) {
//     throw new Error("useFedEvents must be used within FedEventsProvider");
//   }
//   return ctx;
// }

// frontend/src/state/FedEventsProvider.tsx
import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  ReactNode,
} from "react";
import {
  getCurrentModel,
  getSettings,
  listRounds,
  openEventsStream,
} from "../lib/api";

export type DeltaReceivedEvt = {
  type: "delta_received";
  round_id: string;
  client_id: string;
  kind: "hospital" | "patient";
  num_examples: number;
  received_at: string;
};

export type RoundOpenedEvt = {
  type: "round_opened";
  round_id: string;
  opened_at: string;
  window_minutes: number;
};

export type RoundAggregatedEvt = {
  type: "round_aggregated";
  round_id: string;
  aggregated_at: string;
  new_model_id: string;
  new_version: string;
};

export type ModelUpdatedEvt = {
  type: "current_model_updated";
  model_id: string;
  version: string;
  at: string;
};

export type AnyEvt =
  | DeltaReceivedEvt
  | RoundOpenedEvt
  | RoundAggregatedEvt
  | ModelUpdatedEvt;

export type RoundLite = {
  id: string;
  status: "open" | "closed" | "aggregated" | string;
  created_at?: string;
  closed_at?: string | null;
  num_hospital?: number | null;
  num_patient?: number | null;
  window_start?: string | null;
};

type FedEventsState = {
  events: AnyEvt[];
  windowMinutes: number | null;
  currentRound: RoundLite | null;
  currentModel: { id: string; version: string } | null;
  openCounts: { hospital: number; patient: number };
  openedAtIso: string | null;
};

const FedEventsContext = createContext<FedEventsState | undefined>(undefined);

// This should match backend Settings.MIN_TOTAL
const MIN_TOTAL = 2;

export function FedEventsProvider({ children }: { children: ReactNode }) {
  const [events, setEvents] = useState<AnyEvt[]>([]);
  const [windowMinutes, setWindowMinutes] = useState<number | null>(null);
  const [currentRound, setCurrentRound] = useState<RoundLite | null>(null);
  const [currentModel, setCurrentModel] = useState<
    { id: string; version: string } | null
  >(null);
  const [openCounts, setOpenCounts] = useState({
    hospital: 0,
    patient: 0,
  });
  const [openedAtIso, setOpenedAtIso] = useState<string | null>(null);

  const esRef = useRef<EventSource | null>(null);

  // 1) Bootstrap: settings, current round, current model
  useEffect(() => {
    (async () => {
      try {
        const [settings, rounds, model] = await Promise.all([
          getSettings(),
          listRounds(),
          getCurrentModel(),
        ]);

        if ((settings as any)?.window_minutes) {
          setWindowMinutes((settings as any).window_minutes);
        }

        const rows = (rounds as RoundLite[]) || [];
        const open = rows.find((r) => r.status === "open") || null;
        setCurrentRound(open || rows[0] || null);

        if (open) {
          const hosp = open.num_hospital ?? 0;
          const pat = open.num_patient ?? 0;
          const total = hosp + pat;

          setOpenCounts({
            hospital: hosp,
            patient: pat,
          });

          // Only start window if we already had enough deltas
          if (total >= MIN_TOTAL) {
            const startIso =
              (open.window_start as string | undefined) ||
              open.created_at ||
              null;
            setOpenedAtIso(startIso);
          } else {
            setOpenedAtIso(null);
          }
        } else {
          setOpenCounts({ hospital: 0, patient: 0 });
          setOpenedAtIso(null);
        }

        if (model && (model as any).id) {
          setCurrentModel({
            id: (model as any).id,
            version: (model as any).version,
          });
        }
      } catch (e) {
        console.warn("[FedEventsProvider] bootstrap failed:", e);
      }
    })();
  }, []);

  // 2) SSE connection: listen to /v1/events and keep state live
  useEffect(() => {
    const es = openEventsStream((msg) => {
      try {
        const data = JSON.parse(msg.data) as AnyEvt;
        if (!data || typeof data !== "object" || !("type" in data)) return;

        // --- Live feed, with dedupe for round_opened ---
        setEvents((prev) => {
          if (
            data.type === "round_opened" &&
            prev.some(
              (e) => e.type === "round_opened" && e.round_id === data.round_id
            )
          ) {
            // duplicate "round opened" for same round → ignore in feed
            return prev;
          }
          return [data, ...prev].slice(0, 200);
        });

        // --- State updates ---
        if (data.type === "round_opened") {
          // Only treat as a NEW round if the id changed
          setCurrentRound((prev) => {
            if (prev && prev.id === data.round_id) {
              // Same round already known → don't reset counts or timer
              return prev;
            }
            // New round: reset everything
            setOpenCounts({ hospital: 0, patient: 0 });
            setOpenedAtIso(null);
            setWindowMinutes(data.window_minutes);
            return {
              id: data.round_id,
              status: "open",
              created_at: data.opened_at,
            };
          });
        }

        if (data.type === "delta_received") {
          // Ensure we track the active round id
          setCurrentRound((prev) =>
            prev && prev.id === data.round_id
              ? prev
              : { id: data.round_id, status: "open" }
          );

          // Update counts; only start window when total reaches MIN_TOTAL
          setOpenCounts((c) => {
            const next = {
              hospital: c.hospital + (data.kind === "hospital" ? 1 : 0),
              patient: c.patient + (data.kind === "patient" ? 1 : 0),
            };
            const prevTotal = c.hospital + c.patient;
            const nextTotal = next.hospital + next.patient;

            if (prevTotal < MIN_TOTAL && nextTotal >= MIN_TOTAL) {
              // First time we cross the threshold → start countdown now
              setOpenedAtIso((iso) => iso ?? data.received_at);
            }

            return next;
          });
        }

        if (data.type === "round_aggregated") {
          // Round finished; stop countdown & reset counts
          setCurrentRound((prev) => {
            if (!prev || prev.id !== data.round_id) return prev;
            return {
              ...prev,
              status: "aggregated",
              closed_at: data.aggregated_at,
            };
          });
          setOpenedAtIso(null);
          setOpenCounts({ hospital: 0, patient: 0 });
        }

        if (data.type === "current_model_updated") {
          setCurrentModel({
            id: data.model_id,
            version: data.version,
          });
        }
      } catch {
        // ignore keep-alive heartbeats & malformed lines
      }
    });

    esRef.current = es;
    return () => {
      es.close();
      esRef.current = null;
    };
  }, []);

  const value: FedEventsState = {
    events,
    windowMinutes,
    currentRound,
    currentModel,
    openCounts,
    openedAtIso,
  };

  return (
    <FedEventsContext.Provider value={value}>
      {children}
    </FedEventsContext.Provider>
  );
}

export function useFedEvents(): FedEventsState {
  const ctx = useContext(FedEventsContext);
  if (!ctx) {
    throw new Error("useFedEvents must be used within FedEventsProvider");
  }
  return ctx;
}
