# Cálculo de costos de ingredientes por porción — Nivel 2

## Descripción
Script en Python (`calcular_costos.py`) que determina el costo de ingredientes por porción de los 50 platos de la carta al **31/10/2026**. Usa aritmética exacta (`decimal.Decimal` / `fractions.Fraction`) sin redondeos intermedios y redondeo final a dos decimales con `ROUND_HALF_UP`.

## Entradas utilizadas
- `nivel-2/catalogo.csv`: equivalencias entre presentaciones de compra y unidades base (g, ml, unidad).
- `nivel-2/rendimientos.csv`: coeficientes de merma/rendimiento (`limpio_sobre_bruto` y `cocido_sobre_limpio`).
- `nivel-2/facturas/F-001.pdf` … `F-040.pdf`: comprobantes de compra con cantidades, presentaciones, precios unitarios, bonificaciones por volumen e importes netos.
- `nivel-2/notas/NC-001.pdf` … `NC-004.pdf`: notas de crédito asociadas a factura y renglón de origen (bonificación descuenta importe neto; devolución descuenta importe neto y unidades equivalentes).
- `nivel-2/recetas.json`: composición de los 50 platos (P01–P50) y las 15 preparaciones base (S01–S15).

## Lógica de cálculo
1. **Extracción y ajuste documental:** se extrae el texto de cada PDF (respetando el orden dinámico de columnas), se convierten las cantidades a unidades base mediante `catalogo.csv` y se aplican las notas de crédito emitidas hasta el 2026-10-31 sobre su factura y renglón de origen.
2. **Precio unitario efectivo vigente:** para cada producto se selecciona el comprobante con fecha ≤ 2026-10-31 más reciente (desempatando por identificador de factura alfanuméricamente mayor) y se calcula  
   PU_efectivo = Neto ajustado / Cantidad equivalente ajustada.
3. **Explosión de recetas y mermas:** cada ingrediente en estado `limpio` se divide por `limpio_sobre_bruto`, cada ingrediente en estado `cocido` se divide por `limpio_sobre_bruto × cocido_sobre_limpio`, y cada ingrediente `preparado` se prorratea recursivamente según el rendimiento declarado de su tanda.

## Ejecución
Requiere Python 3.10+ y `pypdf` (o texto pre-extraído con `pdftotext`):

```bash
pip install pypdf
python nivel-2/codigo/calcular_costos.py
```

El script escribe `nivel-2/costos.csv` con el encabezado `plato,costo_por_porcion` y una fila por cada plato P01–P50.
