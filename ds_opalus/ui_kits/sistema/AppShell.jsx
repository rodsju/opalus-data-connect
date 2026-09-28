const { SideNav, IconButton, Icon, Input, Badge, Button, Logo } = window.OpalusDesignSystem_2ac06f;

const NAV = [
  { section: "Assistencial" },
  { id: "dash", label: "Painel", icon: "layout-dashboard" },
  { id: "pacientes", label: "Residentes", icon: "users", count: 8 },
  { id: "prescricoes", label: "Prescrições", icon: "clipboard-list" },
  { section: "Gestão" },
  { id: "indicadores", label: "Indicadores", icon: "activity" },
  { id: "leitos", label: "Leitos", icon: "bed-double" },
  { id: "config", label: "Configurações", icon: "settings" },
];

function AppHeader({ title, subtitle, actions, onSearch }) {
  return (
    <header style={{ display: "flex", alignItems: "center", gap: 20, padding: "18px 28px", background: "var(--surface-card)", borderBottom: "1px solid var(--border-default)" }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: 24, fontWeight: 700, letterSpacing: "-.015em", color: "var(--text-primary)", margin: 0 }}>{title}</h1>
        {subtitle && <div style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)", marginTop: 3 }}>{subtitle}</div>}
      </div>
      <div style={{ width: 260 }}><Input size="sm" icon="search" placeholder="Buscar residente, leito…" onChange={onSearch} /></div>
      {actions}
      <IconButton icon="bell" label="Notificações" variant="outline" />
      <div style={{ display: "flex", alignItems: "center", gap: 9, paddingLeft: 6 }}>
        <span style={{ width: 34, height: 34, borderRadius: 999, background: "var(--gradient-symbol)", color: "var(--grey-0)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-ui)", fontSize: 13, fontWeight: 600 }}>RC</span>
        <div style={{ lineHeight: 1.25 }}>
          <div style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-primary)" }}>Renata Costa</div>
          <div style={{ fontSize: "var(--text-3xs)", color: "var(--text-tertiary)" }}>Enfermeira-chefe</div>
        </div>
      </div>
    </header>
  );
}

function AppShell({ nav, onNav, children }) {
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--surface-page)" }}>
      <SideNav items={NAV} value={nav} onChange={onNav} assetBase="../../assets"
        footer={<div style={{ display: "flex", alignItems: "center", gap: 10, color: "rgba(255,255,255,.6)", fontSize: "var(--text-2xs)" }}>
          <Icon name="life-buoy" size={16} /> Suporte · ramal 4400
        </div>} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>{children}</div>
    </div>
  );
}
Object.assign(window, { AppShell, AppHeader, NAV });
