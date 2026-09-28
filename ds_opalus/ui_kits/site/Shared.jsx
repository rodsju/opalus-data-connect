const { Button, Icon, Logo, Badge, Card, StatCard, TopBar } = window.OpalusDesignSystem_2ac06f;

function Section({ children, tone = "page", py = 96, style }) {
  const bg = { page: "var(--grey-0)", tint: "var(--navy-50)", brand: "var(--gradient-navy)", sunken: "var(--surface-sunken)" }[tone];
  return (
    <section style={{ background: bg, color: tone === "brand" ? "var(--text-inverse)" : "var(--text-body)", padding: `${py}px 32px`, ...style }}>
      <div style={{ maxWidth: "var(--container-max)", margin: "0 auto" }}>{children}</div>
    </section>
  );
}

function Eyebrow({ children, tone = "var(--teal-500)" }) {
  return <div style={{ fontFamily: "var(--font-ui)", fontSize: 12, fontWeight: 600, letterSpacing: ".14em", textTransform: "uppercase", color: tone, marginBottom: 14 }}>{children}</div>;
}

function SiteFooter() {
  const cols = [
    { h: "Institucional", l: ["Quem somos", "Governança", "Trabalhe conosco"] },
    { h: "Unidades", l: ["Opalus Premier", "Opalus Pleno", "Opalus Geriatrics"] },
    { h: "Atendimento", l: ["Central 0800", "Fale com a equipe", "Portal do cliente"] },
  ];
  return (
    <footer style={{ background: "var(--navy-800)", color: "var(--text-inverse-muted)", padding: "64px 32px 32px", position: "relative", overflow: "hidden" }}>
      <img src="../../assets/symbol-white.png" alt="" style={{ position: "absolute", right: -60, bottom: -90, width: 300, opacity: .07 }} />
      <div style={{ maxWidth: "var(--container-max)", margin: "0 auto", position: "relative" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr repeat(3,1fr)", gap: 48 }}>
          <div>
            <Logo tone="white" height={30} base="../../assets" />
            <p style={{ marginTop: 18, fontSize: "var(--text-sm)", maxWidth: 280, lineHeight: "var(--leading-relaxed)" }}>
              Excelência, humanização e técnica profissional no cuidado de longa permanência.
            </p>
          </div>
          {cols.map((c) => (
            <div key={c.h}>
              <div style={{ fontFamily: "var(--font-ui)", fontSize: 12, fontWeight: 600, letterSpacing: ".14em", textTransform: "uppercase", color: "rgba(255,255,255,.45)", marginBottom: 14 }}>{c.h}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
                {c.l.map((x) => <a key={x} href="#" style={{ fontSize: "var(--text-sm)", color: "var(--text-inverse-muted)", textDecoration: "none" }}>{x}</a>)}
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 56, paddingTop: 22, borderTop: "1px solid rgba(255,255,255,.12)", display: "flex", justifyContent: "space-between", fontSize: "var(--text-2xs)", color: "rgba(255,255,255,.5)" }}>
          <span>© 2026 Grupo Opalus. Todos os direitos reservados.</span>
          <span style={{ display: "flex", gap: 22 }}><a href="#" style={{ color: "inherit", textDecoration: "none" }}>Privacidade</a><a href="#" style={{ color: "inherit", textDecoration: "none" }}>Termos</a></span>
        </div>
      </div>
    </footer>
  );
}
Object.assign(window, { Section, Eyebrow, SiteFooter });
