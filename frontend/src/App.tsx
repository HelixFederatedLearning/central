// src/App.tsx
import { NavLink, Outlet } from "react-router-dom";

export default function App() {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div>
          <h1>Central</h1>
          <div className="sidebar-sub">Federated Control Plane</div>
        </div>
        <nav>
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/rounds">Rounds</NavLink>
          <NavLink to="/models">Models</NavLink>
          {/* <NavLink to="/clients">Clients</NavLink> */}
          {/* <NavLink to="/settings">Settings</NavLink> */}
          {/* <NavLink to="/audit">Audit</NavLink> */}
          <NavLink to="/inference">Inference</NavLink>
        </nav>
        <div className="sidebar-footer">
          <span className="chip mono">v1.0 · local</span>
        </div>
      </aside>

      <main>
        <Outlet />
      </main>
    </div>
  );
}
