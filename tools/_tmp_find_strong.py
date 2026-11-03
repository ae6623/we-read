import re
from collections import Counter

t = open('index.html', encoding='utf-8').read()

# 1) card-link-strong 出现在哪些容器
cont_c = Counter()
for m in re.finditer(r'class="card-link card-link-strong"', t):
    seg = t[max(0, m.start()-220):m.start()]
    found = re.findall(r'(archive-card|unit-card|reading-panel|archive-grid|set-group|book-entry|set-units-grid)', seg)
    cont_c[' > '.join(found[-2:]) if found else '(none)'] += 1
print("card-link-strong 容器分布:")
for k, v in cont_c.most_common():
    print(f"  {v:3}  {k}")

# 2) 它的 href 都是 outline 吗？
hrefs = re.findall(r'<a class="card-link card-link-strong" href="([^"]+)"', t)
print("\ncard-link-strong href 统计:")
print("  outline:", sum('outline' in h for h in hrefs), " combined:", sum('combined' in h for h in hrefs), " 其他:", sum('outline' not in h and 'combined' not in h for h in hrefs))

# 3) 找它所在的 article class（看是 archive-card 还是 unit-card）
art_c = Counter()
for m in re.finditer(r'class="card-link card-link-strong"', t):
    seg = t[max(0, m.start()-400):m.start()]
    am = re.findall(r'<article class="([^"]+)"', seg)
    art_c[am[-1] if am else '(none)'] += 1
print("\ncard-link-strong 所属 article:", dict(art_c))

# 4) 构建脚本里搜 card-link
print("\n搜索 tools/ 里 card-link 生成:")
