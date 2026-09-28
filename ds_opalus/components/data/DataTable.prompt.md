Record table with a sunken uppercase header and hairline row rules — no zebra striping.

```jsx
<DataTable
  columns={[{key:"nome",label:"Paciente"},{key:"leito",label:"Leito"},{key:"dias",label:"Dias",numeric:true,align:"right"}]}
  rows={[{nome:"Maria S.",leito:"N-104",dias:"12"}]} />
```

Pass `<Badge>` nodes as cell values for status columns. `dense` for 8px rows in high-count views.
