# 修正：调查钩子要插在函数声明区之后（// Implementation 之后）
import io

p = 'work/blackhand/CustomLogic.galaxy'
s = io.open(p, encoding='utf-8').read()

hooks = [
    'void gf_SKF_1_fushou (int lv_a) {',
    'void gf_SKF_1_jingzhang (int lv_a) {',
    'void gf_SKF_1_guanchazhe (int lv_a) {',
    'void gf_SKF_1_tanyuan (int lv_a) {',
    'void gf_SKF_1_lianbangtanyuan (int lv_a) {',
    'void gf_SKF_1_jiandie (int lv_a) {',
    'void gf_SKF_1_zhentan (int lv_a) {',
    'void gf_SKF_1_jianshizhe (int lv_a) {',
]

for h in hooks:
    # 先撤销插在 { 后面的调用
    s = s.replace(h + '\n    gf_BPEventLook(lv_a);', h, 1)
    # 再插到 // Implementation 之后
    i = s.index(h)
    j = s.find('// Implementation\n', i)
    assert j != -1, h
    j += len('// Implementation\n')
    s = s[:j] + '    gf_BPEventLook(lv_a);\n' + s[j:]

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('hooks repositioned')
