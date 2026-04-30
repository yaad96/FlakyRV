with open('/tmp/compare-traces-official.py', 'r') as f:
    src = f.read()

old = "                locations[id] = code[:code.index(')') + 1]"
new = "                if code and ')' in code and id.isdigit():\n                    locations[id] = code[:code.index(')') + 1]"
src = src.replace(old, new)

with open('/tmp/compare-traces-official.py', 'w') as f:
    f.write(src)

print('patched OK')
