import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";

const links = [
  { to: "/", label: "Inicio", end: true },
  { to: "/analizar", label: "Analizar" },
  { to: "/modelos", label: "Modelos de IA" },
];

function Brand() {
  return (
    <Link to="/" className="brand">
      <img alt="" src="/mango.svg" />
      MangoVision <span>AI</span>
    </Link>
  );
}

export default function Header() {
  const [open, setOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const firstLink = useRef<HTMLAnchorElement>(null);
  const { pathname } = useLocation();

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    firstLink.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      menuButton.current?.focus();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const navigation = (mobile = false) =>
    links.map(({ to, label, end }, index) => (
      <NavLink
        key={to}
        to={to}
        end={end}
        ref={mobile && index === 0 ? firstLink : undefined}
        onClick={mobile ? () => setOpen(false) : undefined}
      >
        {label}
      </NavLink>
    ));

  return (
    <header className="site-header">
      <div className="wrap header">
        <Brand />
        <nav className="desktop-nav" aria-label="Principal">
          {navigation()}
        </nav>
        <button
          ref={menuButton}
          className="menu-button"
          type="button"
          aria-label={open ? "Cerrar menú" : "Abrir menú"}
          aria-expanded={open}
          aria-controls="mobile-navigation"
          onClick={() => setOpen((current) => !current)}
        >
          {open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
        </button>
      </div>
      {open && (
        <nav
          id="mobile-navigation"
          className="mobile-nav"
          aria-label="Navegación móvil"
        >
          <div className="wrap">{navigation(true)}</div>
        </nav>
      )}
    </header>
  );
}
