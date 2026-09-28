Switches between sibling views. `underline` for page sections, `pill` for in-card toggles.

```jsx
<Tabs value={t} onChange={setT} items={[{id:"geral",label:"Geral"},{id:"exames",label:"Exames",count:12}]} />
<Tabs variant="pill" items={["Dia","Semana","Mês"]} value={p} onChange={setP} />
```
