import io, re

p = 'work/blackhand/strings-bp.txt'
s = io.open(p, encoding='utf-8').read()

s = re.sub(r'^Param/Value/MRDESC=.*$',
           'Param/Value/MRDESC=可能是饭店老板、流动摊贩、报纸店老板。',
           s, count=1, flags=re.M)

s = re.sub(r'^Param/Value/BPCMDOK=.*$',
           'Param/Value/BPCMDOK=<s val="ModLeftSize16"><c val="00FF00">孩子们，报纸店开张啦，输入\'-paper\'获取最新消息。</c></s>',
           s, count=1, flags=re.M)

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('texts updated')
