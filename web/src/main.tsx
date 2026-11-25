import { createRoot } from "react-dom/client";
import {
  HashRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import { useEffect } from "react";
import { MotionConfig } from "motion/react";
import "@fontsource-variable/manrope";
import "@fontsource-variable/inter";
import "./style.css";
import Home from "./pages/Home";
import Analyze from "./pages/Analyze";
import Models from "./pages/Models";
import { useService } from "./hooks/useService";
import Header from "./components/Header";
function App() {
  const service = useService(),
    { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
    document.title =
      ({
        "/": "Inicio",
        "/analizar": "Analizar mango",
        "/modelos": "Modelos de IA",
      }[pathname] ?? "Inicio") + " · MangoVision AI";
  }, [pathname]);
  return (
    <MotionConfig reducedMotion="user">
      <a
        className="skip"
        href="#contenido"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("contenido")?.focus();
        }}
      >
        Saltar al contenido
      </a>
      <Header />
      <div id="contenido" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/analizar" element={<Analyze service={service} />} />
          <Route path="/modelos" element={<Models />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </MotionConfig>
  );
}
createRoot(document.getElementById("root")!).render(
  <HashRouter>
    <App />
  </HashRouter>,
);
