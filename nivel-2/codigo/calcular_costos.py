import json
import csv
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

catalog = {}
with open("/tmp/nivel2/nivel-2/catalogo.csv") as f:
    for row in csv.DictReader(f):
        catalog[(row["producto"], row["presentacion"].lower())] = (Decimal(row["cantidad_base"]), row["unidad_base"])

rend = {}
with open("/tmp/nivel2/nivel-2/rendimientos.csv") as f:
    for row in csv.DictReader(f):
        rend[row["producto"]] = (Decimal(row["limpio_sobre_bruto"]), Decimal(row["cocido_sobre_limpio"]))

with open("/tmp/nivel2/nivel-2/recetas.json") as f:
    recipes = json.load(f)
recipes_dict = {r["codigo"]: r for r in recipes}

txt_dir = Path("/tmp/nivel2/txt")

def parse_decimal(s):
    return Decimal(s.strip().replace(".", "").replace(",", "."))

invoices = {}
for path in sorted(txt_dir.glob("F-*.txt")):
    text = path.read_text(encoding="utf-8", errors="replace")
    inv_id = path.stem
    m = re.search(r"Fecha:\s*(\d{4}-\d{2}-\d{2})", text)
    if not m: continue
    fecha = m.group(1)
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not re.match(r"^\d+\s+[A-Z]\d{2}\b", line):
            continue
        prod = re.search(r"^\d+\s+([A-Z]\d{2})\b", line).group(1)
        tokens = line.split()
        units = {"g", "kg", "ml", "l", "bolsa", "cajón", "atado", "unidad", "docena", "maple"}
        unit = next((t.lower() for t in tokens if t.lower() in units), None)
        if not unit: continue
        num_tokens = [t for t in tokens if re.match(r"^[\d]+(?:[.,]\d+)?$", t)]
        if num_tokens and num_tokens[0].isdigit() and int(num_tokens[0]) < 20:
            num_tokens = num_tokens[1:]
        if len(num_tokens) < 4: continue
        cands = [parse_decimal(t) for t in num_tokens[-4:]]
        valid = []
        for ii in range(4):
            for jj in range(4):
                if ii == jj: continue
                for kk in range(4):
                    if kk in (ii, jj): continue
                    for mm in range(4):
                        if mm in (ii, jj, kk): continue
                        cant, precio, bonif, neto = cands[ii], cands[jj], cands[kk], cands[mm]
                        if bonif not in (Decimal("0"), Decimal("8"), Decimal("0.00"), Decimal("8.00")): continue
                        expected = (cant * precio * (Decimal("100") - bonif) / Decimal("100")).quantize(Decimal("0.01"))
                        if abs(expected - neto) < Decimal("0.05"):
                            valid.append((cant, precio, bonif, neto))
        if not valid: continue
        best = None
        best_score = -1
        for cant, precio, bonif, neto in valid:
            key = (prod, unit)
            if key not in catalog: continue
            base_qty, base_unit = catalog[key]
            total_base = cant * base_qty
            if total_base <= 0: continue
            unit_price = neto / total_base
            score = 10 if Decimal("0.0001") <= unit_price <= Decimal("500") else 0
            if unit in ("g", "ml") and cant > precio: score += 2
            if unit in ("kg", "l", "bolsa", "cajón") and precio > 100: score += 1
            if score > best_score:
                best_score = score
                best = (cant, precio, bonif, neto)
        if best:
            cant, precio, bonif, neto = best
            lines.append({"prod": prod, "cant": cant, "pres": unit, "precio": precio, "bonif": bonif, "neto": neto, "renglon": len(lines)+1})
    invoices[inv_id] = {"fecha": fecha, "lines": lines, "id": inv_id}

notes = []
for path in sorted(txt_dir.glob("NC-*.txt")):
    text = path.read_text(encoding="utf-8", errors="replace")
    notes.append({
        "id": path.stem,
        "fecha": re.search(r"Fecha:\s*(\d{4}-\d{2}-\d{2})", text).group(1),
        "factura": re.search(r"Factura asociada:\s*(F-\d+)", text).group(1),
        "renglon": int(re.search(r"Renglón:\s*(\d+)", text).group(1)),
        "prod": re.search(r"Producto:\s*([A-Z]\d{2})", text).group(1),
        "concepto": re.search(r"Concepto:\s*(\w+)", text).group(1),
        "cant_devuelta": parse_decimal(re.search(r"Cantidad devuelta:\s*([\d.,]+)", text).group(1)),
        "importe": parse_decimal(re.search(r"Importe acreditado:\s*\$\s*([\d.,]+)", text).group(1))
    })

COSTEO = "2026-10-31"
for note in notes:
    if note["fecha"] > COSTEO: continue
    inv = invoices.get(note["factura"])
    if not inv: continue
    if 1 <= note["renglon"] <= len(inv["lines"]):
        line = inv["lines"][note["renglon"] - 1]
        if line["prod"] == note["prod"]:
            line["neto"] -= note["importe"]
            if note["concepto"] == "devolución" and note["cant_devuelta"] > 0:
                line["cant"] -= note["cant_devuelta"]

product_best = {}
for inv_id, inv in sorted(invoices.items(), key=lambda x: (x[1]["fecha"], x[0])):
    if inv["fecha"] > COSTEO: continue
    for line in inv["lines"]:
        key = (line["prod"], line["pres"])
        if key not in catalog: continue
        base_qty, base_unit = catalog[key]
        total_base = line["cant"] * base_qty
        if total_base <= 0: continue
        cost_per = line["neto"] / total_base
        product_best[line["prod"]] = (inv["fecha"], inv_id, cost_per, base_unit)

def get_cost_of_ingredient(prod, cantidad, estado):
    _, _, price_per_base, _ = product_best[prod]
    lb, cl = rend.get(prod, (Decimal("1"), Decimal("1")))
    if estado == "bruto":
        bruto = cantidad
    elif estado == "limpio":
        bruto = cantidad / lb
    elif estado == "cocido":
        bruto = (cantidad / cl) / lb
    else:
        raise ValueError(estado)
    return bruto * price_per_base

def calculate_recipe_cost(codigo, visited=None):
    if visited is None: visited = set()
    if codigo in visited: raise ValueError("cycle")
    visited.add(codigo)
    rec = recipes_dict[codigo]
    total = Decimal("0")
    for ing in rec["ingredientes"]:
        if ing["estado"] == "preparado":
            pc = calculate_recipe_cost(ing["producto"], visited.copy())
            pr = Decimal(str(recipes_dict[ing["producto"]]["rendimiento"]))
            total += pc * (Decimal(str(ing["cantidad"])) / pr)
        else:
            total += get_cost_of_ingredient(ing["producto"], Decimal(str(ing["cantidad"])), ing["estado"])
    return total

costs = {}
for i in range(1, 51):
    code = f"P{i:02d}"
    cost = calculate_recipe_cost(code)
    costs[code] = cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

out = Path("/workspace/artifacts/nivel-2/costos.csv")
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["plato", "costo_por_porcion"])
    for i in range(1, 51):
        code = f"P{i:02d}"
        w.writerow([code, f"{costs[code]:.2f}"])

print("Done")
