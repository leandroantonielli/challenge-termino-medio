#!/usr/bin/env python3
"""Nivel 3: costos al 31/10/2026 y márgenes del trimestre.
Uso: python3 costeo3.py <datos_nivel2> <datos_nivel3> <salida_dir>
Compras = facturas PDF del nivel 2 + notas NC + compras_ocr.csv (transcripción de facturas/ y tickets/ del nivel 3)."""
import csv, json, glob, re, sys, os, subprocess
from decimal import Decimal, ROUND_HALF_UP

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
    # facturas nivel 2
    renglones = {}
    for f in sorted(glob.glob(f'{n2}/facturas/*.pdf')):
        t = pdf(f); fid = re.search(r'Factura (F-\d+)', t).group(1); fch = re.search(r'Fecha: (\d{4}-\d{2}-\d{2})', t).group(1)
        cols = None
        for line in t.splitlines():
            s = line.strip()
            if s.startswith('R ') and 'Neto' in s: cols = re.split(r'\s{2,}', s); continue
            parts = re.split(r'\s{2,}', s)
            if cols and len(parts)==len(cols) and parts[0].isdigit():
                d = dict(zip(cols, parts)); prod = d['Código / descripción'].split()[0]
                renglones[(fid, int(d['R']))] = dict(fecha=fch, prod=prod, qty=float(d['Cant.'].replace('.','').replace(',','.'))*cat[(prod, d['Unidad'])], neto=num(d['Neto']))
    # notas
    for f in sorted(glob.glob(f'{n2}/notas/*.pdf')):
        t = pdf(f); fch = re.search(r'Fecha: (\d{4}-\d{2}-\d{2})', t).group(1)
        fac = re.search(r'Factura asociada: (F-\d+)', t).group(1); rg = int(re.search(r'Renglón: (\d+)', t).group(1))
        imp = num(re.search(r'Importe acreditado: \$ ([\d,]+)', t).group(1))
        it = renglones[(fac, rg)]; it['neto'] -= imp
        if re.search(r'Concepto: (\S+)', t).group(1).lower().startswith('devol'):
            cd = re.search(r'Cantidad devuelta: ([\d,]+) (\S+)', t); it['qty'] -= float(cd.group(1).replace(',','.'))*cat[(it['prod'], cd.group(2))]
    # compras OCR
    for r in csv.DictReader(open(f'{n3}/codigo/compras_ocr.csv', encoding='utf-8')):
        neto = float(r['cantidad'])*float(r['precio'])*(1-float(r['bonif'])/100)
        renglones[(r['documento'], int(r['renglon']))] = dict(fecha=r['fecha'], prod=r['producto'], qty=float(r['cantidad'])*cat[(r['producto'], r['presentacion'])], neto=neto)
    return cat, rend, rec, renglones

def precio(renglones, prod, fecha):
    cands = [(k[0], v) for k, v in renglones.items() if v['prod']==prod and v['fecha']<=fecha and v['qty']>0]
    if not cands: return 0
    return max(cands, key=lambda x: (x[1]['fecha'], x[0]))[1]['neto'] / max(cands, key=lambda x: (x[1]['fecha'], x[0]))[1]['qty']

def costo_rec(codigo, rec, rend, renglones, fecha, memo=None):
    if memo is None: memo = {}
    key = (codigo, fecha)
    if key in memo: return memo[key]
    total = 0.0
    for ing in rec[codigo]['ingredientes']:
        p, q, e = ing['producto'], float(ing['cantidad']), ing['estado']
        if e == 'preparado':
            total += (q / float(rec[p]['rendimiento'])) * costo_rec(p, rec, rend, renglones, fecha, memo)
        else:
            pu = precio(renglones, p, fecha)
            lb, cl = rend.get(p, (1.0, 1.0))
            bruto = q if e=='bruto' else q/lb if e=='limpio' else q/(lb*cl)
            total += bruto * pu
    memo[key] = total
    return total

def main(n2, n3, out):
    cat, rend, rec, renglones = cargar(n2, n3)
    # costos al 31/10
    with open(f'{out}/costos.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['plato','costo_por_porcion'])
        for i in range(1,51):
            c = f'P{i:02d}'
            w.writerow([c, f'{red2(costo_rec(c, rec, rend, renglones, "2026-10-31")):.2f}'])
    print('costos.csv escrito')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
