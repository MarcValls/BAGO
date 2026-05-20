import sys, json
from collections import Counter
d = json.load(sys.stdin)
tree = d.get('tree', [])
c = Counter()
for item in tree:
    if item['type'] == 'blob':
        ext = item['path'].split('.')[-1].lower() if '.' in item['path'] else 'none'
        c[ext] += 1
        c['total'] += 1
        c['size'] += item.get('size', 0)
print('REPO ANTIGUO (bago-framework):')
print('  Total archivos: ' + str(c['total']))
print('  Python (.py): ' + str(c.get('py', 0)))
print('  Markdown (.md): ' + str(c.get('md', 0)))
print('  JSON (.json): ' + str(c.get('json', 0)))
print('  Tamaño total: {:.1f} MB'.format(c['size'] / 1024 / 1024))
