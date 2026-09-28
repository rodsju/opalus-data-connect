# UI kit — Sistema Opalus

Internal assistential system. Open `index.html`; the sidebar and table rows are clickable.

**Screens**
- `AppShell.jsx` — navy `SideNav` + white `AppHeader` (search, notifications, user).
- `Dashboard.jsx` — alert band, four KPI tiles, occupancy chart + per-wing meters, shift-incident table.
- `PatientList.jsx` — filterable resident table with row actions and pagination.
- `PatientDetail.jsx` — record header, vitals tiles, tabbed evolution log, care-plan meters, prescription `Dialog` → success `Toast`.

**Flow:** Painel → click any incident row → prontuário. Residentes → click a row → prontuário → Voltar.

**Notes**
- No existing Opalus system screens were supplied. This kit is a brand-faithful composition from the Manual da Marca and `/tokens`, not a recreation.
- Sidebar destinations with no supplied design (Prescrições, Indicadores, Mapa de leitos, Configurações) render an explicit "no layout provided" placeholder rather than an invented screen.
- All patient names, figures and events are fictional.
