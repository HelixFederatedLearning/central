import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Rounds as API } from "../api/central";
import { Link } from "react-router-dom";

type Round = {
  id: string;
  status: string;
  window_start: string;
  window_end: string;
};

export default function Rounds() {
  const {
    data,
    isLoading,
    isError,
    error,
  } = useQuery<Round[]>({ queryKey: ["rounds"], queryFn: API.list });

  return (
    <div className="page">
      <div className="page-header">
        <h2>Rounds</h2>
        <span className="muted">Server-side aggregation windows</span>
      </div>

      <div className="card">
        <div className="card-header" style={{ marginBottom: 8 }}>
          <div className="card-title">All Rounds</div>
          {data && (
            <span className="chip mono">
              {data.length} {data.length === 1 ? "round" : "rounds"}
            </span>
          )}
        </div>

        {isLoading && <div className="muted">Loading rounds…</div>}

        {isError && (
          <div className="chip chip--danger">
            Failed to load rounds:{" "}
            <span className="mono">
              {(error as any)?.message ?? "unknown error"}
            </span>
          </div>
        )}

        {!isLoading && !isError && data && data.length === 0 && (
          <div className="muted">No rounds have been created yet.</div>
        )}

        {!isLoading && !isError && data && data.length > 0 && (
          <div style={{ overflowX: "auto", marginTop: 4 }}>
            <table className="table rounds-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Status</th>
                  <th>Start</th>
                  <th>End</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link to={`/rounds/${r.id}`}>
                        <span className="mono">{r.id.slice(0, 8)}…</span>
                      </Link>
                    </td>
                    <td>
                      <span
                        className={
                          "status-pill " + getStatusClass(r.status ?? "")
                        }
                      >
                        {r.status}
                      </span>
                    </td>
                    <td>{new Date(r.window_start).toLocaleString()}</td>
                    <td>{new Date(r.window_end).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function getStatusClass(status: string) {
  const s = status.toLowerCase();
  if (s === "open") return "status-pill--open";
  if (s === "aggregated") return "status-pill--aggregated";
  if (s === "closed") return "status-pill--closed";
  return "status-pill--other";
}
