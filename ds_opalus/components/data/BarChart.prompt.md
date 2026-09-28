Lightweight bar chart for dashboards and slides — baseline rule only, no gridlines, no legend box.

```jsx
<BarChart showValues data={[{label:"Jan",value:82},{label:"Fev",value:91}]} color="var(--navy-700)" />
```

Pass `color` for a single-series chart; omit it only when categories are genuinely unrelated.
