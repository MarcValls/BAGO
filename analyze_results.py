import csv
rows = list(csv.DictReader(open('results.csv', newline='', encoding='utf-8')))
print('Total comandos testeados:', len(rows))
print()

core = [r for r in rows if r.get('stability') == 'core']
dang = [r for r in rows if r.get('stability') == 'dangerous']
exp = [r for r in rows if r.get('stability') == 'experimental']
leg = [r for r in rows if r.get('stability') == 'legacy']
inte = [r for r in rows if r.get('stability') == 'internal']

def report(group, name):
    ok = sum(1 for r in group if int(r['code']) == 0)
    bad = [r for r in group if int(r['code']) != 0]
    print('=== ' + name + ' (' + str(len(group)) + ' comandos) ===')
    print('  OK: ' + str(ok) + '/' + str(len(group)))
    for r in bad:
        print('  KO: ' + r['cmd'] + ' -> exit ' + r['code'] + ' (' + r['ms'] + 'ms)')
    print()

report(core, 'CORE')
report(dang, 'DANGEROUS')
report(exp, 'EXPERIMENTAL')
report(leg, 'LEGACY')
report(inte, 'INTERNAL')

from collections import Counter
codes = Counter(int(r['code']) for r in rows)
print('=== DISTRIBUCION DE EXIT CODES ===')
for c, n in sorted(codes.items()):
    label = {0:'OK', -1:'TIMEOUT', 1:'ERROR/USO', 2:'ARG ERROR'}.get(c, 'CODE ' + str(c))
    print('  ' + label + ': ' + str(n))
