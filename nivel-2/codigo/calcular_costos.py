#!/usr/bin/env python3
"""
Cálculo de costos de ingredientes por porción — Nivel 2
Fecha de costeo: 2026-10-31
"""
import csv
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

FECHA_COSTEO = "2026-10-31"
BASE = Path(__file__).resolve().parent.parent  # nivel-2/


def parse_decimal(s: str) -> Decimal:
    return Decimal(s.strip().replace(".", "").replace(",", "."))


def cargar_catalogo(path: Path) -> dict:
    catalogo = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["producto"].strip(), row["presentacion"].strip().lower())
            catalogo[key] = (Decimal(row["cantidad_base"]), row["unidad_base"].strip())
    return catalogo


def cargar_rendimientos(path: Path) -> dict:
    rend = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rend[row["producto"].strip()] = (
                Decimal(row["limpio_sobre_bruto"]),
                Decimal(row["cocido_sobre_limpio"]),
            )
    return rend


def extraer_texto_pdf(pdf_path: Path) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        txt = pdf_path.with_suffix(".txt")
        if txt.exists():
            return txt.read_text(encoding="utf-8", errors="replace")
        raise


def parsear_facturas(facturas_dir: Path, catalogo: dict) -> dict:
    invoices = {}
    for pdf in sorted(facturas_dir.glob("F-*.pdf")):
        text = extraer_texto_pdf(pdf)
        inv_id = pdf.stem
        m = re.search(r"Fecha:\s*(\d{4}-\d{2}-\d{2})", text)
        if not m:
            continue
        fecha = m.group(1)
        lines = []
        for raw in text.splitlines():
            line = raw.strip()
            if not re.match(r"^\d+\s+[A-Z]\d{2}\b", line):
                continue
            prod = re.search(r"^\d+\s+([A-Z]\d{2})\b", line).group(1)
            tokens = line.split()
            units = {"g", "kg", "ml", "l", "bolsa", "cajón", "atado", "unidad", "docena", "maple"}
            unit = next((t.lower() for t in tokens if t.lower() in units), None)
            if not unit:
                continue
            num_tokens = [t for t in tokens if re.match(r"^[\d]+(?:[.,]\d+)?$", t)]
            if num_tokens and num_tokens[0].isdigit() and int(num_tokens[0]) < 20:
                num_tokens = num_tokens[1:]
            if len(num_tokens) < 4:
                continue
            cands = [parse_decimal(t) for t in num_tokens[-4:]]
            valid = []
            for ii in range(4):
                for jj in range(4):
                    if ii == jj:
                        continue
                    for kk in range(4):
                        if kk in (ii, jj):
                            continue
                        for mm in range(4):
                            if mm in (ii, jj, kk):
                                continue
                            cant, precio, bonif, neto = cands[ii], cands[jj], cands[kk], cands[mm]
                            if bonif not in (Decimal("0"), Decimal("8"), Decimal("0.00"), Decimal("8.00")):
                                continue
                            expected = (cant * precio * (Decimal("100") - bonif) / Decimal("100")).quantize(Decimal("0.01"))
                            if abs(expected - neto) < Decimal("0.05"):
                                valid.append((cant, precio, bonif, neto))
            if not valid:
                continue
            best, best_score = None, -999
            for cant, precio, bonif, neto in valid:
                key = (prod, unit)
                if key not in catalogo:
                    continue
                base_qty, _ = catalogo[key]
                total_base = cant * base_qty
                if total_base <= 0:
                    continue
                unit_price = neto / total_base
                score = 10 if Decimal("0.001") <= unit_price <= Decimal("1000") else 0
                if unit in ("g", "ml") and cant >= 100:
                    score += 3
                if unit in ("kg", "l", "bolsa", "cajón", "unidad") and precio > 100:
                    score += 2
                if score > best_score:
                    best_score = score
                    best = (cant, precio, bonif, neto)
            if best:
                cant, precio, bonif, neto = best
                lines.append({
                    "prod": prod, "cant": cant, "pres": unit,
                    "precio": precio, "bonif": bonif, "neto": neto,
                    "renglon": len(lines) + 1,
                })
        invoices[inv_id] = {"fecha": fecha, "lines": lines, "id": inv_id}
    return invoices


def aplicar_notas(notas_dir: Path, invoices: dict, catalogo: dict, fecha_corte: str):
    for pdf in sorted(notas_dir.glob("NC-*.pdf")):
        text = extraer_texto_pdf(pdf)
        fecha = re.search(r"Fecha:\s*(\d{4}-\d{2}-\d{2})", text).group(1)
        if fecha > fecha_corte:
            continue
        fac = re.search(r"Factura asociada:\s*(F-\d+)", text).group(1)
        reng = int(re.search(r"Renglón:\s*(\d+)", text).group(1))
        prod = re.search(r"Producto:\s*([A-Z]\d{2})", text).group(1)
        concepto = re.search(r"Concepto:\s*(\w+)", text).group(1).lower()
        cant_dev = parse_decimal(re.search(r"Cantidad devuelta:\s*([\d.,]+)", text).group(1))
        unid_dev = re.search(r"Cantidad devuelta:\s*[\d.,]+\s*(\S+)", text).group(1).lower()
        importe = parse_decimal(re.search(r"Importe acreditado:\s*\$\s*([\d.,]+)", text).group(1))

        inv = invoices.get(fac)
        if not inv or not (1 <= reng <= len(inv["lines"])):
            continue
        line = inv["lines"][reng - 1]
        if line["prod"] != prod:
            continue
        line["neto"] -= importe
        if concepto == "devolución" and cant_dev > 0:
            key = (prod, unid_dev)
            if key in catalogo:
                base_qty_dev, _ = catalogo[key]
                base_qty_line, _ = catalogo[(prod, line["pres"])]
                line["cant"] -= cant_dev * base_qty_dev / base_qty_line
            else:
                line["cant"] -= cant_dev


def seleccionar_precios(invoices: dict, catalogo: dict, fecha_corte: str) -> dict:
    best = {}
    for inv_id, inv in sorted(invoices.items(), key=lambda x: (x[1]["fecha"], x[0])):
        if inv["fecha"] > fecha_corte:
            continue
        for line in inv["lines"]:
            key = (line["prod"], line["pres"])
            if key not in catalogo:
                continue
            base_qty, base_unit = catalogo[key]
            total_base = line["cant"] * base_qty
            if total_base <= 0:
                continue
            cost_per = line["neto"] / total_base
            best[line["prod"]] = (inv["fecha"], inv_id, cost_per, base_unit)
    return best


def costo_receta(codigo: str, recipes: dict, prices: dict, rend: dict, visited=None) -> Decimal:
    if visited is None:
        visited = set()
    if codigo in visited:
        raise ValueError(f"ciclo en {codigo}")
    visited.add(codigo)
    rec = recipes[codigo]
    total = Decimal("0")
    for ing in rec["ingredientes"]:
        prod = ing["producto"]
        cant = Decimal(str(ing["cantidad"]))
        estado = ing["estado"]
        if estado == "preparado":
            sub_cost = costo_receta(prod, recipes, prices, rend, visited.copy())
            sub_rend = Decimal(str(recipes[prod]["rendimiento"]))
            total += sub_cost * (cant / sub_rend)
        else:
            _, _, pu, _ = prices[prod]
            lb, cl = rend.get(prod, (Decimal("1"), Decimal("1")))
            if estado == "bruto":
                bruto = cant
            elif estado == "limpio":
                bruto = cant / lb
            elif estado == "cocido":
                bruto = cant / (lb * cl)
            else:
                raise ValueError(estado)
            total += bruto * pu
    return total


def main():
    catalogo = cargar_catalogo(BASE / "catalogo.csv")
    rend = cargar_rendimientos(BASE / "rendimientos.csv")
    with open(BASE / "recetas.json", encoding="utf-8") as f:
        recipes_list = json.load(f)
    recipes = {r["codigo"]: r for r in recipes_list}

    invoices = parsear_facturas(BASE / "facturas", catalogo)
    aplicar_notas(BASE / "notas", invoices, catalogo, FECHA_COSTEO)
    prices = seleccionar_precios(invoices, catalogo, FECHA_COSTEO)

    out_path = BASE / "costos.csv"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["plato", "costo_por_porcion"])
        for i in range(1, 51):
            code = f"P{i:02d}"
            cost = costo_receta(code, recipes, prices, rend)
            rounded = cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            w.writerow([code, f"{rounded:.2f}"])
    print(f"Escrito {out_path}")


if __name__ == "__main__":
    main()
