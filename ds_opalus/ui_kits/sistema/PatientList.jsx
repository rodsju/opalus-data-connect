const { DataTable, Badge, Tag, Button, Input, Select, Card, IconButton, Tooltip } = window.OpalusDesignSystem_2ac06f;

const PEOPLE = [
  ["Maria S. Andrade", "N-104", "82", "Premier", "success", "Estável", "12"],
  ["João P. Ferreira", "N-108", "78", "Premier", "warning", "Atenção", "9"],
  ["Ana L. Moreira", "S-201", "85", "Pleno", "info", "Exames", "4"],
  ["Carlos E. Lima", "L-312", "91", "Geriatrics", "danger", "Crítico", "21"],
  ["Beatriz N. Rocha", "S-118", "74", "Pleno", "success", "Estável", "6"],
  ["Otávio M. Prado", "N-121", "88", "Premier", "success", "Estável", "31"],
];

function PatientList({ onOpen }) {
  const [filter, setFilter] = React.useState("Todos");
  const rows = PEOPLE
    .filter((p) => filter === "Todos" || p[3] === filter)
    .map((p, i) => ({
      id: i,
      nome: <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{p[0]}</span>,
      leito: p[1], idade: p[2], unidade: <Tag>{p[3]}</Tag>,
      status: <Badge tone={p[4]} size="sm" dot>{p[5]}</Badge>,
      dias: p[6],
      acoes: <span style={{ display: "inline-flex", gap: 4, justifyContent: "flex-end" }}>
        <Tooltip label="Prontuário"><IconButton icon="file-text" label="Prontuário" size="sm" /></Tooltip>
        <Tooltip label="Prescrever"><IconButton icon="pill" label="Prescrever" size="sm" /></Tooltip>
      </span>,
    }));
  return (
    <div style={{ flex: 1, overflow: "auto", padding: 28, display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ display: "flex", gap: 8, flex: 1 }}>
          {["Todos", "Premier", "Pleno", "Geriatrics"].map((f) => <Tag key={f} selected={filter === f} onClick={() => setFilter(f)}>{f}</Tag>)}
        </div>
        <div style={{ width: 170 }}><Select size="sm" placeholder="Ordenar por" options={["Nome", "Leito", "Dias de internação"]} /></div>
        <Button size="sm" variant="secondary" icon="download">Exportar</Button>
        <Button size="sm" icon="user-plus">Nova admissão</Button>
      </div>
      <DataTable onRowClick={onOpen}
        columns={[{ key: "nome", label: "Residente" }, { key: "leito", label: "Leito", width: 90 }, { key: "idade", label: "Idade", numeric: true, width: 80, align: "right" }, { key: "unidade", label: "Unidade", width: 130 }, { key: "status", label: "Status", width: 150 }, { key: "dias", label: "Dias", numeric: true, align: "right", width: 80, sorted: "desc" }, { key: "acoes", label: "", align: "right", width: 90 }]}
        rows={rows} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "var(--text-xs)", color: "var(--text-tertiary)" }}>
        <span>Exibindo {rows.length} de 1.284 residentes</span>
        <div style={{ display: "flex", gap: 6 }}>
          <Button size="sm" variant="secondary" icon="chevron-left">Anterior</Button>
          <Button size="sm" variant="secondary" iconAfter="chevron-right">Próxima</Button>
        </div>
      </div>
    </div>
  );
}
Object.assign(window, { PatientList });
