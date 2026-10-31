import json
import io

p = r"I:\大肥鱼\外部项目\blackhand-rewrite-main\work\roles-list.json"
d = json.load(io.open(p, encoding="utf-8"))
print("顶层键:", list(d.keys()))
print("字段说明:", str(d.get("字段"))[:300])
sec = d["sections"]
print("段数:", len(sec))
for s in sec[:2]:
    print(" 段键:", {k: (v if not isinstance(v, list) else "list[%d]" % len(v)) for k, v in s.items()})
    for k, v in s.items():
        if isinstance(v, list) and v:
            print("   ", k, "首条:", json.dumps(v[0], ensure_ascii=False)[:220])
