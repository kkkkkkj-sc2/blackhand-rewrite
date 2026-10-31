import json
import io

P = r"I:\大肥鱼\外部项目\blackhand-rewrite-main\work\roles-list.json"
d = json.load(io.open(P, encoding="utf-8"))

sec = d["sections"]
# 找城镇、变体含 1 的那一段（主教所在的段）
target = None
for s in sec:
    if s.get("category") == 1 and 1 in (s.get("variants") or []) and len(s.get("entries") or []) > 30:
        target = s
        break
assert target, "没找到城镇主段"

entries = target["entries"]
roles = [e["role"] for e in entries]
print("该段现有角色号:", roles[-6:], "共", len(roles))
assert 36 not in roles, "36 已经在列表里了"

# 沿用同段邻居的前后缀键
last = entries[-1]
print("邻居:", last)
entries.append({"role": 36, "prefix": last["prefix"], "suffix": last["suffix"]})

json.dump(d, io.open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("已追加 1/36，新的末条:", entries[-1], "共", len(entries), "条")
