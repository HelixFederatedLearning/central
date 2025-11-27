import React from "react";

export default function Clients() {
  // TODO: wire to /v1/clients once backend route is ready
  return (
    <div className="page">
      <h2>Clients</h2>
      <div className="card">
        <div className="muted">Client management will appear here (register, revoke, rotate keys).</div>
      </div>
    </div>
  );
}
