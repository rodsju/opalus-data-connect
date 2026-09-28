const { Button, Card, Field, Input, Textarea, Select, Checkbox, Alert, Icon } = window.OpalusDesignSystem_2ac06f;

function ContactPage() {
  const [sent, setSent] = React.useState(false);
  return (
    <Section tone="page" py={72}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 64, alignItems: "start" }}>
        <div>
          <Eyebrow>Atendimento</Eyebrow>
          <h1 style={{ fontFamily: "var(--font-display)", fontSize: 40, fontWeight: 800, letterSpacing: "-.03em", color: "var(--text-primary)", margin: 0 }}>Fale com a nossa equipe</h1>
          <p style={{ marginTop: 14, fontSize: 18, fontWeight: 300, color: "var(--text-secondary)", maxWidth: 440 }}>
            Conte um pouco sobre a necessidade de cuidado. Respondemos em até um dia útil.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 34 }}>
            {[["phone", "0800 000 0000", "Central de atendimento, 8h às 20h"], ["mail", "contato@opalus.com.br", "Comercial e institucional"], ["map-pin", "Av. Brigadeiro Faria Lima, 000", "São Paulo · SP"]].map(([i, a, b]) => (
              <div key={a} style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
                <span style={{ width: 38, height: 38, borderRadius: "var(--radius-md)", background: "var(--navy-50)", color: "var(--navy-700)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><Icon name={i} size={18} /></span>
                <div><div style={{ fontSize: "var(--text-md)", fontWeight: 600, color: "var(--text-primary)" }}>{a}</div><div style={{ fontSize: "var(--text-sm)", color: "var(--text-tertiary)" }}>{b}</div></div>
              </div>
            ))}
          </div>
          <img src="../../assets/illustrations/flow-streams.svg" alt="" style={{ width: "100%", marginTop: 40, opacity: .9 }} />
        </div>
        <Card padding="lg">
          {sent && <Alert tone="success" title="Mensagem enviada" style={{ marginBottom: 20 }}>Nossa equipe responde em até um dia útil.</Alert>}
          <div style={{ display: "grid", gap: 18 }}>
            <Field label="Nome completo" required><Input placeholder="Como podemos chamar você?" /></Field>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <Field label="E-mail" required><Input type="email" placeholder="voce@email.com" icon="mail" /></Field>
              <Field label="Telefone"><Input placeholder="(00) 00000-0000" icon="phone" /></Field>
            </div>
            <Field label="Unidade de interesse"><Select placeholder="Selecione a unidade" options={["Opalus Premier", "Opalus Pleno", "Opalus Geriatrics", "Ainda não sei"]} /></Field>
            <Field label="Como podemos ajudar?"><Textarea rows={4} placeholder="Descreva brevemente a necessidade de cuidado" /></Field>
            <Checkbox label="Autorizo o contato por telefone e e-mail" checked onChange={() => {}} />
            <Button size="lg" fullWidth iconAfter="send" onClick={() => setSent(true)}>Enviar mensagem</Button>
          </div>
        </Card>
      </div>
    </Section>
  );
}
Object.assign(window, { ContactPage });
