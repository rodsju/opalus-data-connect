Modal for a decision or a short form; 20px radius, navy scrim at 55% with a 3px blur.

```jsx
<Dialog open={o} title="Confirmar alta?" description="Esta ação libera o leito."
  onClose={()=>setO(false)}
  footer={<><Button variant="secondary" onClick={()=>setO(false)}>Cancelar</Button><Button>Confirmar</Button></>} />
```
