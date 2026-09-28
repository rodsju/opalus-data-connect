const { Card, Badge, Button, Tabs, Breadcrumbs, StatCard, ProgressBar, DataTable, Field, Textarea, Switch, Dialog, Icon, Toast } = window.OpalusDesignSystem_2ac06f;

function PatientDetail({ onBack }) {
  const [tab, setTab] = React.useState("evolucao");
  const [dlg, setDlg] = React.useState(false);
  const [toast, setToast] = React.useState(false);
  return (
    <div style={{ flex: 1, overflow: "auto", padding: 28, display: "flex", flexDirection: "column", gap: 20, position: "relative" }}>
      <Breadcrumbs items={[{ label: "Residentes", href: "#" }, { label: "Ala Norte", href: "#" }, { label: "Maria S. Andrade" }]} />
      <div style={{ display: "flex", alignItems: "flex-start", gap: 18 }}>
        <span style={{ width: 60, height: 60, borderRadius: "var(--radius-lg)", background: "var(--gradient-symbol)", color: "var(--grey-0)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-ui)", fontSize: 21, fontWeight: 600, flexShrink: 0 }}>MA</span>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <h2 style={{ fontFamily: "var(--font-display)", fontSize: 28, fontWeight: 700, letterSpacing: "-.02em", color: "var(--text-primary)", margin: 0 }}>Maria S. Andrade</h2>
            <Badge tone="warning" dot>Em observação</Badge>
          </div>
          <div style={{ display: "flex", gap: 20, marginTop: 7, fontSize: "var(--text-xs)", color: "var(--text-secondary)", fontFamily: "var(--font-ui)" }}>
            <span>82 anos</span><span>Leito N-104</span><span>Opalus Premier</span><span>Prontuário 44.821</span><span>Admissão 14/09/2026</span>
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={onBack} icon="arrow-left">Voltar</Button>
        <Button size="sm" icon="pill" onClick={() => setDlg(true)}>Nova prescrição</Button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
        <StatCard label="Pressão arterial" value="148/92" unit="mmHg" delta="+8" deltaTone="danger" icon="heart-pulse" />
        <StatCard label="Saturação" value="96" unit="%" icon="activity" />
        <StatCard label="Frequência card." value="82" unit="bpm" icon="heart" />
        <StatCard label="Dias de internação" value="12" icon="calendar-days" />
      </div>
      <Tabs value={tab} onChange={setTab} items={[{ id: "evolucao", label: "Evolução", icon: "notebook-pen", count: 34 }, { id: "prescricoes", label: "Prescrições", icon: "pill", count: 6 }, { id: "exames", label: "Exames", icon: "flask-conical" }, { id: "plano", label: "Plano de cuidado", icon: "clipboard-list" }]} />
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 20, alignItems: "start" }}>
        <Card padding="sm">
          <DataTable dense
            columns={[{ key: "d", label: "Data", numeric: true, width: 110 }, { key: "p", label: "Profissional" }, { key: "n", label: "Registro" }]}
            rows={[
              { d: "25/08 14:32", p: "R. Costa · Enf.", n: "PA alterada, mantida observação e reavaliação em 2h." },
              { d: "25/08 08:10", p: "L. Duarte · Méd.", n: "Ajuste de anti-hipertensivo conforme protocolo PA-03." },
              { d: "24/08 21:45", p: "T. Alves · Téc.", n: "Sinais vitais dentro do esperado. Boa aceitação da dieta." },
              { d: "24/08 15:02", p: "R. Costa · Enf.", n: "Fisioterapia motora realizada, sem intercorrências." },
            ]} />
        </Card>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card>
            <h4 style={{ fontFamily: "var(--font-display)", fontSize: 17, fontWeight: 700, color: "var(--text-primary)", margin: "0 0 14px" }}>Plano de cuidado</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
              <ProgressBar label="Mobilidade" value={72} showValue size="sm" />
              <ProgressBar label="Nutrição" value={88} showValue size="sm" tone="success" />
              <ProgressBar label="Cognição" value={54} showValue size="sm" tone="accent" />
            </div>
          </Card>
          <Card>
            <Field label="Novo registro de evolução">
              <Textarea rows={4} placeholder="Descreva a evolução do turno" />
            </Field>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 14 }}>
              <Switch label="Notificar médico" checked onChange={() => {}} />
              <Button size="sm" iconAfter="check" onClick={() => setToast(true)}>Salvar</Button>
            </div>
          </Card>
        </div>
      </div>
      <Dialog open={dlg} title="Nova prescrição" description="O registro será enviado à farmácia após a assinatura eletrônica." onClose={() => setDlg(false)}
        footer={<><Button variant="secondary" onClick={() => setDlg(false)}>Cancelar</Button><Button onClick={() => { setDlg(false); setToast(true); }}>Assinar e enviar</Button></>}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Field label="Medicamento"><Textarea rows={2} placeholder="Losartana 50mg — 1 comprimido, 12/12h" /></Field>
          <Switch label="Prescrição de uso contínuo" checked onChange={() => {}} />
        </div>
      </Dialog>
      {toast && <div style={{ position: "fixed", right: 28, bottom: 28, zIndex: 70 }}>
        <Toast tone="success" title="Registro salvo" onClose={() => setToast(false)}>Evolução registrada às 14:32.</Toast>
      </div>}
    </div>
  );
}
Object.assign(window, { PatientDetail });
