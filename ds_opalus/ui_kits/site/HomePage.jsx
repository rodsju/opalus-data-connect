const { Button, Icon, Badge, Card, StatCard, ProgressBar } = window.OpalusDesignSystem_2ac06f;

function Hero() {
  return (
    <section style={{ background: "var(--gradient-navy)", color: "var(--text-inverse)", padding: "96px 32px 104px", position: "relative", overflow: "hidden" }}>
      <img src="../../assets/illustrations/node-mesh.svg" alt="" style={{ position: "absolute", right: -80, top: -40, width: 620, opacity: .2 }} />
      <div style={{ maxWidth: "var(--container-max)", margin: "0 auto", position: "relative", display: "grid", gridTemplateColumns: "1.15fr .85fr", gap: 64, alignItems: "center" }}>
        <div>
          <div style={{ fontFamily: "var(--font-ui)", fontSize: 12, fontWeight: 600, letterSpacing: ".14em", textTransform: "uppercase", color: "var(--navy-300)", marginBottom: 18 }}>Grupo Opalus · desde 2008</div>
          <h1 style={{ fontFamily: "var(--font-display)", fontSize: 60, fontWeight: 900, lineHeight: 1.02, letterSpacing: "-.03em", color: "var(--grey-0)", margin: 0 }}>
            Cuidado de longa<br />permanência com<br />técnica e humanidade.
          </h1>
          <p style={{ marginTop: 24, fontSize: 20, fontWeight: 300, lineHeight: 1.5, color: "var(--text-inverse-muted)", maxWidth: 520 }}>
            Quatro unidades, uma única forma de cuidar: protocolos assistenciais rigorosos, equipe multiprofissional e acompanhamento contínuo da família.
          </p>
          <div style={{ display: "flex", gap: 12, marginTop: 36 }}>
            <Button variant="inverse" size="lg" iconAfter="arrow-right">Agendar uma visita</Button>
            <Button variant="ghost" size="lg" style={{ color: "var(--grey-0)", border: "1px solid rgba(255,255,255,.28)" }}>Conheça as unidades</Button>
          </div>
        </div>
        <img src="../../assets/illustrations/orbit-core.svg" alt="" style={{ width: "100%" }} />
      </div>
    </section>
  );
}

function Pillars() {
  const items = [
    { i: "shield-check", t: "Excelência", d: "Protocolos auditados e indicadores assistenciais publicados mensalmente." },
    { i: "heart-handshake", t: "Humanização", d: "Plano de cuidado individual, construído com o residente e a família." },
    { i: "scale", t: "Ética", d: "Governança clínica independente e transparência em todas as decisões." },
    { i: "stethoscope", t: "Técnica profissional", d: "Equipe multiprofissional própria, com educação continuada." },
  ];
  return (
    <Section tone="page">
      <Eyebrow>Nossos valores</Eyebrow>
      <h2 style={{ fontFamily: "var(--font-display)", fontSize: 38, fontWeight: 700, letterSpacing: "-.015em", color: "var(--text-primary)", margin: 0, maxWidth: 620 }}>
        Seis princípios sustentam cada decisão assistencial.
      </h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 20, marginTop: 44 }}>
        {items.map((x) => (
          <Card key={x.t} interactive>
            <div style={{ width: 44, height: 44, borderRadius: "var(--radius-md)", background: "var(--navy-50)", color: "var(--navy-700)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 18 }}>
              <Icon name={x.i} size={22} />
            </div>
            <h4 style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 700, color: "var(--text-primary)", margin: "0 0 8px" }}>{x.t}</h4>
            <p style={{ margin: 0, fontSize: "var(--text-sm)", lineHeight: "var(--leading-relaxed)", color: "var(--text-secondary)" }}>{x.d}</p>
          </Card>
        ))}
      </div>
    </Section>
  );
}

function Indicators() {
  return (
    <Section tone="tint">
      <div style={{ display: "grid", gridTemplateColumns: ".9fr 1.1fr", gap: 64, alignItems: "center" }}>
        <div>
          <Eyebrow>Indicadores abertos</Eyebrow>
          <h2 style={{ fontFamily: "var(--font-display)", fontSize: 34, fontWeight: 700, letterSpacing: "-.015em", color: "var(--text-primary)", margin: 0 }}>
            O que medimos, publicamos.
          </h2>
          <p style={{ marginTop: 16, fontSize: "var(--text-md)", lineHeight: "var(--leading-relaxed)", color: "var(--text-secondary)", maxWidth: 420 }}>
            Painéis de qualidade atualizados mensalmente e auditados por nossa governança clínica.
          </p>
          <div style={{ marginTop: 26 }}><Button variant="secondary" iconAfter="arrow-up-right">Ver painel completo</Button></div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          <StatCard label="Satisfação das famílias" value="96,7" unit="%" delta="+2,1 p.p." icon="smile" footnote="NPS trimestral" />
          <StatCard label="Adesão a protocolos" value="98,2" unit="%" icon="clipboard-check" footnote="Auditoria set/2026" />
          <StatCard label="Leitos ativos" value="1.284" icon="bed-double" footnote="4 unidades" />
          <StatCard tone="brand" label="Equipe própria" value="620" unit="profissionais" />
        </div>
      </div>
    </Section>
  );
}

function Units({ onOpen }) {
  const units = [
    { n: "Opalus Premier", d: "Residência sênior de alta complexidade", c: "var(--blue-600)", i: "data-constellation" },
    { n: "Opalus Pleno", d: "Cuidado assistido e centro-dia", c: "var(--teal-500)", i: "signal-bars" },
    { n: "Opalus Geriatrics", d: "Ambulatório e reabilitação geriátrica", c: "var(--purple-500)", i: "pulse-trace" },
  ];
  return (
    <Section tone="page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 40 }}>
        <div><Eyebrow>Controladas</Eyebrow><h2 style={{ fontFamily: "var(--font-display)", fontSize: 34, fontWeight: 700, letterSpacing: "-.015em", color: "var(--text-primary)", margin: 0 }}>Três marcas, um mesmo padrão.</h2></div>
        <Button variant="ghost" iconAfter="arrow-right" onClick={onOpen}>Todas as unidades</Button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 20 }}>
        {units.map((u) => (
          <Card key={u.n} interactive padding="sm" onClick={onOpen}>
            <div style={{ borderRadius: "var(--radius-md)", background: "var(--navy-50)", padding: 12, marginBottom: 16 }}>
              <img src={`../../assets/illustrations/${u.i}.svg`} alt="" style={{ width: "100%", display: "block" }} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: u.c }} />
              <h4 style={{ fontFamily: "var(--font-display)", fontSize: 19, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>{u.n}</h4>
            </div>
            <p style={{ margin: 0, fontSize: "var(--text-sm)", color: "var(--text-secondary)" }}>{u.d}</p>
          </Card>
        ))}
      </div>
    </Section>
  );
}

function CtaBand() {
  return (
    <section style={{ background: "var(--gradient-blue)", color: "var(--text-inverse)", padding: "72px 32px", position: "relative", overflow: "hidden" }}>
      <img src="../../assets/illustrations/cross-lattice.svg" alt="" style={{ position: "absolute", left: -40, bottom: -60, width: 460, opacity: .2 }} />
      <div style={{ maxWidth: "var(--container-max)", margin: "0 auto", position: "relative", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 40 }}>
        <div>
          <h3 style={{ fontFamily: "var(--font-display)", fontSize: 30, fontWeight: 700, letterSpacing: "-.015em", color: "var(--grey-0)", margin: 0 }}>Vamos conversar sobre o cuidado que sua família precisa.</h3>
          <p style={{ margin: "10px 0 0", color: "var(--text-inverse-muted)", fontSize: "var(--text-md)" }}>Nossa equipe responde em até um dia útil.</p>
        </div>
        <Button variant="inverse" size="lg" icon="phone">Falar com a equipe</Button>
      </div>
    </section>
  );
}

function HomePage({ onOpenUnits }) {
  return <><Hero /><Pillars /><Indicators /><Units onOpen={onOpenUnits} /><CtaBand /></>;
}
Object.assign(window, { HomePage, Hero, Pillars, Indicators, Units, CtaBand });
