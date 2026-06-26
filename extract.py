import csv, re

rows = list(csv.reader(open('out.csv', encoding='utf-8')))

def num(x):
    x = (x or '').strip()
    if x in ('', '<не заполнен>'):
        return None
    try:
        return float(x)
    except:
        return None

# find columns: number col, inn col, name col, total col, overdue col
# Based on inspection: col1=number, col5=INN, col11=name, col19=total, col23=overdue
debitor = []  # (num, inn, name, total, overdue)
kreditor = []
section = None
for r in rows:
    # pad
    r = r + ['']*(30-len(r))
    n = r[1].strip()
    if n.startswith('2.1.') or n.startswith('2.2.'):
        section = 'D'
    elif n.startswith('3.1.'):
        section = 'K'
    else:
        # detect headers
        if 'ДЕБИТОРЛИК ҚАРЗ' in (r[1] or ''):
            section = 'D'
        if 'КРЕДИТОРЛИК ҚАРЗ' in (r[1] or ''):
            section = 'K'
    # data row?
    m = re.match(r'^(2\.1\.\d+|2\.2\.\d+|3\.1\.\d+)$', n)
    if not m:
        continue
    inn = r[5].strip()
    name = r[11].strip()
    total = r[19].strip()
    overdue = r[23].strip()
    rec = (n, inn, name, total, overdue)
    if n.startswith('3.'):
        kreditor.append(rec)
    else:
        debitor.append(rec)

print('Debitor count:', len(debitor))
print('Kreditor count:', len(kreditor))

def norm_name(s):
    s = s.strip().strip('"').strip()
    s = re.sub(r'\s+', ' ', s).upper()
    s = s.replace('`', "'").replace('’', "'").replace('‘', "'")
    return s

def key(rec):
    inn = rec[1]
    if inn and inn != '<не заполнен>' and re.match(r'^\d+$', inn):
        return ('inn', inn)
    return ('name', norm_name(rec[2]))

dindex = {}
for rec in debitor:
    dindex.setdefault(key(rec), []).append(rec)

matches = []
seen = set()
for krec in kreditor:
    k = key(krec)
    if k in dindex:
        for drec in dindex[k]:
            matches.append((drec, krec))

print('\n=== MATCHES (present in BOTH debitor & kreditor) ===')
print('count:', len(matches))
for i,(d,k) in enumerate(matches,1):
    inn = d[1] if (d[1] and d[1]!='<не заполнен>') else k[1]
    name = d[2] or k[2]
    print(f'{i}\tINN={inn}\tD#{d[0]}={d[3]}\tK#{k[0]}={k[3]}\t{name}')

def clean(s):
    return (s or '').replace('ЋЋЋ', 'ООО').replace('€Џ', '').strip()

# write a clean csv of matches (UTF-8 BOM so Excel opens Cyrillic correctly)
with open('debitor_kreditor_umumiy.csv','w',encoding='utf-8-sig',newline='') as f:
    w = csv.writer(f)
    w.writerow(['№','СТИР/ИНН','Номи / Наименование',
                'Дебиторлик қарзи (жами)','Кредиторлик қарзи (жами)'])
    for i,(d,k) in enumerate(matches,1):
        inn = d[1] if (d[1] and d[1]!='<не заполнен>') else (k[1] if k[1] and k[1]!='<не заполнен>' else '—')
        name = clean(d[2] or k[2])
        w.writerow([i, inn, name, d[3], k[3]])
print('\nwrote debitor_kreditor_umumiy.csv')

# also print a markdown table
print('\n=== MARKDOWN ===')
print('| № | СТИР/ИНН | Номи / Наименование | Дебитор (жами) | Кредитор (жами) |')
print('|---|----------|---------------------|----------------|-----------------|')
for i,(d,k) in enumerate(matches,1):
    inn = d[1] if (d[1] and d[1]!='<не заполнен>') else (k[1] if k[1] and k[1]!='<не заполнен>' else '—')
    name = clean(d[2] or k[2]).replace('|','/')
    print(f'| {i} | {inn} | {name} | {d[3]} | {k[3]} |')
