import React from "react";

export default function Settings() {
  // TODO: fetch & save settings via /v1/settings
  return (
    <div className="page">
      <h2>Settings</h2>
      <div className="card">
        <div className="muted">Aggregation window, EMA decay, thresholds, and webhooks will be configured here.</div>
      </div>
    </div>
  );
}
