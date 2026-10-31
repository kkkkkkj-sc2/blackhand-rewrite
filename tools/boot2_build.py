#!/usr/bin/env python3
"""boot2 系（黑手：升温）生产打包 —— 一套命令出正式图，避免再漏件。

打包五件套（shw141 事故沉淀：少了文案那件 → 界面全是 Param/Value/XXX 原始键；
shw154 事故沉淀：少了样式表那件 → 名字里的斜体标签找不到样式定义 → 不斜体）：

  1. 复制基线地图（默认 work/boot2-user.SC2Map，含用户的变体修改，不要覆盖它）
  2. 直写 CustomLogic.galaxy（工作区脚本）
  3. 合并样式表（work/blackhand/NewFontStyles.SC2Style → 包内同名成员，按 Style name 增量并入；
     缺它 = `<i>` 名字经 gf_BHItalicize 改写成 `<s val="ModItalic">` 后无样式可查 → 不渲染斜体）
  4. 合并自加 GameStrings（work/blackhand/strings-*.txt → zhCN.SC2Data\\LocalizedData\\GameStrings.txt）
  5. 写回 BankList.xml（tools/banklist_fix.py；缺它 = BankLoad 永远读空 → 每局清档）
  6. 补丁说明 + 加载页面（tools/bh_meta.py 读 work/blackhand/patch-notes.txt，可重复执行）

**不要用 tools/sc2pack.py**（boot2 系会剥触发器，shw96 事故）。

用法：
    python3 tools/boot2_build.py --out work/boot2-shw141.SC2Map
    python3 tools/boot2_build.py --out work/boot2-shw141-solo.SC2Map --solo
    # --solo 测试包把 CA 三件改成编辑器口径的纯本地路径 file:Mods\…；
    # 发布包（默认、release.py）保持原图纯 bnet 依赖。
    python3 tools/boot2_build.py --out work/boot2-xxx.SC2Map --strings-only-preview
    python3 tools/boot2_build.py --out work/boot2-shw141.SC2Map --base work/boot2-shw136.SC2Map

退出码：0 = 成功（含全部回读断言），1 = 任一步失败（不会留下半个包）。
"""
from __future__ import annotations

import argparse
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

import bh_deps  # noqa: E402
import bh_meta  # noqa: E402
import sc2map  # noqa: E402

ZH_STRINGS = r'zhCN.SC2Data\LocalizedData\GameStrings.txt'
# 其余中文语种成员：客户端只读 zhCN，但发布出去的整包会被平台审核逐成员扫描
# （实测 zhCH 里残留原图自带的「杀」×6、「邪」×1），所以一并过和谐词表。
OTHER_CN_STRINGS = [
    r'zhCH.SC2Data\LocalizedData\GameStrings.txt',
    r'zhCH.SC2Data\LocalizedData\ObjectStrings.txt',
    r'zhCH.SC2Data\LocalizedData\TriggerStrings.txt',
    r'zhCH.SC2Data\LocalizedData\GameHotkeys.txt',
    r'zhCN.SC2Data\LocalizedData\ObjectStrings.txt',
    r'zhCN.SC2Data\LocalizedData\TriggerStrings.txt',
    r'zhCN.SC2Data\LocalizedData\GameHotkeys.txt',
]
DEFAULT_BASE = ROOT / 'work' / 'boot2-user.SC2Map'
DEFAULT_GALAXY = ROOT / 'work' / 'blackhand' / 'CustomLogic.galaxy'
STRINGS_GLOB = 'work/blackhand/strings-*.txt'
NOTES_SRC = ROOT / 'work' / 'blackhand' / 'patch-notes.txt'
DESC_SRC = ROOT / 'work' / 'blackhand' / 'desc-long.txt'

# 样式表（斜体等自定义 GameText 样式的定义处）：按 Style name 增量并入包内同名成员
STYLE_MEMBER = 'NewFontStyles.SC2Style'
STYLE_SRC = ROOT / 'work' / 'blackhand' / 'NewFontStyles.SC2Style'
STYLE_NAME_RE = re.compile(r'<Style\s+name="([^"]+)"')
STYLE_ELEM_RE = re.compile(r'<Style\s+[^>]*?/>')
# 字体相关：<Constant name= val= /> 与 <FontGroup name= >…</FontGroup>（shw159）
TAG_ELEM_RE = re.compile(r'<(Style|Constant)\s+[^>]*?/>')
GROUP_ELEM_RE = re.compile(r'<FontGroup\s+name="([^"]+)"\s*>.*?</FontGroup>', re.S)
ELEM_NAME_RE = re.compile(r'name="([^"]+)"')

# 地图内置字体：包内成员路径 ← work/blackhand/fonts/ 下的文件（OFL，许可文本一起分发）
FONT_DIR = ROOT / 'work' / 'blackhand' / 'fonts'
FONTS = [
    (r'Fonts\BH-Serif-Italic.ttf', 'BH-Serif-Italic.ttf'),
    (r'Fonts\Lora-OFL.txt', 'Lora-OFL.txt'),
    (r'Fonts\BH-CJK-Italic.ttf', 'BH-CJK-Italic.ttf'),
    (r'Fonts\NotoSansCJK-OFL.txt', 'NotoSansCJK-OFL.txt'),
]


def put(archive, name, data):
    """写成员；与包内已有内容完全一致就跳过（MPQ 每次写都是追加、旧数据不回收）。"""
    try:
        if sc2map.read(archive, name) == data:
            print(f"   跳过（内容相同）{name}")
            return False
    except Exception:
        pass

    sc2map.write(archive, name, data)

    return True


def write_fonts(archive: Path) -> list[str]:
    """把地图自带字体写进包内 Fonts\\；缺文件或回读不一致直接抛错。"""
    done = []
    for member, name in FONTS:
        src = FONT_DIR / name
        assert src.exists(), f'字体源文件不存在: {src}'
        data = src.read_bytes()
        put(archive, member, data)
        assert sc2map.read(archive, member) == data, f'字体回读不一致: {member}'
        done.append(member)
    return done


# 地图根目录贴图（自加胜利图）：包内成员名 ← data/ 下的文件
# shw169：shw98 加的两张胜利图只手工塞进当次产物，shw100 起每版都丢（结算画面按图名找不到贴图）
DDS_DIR = ROOT / 'data'
DDS_ASSETS = [
    ('WinCorruptInquisitor.dds', 'WinCorruptInquisitor.dds'),
    ('WinShadow.dds', 'WinShadow.dds'),
    ('WinChosen.dds', 'WinChosen.dds'),
    ('WinDemagogue.dds', 'WinDemagogue.dds'),
    ('WinRipper.dds', 'WinRipper.dds'),
    ('WinGanranzhe.dds', 'WinGanranzhe.dds'),
    ('WinYanluo.dds', 'WinYanluo.dds'),
    ('WinEgun.dds', 'WinEgun.dds'),
]
# 街机封面：DocumentInfo 的 Screenshot=Preview.dds。基线缺这张图，所以战网没有缩略图。
# 列表小图标仍用原图 Mafia Icon.dds，不要覆盖。源 PNG 用 tools/png2cover.py 出 Preview DDS。
COVER_DEFAULT = 'Cover1'


def write_dds(archive: Path) -> list[str]:
    """把自加贴图写进包内根目录；缺文件或回读不一致直接抛错。"""
    done = []
    for member, name in DDS_ASSETS:
        src = DDS_DIR / name
        assert src.exists(), f'贴图源文件不存在: {src}'
        data = src.read_bytes()
        put(archive, member, data)
        assert sc2map.read(archive, member) == data, f'贴图回读不一致: {member}'
        done.append(member)
    return done


SOUND_DATA = r'Base.SC2Data\GameData\SoundData.xml'
LAUGH_SOUND = """    <CSound id="BHLaugh">
        <AssetArray File="Assets\\Sounds\\BHLaugh.ogg"/>
        <Category value="Dialogue"/>
        <Mode value="2D"/>
        <LoopCount value="0"/>
        <Volume value="0.000000,0.000000"/>
        <DupeDestroyCount value="8"/>
        <DupeMuteCount value="8"/>
    </CSound>
"""
# shw263 夜曲：挂在游戏自带 MUSIC 父类下（与原图 GameMusicTerr22* 一致），循环到天亮被停
NIGHT_SOUND = """    <CSound id="BHNightMusic" parent="MUSIC">
        <AssetArray File="Assets\\Sounds\\BHNightMusic.ogg" LoopCount="-1" FacialGroup=""/>
    </CSound>
"""


def dialogue_csound(sid: str, filename: str) -> str:
    """2D 对白，属性抄 BHLaugh。响度由 SoundPlay 决定，这里不加增益。"""
    return (
        f'    <CSound id="{sid}">\n'
        f'        <AssetArray File="Assets\\Sounds\\{filename}"/>\n'
        f'        <Category value="Dialogue"/>\n'
        f'        <Mode value="2D"/>\n'
        f'        <LoopCount value="0"/>\n'
        f'        <Volume value="0.000000,0.000000"/>\n'
        f'        <DupeDestroyCount value="8"/>\n'
        f'        <DupeMuteCount value="8"/>\n'
        f'    </CSound>\n'
    )


# 精神病患者连杀播报。超过五次仍播第五条，故只登记 1–5。
JS_STREAK_SOUNDS = [
    ('BHJSKill1', 'BHJSKill1.ogg'),
    ('BHJSKill2', 'BHJSKill2.ogg'),
    ('BHJSKill3', 'BHJSKill3.ogg'),
    ('BHJSKill4', 'BHJSKill4.ogg'),
    ('BHJSKill5', 'BHJSKill5.ogg'),
]

# 自加音效：(CSound id, 源文件, 包内成员, CSound 片段)
# 一趟写完 SoundData —— MPQ 每次写成员都是追加、旧数据不回收，同一成员一次构建只能写一次。
CUSTOM_SOUNDS = [
    ('BHLaugh', DDS_DIR / 'BHLaugh.ogg', r'Assets\Sounds\BHLaugh.ogg', LAUGH_SOUND),
    ('BHNightMusic', DDS_DIR / 'BHNightMusic.ogg', r'Assets\Sounds\BHNightMusic.ogg', NIGHT_SOUND),
    # 裁决者：原创合成破门/纸张/窒息闷响；2D 单次，不借雷击或爆炸音效。
    ('BHCJExecution', DDS_DIR / 'BHCJExecution.ogg', r'Assets\Sounds\BHCJExecution.ogg',
     dialogue_csound('BHCJExecution', 'BHCJExecution.ogg')),
    *[
        (sid, DDS_DIR / filename, rf'Assets\Sounds\{filename}', dialogue_csound(sid, filename))
        for sid, filename in JS_STREAK_SOUNDS
    ],
]

MODEL_DATA = r'Base.SC2Data\GameData\ModelData.xml'
# 奶龙只进模型表，不新建单位或 Actor。贴图路径必须与 M3 内嵌路径一致。
NAILONG_MODEL = """    <CModel id="Nailong" parent="Unit">
        <Model value="Assets\\Units\\Nailong\\Nailong.m3"/>
        <Occlusion value="Show"/>
    </CModel>
"""
# 隐藏外观「2D 立牌」（默认外观仍是奶龙，脚本聊天输入 mon3tr / reed 切换，见 CustomLogic
# 的 gt_BHMon3tr / gt_BHReed；走路段的帧来自同一立绘的基建小人）。每套两张：正常 + 镜像
# （镜像那张 = 朝左走时用，脚本按 UnitGetFacing 换模型）。素材仅本地自用。
def _hidden_model_block(cid: str, member: str) -> str:
    """CModel 片段。

    **成员路径原样写**（单反斜杠）：SC2 的 ModelData `value` 不认双反斜杠转义，
    写成 Assets\\Units\\... 会让引擎找不到模型 ⇒ 单位显示棋盘格 fallback 占位
    （2026-10-22 事故：给苇草加模型时顺手加了转义，结果 mon3tr 也跟着坏）。
    """
    return ('    <CModel id="' + cid + '" parent="Unit">\n'
            '         <Model value="' + member + '"/>\n'
            '         <Occlusion value="Show"/>\n'
            '    </CModel>\n')


HIDDEN_SPRITES = [
    # (模型 id, m3 源, 包内 m3 成员, 贴图源, 包内贴图成员)
    ('BHMon3tr', DDS_DIR / 'BHSprite.m3', r'Assets\Units\BHSprite2D\BHSprite2D.m3',
     DDS_DIR / 'BHMonstrBoc.dds', r'Assets\Textures\BHMonstrBoc.dds'),
    ('BHMon3trL', DDS_DIR / 'BHSpriteL.m3', r'Assets\Units\BHSpriteL\BHSpriteL.m3',
     DDS_DIR / 'BHMonstrBocL.dds', r'Assets\Textures\BHMonstrBocL.dds'),
    ('BHReed', DDS_DIR / 'BHSpriteReed.m3', r'Assets\Units\BHSpriteReed2D\BHSpriteReed2D.m3',
     DDS_DIR / 'BHReed.dds', r'Assets\Textures\BHReed.dds'),
    ('BHReedL', DDS_DIR / 'BHSpriteReedL.m3', r'Assets\Units\BHSpriteReed2D_L\BHSpriteReed2D_L.m3',
     DDS_DIR / 'BHReedL.dds', r'Assets\Textures\BHReedL.dds'),
    ('BHNight', DDS_DIR / 'BHSpriteNight.m3', r'Assets\Units\BHSpriteNight2D\BHSpriteNight2D.m3',
     DDS_DIR / 'BHNightingale.dds', r'Assets\Textures\BHNightingale.dds'),
    ('BHNightL', DDS_DIR / 'BHSpriteNightL.m3', r'Assets\Units\BHSpriteNight2D_L\BHSpriteNight2D_L.m3',
     DDS_DIR / 'BHNightingaleL.dds', r'Assets\Textures\BHNightingaleL.dds'),
]
HIDDEN_MODELS = [
    (cid, m3, member, tex, texm, _hidden_model_block(cid, member))
    for cid, m3, member, tex, texm in HIDDEN_SPRITES
]
# 奶龙已从源工程按 -Y 前向、+Z 向上整份重导出；GAME 只施加贴地平移，不加 Z 旋转。
# Stand 为 4 秒循环，Walk 保留。不要再叠加历史 Origin -90° 补丁或旋转 IREF；见 docs/NAILONG-MODEL.md。
NAILONG_MODELS = [
    ('Nailong', DDS_DIR / 'Nailong.m3', r'Assets\Units\Nailong\Nailong.m3',
     DDS_DIR / 'Nailong_Diffuse.dds', r'Assets\Textures\Nailong_Diffuse.dds', NAILONG_MODEL),
]
CUSTOM_MODELS = NAILONG_MODELS + HIDDEN_MODELS  # 奶龙（默认外观）+ 隐藏的 2D 立牌



def write_sounds(archive: Path) -> list[str]:
    """把自加音效打进地图，并在 SoundData 里登记对应 CSound。"""
    xml = sc2map.read(archive, SOUND_DATA).decode('utf-8')
    members = []
    added = []
    for sid, src, member, _ in CUSTOM_SOUNDS:
        assert src.exists(), f'音效源文件不存在: {src}'
        data = src.read_bytes()
        put(archive, member, data)
        assert sc2map.read(archive, member) == data, f'音效回读不一致: {member}'
        members.append(member)
        if f'id="{sid}"' not in xml:
            added.append(sid)

    if added:
        assert xml.rstrip().endswith('</Catalog>'), 'SoundData 结尾不是 </Catalog>'
        blocks = ''.join(b for sid, _, _, b in CUSTOM_SOUNDS if sid in added)
        xml = xml.rstrip()[: -len('</Catalog>')] + blocks + '</Catalog>\n'
        put(archive, SOUND_DATA, xml.encode('utf-8'))
        xml = sc2map.read(archive, SOUND_DATA).decode('utf-8')

    for sid, _, _, _ in CUSTOM_SOUNDS:
        assert f'id="{sid}"' in xml, f'SoundData 没有 {sid}'

    return members


def write_models(archive: Path, models: list | None = None) -> list[str]:
    """把自加模型打进地图，并在 ModelData 里登记对应 CModel。"""
    models = CUSTOM_MODELS if models is None else models
    xml = sc2map.read(archive, MODEL_DATA).decode('utf-8')
    members = []
    added = []
    for mid, m3, m3member, tex, texmember, _ in models:
        for src, member in ((m3, m3member), (tex, texmember)):
            assert src.exists(), f'模型源文件不存在: {src}'
            data = src.read_bytes()
            put(archive, member, data)
            assert sc2map.read(archive, member) == data, f'模型回读不一致: {member}'
            members.append(member)

        if f'id="{mid}"' not in xml:
            added.append(mid)

    if added:
        assert xml.rstrip().endswith('</Catalog>'), 'ModelData 结尾不是 </Catalog>'
        blocks = ''.join(b for mid, _, _, _, _, b in models if mid in added)
        xml = xml.rstrip()[: -len('</Catalog>')] + blocks + '</Catalog>\n'
        put(archive, MODEL_DATA, xml.encode('utf-8'))
        xml = sc2map.read(archive, MODEL_DATA).decode('utf-8')

    for mid, _, m3member, _, texmember, _ in models:
        assert f'id="{mid}"' in xml, f'ModelData 没有 {mid}'
        assert m3member in xml, f'{mid} 的模型路径没写进 ModelData（或写成了双反斜杠转义）'

    return members


def write_cover(archive: Path, stem: str) -> list[str]:
    """只写入 Preview.dds（街机缩略图）。Mafia Icon.dds 保持原图。"""
    preview = DDS_DIR / f'{stem}-Preview.dds'
    assert preview.exists(), f'封面 Preview 不存在: {preview}（先跑 python3 tools/png2cover.py data/{stem}.png）'
    data = preview.read_bytes()
    put(archive, 'Preview.dds', data)
    assert sc2map.read(archive, 'Preview.dds') == data, '封面回读不一致: Preview.dds'
    return ['Preview.dds']

# 必须在包内 zhCN 表里能查到的自加键（缺任一 → 界面会显示原始键名）
MUST_HAVE_KEYS = [
  # shw321: passerby professions, private objectives, public announcements and skills.
  'Param/Value/GKTYPE',
  'Param/Value/GKCOMMON',
  'Param/Value/GKWINTEAM',
  'Param/Value/GKWINTOWN',
  'Param/Value/GKWINMAFIA',
  'Param/Value/GKWINTRIAD',
  'Param/Value/GKWINNEUTRAL',
  'Param/Value/GKANNOUNCE',
  'Param/Value/GKDOT',
  'Param/Value/GKARRIVE',
  'Param/Value/GKROLEEND',
  'Param/Value/GKSELECT',
  'Param/Value/GKSELECTEND',
  'Param/Value/GKCANCEL',
  'Param/Value/GKBLOCKED',
  'Param/Value/GKUSED',
  'Param/Value/GKINVALID',
  'Param/Value/GKTEAMINFO',
  'Param/Value/GKNEUTRALINFO',
  'Param/Value/GKWIN',
  'Param/Value/GKLOSE',
  'Param/Value/GK33NAME',
  'Param/Value/GK33DESC',
  'Param/Value/GK33ABIL',
  'Param/Value/GK33TRAIT',
  'Param/Value/GK33WHITE',
  'Param/Value/GK33CARD',
  'Param/Value/GK33INV1',
  'Param/Value/GK33INV2',
  'Param/Value/GK33CRIME',
  'Param/Value/GK33RESULT',
  'Param/Value/GK33RESULTEND',
  'Param/Value/GK33HINT',
  'Param/Value/GK34NAME',
  'Param/Value/GK34DESC',
  'Param/Value/GK34ABIL',
  'Param/Value/GK34TRAIT',
  'Param/Value/GK34WHITE',
  'Param/Value/GK34CARD',
  'Param/Value/GK34INV1',
  'Param/Value/GK34INV2',
  'Param/Value/GK34CRIME',
  'Param/Value/GK34HINT',
  'Param/Value/GK34LINK',
  'Param/Value/GK34LINKWITH',
  'Param/Value/GK34CHAT',
  'Param/Value/GK34CHATSEP',
  'Param/Value/GK34CHATEND',
  'Param/Value/GK34CANCEL',
  'Param/Value/GKMAILTITLE',
  'Param/Value/GKMAILHINT',
  'Param/Value/GKMAILCOUNT',
  'Param/Value/GKMAILTIP',
  'Param/Value/GKMAILCLEAR',
  'Param/Value/GKMAILCLOSE',
  'Param/Value/GKMAILFULL',
  'Param/Value/GKMAILSET',
  'Param/Value/GKMAILBAD',
  'Param/Value/GK35NAME',
  'Param/Value/GK35DESC',
  'Param/Value/GK35ABIL',
  'Param/Value/GK35TRAIT',
  'Param/Value/GK35WHITE',
  'Param/Value/GK35CARD',
  'Param/Value/GK35INV1',
  'Param/Value/GK35INV2',
  'Param/Value/GK35CRIME',
  'Param/Value/GK35HINT',
  'Param/Value/GK35ON',
  'Param/Value/GK35OFF',
  'Param/Value/GK35SACRIFICE',
  'Param/Value/GK35DEATH',
  'Param/Value/GK35OWN',
  'Param/Value/GK36NAME',
  'Param/Value/GK36DESC',
  'Param/Value/GK36ABIL',
  'Param/Value/GK36TRAIT',
  'Param/Value/GK36WHITE',
  'Param/Value/GK36CARD',
  'Param/Value/GK36INV1',
  'Param/Value/GK36INV2',
  'Param/Value/GK36CRIME',
  'Param/Value/GK36HINT',
  'Param/Value/GK36SUCCESS',
  'Param/Value/GK36RECEIVE',
  'Param/Value/GK37NAME',
  'Param/Value/GK37DESC',
  'Param/Value/GK37ABIL',
  'Param/Value/GK37TRAIT',
  'Param/Value/GK37WHITE',
  'Param/Value/GK37CARD',
  'Param/Value/GK37INV1',
  'Param/Value/GK37INV2',
  'Param/Value/GK37CRIME',
  'Param/Value/GK37HINT',
  'Param/Value/GK37SUCCESS',
  'Param/Value/GK37RECEIVE',
  # shw306：动态拼接的职业名同样必须回读，不能只检查字面量 StringExternal。
  'Param/Value/BHFROLE1',
  'Param/Value/BHFROLE2',
  'Param/Value/BHFROLE3',
  'Param/Value/BHFROLE4',
  'Param/Value/BHFROLE5',
  'Param/Value/BHFROLE6',
  'Param/Value/BHFROLE7',
  'Param/Value/BHFROLE8',
  'Param/Value/BHFROLE9',
  'Param/Value/BHFROLE10',
  'Param/Value/BHFROLE11',
  'Param/Value/BHFROLE12',
  'Param/Value/BHFROLE13',
  'Param/Value/BHFROLE14',
  'Param/Value/BHFROLE15',
  'Param/Value/BHFROLE16',
  'Param/Value/BHFROLE17',
  'Param/Value/BHFROLE18',
  'Param/Value/BHFROLE19',
  'Param/Value/BHFROLE20',
  'Param/Value/BHFROLE21',
  'Param/Value/BHFROLE22',
  'Param/Value/BHFROLE23',
  'Param/Value/BHFROLE24',
  'Param/Value/BHFROLE25',
  'Param/Value/BHFROLE26',
  'Param/Value/BHFROLE27',
  'Param/Value/BHFROLE30',
  'Param/Value/BHFROLE31',
  'Param/Value/BHFROLE32',
  'Param/Value/BHFROLE33',
  'Param/Value/BHFROLE34',
  'Param/Value/BHFROLE35',
  'Param/Value/BHFJOIN2',
  'Param/Value/BHFJOIN5',
  'Param/Value/BHFGOAL2',
  'Param/Value/BHFGOAL5',
  'Param/Value/BHFKEEP',
  'Param/Value/BHFSPYTRAIT',
  'Param/Value/BHFAPPTRAIT',
  'Param/Value/BHFVIGTRAIT',
  'Param/Value/BHFFORTRAIT',
  'Param/Value/BHFMEDTRAIT',
  'Param/Value/BHFMEMTRAIT',
  'Param/Value/BHFMAYORTRAIT', 'Param/Value/BHFMAYORPREFIX',
  'Param/Value/BHFMAYORMAFIA', 'Param/Value/BHFMAYORTRIAD',
  'Param/Value/BHFUSAGE',
  'Param/Value/BHFREJECT',
  'Param/Value/BHFDONE',
  # 帮派夜间行动意向：转阵营职业与原生成员共享私密频道资格
  'Param/Value/BHFACWANT', 'Param/Value/BHFACCHANGE', 'Param/Value/BHFACCANCEL',
  'Param/Value/BHFACJOIN', 'Param/Value/BHFACEND',
  # 先知 (3/30)：首夜情报、黎明转职与完整角色卡
  'Param/Value/XZNAME', 'Param/Value/XZDESC', 'Param/Value/XZHEAD',
  'Param/Value/XZBOX1', 'Param/Value/XZBOX2', 'Param/Value/XZBOX4',
  'Param/Value/XZCARD', 'Param/Value/XZINFOPREFIX', 'Param/Value/XZINFOFULL',
  'Param/Value/XZINFOSHORT', 'Param/Value/XZINFONOFAKE', 'Param/Value/XZINFOEMPTY',
  'Param/Value/XZBECOME', 'Param/Value/XZSEP',
  # 共生体 (3/29)：角色卡/绑定/共享频道/死亡与判胜
  'Param/Value/GSNAME',
  'Param/Value/GSCARD',
  'Param/Value/GSALIGN',
  'Param/Value/GSDESC',
  'Param/Value/GSBOX1',
  'Param/Value/GSBOX2',
  'Param/Value/GSBOX4',
  'Param/Value/GSBOX6',
  'Param/Value/GSCRIME',
  'Param/Value/GSSCAN1',
  'Param/Value/GSSCAN2',
  'Param/Value/GSBINDTIP',
  'Param/Value/GSHOST1',
  'Param/Value/GSHOST2',
  'Param/Value/GSKNOW2',
  'Param/Value/GSKNOW3',
  'Param/Value/GSCHOOSE',
  'Param/Value/GSSHIELDHINT',
  'Param/Value/GSSHIELDON',
  'Param/Value/GSSHIELDOFF',
  'Param/Value/GSSTRIKEHINT',
  'Param/Value/GSSTRIKEWAIT',
  'Param/Value/GSSTRIKESEL1',
  'Param/Value/GSSTRIKESEL2',
  'Param/Value/GSSTRIKECANCEL',
  'Param/Value/GSSTRIKEERROR',
  'Param/Value/GSWIN',
  'Param/Value/GSLOSE',
  'Param/Value/GSATTACKNIGHT',
  'Param/Value/GSATTACKDEATH',
  'Param/Value/GSATTACKOWN',
  'Param/Value/GSUNBOUNDDEATH',
  'Param/Value/GSUNBOUNDOWN',
  'Param/Value/GSUNBOUNDNIGHT',
  'Param/Value/GSBONDNIGHT',
  'Param/Value/GSBONDDEATH',
  'Param/Value/GSBONDOWN',
  'Param/Value/GSSACRIFICEDEATH',
  'Param/Value/GSSACRIFICEOWN',
  'Param/Value/GSSHIELDSELF',
  'Param/Value/GSSHIELDHOST',
  'Param/Value/GSATTACKIMMUNE',
  'Param/Value/GSCORONERQ',
  'Param/Value/GSCORONERR',
  'Param/Value/GSCORONERS',
  'Param/Value/GSCORONERT',
  'Param/Value/GSCHNAME',
  'Param/Value/GSCHJOIN',
  'Param/Value/GSCHOPEN',
  'Param/Value/GSCHSEP',
  'Param/Value/GSCHCLOSE',
  # 恶棍 (3/28)：全部外围/伤势/结算键
  'Param/Value/EGNAME',
  'Param/Value/EGCARD',
  'Param/Value/EGALIGN',
  'Param/Value/EGDESC',
  'Param/Value/EGBOX1',
  'Param/Value/EGBOX2',
  'Param/Value/EGBOX4',
  'Param/Value/EGBOX6',
  'Param/Value/EGCRIME',
  'Param/Value/EGTIP',
  'Param/Value/EGCANCELTIP',
  'Param/Value/EGSEL1',
  'Param/Value/EGSEL2',
  'Param/Value/EGCANCEL',
  'Param/Value/EGWOUND',
  'Param/Value/EGATTACK1',
  'Param/Value/EGATTACK2',
  'Param/Value/EGIMMUNET1',
  'Param/Value/EGIMMUNET2',
  'Param/Value/EGIMMUNEA1',
  'Param/Value/EGIMMUNEA2',
  'Param/Value/EGALREADY',
  'Param/Value/EGHEALER',
  'Param/Value/EGPATIENT',
  'Param/Value/EGCLEANSE',
  'Param/Value/EGHEALBLOCK1',
  'Param/Value/EGHEALBLOCK2',
  'Param/Value/EGNIGHT',
  'Param/Value/EGDEATH',
  'Param/Value/EGDIED',
  'Param/Value/EGCORONER',
  'Param/Value/EGWIN',
  'Param/Value/EGWINTITLE',
  'Param/Value/EGWINBODY',
  'Param/Value/1CEF178B',
  'Param/Value/1DEADB2F',
  'Param/Value/1FD3905E',
  'Param/Value/2B772EFE',
  'Param/Value/2D76CD9B',
  'Param/Value/41166422',
  'Param/Value/4654F827',
  'Param/Value/56E7EEEB',
  'Param/Value/A5853129',
  'Param/Value/C0D6293D',
  'Param/Value/CF76CC01',
  'Param/Value/D24C65D8',
  'Param/Value/DEF7D7EB',
  'Param/Value/EACC9ADF',
  'Param/Value/FC60340A',
  'Param/Value/D9495B72',

    # 新增城镇角色的独立帮助栏首字母配色
    'Param/Value/GCZCARD', 'Param/Value/SQCARD', 'Param/Value/FENGCARD',
    'Param/Value/JJCARD', 'Param/Value/ZJCARD',

    # 主教 (1/35)：卡面、互斥票数选项、晨报、行动提示与公共场所组候选
    'Param/Value/ZJNAME', 'Param/Value/ZJALIGN', 'Param/Value/ZJDESC',
    'Param/Value/ZJBOX1', 'Param/Value/ZJBOX2A', 'Param/Value/ZJBOX2B',
    'Param/Value/ZJBOX2C', 'Param/Value/ZJBOX2D', 'Param/Value/ZJBOX2E',
    'Param/Value/ZJBOX4', 'Param/Value/ZJOPT2', 'Param/Value/ZJOPT3', 'Param/Value/ZJCRIME',
    'Param/Value/ZJNEWS1', 'Param/Value/ZJNEWS2', 'Param/Value/ZJSELECT', 'Param/Value/ZJCANCEL',
    'Param/Value/ZJPICK', 'Param/Value/ZJPICKEND', 'Param/Value/ZJOFF', 'Param/Value/ZJCOOLDOWN',
    'Param/Value/3051C3D7', 'Param/Value/4F1EBF4B', 'Param/Value/72BB7C73',
    'Param/Value/A51EA15F', 'Param/Value/B7F2DBC2', 'Param/Value/C84927BC',
    'Param/Value/C8AB6DDE', 'Param/Value/CF0DFBAB', 'Param/Value/CWINV2',

    # 饭店老板 (1/36)：卡面、面板两档、播报与侦探收尸措辞
    'Param/Value/FDNAME', 'Param/Value/FDALIGN', 'Param/Value/FDDESC',
    'Param/Value/FDBOX1', 'Param/Value/FDBOX2A', 'Param/Value/FDBOX2B',
    'Param/Value/FDFACTION',
    'Param/Value/FDBOX2C', 'Param/Value/FDBOX2D', 'Param/Value/FDBOX2E',
    'Param/Value/FDBOX2F', 'Param/Value/FDBOX2G', 'Param/Value/FDBOX2H',
    'Param/Value/FDBOX4',
    'Param/Value/FDINV1', 'Param/Value/FDINV2', 'Param/Value/FDCRIME',
    'Param/Value/FDCOOK', 'Param/Value/FDDELIVER', 'Param/Value/FDCANCEL',
    'Param/Value/FDCOOKTIP', 'Param/Value/FDDELIVERTIP', 'Param/Value/FDNOFOOD',
    'Param/Value/FDPICK', 'Param/Value/FDPICKEND',
    'Param/Value/FDLOOT', 'Param/Value/FDRECOVER', 'Param/Value/FDGRACE',
    'Param/Value/FDVOTE',
    'Param/Value/FDSURVIVOR',
    'Param/Value/FDCOUNT', 'Param/Value/FDCOUNTEND',
    'Param/Value/FDDET1', 'Param/Value/FDDET2', 'Param/Value/FDDET3', 'Param/Value/FDDET4',

    # 律师 / 状师
    'Param/Value/LSNAME',
    'Param/Value/DZNAME',
    'Param/Value/LSDESC',
    'Param/Value/DZDESC',
    'Param/Value/LSTAG',
    'Param/Value/DZTAG',
    'Param/Value/LSCARD',
    'Param/Value/DZCARD',
    'Param/Value/LSBOX4',
    'Param/Value/DZBOX4',
    'Param/Value/LSABILITY',
    'Param/Value/LSBOX2',
    'Param/Value/LSCONVERT',
    'Param/Value/DZCONVERT',
    'Param/Value/LSCRIME',
    'Param/Value/LSSELECT',
    'Param/Value/LSWILL',
    'Param/Value/LSCANCEL',
    'Param/Value/LSGONE',
    'Param/Value/LSDEFENSE',
    'Param/Value/LSBLOCK',

    # 陷阱师 / 天工
    'Param/Value/XJSNAME',
    'Param/Value/TGNAME',
    'Param/Value/XJSDESC',
    'Param/Value/TGDESC',
    'Param/Value/XJSTAG',
    'Param/Value/TGTAG',
    'Param/Value/XJSBOX4',
    'Param/Value/TGBOX4',
    'Param/Value/XJSBOX2',
    'Param/Value/TGBOX2',
    'Param/Value/XJSREST',
    'Param/Value/XJSCRIME',

    'Param/Value/BHADMINNAME',
    # 征募官首夜机制选择、老版反馈与单发义警
    'Param/Value/ZMBOXBASE', 'Param/Value/ZMBOXNEW', 'Param/Value/ZMBOXOLD',
    'Param/Value/ZMSTATE0', 'Param/Value/ZMSTATE1', 'Param/Value/ZMSTATE2',
    'Param/Value/ZMCHOICE', 'Param/Value/ZMCHOICETIP', 'Param/Value/ZMNEWBTN', 'Param/Value/ZMOLDBTN',
    'Param/Value/ZMNEWTIP', 'Param/Value/ZMOLDTIP', 'Param/Value/ZMCHOSENEW', 'Param/Value/ZMCHOSEOLD',
    'Param/Value/ZMDEFAULT', 'Param/Value/ZMNOREVEAL', 'Param/Value/ZMOK', 'Param/Value/ZMOKEND', 'Param/Value/ZMFAIL',
    'Param/Value/ZMBY', 'Param/Value/ZMTOOK', 'Param/Value/ZMTOFAIL', 'Param/Value/ZMVIGBOX', 'Param/Value/ZMNEWTO',
    # shw254 保存格位（4 槽位 + 命名）
    'Param/Value/SHWSLOT1',
    'Param/Value/SHWSLOT6',
    'Param/Value/SHWSLOT7',
    'Param/Value/SHWSLOTA',
    'Param/Value/SHWSLOTH',
    'Param/Value/SHWSLOTT2',
    'Param/Value/SHWSLOTT3',
    'Param/Value/SHWSLOTT4',
    'Param/Value/SHWSLOT8',
    'Param/Value/SHWSLOTS1',
    'Param/Value/SHWSLOTS0',
    'Param/Value/SHWSLOTS2',
    'Param/Value/SHWSLOTS3',
    'Param/Value/SHWSLOTS4',
    'Param/Value/SHWSLOTS5',
    'Param/Value/SHWSLOTS6',
    'Param/Value/SHWSLOTS7',
    'Param/Value/SHWSLOTS8',
    'Param/Value/SHWSLOTS9',
    'Param/Value/SHWSLOTC',
    'Param/Value/SHWSLOTD',
    'Param/Value/SHWSLOTE',
    'Param/Value/SHWSLOTF',
    'Param/Value/SHWNAME',
    'Param/Value/XRBTN', 'Param/Value/XRBTNTIP', 'Param/Value/XRTITLE', 'Param/Value/XRHINT',
    'Param/Value/XRDEADLAB', 'Param/Value/XRGANGLAB', 'Param/Value/XRLIFELAB', 'Param/Value/XRLIFEDOT', 'Param/Value/XRLIFEON', 'Param/Value/XRCLOSE',
    'Param/Value/XRDEAD', 'Param/Value/XRGANG', 'Param/Value/XRGANG2', 'Param/Value/XRIN', 'Param/Value/XRGANGWIN',
    'Param/Value/XRFOODBOX',
    'Param/Value/XRLIFEREBORN', 'Param/Value/XRLIFEPASSIVE',
    'Param/Value/XRANNHEADER', 'Param/Value/XRANNLIFE', 'Param/Value/XRANNGANG', 'Param/Value/XRANNDEAD',
    'Param/Value/JJNAME', 'Param/Value/JJDESC', 'Param/Value/JJTAG',
    'Param/Value/JJBOX1', 'Param/Value/JJBOX2', 'Param/Value/JJBOX4',
    'Param/Value/JJCRIME', 'Param/Value/JJINV1', 'Param/Value/JJINV2',
    'Param/Value/JJBTN', 'Param/Value/JJCANCEL', 'Param/Value/JJPICK',
    'Param/Value/JJRE', 'Param/Value/JJOFF', 'Param/Value/JJDOT',
    'Param/Value/JJGONE', 'Param/Value/JJLIVE',
    'Param/Value/JJSIZE', 'Param/Value/JJCLOSE', 'Param/Value/JJREVIVED',
    'Param/Value/SHWDESC',
    'Param/Value/GCZNAME',
    'Param/Value/GCZBNAME',
    'Param/Value/GCZJNAME',
    'Param/Value/GCZTNAME',
    # shw218 唐人街[高阶]（自设面板第 34 项 / variant 13 sub 3）
    'Param/Value/SHWCT3NAME', 'Param/Value/SHWCT3DESC', 'Param/Value/SHWCT3BTN',
    # shw220 影武者双目标的选择提示（目标一=跟踪、目标二=预测其访问）
    'Param/Value/SHWTRK1', 'Param/Value/SHWTRK2', 'Param/Value/SHWTRK3', 'Param/Value/SHWTRK4',
    'Param/Value/TXNAME',
    'Param/Value/JSNAME', 'Param/Value/JSDESC', 'Param/Value/JSCARD', 'Param/Value/JSALIGN',
    'Param/Value/JSBOX1', 'Param/Value/JSBOX2', 'Param/Value/JSBOX4', 'Param/Value/JSBOX6',
    'Param/Value/JSCRIME', 'Param/Value/JSDM',
    # 天选者角色卡各栏（缺任一项 → 界面直接显示原始键名，shw192 事故）
    'Param/Value/TXBOX1', 'Param/Value/TXBOX2', 'Param/Value/TXBOX4',
    'Param/Value/TXBOXINV', 'Param/Value/TXBOXVISIT',
    'Param/Value/BHYIN01',
    'Param/Value/SHWZFRC',   # shw214：城镇zf「不包括 征募官」
    # 警长的「可查出X」开关与播报、影武者/天选者/堕落审判者的卡片特性行（shw149）
    'Param/Value/SHWBOXS',
    'Param/Value/SHWMLCULT',  # shw262：共济会长老角色卡「目标免疫协教转化」
    'Param/Value/BHJAILSWAP', 'Param/Value/BHJAILSWAP0',  # 司机/欺骗者/迷惑者：目标含狱中则能力不生效
    'Param/Value/CWNAME', 'Param/Value/CWCARD', 'Param/Value/CWDESC', 'Param/Value/CWINV1', 'Param/Value/CWINV2',
    'Param/Value/CWBOX1', 'Param/Value/CWBOX2', 'Param/Value/CWBOX4', 'Param/Value/CWBOX4ID',
    'Param/Value/CWWIN', 'Param/Value/CWTIP', 'Param/Value/CWCRIME', 'Param/Value/CWSHREV',
    'Param/Value/CWTNAME', 'Param/Value/CWTDESC', 'Param/Value/CWTBTN',
    'Param/Value/CWTSUBA', 'Param/Value/CWTSUBB', 'Param/Value/CWTSUBC', 'Param/Value/CWTSUBD',
    'Param/Value/CWNATG', 'Param/Value/CWDARKG', 'Param/Value/CWDARKI',
    'Param/Value/SHWREV',
    'Param/Value/TXSW',
    'Param/Value/TXREVSH',
    'Param/Value/TXBOXS',
    'Param/Value/DLSW',
    'Param/Value/DLREV',
    'Param/Value/DLBOXS',
 'Param/Value/TXACH1', 'Param/Value/TXACH2', 'Param/Value/TXACH3',
 # 影武者成就「影缝」(shw152)
 'Param/Value/SHACH1', 'Param/Value/SHACH2', 'Param/Value/SHACH3',
 # 煽动家成就 全票当选/罢免案/无声喝彩 (70/71/72)
 'Param/Value/CWACHP', 'Param/Value/CWACH1S', 'Param/Value/CWACH1N',
 'Param/Value/CWACH2S', 'Param/Value/CWACH2N', 'Param/Value/CWACH3S', 'Param/Value/CWACH3N',
 # 斜体名字跟随公屏放大：gf_CBMagnifyText 的替换源/目标标签（shw155）
 'Param/Value/SHWMGIA', 'Param/Value/SHWMGIB', 'Param/Value/SHWMGIC',
 'Param/Value/SHWMGID',
 # 角色首胜播报（shw180）
  'Param/Value/SHWFR1', 'Param/Value/SHWFR2', 'Param/Value/SHWFR3',
  # shw274 开膛手 (3/20)
  'Param/Value/KCNAME', 'Param/Value/KCDESC', 'Param/Value/KCCARD',
  'Param/Value/KCBOX1', 'Param/Value/KCBOX2', 'Param/Value/KCBOX3',
  'Param/Value/KCBOX4', 'Param/Value/KCBOX5', 'Param/Value/KCBOXS',
  'Param/Value/KCTIP', 'Param/Value/KCSEL1', 'Param/Value/KCSEL2',
  'Param/Value/KCCLR', 'Param/Value/KCISO', 'Param/Value/KCNIGHT0',
  'Param/Value/KCNIGHT1', 'Param/Value/KCNIGHT2', 'Param/Value/KCDEATH0',
  'Param/Value/KCDEATH1', 'Param/Value/KCDEATH2', 'Param/Value/KCDEATH0B',
  'Param/Value/KCDEATHC0', 'Param/Value/KCDEATHC1', 'Param/Value/KCDM',
  'Param/Value/KCSHREV', 'Param/Value/KCMODE1', 'Param/Value/KCMODE1B',
  'Param/Value/KCMODE2', 'Param/Value/KCRESTRICT',
  'Param/Value/KCACH1S', 'Param/Value/KCACH1N',
  'Param/Value/KCACH2S', 'Param/Value/KCACH2N',
  'Param/Value/KCACH3S', 'Param/Value/KCACH3N',
  'Param/Value/KCSW', 'Param/Value/KCSWBOX', 'Param/Value/KCSWBOX0',
  # shw276 随机：雾都
  'Param/Value/WDTNAME', 'Param/Value/WDTDESC', 'Param/Value/WDTBTN',
  'Param/Value/WDTSUBA', 'Param/Value/WDTSUBB', 'Param/Value/WDTSUBC',
  'Param/Value/WDTSUBD',
  # 随机：决死之心
  'Param/Value/JSXTNAME', 'Param/Value/JSXTDESC', 'Param/Value/JSXTBTN',
  'Param/Value/JSXTSUBA', 'Param/Value/JSXTSUBB', 'Param/Value/JSXTSUBC', 'Param/Value/JSXTSUBD',
  # 随机：传承者
  'Param/Value/CCZTNAME', 'Param/Value/CCZTDESC', 'Param/Value/CCZTBTN',
  'Param/Value/CCZTSUBA', 'Param/Value/CCZTSUBB', 'Param/Value/CCZTSUBC',
  # 随机：混乱之始
  'Param/Value/HLZSNAME', 'Param/Value/HLZSDESC', 'Param/Value/HLZSBTN',
  'Param/Value/HLZSSUBA',
  # 随机：实验性角色
  'Param/Value/SYJXNAME', 'Param/Value/SYJXDESC', 'Param/Value/SYJXBTN',
  'Param/Value/SYJXSUBA', 'Param/Value/SYJXSUBB',
  # 白手起家（仅15人，原始导出阵容）
  'Param/Value/BSQJNAME', 'Param/Value/BSQJDESC', 'Param/Value/BSQJBTN',
  'Param/Value/BSQJSUBA', 'Param/Value/BSQJONLY15',
  # shw288 唐吉诃德 (3/21)
  'Param/Value/DQNAME', 'Param/Value/DQDESC', 'Param/Value/DQCARD',
  'Param/Value/DQBOX1', 'Param/Value/DQBOX2', 'Param/Value/DQBOX4',
  'Param/Value/DQBOX6', 'Param/Value/DQALIGN', 'Param/Value/DQCRIME', 'Param/Value/DQREV',
  'Param/Value/DQINV1', 'Param/Value/DQINV2',
  'Param/Value/DQNIGHT',
  'Param/Value/DQACH2S', 'Param/Value/DQACH3',
  'Param/Value/DQACHD',
  # 感染者 (3/22)：文案登记
   'Param/Value/GRNAME', 'Param/Value/GRCARD', 'Param/Value/GRDESC',
   'Param/Value/GRBOX1', 'Param/Value/GRBOX2', 'Param/Value/GRBOX3',
   'Param/Value/GRBOX4', 'Param/Value/GRBOX6', 'Param/Value/GRBOXS',
   'Param/Value/GROPTIMM', 'Param/Value/GRTIP', 'Param/Value/GRSEL',
   'Param/Value/GRRESEL', 'Param/Value/GRCANCEL', 'Param/Value/GRREADY',
   'Param/Value/GRDISARM', 'Param/Value/GRNOCHARGE', 'Param/Value/GRREST',
   'Param/Value/GRCONVERT', 'Param/Value/GRNEW', 'Param/Value/GRFAILED',
   'Param/Value/GRIMMUNE', 'Param/Value/GRHEALED', 'Param/Value/GRGUARDED',
   'Param/Value/GRCHATON', 'Param/Value/GRCHATOFF', 'Param/Value/GRCHATDAY',
   'Param/Value/GRCHATNONE', 'Param/Value/GRCHATHELP', 'Param/Value/GRDEATH0',
   'Param/Value/GRDEATH1', 'Param/Value/GRDEATHS0', 'Param/Value/GRDEATHS1',
   'Param/Value/GRDM', 'Param/Value/GRCRIME',
   'Param/Value/GRDMSELF', 'Param/Value/GRNIGHT', 'Param/Value/GRCHATMSG',
   'Param/Value/GRSHREV',
   # 阎罗 (3/26)
   'Param/Value/YLNAME', 'Param/Value/YLCARD', 'Param/Value/YLDESC',
   'Param/Value/YLBOX1', 'Param/Value/YLBOX2', 'Param/Value/YLBOX4',
   'Param/Value/YLBOX6', 'Param/Value/YLOPTIMM', 'Param/Value/YLCRIME',
   'Param/Value/YLBTN', 'Param/Value/YLCX', 'Param/Value/YLSEL',
   'Param/Value/YLCLEAR', 'Param/Value/YLINTRO', 'Param/Value/YLSEE1',
   'Param/Value/YLSEE2', 'Param/Value/YLFACT1', 'Param/Value/YLFACT2',
   'Param/Value/YLFACT5', 'Param/Value/YLFACTN', 'Param/Value/YLIMMUNE',
   'Param/Value/YLHEALED', 'Param/Value/YLGUARDED', 'Param/Value/YLNIGHT',
   'Param/Value/YLDEATH0', 'Param/Value/YLDEATH1', 'Param/Value/YLDM',
   'Param/Value/YLSHREV',
   # 调停者 (3/23)
   'Param/Value/TTPOOL', 'Param/Value/TTPOOLDESC',
   'Param/Value/TTNAME', 'Param/Value/TTCARD', 'Param/Value/TTALIGN',
   'Param/Value/TTDESC', 'Param/Value/TTBOX1', 'Param/Value/TTBOX2',
   'Param/Value/TTBOX4', 'Param/Value/TTBOX6', 'Param/Value/TTCRIME',
   'Param/Value/TTPROT', 'Param/Value/TTSUPR', 'Param/Value/TTPROTSEL',
   'Param/Value/TTSUPRSEL', 'Param/Value/TTCANCEL', 'Param/Value/TTCX',
   'Param/Value/TTANON', 'Param/Value/TTQUIET', 'Param/Value/TTBLOCK',
   'Param/Value/TTADJOURN', 'Param/Value/TTWON', 'Param/Value/TTLOST',
   'Param/Value/TTSTOPTIP', 'Param/Value/TTNOSTOP', 'Param/Value/TTUSED',
   # shw289 弃子(2/16) / 死士(5/16)
  'Param/Value/QZNAME', 'Param/Value/QZDESC', 'Param/Value/QZCARD',
  'Param/Value/SSNAME', 'Param/Value/SSDESC', 'Param/Value/SSCARD',
  'Param/Value/QZBOX1', 'Param/Value/QZBOX2', 'Param/Value/QZBOX4',
  'Param/Value/SSBOX2', 'Param/Value/SSBOX4', 'Param/Value/QZBOX6', 'Param/Value/SSBOX6',
  'Param/Value/QZCRIME', 'Param/Value/QZN1', 'Param/Value/QZFAIL',
  'Param/Value/QZNIGHT', 'Param/Value/QZDEATH1', 'Param/Value/QZDEATH2',
  'Param/Value/QZSELF1', 'Param/Value/QZSELF2', 'Param/Value/QZDM',
  'Param/Value/QZTIP', 'Param/Value/QZSEL1', 'Param/Value/QZSEL2',
  'Param/Value/QZCLR', 'Param/Value/QZYOU', 'Param/Value/QZYOUSELF',
  'Param/Value/BHASTOK', 'Param/Value/BHASTNONE', 'Param/Value/BHASTHAVE',
  'Param/Value/BHASTBAD', 'Param/Value/BHASTCLR', 'Param/Value/BHASTFULL',
  'Param/Value/BHASTDONE',
  'Param/Value/QZACH1S', 'Param/Value/QZACH1N', 'Param/Value/QZACH1D',
  'Param/Value/QZACH2S', 'Param/Value/QZACH2N', 'Param/Value/QZACH2D',
  'Param/Value/MYXACHS', 'Param/Value/MYXACHN', 'Param/Value/MYXACHD',
  'Param/Value/WLKFACHS', 'Param/Value/WLKFACHN', 'Param/Value/WLKFACHD',
  'Param/Value/BWZYN',
  'Param/Value/SHWWILLBTN', 'Param/Value/SHWWILLTIP',
  'Param/Value/VETSELF', 'Param/Value/XMVIST', 'Param/Value/DLNOBLOCK',
  'Param/Value/DTBLOCK', 'Param/Value/DTBECAUSE', 'Param/Value/DTWHYB',
  'Param/Value/DTNONE', 'Param/Value/DTWHY5', 'Param/Value/DTSELF',
  'Param/Value/DTWHY2', 'Param/Value/DTPLAN', 'Param/Value/DTBUT',
  'Param/Value/DTEND', 'Param/Value/DTDBL1', 'Param/Value/DTTHEN',
  'Param/Value/DTWHY4', 'Param/Value/DTWHY3', 'Param/Value/DTSTAY',
  'Param/Value/DTNOPLAN', 'Param/Value/ZHIGNITE', 'Param/Value/DTREASON',
  'Param/Value/SHWWILLEMPTY',
  'Param/Value/SKBURSTBOX', 'Param/Value/SKBURSTREADY',
  'Param/Value/SKBURSTFIRST', 'Param/Value/SKBURSTSECOND',
  'Param/Value/SKBURSTSET', 'Param/Value/SKBURSTEND',
  'Param/Value/SKBURSTCANCEL',
  # 护林人 (1/22)
  'Param/Value/HLDESC', 'Param/Value/HLABILITY', 'Param/Value/HLTRAITS', 'Param/Value/HLCRIME',
  'Param/Value/HLNIGHT1', 'Param/Value/HLGONE', 'Param/Value/HLSETA', 'Param/Value/HLSETB',
  'Param/Value/HLDIED', 'Param/Value/HLGOT', 'Param/Value/HLHEAL', 'Param/Value/HLSAVED',
  'Param/Value/HLGUARD', 'Param/Value/HLGUARDDIE', 'Param/Value/HLGUARDGOT',
  'Param/Value/HLBOUNCE', 'Param/Value/HLSNAP', 'Param/Value/HLDEATHM', 'Param/Value/HLDEATHF',
  # 狸猫 (3/24)
  'Param/Value/LMNAME', 'Param/Value/LMCARD', 'Param/Value/LMALIGN', 'Param/Value/LMDESC',
  'Param/Value/LMBOX1', 'Param/Value/LMBOX2', 'Param/Value/LMBOX4', 'Param/Value/LMBOX6',
  'Param/Value/LMCRIME', 'Param/Value/LMBTN', 'Param/Value/LMCX', 'Param/Value/LMCLEAR', 'Param/Value/LMSEL',
  'Param/Value/LMGOTA', 'Param/Value/LMGOTB',
   # 人口普查官 (1/32)
   'Param/Value/SQNAME', 'Param/Value/SQDESC', 'Param/Value/SQTAG',
   'Param/Value/SQABIL', 'Param/Value/SQTRAITS', 'Param/Value/SQIDENT', 'Param/Value/SQCRIME',
   'Param/Value/SQHEAD', 'Param/Value/SQN1', 'Param/Value/SQN2', 'Param/Value/SQN3',
   'Param/Value/SQTAIL',
   'Param/Value/SQN4', 'Param/Value/SQN5', 'Param/Value/SQN6', 'Param/Value/SQN7',
   'Param/Value/SQREV1', 'Param/Value/SQREV2',
   'Param/Value/BZNAME', 'Param/Value/BZDESC', 'Param/Value/BZTAG',
   'Param/Value/BZBOX1', 'Param/Value/BZBOX2', 'Param/Value/BZBOX4', 'Param/Value/BZCRIME',
   'Param/Value/QLNAME', 'Param/Value/QLDESC', 'Param/Value/QLTAG',
   'Param/Value/QLBOX1', 'Param/Value/QLBOX2', 'Param/Value/QLBOX4', 'Param/Value/QLCRIME',
   'Param/Value/BZKILL', 'Param/Value/BZFAKE', 'Param/Value/BZMASK', 'Param/Value/BZMASKTIP',
   'Param/Value/BZMASKMSG', 'Param/Value/BZTGT', 'Param/Value/BZWILL', 'Param/Value/BZFEIGNYOU', 'Param/Value/BZFEIGNDONE',
   'Param/Value/BZNO8', 'Param/Value/BZBLOC', 'Param/Value/BZHEAL', 'Param/Value/BZDIE',
   'Param/Value/BZLEAD', 'Param/Value/BZLEADD', 'Param/Value/QLLEAD', 'Param/Value/QLLEADD',
    'Param/Value/FZNAME', 'Param/Value/FZDESC', 'Param/Value/FZTAG',
    'Param/Value/FZBOX1', 'Param/Value/FZBOX2', 'Param/Value/FZBOX4', 'Param/Value/FZCRIME',
    'Param/Value/FZFATAL',
    'Param/Value/ZSNAME', 'Param/Value/ZSDESC', 'Param/Value/ZSTAG',
    'Param/Value/ZSBOX1', 'Param/Value/ZSBOX2', 'Param/Value/ZSBOX4', 'Param/Value/ZSCRIME',
    'Param/Value/YSNAME', 'Param/Value/YSDESC', 'Param/Value/YSTAG',
    'Param/Value/YSBOX1', 'Param/Value/YSBOX2', 'Param/Value/YSBOX4', 'Param/Value/YSCRIME',
    'Param/Value/BWNAME', 'Param/Value/BWDESC', 'Param/Value/BWTAG',
    'Param/Value/BWBOX1', 'Param/Value/BWBOX2', 'Param/Value/BWBOX4', 'Param/Value/BWCRIME',
    'Param/Value/YSMSG0', 'Param/Value/YSMSG1', 'Param/Value/YSMSG2', 'Param/Value/YSMSGP',
    'Param/Value/YSMSGZ', 'Param/Value/YSMSGX', 'Param/Value/YSMSGN0', 'Param/Value/YSMSGN1',
    'Param/Value/YSSEL', 'Param/Value/YSUNSEL', 'Param/Value/YSDUP',
    'Param/Value/YSBTN1', 'Param/Value/YSBTN2',
    'Param/Value/FENGNAME', 'Param/Value/FENGDESC', 'Param/Value/FENGTAG',
    'Param/Value/FENGBOX1', 'Param/Value/FENGBOX2', 'Param/Value/FENGBOX4',
    'Param/Value/FENGCRIME', 'Param/Value/FENGATK',
    # 男爵(2/22) / 泰斗(5/22)
    'Param/Value/NJNAME',
    'Param/Value/NJDESC',
    'Param/Value/NJTAG',
    'Param/Value/NJBOX1',
    'Param/Value/NJBOX2',
    'Param/Value/NJBOX4',
    'Param/Value/NJCRIME',
    'Param/Value/TDNAME',
    'Param/Value/TDDESC',
    'Param/Value/TDTAG',
    'Param/Value/TDBOX1',
    'Param/Value/TDBOX2',
    'Param/Value/TDBOX4',
    'Param/Value/TDCRIME',
    'Param/Value/BRUSAGE',
    'Param/Value/BRSELECT',
    'Param/Value/BRMAX2',
    'Param/Value/BRMAX3',
    'Param/Value/BRMAX4',
    'Param/Value/BRBOXMAX',
    'Param/Value/BRLIMIT',
    'Param/Value/BRINVALID',
    'Param/Value/BRRESULT',
    'Param/Value/BRFAIL1', 'Param/Value/BRFAIL2', 'Param/Value/BRFAIL3',
    'Param/Value/BRREFUSE2', 'Param/Value/BRREFUSE5',
    'Param/Value/BRBUTTON',
    'Param/Value/BRTOOLTIP',
    'Param/Value/BRFIRST',
    'Param/Value/BRFIRST5',
    'Param/Value/BRPANELTITLE',
    'Param/Value/BRPANELHINT',
    'Param/Value/BRPANELCOUNT',
    'Param/Value/BRPANELCLEAR',
    'Param/Value/BRPANELCLOSE',
    'Param/Value/BRLEADMAFIA',
    'Param/Value/BRLEADTRIAD',
    'Param/Value/BRINVSTRONG',
]


def parse_strings_file(path: Path) -> dict:
    """strings-*.txt → {key: value}；忽略空行与 // 注释。"""
    out = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        s = line.strip()
        if not s or s.startswith('//'):
            continue
        if '=' not in s:
            continue
        k, v = s.split('=', 1)
        out[k.strip()] = v
    return out


def collect_strings(paths: list[Path]) -> dict:
    merged, dup = {}, []
    for p in paths:
        for k, v in parse_strings_file(p).items():
            if k in merged and merged[k] != v:
                dup.append(k)
            merged[k] = v
    if dup:
        print(f"  ! 多文件重复键（后写的生效）: {sorted(set(dup))}")
    return merged


def merge_styles(archive: Path, src: Path, member: str = STYLE_MEMBER) -> tuple[list, list]:
    """把 src 里的 <Style> 逐条并入包内样式表；基线已有同名条目不动（增量，不整文件覆盖）。

    返回 (新增的样式名, 源文件里的全部样式名)。斜体依赖 ModItalic 定义在包内存在：
    shw87 只把它写进了当次产物 boot2-shw87.SC2Map，基线没有 → shw88 起所有版本都丢了。
    """
    cur = sc2map.read(archive, member)
    cur = cur.decode('utf-8') if isinstance(cur, bytes) else cur
    have = set(STYLE_NAME_RE.findall(cur))
    want = STYLE_NAME_RE.findall(src.read_text(encoding='utf-8'))

    text = src.read_text(encoding='utf-8')
    chunks = GROUP_ELEM_RE.findall(text) + TAG_ELEM_RE.findall(text)
    # findall 在含分组时会只返回分组 → 用 finditer 取整段
    # 顺序照文档：先 Constant 再 FontGroup 再 Style（引用解析是否先后无关，但保持规范顺序）
    tags = [m.group(0) for m in TAG_ELEM_RE.finditer(text)]
    chunks = [e for e in tags if e.startswith('<Constant')] + \
             [m.group(0) for m in GROUP_ELEM_RE.finditer(text)] + \
             [e for e in tags if e.startswith('<Style')]

    added = []
    for elem in chunks:
        name = ELEM_NAME_RE.search(elem).group(1)
        if name in have or f'name="{name}"' in cur:
            continue
        cur = cur.replace('</StyleFile>', f'    {elem}\n</StyleFile>')
        have.add(name)
        added.append(name)

    put(archive, member, cur.encode('utf-8'))
    return added, want


def put(archive, name, data, label=''):
    """写成员；内容与包内已有的完全一致就跳过（MPQ 每次写都是追加、旧数据不回收）。"""
    try:
        if sc2map.read(archive, name) == data:
            print(f"   跳过（内容相同）{name}")
            return False
    except Exception:
        pass

    sc2map.write(archive, name, data)

    return True


# 工作区脚本必须保持正式值 false。solo 包只在写入包内的副本上改，禁止改源码。
SOLO_DECL = {
    'c_bhSoloBuild': 'const bool c_bhSoloBuild = {val};',
    'c_bhSoloFill': 'const bool c_bhSoloFill = {val};',
}


def solo_decl_values(src: str) -> dict[str, str]:
    found = {}
    for name in SOLO_DECL:
        m = re.search(rf'const bool {name} = (true|false);', src)
        if m:
            found[name] = m.group(1)
    return found


def apply_solo_patch(src: str) -> str:
    """把两处常量改成 true，只动内存副本。源文件必须已经是 false。"""
    found = solo_decl_values(src)
    want = {'c_bhSoloBuild': 'false', 'c_bhSoloFill': 'false'}
    if found != want:
        raise SystemExit(
            f'✗ 工作区脚本 solo 常量是 {found}，必须保持 {want}。'
            f'solo 包请加 --solo，不要改源码'
        )
    out = src
    for name, tmpl in SOLO_DECL.items():
        old, new = tmpl.format(val='false'), tmpl.format(val='true')
        if out.count(old) != 1:
            raise SystemExit(f'✗ {name} 声明不是恰好 1 处，拒绝打补丁')
        out = out.replace(old, new, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, help='输出地图（用新文件名，编辑器会锁住已打开的）')
    ap.add_argument('--base', default=str(DEFAULT_BASE))
    ap.add_argument('--galaxy', default=str(DEFAULT_GALAXY))
    ap.add_argument('--strings', nargs='*', default=None, help='自加文案文件（默认 work/blackhand/strings-*.txt）')
    ap.add_argument('--skip-role-gate', action='store_true',
                    help='跳过 0e) 角色登记表检查（仓库里有半成品角色时用来出验证包；**不要出发布包**）')
    ap.add_argument('--skip-strings', action='store_true', help='不合并文案（仅当基线已含全部累积键时）')
    ap.add_argument('--skip-notes', action='store_true', help='不写补丁说明/加载页面（仅供验证包）')
    ap.add_argument('--name', default=None,
                    help='覆盖包内地图名（DocInfo/Name）—— 多发布线用，例如试验线「黑手：Revision Preview」')
    ap.add_argument('--desc-prepend', help='在地图详情（DocInfo/DescLong）开头插入一段（多发布线用，如预览版说明）')
    ap.add_argument('--desc-append', help='在地图详情（DocInfo/DescLong）结尾追加一段')
    ap.add_argument('--solo', action='store_true',
                    help='单人测试包：只把写入包内的 c_bhSoloBuild / c_bhSoloFill 改成 true，不动工作区源码；并给自定义 mod 补本地 file: 依赖回退')
    ap.add_argument('--local-deps', action='store_true',
                    help='把 CA 三件改成 file:Mods\\… 纯本地路径（--solo 默认打开；发布包不要加）')
    ap.add_argument('--sprite-variants', default=None,
                    help='逗号分隔：把 data/probe_<标签>.m3 登记成 BHSprite<大写>（探针批量对比用）')
    ap.add_argument('--no-hidden', action='store_true',
                    help='不打包隐藏的 2D 立牌模型（省几十 MB；要规避第三方素材时用）')
    ap.add_argument('--sprite-poc', action='store_true',
                    help='2D 立牌 PoC：把「60 号外观」的模型换成 data/BHSprite.m3（奶龙留到发布构建）')
    ap.add_argument('--extra-member', action='append', default=None,
                    help='直塞任意成员：`包内成员=源文件`，可重复（探针贴图等）')
    ap.add_argument('--cover', default=COVER_DEFAULT,
                    help='封面 stem（data/<stem>-Preview.dds + data/<stem>-Icon.dds）；默认 Cover2')
    args = ap.parse_args()

    out = Path(args.out)
    base = Path(args.base)
    galaxy = Path(args.galaxy)

    assert base.exists(), f'基线不存在: {base}'
    assert galaxy.exists(), f'脚本不存在: {galaxy}'

    # 0) 脚本静态体检（配平 + 自动变量声明）—— 不通过就不打包
    lint = subprocess.run([sys.executable, str(ROOT / 'tools' / 'galaxy_lint.py'), str(galaxy)],
                          capture_output=True, text=True)
    print(lint.stdout.strip())

    if lint.returncode != 0:
        print('✗ galaxy_lint 未通过，停止打包')
        return 1

    # 0b) 角色卡体检：覆盖（有显示名的角色必须有卡片块）+ 池专属不变式
    card = subprocess.run([sys.executable, str(ROOT / 'tools' / 'role_card_check.py'), '--strict'],
                          capture_output=True, text=True)
    print(card.stdout.strip())

    if card.returncode != 0:
        print('✗ role_card_check 未通过，停止打包')
        return 1

    # 0c) 自设列表漂移检测（shw247）：gt_OSMenus_Func 的列表构建 + gt_OSRoleSelect_Func 的
    #     选中映射必须仍是 work/roles-list.json 的生成物（逐字节等价）。
    #     手改那两段、或改完 JSON 忘了跑 --apply，都会在这里被拦下。
    rlist = subprocess.run([sys.executable, str(ROOT / 'tools' / 'role_list_gen.py'), '--check'],
                           capture_output=True, text=True)
    print(rlist.stdout.strip().splitlines()[-1] if rlist.stdout.strip() else '(role_list_gen 无输出)')

    if rlist.returncode != 0:
        print('✗ role_list_gen 未通过（自设列表与数据源不一致，先跑 --apply），停止打包')
        return 1

    # 0d) 抽出函数结构不变式（shw247）：void / 不给参数赋值 / 体内标识符可解析。
    #     不带 --rev ⇒ 只跑与历史无关的结构判据，1 秒内完成。
    skv = subprocess.run([sys.executable, str(ROOT / 'tools' / 'sk_verify.py')],
                         capture_output=True, text=True)
    tail = [x for x in skv.stdout.strip().splitlines() if x.startswith(('✓', '✗'))]
    print(tail[-1] if tail else '(sk_verify 无输出)')

    if skv.returncode != 0:
        print('✗ sk_verify 未通过，停止打包')
        return 1

    # 0e) 角色登记表（shw248）：spec 里的角色必须逐项登记（定义块 / 拼音 / 开关四件套 /
    #     图鉴犯罪 / 四项交互声明），且各路「上界」必须 ≥ 脚本里实际存在的最大角色号。
    #     加角色忘了放宽上界 = 角色静默发不到（shw115/149 的事故类型）。
    if args.skip_role_gate:
        # 仅供验证包：仓库里有「已写 spec、还没登记进脚本」的半成品角色时，正常出门是失败的。
        # 用它跳过会让那些角色保持「发不到」的状态 —— **永远不要用它出发布包**。
        print('⚠ 跳过 0e) 角色登记表（--skip-role-gate，仅供验证）')
    else:
        rg = subprocess.run([sys.executable, str(ROOT / 'tools' / 'role_gen.py')],
                            capture_output=True, text=True)
        rg_tail = [x for x in rg.stdout.strip().splitlines() if x.startswith(('✓', '✗'))]

        print(rg_tail[-1] if rg_tail else '(role_gen 无输出)')

        if rg.returncode != 0:
            print('✗ role_gen 未通过（角色登记与 spec 不一致，看 roles/*.json），停止打包')
            return 1

    # 0f) Wait 调用图（shw250）：含 Wait 的函数，调用链必须全部源自触发器。
    wg = subprocess.run([sys.executable, str(ROOT / 'tools' / 'wait_graph_check.py')],
                        capture_output=True, text=True)
    wg_tail = [l for l in (wg.stdout or '').strip().split('\n') if l.strip()][-2:]

    print(wg_tail[-1] if wg_tail else '(wait_graph_check 无输出)')

    if wg.returncode != 0:
        print('✗ wait_graph_check 未通过（含 Wait 的函数被非触发器上下文调用），停止打包')
        return 1

    if out.exists():
        print(f"  ! 覆盖已存在的 {out}")

    # 1) 复制基线
    out.write_bytes(base.read_bytes())
    print(f"1) 基线 {base.name} → {out.name}")

    # 2) 直写脚本（--solo 只改这份内存副本，工作区源码保持正式值 false）
    src_text = galaxy.read_text(encoding='utf-8')
    src_flags = solo_decl_values(src_text)
    if src_flags != {'c_bhSoloBuild': 'false', 'c_bhSoloFill': 'false'}:
        print(f'✗ 工作区脚本 solo 常量是 {src_flags}，必须保持 false（solo 包加 --solo，不要改源码）')
        return 1

    if args.solo:
        if 'solo' not in out.name.lower():
            print(f'⚠ --solo 但输出文件名 {out.name!r} 不含 solo，容易和正式包搞混')
        src_text = apply_solo_patch(src_text)

    put(out, 'CustomLogic.galaxy', src_text.encode('utf-8'))
    back = sc2map.read(out, 'CustomLogic.galaxy').decode('utf-8')
    assert back.count('BankWait(') >= 2, '包内脚本缺 BankWait'
    packed_flags = solo_decl_values(back)
    expect_flags = (
        {'c_bhSoloBuild': 'true', 'c_bhSoloFill': 'true'} if args.solo
        else {'c_bhSoloBuild': 'false', 'c_bhSoloFill': 'false'}
    )
    if packed_flags != expect_flags:
        print(f'✗ 包内 solo 常量是 {packed_flags}，期望 {expect_flags}')
        return 1

    disk_flags = solo_decl_values(galaxy.read_text(encoding='utf-8'))
    if disk_flags != {'c_bhSoloBuild': 'false', 'c_bhSoloFill': 'false'}:
        print(f'✗ 打包后工作区源码 solo 常量变成了 {disk_flags}，必须仍是 false')
        return 1

    print(f"2) CustomLogic.galaxy 写入 {len(back.splitlines())} 行（BankWait ×{back.count('BankWait(')}）"
          f"{'  [solo 包：c_bhSoloBuild/Fill=true，源码未改]' if args.solo else ''}")

    # 3) 样式表（斜体等自定义样式的定义处）
    assert STYLE_SRC.exists(), f'样式表不存在: {STYLE_SRC}'
    added, want_styles = merge_styles(out, STYLE_SRC)
    print(f"3) {STYLE_MEMBER} 样式声明 {len(want_styles)} 条（新增 {added or '无'}）← {STYLE_SRC.name}")

    # 4) 地图内置字体（斜体字面，OFL）
    fonts = write_fonts(out)
    print(f"4) 包内字体 {len(fonts)} 个 ← {FONT_DIR.name}/: {[Path(f).name for f in fonts]}")

    # 5) 自加贴图（胜利图等，写在地图根目录；漏了就是结算画面找不到贴图）
    dds = write_dds(out)
    print(f"5) 根目录贴图 {len(dds)} 张 ← {DDS_DIR.name}/: {dds}")
    sounds = write_sounds(out)
    print(f"5c) 自加音效 {len(sounds)} 个 ← {DDS_DIR.name}/: {[Path(m).name for m in sounds]}")
    if args.sprite_variants:
        model_defs = sprite_variants([x.strip() for x in args.sprite_variants.split(',') if x.strip()])
    else:
        model_defs = NAILONG_MODELS if args.no_hidden else CUSTOM_MODELS
    models = write_models(out, model_defs)
    print(f"5d) 自加模型 {len(models)} 个 ← {DDS_DIR.name}/: {[Path(m).name for m in models]}"
          f"{'  [只用奶龙（--no-hidden）]' if args.no_hidden else '  [奶龙 + 隐藏立牌 mon3tr/reed/night]'}"
          f"{'  [探针变体 ' + args.sprite_variants + ']' if args.sprite_variants else ''}")
    cover = write_cover(out, args.cover)
    print(f"5b) 街机封面 {args.cover} → {cover}")

    # 5e) 直塞任意成员（探针贴图一类；`包内成员=d:/路径`，可重复）
    for spec in (args.extra_member or []):
        member, _, src = spec.partition('=')
        assert member and src, f'--extra-member 要写成「包内成员=源文件」：{spec!r}'
        data = Path(src).read_bytes()
        put(out, member, data)
        assert sc2map.read(out, member) == data, f'额外成员回读不一致: {member}'
        print(f"5e) 直塞成员 {member} ← {src}（{len(data)} B）")

    # 6) 补丁说明 + 加载页面（写 DocumentHeader/DocumentInfo；zhCN 行并入下面的文案合并，
    #    因为 MPQ 每次写成员都是追加、旧数据不回收，同一成员一次构建只能写一次）
    notes_missing = []
    if NOTES_SRC.exists() and not args.skip_notes:
        overrides = {'DocInfo/Name': args.name} if args.name else {}
        if DESC_SRC.exists() or args.desc_prepend or args.desc_append:
            if DESC_SRC.exists():
                base = DESC_SRC.read_text(encoding='utf-8').strip()
            else:
                base = bh_meta.desc_long(out)      # 已清洗掉作废的「未取得授权…下架」句
            assert base, '读不到地图详情正文，无法按线改写 DocInfo/DescLong'
            overrides['DocInfo/DescLong'] = (args.desc_prepend or '') + base + (args.desc_append or '')
            overrides['LoadingScreen/Tip'] = (
                '企鹅群  795173021<n/>更新日志与百科： https://mafia.melodify.cn'
                '<n/>特别鸣谢《忘却的旋律》的网页支持'
            )
        res, extra = bh_meta.apply_file(out, NOTES_SRC, defer_strings=True, overrides=overrides or None)
        print(f"6a) 补丁说明 {[v for v, _, _ in res]}；加载页面已同步 ← {NOTES_SRC.name}")
        if args.name:
            print(f"6b) 地图名 → {args.name!r}（DocInfo/Name，随文案合并一次写入 zhCN）")
        if args.desc_prepend or args.desc_append:
            print(f"6c) 地图详情：前置 {len(args.desc_prepend or '')} 字 / 追加 {len(args.desc_append or '')} 字")
    else:
        extra = {}
        print('6a) 补丁说明 跳过')

    # 7) 合并自加文案
    entries = {}
    if not args.skip_strings:
        paths = [Path(p) for p in args.strings] if args.strings else sorted(ROOT.glob(STRINGS_GLOB))
        assert paths, '找不到任何 strings 源文件'
        entries = collect_strings(paths)
        entries.update(extra)
        print(f"7) 合并文案 {len(entries)} 条 ← {[p.name for p in paths]}（含补丁说明/加载页面）")

        cur = sc2map.read(out, ZH_STRINGS)
        merged, hz = bh_meta.harmonize_text(sc2map.merge_strings(cur, entries).decode('utf-8'))
        put(out, ZH_STRINGS, merged.encode('utf-8'))
        print(f"7b) 游戏内文案还原（详情页/加载页仍和谐）{'、'.join(f'{k}×{v}' for k, v in hz.items()) or '无命中'}")

        # 7b2) 其余中文语种成员同样过一遍和谐词表：客户端只读 zhCN，但发布包会被平台审核
        #      逐成员扫描，实测 zhCH 里还留着原图自带的「杀」×6、「邪」×1。
        for member in OTHER_CN_STRINGS:
            try:
                cur2 = sc2map.read(out, member)
            except Exception:
                continue

            merged2, hz2 = bh_meta.harmonize_text(cur2.decode('utf-8'))
            if hz2:
                put(out, member, merged2.encode('utf-8'))
                print(f"7b2) {member.split(chr(92))[0]} 文案还原 {'、'.join(f'{k}×{v}' for k, v in hz2.items())}")

        # 7c) 结构自检：DocumentHeader 的条目是「键 + NChz + 声明字符数 + 正文」的长度前缀结构，
        #     **绝不能在外面按字节改写**（改了长度却不动前缀 → 读方解析错位 → 加载页/详情页空白）。
        #     加载页正文一律只经 bh_meta 写入，这里只核对前缀与包内 zhCN 正文字节数是否一致。
        hdr = sc2map.read(out, 'DocumentHeader')
        m = re.search(rb'LoadingScreen/TextBodyNChz(..)', hdr)

        if m:
            declared = struct.unpack('<H', m.group(1))[0]
            m2 = re.search(r'^LoadingScreen/TextBody=(.*)$',
                           sc2map.read(out, ZH_STRINGS).decode('utf-8'), re.M)
            actual = len(m2.group(1).encode('utf-8')) if m2 else -1

            # 前缀 = 该条目的字节长度（含 1–2 字节的额外标记：BOM/终止符），故容差 ±2
            if abs(declared - actual) > 2:
                print(f"✗ DocumentHeader 加载页前缀 {declared} 与 zhCN 正文字节数 {actual} 相差过大，结构已错位")
                return 1

            print(f"7c) 结构自检 DocumentHeader 加载页前缀 {declared} ≈ 正文字节数 {actual} ✓")

    # 8) BankList 预加载表
    fix = subprocess.run([sys.executable, str(ROOT / 'tools' / 'banklist_fix.py'), str(out)],
                         capture_output=True, text=True)
    print(f"8) {fix.stdout.strip() or fix.stderr.strip()}")

    if fix.returncode != 0:
        print('✗ banklist_fix 失败，停止')
        return 1

    # 8b) 测试包依赖：自定义三件改成 file:Mods\…（编辑器手改口径）；发布包保持纯 bnet
    want_local_deps = bool(args.solo or args.local_deps)
    di_text = sc2map.read(out, 'DocumentInfo').decode('utf-8-sig')
    local_markers = [bh_deps.local_value(path) for _, path in bh_deps.CUSTOM_LOCAL]
    if want_local_deps:
        rc = bh_deps.fix_deps(out, check_only=False)
        if rc != 0:
            print('✗ 给测试包改本地依赖失败，停止')
            return 1
        di_text = sc2map.read(out, 'DocumentInfo').decode('utf-8-sig')
        missing_fb = [m for m in local_markers if m not in di_text]
        leaked_bnet = [name for name, _ in bh_deps.CUSTOM_LOCAL if f'bnet:{name}/' in di_text]
        if missing_fb or leaked_bnet:
            print(f'✗ 测试包依赖未改成纯 file:Mods\\（缺 {missing_fb} 残留 bnet {leaked_bnet}）')
            return 1
        print(r'8b) 测试包依赖：自定义三件已改成 file:Mods\… 纯本地路径')
    else:
        leaked = [line.strip() for line in di_text.splitlines()
                  if any(m in line or m.replace('\\', '/') in line for m in local_markers)]
        missing_bnet = [name for name, _ in bh_deps.CUSTOM_LOCAL if f'bnet:{name}/' not in di_text]
        if leaked or missing_bnet:
            print('✗ 发布包自定义 mod 应保持纯 bnet（不要 file:Mods\\）：')
            for line in leaked:
                print(f'    {line}')
            if missing_bnet:
                print(f'    缺少 {missing_bnet}')
            return 1
        print('8b) 发布包依赖：自定义 mod 保持纯 bnet')

    b = bh_meta.budget(out) if NOTES_SRC.exists() and not args.skip_notes else None
    if b:
        print(f"   说明：最新 5 版 {b['shown_lines']}/100 行，最长 {b['longest'][0]}/140 字符")
        for line in NOTES_SRC.read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.lstrip().startswith('#') or line.startswith('@'):
                continue
            num = line.split('\t')[0].split('  ')[0].strip()
            if not num.isdigit():
                continue
            if not re.search(rf'^DocInfo/PatchNote{int(num):03d}=', sc2map.read(out, ZH_STRINGS).decode('utf-8-sig'), re.M):
                notes_missing.append(num)

    # 回读校验
    zh = sc2map.read(out, ZH_STRINGS).decode('utf-8-sig')
    missing = [k for k in MUST_HAVE_KEYS if not re.search(rf'^{re.escape(k)}=', zh, re.M)]
    style_txt = sc2map.read(out, STYLE_MEMBER).decode('utf-8')
    style_missing = [n for n in want_styles if f'name="{n}"' not in style_txt]
    files = subprocess.run([str(ROOT / 'tools' / 'mpqc' / 'mpqtool'), 'list', str(out)],
                           capture_output=True, text=True).stdout
    font_missing = [m for m, _ in FONTS if Path(m).name not in files]
    dds_missing = [m for m, _ in DDS_ASSETS if m not in files]
    sound_xml = sc2map.read(out, SOUND_DATA).decode('utf-8')
    sounds_missing = [sid for sid, _, member, _ in CUSTOM_SOUNDS
                      if Path(member).name not in files or f'id="{sid}"' not in sound_xml]
    model_xml = sc2map.read(out, MODEL_DATA).decode('utf-8')
    models_missing = [mid for mid, _, m3member, _, texmember, _ in model_defs
                      if Path(m3member).name not in files or Path(texmember).name not in files
                      or f'id="{mid}"' not in model_xml]
    cover_missing = [m for m in ('Preview.dds',) if m not in files]

    print(f"   回读: zhCN {len(zh.splitlines())} 行；Triggers={'Triggers' in files}；"
          f"BankList={'BankList.xml' in files}；自加键缺失={missing or '无'}；"
          f"样式缺失={style_missing or '无'}；字体缺失={font_missing or '无'}；贴图缺失={dds_missing or '无'}；"
          f"音效缺失={sounds_missing or '无'}；模型缺失={models_missing or '无'}；"
          f"封面缺失={cover_missing or '无'}；说明缺失={notes_missing or '无'}")

    if missing:
        print('✗ 自加键缺失，界面会显示原始键名')
        return 1

    if notes_missing:
        print('✗ 补丁说明缺失，地图详情里看不到这几条')
        return 1

    if style_missing:
        print('✗ 样式定义缺失，斜体所用的样式查不到')
        return 1

    if font_missing:
        print('✗ 包内字体缺失，斜体字面会回落到系统字体')
        return 1

    if dds_missing:
        print('✗ 自加贴图缺失，结算画面按图名找不到贴图')
        return 1

    if sounds_missing:
        print(f"✗ 自加音效缺失 {sounds_missing}，对应 SoundPlay 会没声音")
        return 1

    if models_missing:
        print(f"✗ 自加模型缺失 {models_missing}，数据编辑器里看不到这个模型")
        return 1

    if cover_missing:
        print('✗ 街机封面缺失（Preview.dds），战网条目没有预览图')
        return 1

    print(f"✓ 打包完成 {out}  ({out.stat().st_size} 字节)")
    return 0


def _guarded() -> int:
    try:
        return main()
    except BaseException:
        out = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--out=')), None)
        if out is None and '--out' in sys.argv:
            i = sys.argv.index('--out')
            out = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
        if out and Path(out).exists():
            Path(out).unlink()
            print(f'✗ 打包中断，已删除半成品 {out}')
        raise


if __name__ == '__main__':
    sys.exit(main())
