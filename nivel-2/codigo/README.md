# Nivel 2 · Cálculo de costos por porción

## Entradas

- `catalogo.csv`: equivalencias de cada presentación de cada producto a unidad base (g, ml o unidad).
- `rendimientos.csv`: coeficientes limpio/bruto y cocido/limpio por producto.
- `recetas.json`: recetario completo (50 platos P01–P50 y 15 preparaciones S01–S15).
- `facturas/F-001.pdf` … `F-040.pdf`: 40 facturas de compra.
- `notas/NC-001.pdf` … `NC-004.pdf`: documentos asociados (bonificaciones o devoluciones) que ajustan renglones de facturas anteriores.

## Lógica del cálculo

1. Se extrae el texto de cada factura y nota con `pdftotext`.
2. Se parsean las líneas de factura identificando producto, presentación, cantidad, precio unitario, bonificación y neto (el orden de columnas varía entre facturas; se valida que `neto ≈ cantidad × precio × (1 − bonif/100)`).
3. Se aplican las notas de crédito con fecha ≤ 31/10/2026:
   - Se resta el importe acreditado del neto del renglón.
   - Si es devolución, se resta también la cantidad devuelta.
4. Para cada producto se toma la última factura con fecha ≤ 31/10/2026 (en empate de fecha, el identificador alfanumérico mayor).
5. Precio efectivo = neto ajustado / cantidad equivalente en unidad base (según catálogo).
6. Para cada plato se calcula el costo de ingredientes:
   - Se convierte la cantidad de la receta (según estado bruto/limpio/cocido) a cantidad bruta usando los rendimientos.
   - Se multiplica por el precio efectivo por unidad base.
   - Las preparaciones (Sxx) se costean por su rendimiento completo y se prorratean.
7. Se redondea el resultado final a 2 decimales (half-up). No hay redondeos intermedios.

## Salida

`../costos.csv` con encabezado `plato,costo_por_porcion` y una fila por cada plato P01–P50.
