#!/usr/bin/env python3
"""Nivel 3: costos y márgenes.
- Notas se aplican a partir de su fecha.
- Costo de cada venta/reverso usa el precio vigente a la fecha del movimiento original.
"""
import csv, json, glob, re, sys, os, subprocess
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

def pdf(path):
    t = path[:-4]+'.txt'
    return open(t, encoding='utf-8').read() if os.path.exists(t) else subprocess.run(['pdftotext','-layout',path,'-'],capture_output=True,text=True).stdout

def num(s):
    return float(s.replace('$','').replace('.','').replace(',','.').strip()) if ',' in s else float(s)

DOS = Decimal('0.01')
SEIS = Decimal('0.000001')
def red2(x): return Decimal(str(x)).quantize(DOS, rounding=ROUND_HALF_UP)
def red6(x): return Decimal(str(x)).quantize(SEIS, rounding=ROUND_HALF_UP)

def cargar(n2, n3):
    cat = {(r['producto'], r['presentacion']): float(r['cantidad_base']) for r in csv.DictReader(open(f'{n2}/catalogo.csv', encoding='utf-8'))}
    rend = {r['producto']: (float(r['limpio_sobre_bruto']), float(r['cocido_sobre_limpio'])) for r in csv.DictReader(open(f'{n2}/rendimientos.csv', encoding='utf-8'))}
    rec = {r['codigo']: r for r in json.load(open(f'{n2}/recetas.json', encoding='utf-8'))}
    base = {}
    for f in sorted(glob.glob(f'{n2}/facturas/*.pdf')):
        t = pdf(f); fid = re.search(r'Factura (F-\d+)', t).group(1); fch = re.search(r'Fecha: (\d{4}-\d{2}-\d{2})', t).group(1)
        cols = None
        for line in t.splitlines():
            s = line.strip()
            if s.startswith('R ') and 'Neto' in s: cols = re.split(r'\s{2,}', s); continue
            parts = re.split(r'\s{2,}', s)
            if cols and len(parts)==len(cols) and parts[0].isdigit():
                d = dict(zip(cols, parts)); prod = d['Código / descripción'].split()[0]
                base[(fid, int(d['R']))] = dict(fecha=fch, prod=prod, qty=float(d['Cant.'].replace('.','').replace(',','.'))*cat[(prod, d['Unidad'])], neto=num(d['Neto']))
    notas = []
    for f in sorted(glob.glob(f'{n2}/notas/*.pdf')):
        t = pdf(f); fch = re.search(r'Fecha: (\d{4}-\d{2}-\d{2})', t).group(1)
        fac = re.search(r'Factura asociada: (F-\d+)', t).group(1)
        rg = int(re.search(r'Renglón: (\d+)', t).group(1))
        imp = num(re.search(r'Importe acreditado: \$ ([\d,]+)', t).group(1))
        conc = re.search(r'Concepto: (\S+)', t).group(1).lower()
        dev_qty = 0.0
        if conc.startswith('devol'):
            cd = re.search(r'Cantidad devuelta: ([\d,]+) (\S+)', t)
            dev_qty = float(cd.group(1).replace(',','.')) * cat[(base[(fac, rg)]['prod'], cd.group(2))]
        notas.append((fch, fac, rg, imp, dev_qty))
    for r in csv.DictReader(open(f'{n3}/codigo/compras_ocr.csv', encoding='utf-8')):
        neto = float(r['cantidad'])*float(r['precio'])*(1-float(r['bonif'])/100)
        base[(r['documento'], int(r['renglon']))] = dict(fecha=r['fecha'], prod=r['producto'], qty=float(r['cantidad'])*cat[(r['producto'], r['presentacion'])], neto=neto)
    return cat, rend, rec, base, notas

def get_adjusted(base, notas, fecha):
    adj = {k: dict(v) for k, v in base.items()}
    for fch, fac, rg, imp, dev_qty in notas:
        if fch <= fecha and (fac, rg) in adj:
            adj[(fac, rg)]['neto'] -= imp
            adj[(fac, rg)]['qty'] -= dev_qty
    return adj

def precio(adj, prod, fecha):
    cands = [(k[0], v) for k, v in adj.items() if v['prod']==prod and v['fecha']<=fecha and v['qty']>0]
    if not cands: return 0.0
    best = max(cands, key=lambda x: (x[1]['fecha'], x[0]))
    return best[1]['neto'] / best[1]['qty']

def costo_porcion(codigo, rec, rend, adj, fecha, memo=None):
    if memo is None: memo = {}
    key = (codigo, fecha)
    if key in memo: return memo[key]
    total = 0.0
    for ing in rec[codigo]['ingredientes']:
        p, q, e = ing['producto'], float(ing['cantidad']), ing['estado']
        if e == 'preparado':
            total += (q / float(rec[p]['rendimiento'])) * costo_porcion(p, rec, rend, adj, fecha, memo)
        else:
            pu = precio(adj, p, fecha)
            lb, cl = rend.get(p, (1.0, 1.0))
            bruto = q if e=='bruto' else q/lb if e=='limpio' else q/(lb*cl)
            total += bruto * pu
    memo[key] = total
    return total

def main(n2, n3, out):
    cat, rend, rec, base, notas = cargar(n2, n3)
    adj31 = get_adjusted(base, notas, "2026-10-31")
    with open(f'{out}/costos.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['plato','costo_por_porcion'])
        for i in range(1,51):
            c = f'P{i:02d}'
            w.writerow([c, f'{red2(costo_porcion(c, rec, rend, adj31, "2026-10-31")):.2f}'])
    print('costos.csv escrito')
    articulos = {r['articulo']: r for r in csv.DictReader(open(f'{n3}/caja/articulos.csv', encoding='utf-8'))}
    combos = defaultdict(list)
    for r in csv.DictReader(open(f'{n3}/caja/combos.csv', encoding='utf-8')):
        combos[r['combo']].append((r['plato'], float(r['unidades']), float(r['peso_ingreso'])))
    acc = {f'P{i:02d}': {'u': 0.0, 'ing': 0.0, 'cos': 0.0} for i in range(1,51)}
    orig_fecha = {}
    for month in ['2026-08','2026-09','2026-10']:
        for r in csv.DictReader(open(f'{n3}/caja/{month}.csv', encoding='utf-8')):
            tipo = r['tipo']
            if tipo == 'EXT': continue
            mid = r['id']
            fecha = r['fecha_hora'][:10]
            cant = float(r['cantidad'])
            ingreso = float(r['importe_bruto']) - float(r['descuento'])
            if tipo in ('VTA','COM'):
                orig_fecha[mid] = fecha
            if tipo == 'VTA':
                art = r['articulo']
                if art in articulos and articulos[art]['desde'] <= fecha <= articulos[art]['hasta']:
                    plato = articulos[art]['plato']
                    adj = get_adjusted(base, notas, fecha)
                    cos = cant * costo_porcion(plato, rec, rend, adj, fecha)
                    acc[plato]['u'] += cant
                    acc[plato]['ing'] += ingreso
                    acc[plato]['cos'] += cos
            elif tipo == 'COM':
                combo = r['articulo']
                if combo in combos:
                    adj = get_adjusted(base, notas, fecha)
                    total_peso = sum(p[2] for p in combos[combo])
                    for plato, u, peso in combos[combo]:
                        share = ingreso * (peso / total_peso) if total_peso else 0
                        uc = cant * u
                        cos = uc * costo_porcion(plato, rec, rend, adj, fecha)
                        acc[plato]['u'] += uc
                        acc[plato]['ing'] += share
                        acc[plato]['cos'] += cos
            elif tipo == 'REV':
                ref = r['referencia']
                if ref in orig_fecha:
                    f_orig = orig_fecha[ref]
                    art = r['articulo']
                    if art in articulos and articulos[art]['desde'] <= f_orig <= articulos[art]['hasta']:
                        plato = articulos[art]['plato']
                        adj = get_adjusted(base, notas, f_orig)
                        cos = cant * costo_porcion(plato, rec, rend, adj, f_orig)
                        acc[plato]['u'] -= cant
                        acc[plato]['ing'] -= ingreso
                        acc[plato]['cos'] -= cos
                    elif art in combos:
                        adj = get_adjusted(base, notas, f_orig)
                        total_peso = sum(p[2] for p in combos[art])
                        for plato, u, peso in combos[art]:
                            share = ingreso * (peso / total_peso) if total_peso else 0
                            uc = cant * u
                            cos = uc * costo_porcion(plato, rec, rend, adj, f_orig)
                            acc[plato]['u'] -= uc
                            acc[plato]['ing'] -= share
                            acc[plato]['cos'] -= cos
    with open(f'{out}/margenes.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['plato','unidades_vendidas','ingreso_neto','costo','margen'])
        for i in range(1,51):
            p = f'P{i:02d}'
            a = acc[p]
            u = int(round(a['u']))
            ing = red2(a['ing'])
            cos = red2(a['cos'])
            mar = red6((ing - cos) / ing) if ing else Decimal('0.000000')
            w.writerow([p, u, f'{ing:.2f}', f'{cos:.2f}', f'{mar:.6f}'])
    print('margenes.csv escrito')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
