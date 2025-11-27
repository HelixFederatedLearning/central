// // src/main.tsx
// import React from "react";
// import ReactDOM from "react-dom/client";
// import { createBrowserRouter, RouterProvider } from "react-router-dom";
// import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// import App from "./App";
// import Dashboard from "./pages/Dashboard";
// import Rounds from "./pages/Rounds";
// import RoundDetail from "./pages/RoundDetail";
// import Models from "./pages/Models";
// import Clients from "./pages/Clients";
// import Settings from "./pages/Settings";
// import Audit from "./pages/Audit";
// import ErrorBoundary from "./ErrorBoundary";
// import "./styles.css";
// import Inference from "./pages/Inference";

// const router = createBrowserRouter([
//   {
//     path: "/",
//     element: <App />,
//     children: [
//       { index: true, element: <Dashboard /> },
//       { path: "rounds", element: <Rounds /> },
//       { path: "rounds/:id", element: <RoundDetail /> },
//       { path: "models", element: <Models /> },
//       { path: "clients", element: <Clients /> },
//       { path: "settings", element: <Settings /> },
//       { path: "audit", element: <Audit /> },
      
//     ],
//   },
// ]);

// const qc = new QueryClient();

// ReactDOM.createRoot(document.getElementById("root")!).render(
//   <React.StrictMode>
//     <ErrorBoundary>
//       <QueryClientProvider client={qc}>
//         <RouterProvider router={router} />
//       </QueryClientProvider>
//     </ErrorBoundary>
//   </React.StrictMode>
// );

// src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import Dashboard from "./pages/Dashboard";
import Rounds from "./pages/Rounds";
import RoundDetail from "./pages/RoundDetail";
import Models from "./pages/Models";
import Clients from "./pages/Clients";
import Settings from "./pages/Settings";
import Audit from "./pages/Audit";
import Inference from "./pages/Inference";
import "./styles.css";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "rounds", element: <Rounds /> },
      { path: "rounds/:id", element: <RoundDetail /> },
      { path: "models", element: <Models /> },
      { path: "clients", element: <Clients /> },
      { path: "settings", element: <Settings /> },
      { path: "audit", element: <Audit /> },
      { path: "inference", element: <Inference /> },
    ],
  },
]);

const qc = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>
);
