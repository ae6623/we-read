import re
from collections import Counter

t = open('index.html', encoding='utf-8').read()
links = re.findall(r'href="([^"]*outline\.html)"', t)
print("总 outline 链接数:", len(links))

def ctx(h):
    i = t.find('href="' + h + '"')
    pre = t[max(0, i-50):i]
    m = re.search(r'class="([^"]+)"[^>]*>\s*$', pre)
    return (m.group(1) if m else pre[-30:]).strip()

c = Counter(ctx(h) for h in links)
print("\n按前导 class/文字 分类:")
for k, v in c.most_common(15):
    print(f"  {v:3}  {k}")

print("\n样例 href:", links[:3])

# 定位每个 outline 链接所在的容器容器链
print("\n各 outline 链接所在容器（向上最近标记）:")
containers = Counter()
for m in re.finditer(r'href="([^"]*outline\.html)"', t):
    i = m.start()
    seg = t[max(0, i-400):i]
    found = re.findall(r'(set-group|unit-card|archive-grid|reading-panel|set-units-grid|book-entry|entry-links|card-title-link|series-|archive-card)', seg)
    key = ' > '.join(found[-3:]) if found else '(none)'
    containers[key] += 1
for k, v in containers.most_common(15):
    print(f"  {v:3}  {k}")
