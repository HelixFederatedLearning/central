// import { NavLink, Outlet } from "react-router-dom";
// export default function App() {
//   return (
//     <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", minHeight: "100vh" }}>
//       <aside style={{ padding: 16, borderRight: "1px solid #eee" }}>
//         <h2>Central</h2>
//         <nav style={{ display: "grid", gap: 8 }}>
//           <NavLink to="/">Dashboard</NavLink>
//           <NavLink to="/rounds">Rounds</NavLink>
//           <NavLink to="/models">Models</NavLink>
//           <NavLink to="/clients">Clients</NavLink>
//           <NavLink to="/settings">Settings</NavLink>
//           <NavLink to="/audit">Audit</NavLink>
//           <NavLink to="/inference">Inference</NavLink>
//         </nav>
//       </aside>
//       <main style={{ padding: 24 }}>
//         <Outlet />
//       </main>
//     </div>
//   );
// }

// src/App.tsx
import { NavLink, Outlet } from "react-router-dom";

export default function App() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", minHeight: "100vh" }}>
      <aside style={{ padding: 16, borderRight: "1px solid #eee" }}>
        <h2>Central</h2>
        <nav style={{ display: "grid", gap: 8 }}>
          <NavLink to="/">Dashboard</NavLink>
          <NavLink to="/rounds">Rounds</NavLink>
          <NavLink to="/models">Models</NavLink>
          <NavLink to="/clients">Clients</NavLink>
          <NavLink to="/settings">Settings</NavLink>
          <NavLink to="/audit">Audit</NavLink>
          <NavLink to="/inference">Inference</NavLink>
        </nav>
      </aside>
      <main style={{ padding: 24 }}>
        <Outlet />
      </main>
    </div>
  );
}
