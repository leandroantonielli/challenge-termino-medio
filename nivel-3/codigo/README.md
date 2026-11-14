# Nivel 3 · Costos al 31/10 y márgenes del trimestre

`costeo3.py` (Python 3, sin dependencias externas; usa `pdftotext` para los PDF del nivel 2) genera `nivel-3/costos.csv` y `nivel-3/margenes.csv`.

## Entradas
- Recetas, catálogo y rendimientos del nivel 2, que no cambian.
- Las compras del nivel 2: 40 facturas PDF y las notas NC-001 a NC-004.
- `compras_ocr.csv`: las 27 imágenes nuevas pasadas a texto (facturas manuscritas M-001 a M-012 y tickets T-001 a T-015). Se toma el último valor corregido cuando hay tachaduras. Se guardan cantidad, presentación, precio y bonificación, y el neto se recalcula como cantidad × precio × (1 − bonificación). Las imágenes no se suben al repo.
- La caja de agosto a octubre (no se sube), con `articulos.csv` y `combos.csv`.

## Costos
Se usa el mismo método que en el nivel 2: por producto, la última compra con fecha menor o igual al corte. Si hay empate de fecha, gana el documento con id alfanuméricamente mayor. Las notas emitidas hasta el corte restan importe y, si son devoluciones, también unidades. Después se pasa a cantidad bruta con los rendimientos y las subrecetas se costean en forma recursiva.

## Márgenes
- `VTA`: el artículo se traduce a plato con el maestro de artículos, según la vigencia a la fecha de la venta. El cobro es bruto − descuento.
- `COM`: el cobro neto se reparte entre los componentes en proporción a `peso_ingreso`, sin redondear. Las unidades son cantidad × unidades por combo.
- `REV`: resta exactamente las unidades, el ingreso y el costo del movimiento que referencia, calculados a la fecha de ese movimiento original.
- `EXT` (propinas): se ignora.
- El costo de cada venta usa el costo por porción a la fecha de esa venta: las compras y notas disponibles hasta ese día.
- Margen = (ingreso − costo) / ingreso, con 6 decimales; si el ingreso es 0, el margen es 0.

## Reproducir
```
python3 costeo3.py ruta/nivel-2 ruta/nivel-3 ..
```
