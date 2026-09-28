const { Button, Icon, Badge, Card, Tag, DataTable, ProgressBar, Breadcrumbs, Tabs } = window.OpalusDesignSystem_2ac06f;

function UnitsPage() {
  const [filter, setFilter] = React.useState("Todas");
  const [tab, setTab] = React.useState("estrutura");
  const rows = [
    { id: 1, u: "Opalus Premier", c: "São Paulo · SP", l: "480", m: <Badge tone="success" size="sm" dot>Vagas</Badge> },
    { id: 2, u: "Opalus Pleno", c: "Campinas · SP", l: "360", m: <Badge tone="warning" size="sm" dot>Lista de espera</Badge> },
    { id: 3, u: "Opalus Geriatrics", c: "Curitiba · PR", l: "264", m: <Badge tone="success" size="sm" dot>Vagas</Badge> },
    { id: 4, u: "Opalus Pleno", c: "Belo Horizonte · MG", l: "180", m: <Badge tone="info" size="sm" dot>Em obras</Badge> },
  ];
  return (
    <>
      <section style={{ background: "var(--navy-50)", padding: "40px 32px 56px" }}>
        <div style={{ maxWidth: "var(--container-max)", margin: "0 auto" }}>
          <Breadcrumbs items={[{ label: "Institucional", href: "#" }, { label: "Unidades" }]} />
          <h1 style={{ fontFamily: "var(--font-display)", fontSize: 44, fontWeight: 800, letterSpacing: "-.03em", color: "var(--text-primary)", margin: "18px 0 0" }}>Unidades do grupo</h1>
          <p style={{ marginTop: 12, fontSize: 18, fontWeight: 300, color: "var(--text-secondary)", maxWidth: 560 }}>
            Quatro endereços, o mesmo padrão assistencial. Filtre por região ou modalidade de cuidado.
          </p>
          <div style={{ display: "flex", gap: 8, marginTop: 26 }}>
            {["Todas", "São Paulo", "Sul", "Sudeste"].map((f) => (
              <Tag key={f} selected={filter === f} onClick={() => setFilter(f)}>{f}</Tag>
            ))}
          </div>
        </div>
      </section>
      <Section tone="page" py={64}>
        <DataTable
          columns={[{ key: "u", label: "Unidade" }, { key: "c", label: "Cidade" }, { key: "l", label: "Leitos", numeric: true, align: "right" }, { key: "m", label: "Disponibilidade", align: "right" }]}
          rows={rows} />
        <div style={{ marginTop: 56 }}>
          <Tabs value={tab} onChange={setTab} items={[{ id: "estrutura", label: "Estrutura", icon: "building-2" }, { id: "equipe", label: "Equipe", icon: "users" }, { id: "protocolos", label: "Protocolos", icon: "clipboard-list" }]} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 20, marginTop: 28 }}>
            {[["Quartos individuais", "Todos com banheiro adaptado e chamada de enfermagem."],
              ["Centro de reabilitação", "Fisioterapia, fonoaudiologia e terapia ocupacional no local."],
              ["Retaguarda clínica 24h", "Equipe médica presencial e convênio de urgência."]].map(([t, d]) => (
              <Card key={t}>
                <h4 style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, color: "var(--text-primary)", margin: "0 0 8px" }}>{t}</h4>
                <p style={{ margin: 0, fontSize: "var(--text-sm)", color: "var(--text-secondary)", lineHeight: "var(--leading-relaxed)" }}>{d}</p>
              </Card>
            ))}
          </div>
        </div>
      </Section>
    </>
  );
}
Object.assign(window, { UnitsPage });
