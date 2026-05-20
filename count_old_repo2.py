import sys, json
from collections import Counter
d = json.load(sys.stdin)
tree = d.get('tree', [])

paths = [item['path'] for item in tree if item['type'] == 'blob']

dirs = Counter()
for p in paths:
    parts = p.split('/')
    if len(parts) > 1:
        dirs[parts[0]] += 1
    else:
        dirs['(root)'] += 1

print('Estructura repo antiguo (top-level):')
for d, n in dirs.most_common(15):
    print('  ' + d + ': ' + str(n) + ' archivos')

# Tools en .bago/tools
tools = [p for p in paths if p.startswith('.bago/tools/')]
print()
print('Tools en .bago/tools: ' + str(len(tools)))

# Workflows
workflows = [p for p in paths if 'workflow' in p.lower() and p.endswith('.md')]
print('Workflows .md: ' + str(len(workflows)))

# Agents / roles
agents = [p for p in paths if 'agent' in p.lower() and p.endswith('.md')]
print('Agent docs .md: ' + str(len(agents)))

roles = [p for p in paths if 'role' in p.lower() and p.endswith('.md')]
print('Role docs .md: ' + str(len(roles)))
