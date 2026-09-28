const { StatCard, Card, BarChart, ProgressBar, Badge, DataTable, Tabs, Button, Alert, Icon } = window.OpalusDesignSystem_2ac06f;

function Dashboard({ onOpenPatient }) {
  const [range, setRange] = React.useState("Semana");
  return (
    <div style={{ flex: 1, overflow: "auto", padding: 28, display: "flex", flexDirection: "column", gap: 20 }}>
      <Alert tone="warning" title="3 prescrições vencem hoje" onClose={() => {}}>Ala Norte — revise antes das 18h.</Alert>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16 }}>
        <StatCard label="Ocupação" value="92,4" unit="%" delta="+4,2 p.p." icon="bed-double" footnote="Últimas 24h" />
        <StatCard label="Residentes ativos" value="1.284" delta="+12" icon="users" footnote="4 unidades" />
        <StatCard label="Tempo médio" value="12,4" unit="dias" delta="-1,1" icon="clock" footnote="Internação clínica" />
        <StatCard tone="brand" label="Adesão a protocolos" value="96,7" unit="%" footnote="Auditoria set/2026" />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.35fr 1fr", gap: 20, alignItems: "start" }}>
        <Card header={<div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div><div style={{ fontFamily: "var(--font-ui)", fontSize: 12, fontWeight: 600, letterSpacing: ".14em", textTransform: "uppercase", color: "var(--text-tertiary)" }}>Ocupação por mês</div>
          <h4 style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 700, color: "var(--text-primary)", margin: "4px 0 0" }}>Média consolidada</h4></div>
          <Tabs variant="pill" value={range} onChange={setRange} items={["Semana", "Mês", "Ano"]} /></div>}>
          <BarChart height={200} showValues color="var(--navy-700)"
            data={[{ label: "Abr", value: 78 }, { label: "Mai", value: 84 }, { label: "Jun", value: 81 }, { label: "Jul", value: 89 }, { label: "Ago", value: 92 }, { label: "Set", value: 88 }]} />
        </Card>
        <Card header={<h4 style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>Ocupação por ala</h4>}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <ProgressBar label="Ala Norte" value={92} showValue tone="warning" />
            <ProgressBar label="Ala Sul" value={64} showValue />
            <ProgressBar label="Ala Leste" value={78} showValue tone="accent" />
            <ProgressBar label="Centro-dia" value={38} showValue tone="success" />
          </div>
          <div style={{ marginTop: 22, padding: 14, borderRadius: "var(--radius-md)", background: "var(--navy-50)", display: "flex", gap: 11 }}>
            <span style={{ color: "var(--navy-600)" }}><Icon name="info" size={17} /></span>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--text-body)", lineHeight: "var(--leading-normal)" }}>
              Ala Norte acima do limite de segurança (90%). Considere redistribuir novas admissões.
            </div>
          </div>
        </Card>
      </div>
      <Card padding="sm" header={<div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 4 }}>
        <h4 style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>Intercorrências do turno</h4>
        <Button variant="ghost" size="sm" iconAfter="arrow-right">Ver todas</Button></div>}>
        <DataTable dense onRowClick={onOpenPatient}
          columns={[{ key: "h", label: "Hora", numeric: true, width: 80 }, { key: "r", label: "Residente" }, { key: "l", label: "Leito", width: 90 }, { key: "e", label: "Evento" }, { key: "s", label: "Status", align: "right", width: 130 }]}
          rows={[
            { h: "14:32", r: "Maria S. Andrade", l: "N-104", e: "Pressão arterial alterada", s: <Badge tone="warning" size="sm" dot>Em observação</Badge> },
            { h: "12:05", r: "João P. Ferreira", l: "N-108", e: "Ajuste de prescrição", s: <Badge tone="success" size="sm" dot>Resolvido</Badge> },
            { h: "09:48", r: "Ana L. Moreira", l: "S-201", e: "Coleta laboratorial", s: <Badge tone="info" size="sm" dot>Aguardando</Badge> },
            { h: "07:20", r: "Carlos E. Lima", l: "L-312", e: "Queda sem lesão", s: <Badge tone="danger" size="sm" dot>Notificado</Badge> },
          ]} />
      </Card>
    </div>
  );
}
Object.assign(window, { Dashboard });
