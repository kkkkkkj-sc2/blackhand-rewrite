# AGENTS.md — 黑手：升温 脚本二改工程

> 本文件是**长期维护**的工程约定，任何改动前先读它。
> 详细操作手册见 `docs/ROLE-PIPELINE.md`；设计见 `docs/BLACKHAND-REWRITE.md`。

## 工程定位

- **改版定位**：玩家自维护二改（原作者长期停更）；**原作者 = 國仕、無雙**（简体「国士无双」，也就是原图 `gv_管理员名称` 里 `1315FC99` / `EF03967D` 两个键的作者名；更早的上游原作 = Dark.Revenant 的《Mafia》，见地图 `DocInfo/Author`）。**已于 2026-09-13 获得原作者口头授权**（原作者在群内看到改版后直接把授权给了用户；用户决定**不对外宣称**，只删掉旧的「未取得授权 / 立即下架」声明句、不新增授权声明，见 `bh_meta.AUTH_NOTICE`）。对外说明仍须写明 ① 原作者 ② 致谢与企鹅群/百科链接。**永不收费**（不收赞助/打赏/任何费用，不设付费门槛）；原管理员的权限与署名一律完整保留，二改 handle 的管理员名留空、不得冒名。
- 以**原图**（黑手：升温）为基底，通过**外挂 Galaxy 脚本**替换/扩展核心逻辑；
- 保留原图地形、美术、UI、角色卡、行动面板与演出；
- 主脚本：`work/blackhand/CustomLogic.galaxy`（唯一维护目标）；
- 基线地图：`work/boot2-user.SC2Map`（含用户的变体修改、**游戏属性/隐藏属性**，以及地图信息里的原作者署名/致谢/游戏内更新日志（旧的「下架承诺」句已在打包第 ⑥ 步按 `bh_meta.AUTH_NOTICE` 删除），**不要覆盖**）。历次备份：`.baseline-0909`（原图作者版）、`.baseline-0912-pre-attrs`（改图第一版，隐藏属性之前）。用户每次在编辑器里改完（游戏属性只能这么改），都把另存的整图收为新基线 —— 打包器"内容相同就不写"，接管不会虚胖；用户编辑版留档 `work/remote-shw<NNN>-user-edit.SC2Map`）；
- 仓库：https://github.com/mon3stera/blackhand-rewrite（私有）。

## 知识索引（AGENTS.md 放通用知识，专题在记忆里）

**本文件只放「每个任务都用得上」的铁律、标准循环与红线**；下列专题已迁入项目记忆，用 `ctx_search` 按表格里的关键词检索（不要凭印象改，先搜）：

| 要做的事 | 检索词 |
|---|---|
| 加/改成就、成就存档兼容、见微知著、影缝 | 「成就体系 见微知著 影缝 gv_bankOtherAchievements A3」 |
| 加/改变体预设、随机槽选项、座席排序 | 「预设系统 preset_gen 随机槽使能串 座席排序」 |
| 单人测试、虚拟占位补位、-prefer 优选 | 「单人测试 -solo 占位玩家 prefer」 |
| 新增/改造角色（11 步流程、清单、死亡三件套） | 「新增角色端到端流程」「一个角色要改的地方」 |
| 角色上界/审查页自洽的机器检查（**不需要 spec**）与按需的登记 spec | 「角色登记表 role_gen 上界族 审查页映射」 |
| 加的六道打包门挡什么（Wait 调用图 / 死因字母码 / 镜头覆盖 / 卡片栏位） | 「打包门 wait_graph 死因字母码 镜头覆盖 角色卡栏位」 |
| 夜晚镜头组、行动面板/开关按钮、访问措辞 | 「夜晚镜头体系 行动面板 开关按钮 措辞 访问」 |
| 「进图即清档」根因、bank 预加载与 BankWait | 「bank 清档 BankList BankWait」 |
| 探员线索 / 案底 / 警长「可查出X」开关 | 「探员 警长 案底 可查出 gv_roleInvestigatorArray」 |
| 胜利图、结算画面、dds 出图规格 | 「胜利图 WinScreen dds 图码」 |
| Galaxy 语言陷阱、补丁与断言踩坑（含 **text/string 类型**：text→string 引擎里无函数可转） | 「Galaxy 陷阱 soundlink 断言 白名单 斜体 text string 隐式强制转换」 |
| 保存格多槽位（银行 I/Slot&lt;N&gt;Code|Name、面板第 10 项、shw255 修的四个 bug） | 「保存格 槽位 saveSlot gv_saveSlotCode ActiveSlot SHWSLOT」 |
| 天选者(3/32) 规格、洞察/雷击/免死、新角色 UI 坑 | 「天选者 雷击 guess 洞察 卡片底色 换行」 |
| 审判台免死、处决点、跳过审判恢复白天 | 「审判台 免死 处决 gf_EExecution gf_TXResumeDay」 |
| 角色号 >30 要放宽的上界、死因字母码、命令注册 | 「上界 放宽 数组身份 shw115 验尸官 字母码 命令注册」 |
| 夜间按钮点不动、行动面板接线、角色首胜与 -alist、诬陷/栽赃 | 「行动面板 gv_variableOptions 栽赃者 诬陷 首胜 gv_bankRoleAchievements」 |
| 改地图详情 / 补丁说明 / 加载页面文本（不经过编辑器） | 「补丁说明 DocInfo PatchNote DocumentInfo 加载页面 LoadingScreen bh_meta」 |

## 铁律

1. **大括号配平定位函数体**，不要用文本锚点。同一段代码在多个函数里出现，`replace(..., 1)` 会命中错的。
2. **插入后必须验证落点**：①全文 `{}` 配平 = 0；②**打印目标分支/函数的行号范围和条目数**，确认代码在正确的位置。只看配平不够——曾连续三次把代码插进错误的分支。
   - **Galaxy 声明必须先于语句（shw137 事故）**：函数/块内**所有局部变量声明（含 `int autoXXX;`、`const int autoXXX_ae = N;`）必须在任何语句之前**。插桩点只能选在 `// Actions` 或已有语句之后；插进声明块中间 → 编译器在下一条声明处报 `解析函数行出错，可能有无效的变量名/函数调用，或是函数结尾缺失`（dbg9 报 `int init_i;`）。`gt_Init2_Func` 的声明块很长（auto 变量 + `// Variable Declarations` + `// Automatic Variable Declarations` 一直排到 `// Variable Initialization`），**不要在函数开头插任何东西**。
   - **自动变量必须有声明（shw139 事故）**：生成的循环写法 `for ( ; ( (autoXXXX_ai >= 0 && lv_a <= autoXXXX_ae) || …) ; lv_a += autoXXXX_ai )` **依赖声明区的 `const int autoXXXX_ae = N; const int autoXXXX_ai = 1;`**（动态上界写 `int autoXXXX_ae;` 再在体里赋值）。漏掉 → 游戏内 `解析for时出错，可能缺少分号`、**整个脚本读取失败**。自加函数（尤其 preset_gen 生成的 V 函数）必须克隆参考函数 `gf_VBFCZOptions` 的声明块；**改完必跑 `python3 tools/galaxy_lint.py`**（配平 + 962 函数 auto 声明检查，非 0 禁止打包）。
   - **改 `if (...)` 条件必须打印整行人工核对**：`()` 配平检查发现不了"括号位置错"——曾把 `!= 4)) {` 改成 `!= 4)) && (X) {`，配平过但 `&&` 跑到 `if` 外面，游戏报"需要一个左大括号"。正确写法是把新条件并入 `if` 内：`... && (X)) {`。
2a. **python 批量补丁：插入偏移必须在所有前置 replace 之后重新测量**（shw67 事故）。用旧偏移做插入会把新函数插进行中间 → 脚本读取失败 → 游戏取名后卡死。顺序：①提取函数体（`\n}\n` 定位）②对**提取文本**做替换 ③做完其它 rep 后**重新 index 测插入点** ④断言插入点前是 `}`/行首结构，插入后断言新函数位于行首且结构完整。
2b. **用切片拼 `if` 条件时逐行验证 `()` 配平**（shw69 事故）：`w[:-3]` 会把 `...16))) {` 削成 `...16))`，再拼 `|| (X))) {` 多一个 `)`——全文配平仍是 0 但该行解析失败。修完必须对**每个被改的 if 行**做 `line.count('(')==line.count(')')`。
3. **两套角色面板别搞混**（踩坑高发区）：
   - 自设界面（玩家可见）：`gv_rolesMenusItem[1]`，`gf_OSE...` 内按 `gv_roleCategory` 分支，约 86150–86300 行，**逐角色硬编码**；
   - 审查页：`gv_e8A792E889B2E68EA7E4BBB6`，`gf_ASE5AEA1E69FA5E98089E9A1B92`，约 38802 行。
   - 选中项 → 角色号 的映射在 `gt_OSRoleSelect_Func`（约 85413 行），同样是**按列表索引**逐条硬编码。
3.1 **自设列表：两处硬编码已改为「数据源 + 生成器」，不要再手改那两段**（shw247）
   - 结构（了解即可，定位请用工具）：**位置 A** 列表构建在 `gt_OSMenus_Func`，按 `gv_roleCategory` 分段、段内按 `gv_variantSelection` 分档，逐行 `DialogControlAddItem(gv_rolesMenusItem[1], ...)`；**行序就是列表索引（1-based）**。**位置 B** 选中映射在 `gt_OSRoleSelect_Func`，同样分段分档，逐行 `if (SelectedItem == N) gv_roleSelection = 角色号;`。历史上这段结构出过事故（把狱警显示成树妖、删条目后索引整体前移、往中间插导致后续映射全错）。
   - **现在加/改角色的做法**：改 `work/roles-list.json`（一条 = `category` / `variants` / `role` / `prefix` / `suffix`）→ `python3 tools/role_list_gen.py --apply`。
     · 索引 N 由生成器按段内次序算 ⇒ **中间插入、重排、删除都安全**（旧的「只能追加到末尾」铁律作废）；
     · 两处永远同源 ⇒ 不会再出现「A 有 B 没有」；
     · 前缀/后缀文本键沿用同段邻居（前缀常见 `<s val="ModLeftSize20">` 一类，后缀常见 `258B2E40` = `</s>`）。
   - **漂移检测已进打包门（第 0c 步）**：手改那两段、或改了 JSON 忘了 `--apply`，打包直接停下。手动核对用 `python3 tools/role_list_gen.py --check`（口径 = 生成结果与脚本现状**逐字节相同**）。
   - 工具自带两项审计：① 两处段数/段头/角色序列必须一致 ② 每段映射索引必须从 1 连续到 N。
3.2 **不要靠「换槽位」规避遗留代码**：旧角色散落在十几个硬编码分支里，换槽位只会多破坏一个角色。正确做法是**逐处加池判断** `(gv_roles[lv_a][1] == 池)`。
3.3 **判定槽位空闲必须查原图 `work/bh-src/MapScript.galaxy`**，不能凭「没有名称数组」下结论：
   - 池 3 / 18 = **小金执行者**（`gv_roleNameInput[3][18] = "xiaojinzhixingzhe"` + options + 权重），**已被误覆盖过一次**，不要再用；
   - 池 3 / 13 = `duoluoshenpanzhe`（旧堕落审判者），原图**只有拼音名和开关、没有名称/描述**，是真正可复用的遗留空槽；其行为代码仍在（见 3.2）。
3.4 **Test Document 的大厅属性为空**：当前基线**已不需要**强制 `gv_variantSelection = 1`——那是 shw45 时期的死路补丁（变体 1=随机系会命中 `gt_OSRoleSelect_Func` 的禁用子句，添加按钮永远不亮）。当前基线在 Test Document 下自设路径直接可用，**不要再加变体强制补丁**。
4. **改角色要同时改多处**：完整清单见「知识索引」里的记忆（搜「新增角色端到端流程」）。漏一处就"看起来没生效"。
5. **回退文件前先列出已完成的所有改动**，`git checkout` 会把未提交的清理一起还原。
6. **部署用新文件名**（编辑器打开中的地图被锁定），部署后确认 `scp` 无 `failed to upload`。
7. **每次改完立刻提交**，提交信息写清"第几步 / 改了什么"。
8. **测试地图统一放 `D:\StarCraft II\Maps\Test\`**，不要放桌面。
9. **角色号上限红线**：`gv_bankRoleAchievements` 维度是 `int[16][9][21]`——角色卡分支里 `[xx][1][角色号]` 用 21 以上的角色号会数组越界（ScriptError 41358）；31 号角色**不得**做银行成就检查。`gf_VLoadSaveSlot` 的槽位加载校验曾用 `> gv_townMax(30)` 把 31 号槽清零（预设列表空行+实际阵容缺人），已放宽为 `> 31`；再加大于 31 的角色号需同步放宽。

- **`SoundLink` 的参数类型是 `soundlink`**（不是 `sound`）：自定义函数收音效参数写错类型 → 所有调用处报「参数类型同函数定义不匹配」并连带整个脚本解析失败（整图报废）。

## 标准循环

```bash
# 1) 改脚本 + 自检（配平 + 落点）+ 打包
python3 - <<'EOF'
...修改 work/blackhand/CustomLogic.galaxy...
...sc2map.write 写入 CustomLogic.galaxy 与 GameStrings...
EOF

# ⚠ 打包命令不要写成 `python3 tools/boot2_build.py … | tail -3 && scp …`
#   管道退出码取的是 tail 的 0 ⇒ 打包失败也会照常部署（2026-09-12 踩过）。用 `set -o pipefail` 或 ${PIPESTATUS[0]}

# 2) 部署到 Test 里的**新文件名**（不放桌面；同名文件常被编辑器锁住）
scp -o BatchMode=yes work/boot2-<name>.SC2Map "Administrator@100.94.140.84:D:/StarCraft II/Maps/Test/boot2-<name>-<后缀>.SC2Map"
# 发版包直接走 python3 tools/release.py build（它自己改名 + 只投 Test + 打印 md5 核对命令）

# 3) 提交
git add -A && git -c user.name="mon3stera" -c user.email="mon3stera@users.noreply.github.com" commit -q -m "<说明>"
```

验证：游戏内 `File → Test Document` → 看 `Documents\StarCraft II\GameLogs\*ScriptError.txt`（只看最近一次）；`Script compile error` 必修，运行期参数错误先对照原版同类角色判断是否为原图自带。

- 测试指令 `-reveal`（`gt_BHRevealRoles`，游戏开始后；**shw179 起仅管理员 `gv_oP[..][7]` 与二改作者 handle 可用，主机不再可用**）私密列出全部玩家**带色名字**（电脑N，N=玩家编号；投票面板左侧是楼层序，与编号无关）+ 角色名，用于验证调查结果/案底等。
- **测试指令在发布构建里静默失效**（shw179）：`c_bhSoloBuild = false` 时 `-solo`、`-italictest` 直接 return（不报错、不生效）；`c_bhSoloFill` 关掉后开局不再自动补「电脑N」，要单人开满席请在大厅手动加电脑。
- 运行期报错先分新旧：`triggerControl(值:0)`、`StringWord(值:0)`、`CameraSetBounds region(值:0)`、`gv_roll点冷却 int[2] 越界` 等均为基线/单人测试固有，不是新改动引入。

## 角色文案与设计规范

### 文案格式（对齐原图）

| 部分 | 格式 | 示例 |
|---|---|---|
| 名称 | `<c val="颜色">名字</c>`，不带字号标签（面板会套用大字） | `<c val="DE8421">系命人</c>` |
| 背景介绍 | **白色正文**，一段 | `影武者是一名隐于市井的杀手……` |
| 能力介绍 | 空两行后接 **天蓝色** `<c val="BBDDFF">…</c>` | `<n/><n/><c val="BBDDFF">每晚选择两名玩家……</c>` |

角色名颜色按阵营：城镇青绿 / 黑手党红、橙红、玫红 / 三合会蓝、蓝紫（不是黄）/ 中立按主题（影武者 = 银灰 `C0C0C0`）/ 随机组灰；新角色以现行 GameStrings 配色为准。

**渐变色名称（shw131/132，用户要求）**：`<c val="上色-下色">` 支持上下渐变，但**每段必须是 8 位 ARGB**（如天选者 `FFFFFF99-FFFF8800`）——**6 位色值（`FFFF99-FF8800`）是非法标签，会让整张地图「无法运行游戏」**（shw131 事故：GameStrings 里一条非法文本标签 = 地图加载失败，且无 ScriptError）。名称色等用户验收；若 8 位仍不渲染渐变再回退单色。

### 国服和谐用词（shw147 沉淀；「杀」已于 2026-09 改回）

**「杀」可以过审，新文案直接写杀**（杀死、杀手、击杀、谋杀、射杀、截杀、自杀、杀人）。原图曾把「杀」整字换成「爱」（爱死、爱手、谋爱、击爱、连环爱手、爱人狂……）。打包时 `bh_meta.restore_kills` 按词表把这些替身改回，所以基线 zhCN 里的旧文案不用逐条手改。

留下不改的「爱」：可爱了、亲爱的、挚爱、你的爱吧、相爱。不要把这些再改成杀。

**游戏内和谐文本已经还原；今后新文案直接写「黑手党」**（用户 2026-10-22 明确），不要再写「黑手D」。现行 `bh_meta.harmonize_text` 对游戏内键使用 `GAME_RESTORE`，将黑手D、jian谍、zf、协教等替身还原为黑手党、间谍、政府、邪教等原词。**地图详情 `DocInfo/*` 与加载页 `LoadingScreen/*` 仍保留现有独立策略**，只有这两类继续使用 `HARMONIZE_PAIRS`（黑手党→黑手D / 间谍→jian谍 / 政府→zf / 邪→协）；不要把这套替换重新施加到整张 zhCN。词表唯一实现仍在 `tools/bh_meta.py`。

- **自加文案不要再写爱死、爱手、谋爱、击爱**；写成杀死、杀手、谋杀、击杀。案底写法 = `非法闯入，谋杀`。

- **加载页面正文有 800 字上限（编辑器口径 = UTF-8 字节减去 `<n/>` 标签）**：`LoadingScreen/TextBody`（包内 zhCN）超限时编辑器会显示「文本长度 1636 / 800」并可能静默截断。`tools/bh_meta.py` 的 `loading_body()` 现在**自带预算**（`LOADING_LIMIT=800` / `LOADING_RESERVE=40`，`loading_units()` 复刻编辑器口径）：说明行按「旧→新」传入，装不下就**从最旧的开始丢**，只保留最新若干条，打包时打印 `加载页面 757/800（保留最新 6 条，截去较早 12 条)`。完整日志仍在地图详情页（前言里已写明）。 取舍方向由 `patch-notes.txt` 的 **`@loading-keep front|newest`** 决定（`front` = 优先展示靠前的重头戏，适合本版对玩家全新时；默认 `newest`）。

- **`DocumentHeader` / `DocumentInfo` 是「长度前缀」结构，只能经 `bh_meta` 写**（shw202 事故）：条目形如 `<键>NChz<2 字节 LE 长度><正文(UTF-8)>`，长度 = 正文的**字节数**（含 1–2 字节额外标记，实测 ±1）。**在外面按字节 replace 会改长度却不动前缀 ⇒ 读方解析错位 ⇒ 加载页面/地图详情页「时有时无、整体空白」**（shw199 加的 7c 步就这么踩了；shw202 撤掉改写，改成 `7c)` 结构自检：读 header 里 `LoadingScreen/TextBody` 的前缀与包内 zhCN 正文字节数比对，差 > 2 即拒绝出包 —— 该自检第一次运行就抓到了这个 bug）。和谐修正（7b）只作用于 **zhCN 纯文本表**（安全）；header 里原图旧补丁说明的用词如需清理，必须走 bh_meta 的写入口。
- **原图遗留的天选者素材（未接线，可复用）**：`B0292835` = 该角色的完整描述（「[非官方]一个天神的凡人化身，有着不朽之躯…若预测成功，那么在次日天选者将无法被公开处死」）、`47843C61` = 「- 你可召唤 5 次雷击」（**作者原始设计是 5 次**）、`19E7B48E` = 「你无法再次召唤雷击。」、`3790B10C` = 「你被 天选者 的雷击杀死了。」（库存原文仍是旧替身「爱死」，打包时改回）、`A22C4229` = 能力行、`6B6EC9D0` = 验尸官线索、`58366F04` = 死亡描述、`757361A4`/`A228729A` = 行动确认。这些键在现行脚本里**引用数为 0**（作者开发残留），我们的 天选者(3/32) 是这套未实装设计的落地。

### 能力开关

原图每个角色需要四组数组同时存在，缺一不可：

```galaxy
    gv_roleOptionExists[池][角色][i]     = true;          // 该开关存在
    gv_roleOptionsImportant[池][角色][i] = 2;             // 显示权重/样式
    gv_roleOptionsText[池][角色][i]      = StringExternal("Param/Value/键");  // 标签文案
    gv_roleOptions[池][角色][i]          = true/false;     // 默认值
```

开关标签**沿用原图既有措辞**（如「在夜间无敌」），不要自创说法。

### 阵营设计惯例

| 阵营 | 惯例 |
|---|---|
| **中立·致命** | **默认永久夜间无敌**（`gv_roleOptions[...][0] = true`，标签「在夜间无敌」） |
| 中立·温和 | 一般无夜间无敌 |
| 城镇 | 无夜间无敌；调查/保护类有各自开关 |

### 银行与存档（不验签设计决定 + 迁移）

- **不验签设计决定（shw139/143，取代 shw134 的临时旁路）**：目标是**原图存档直接复制即可用**（跨命名空间迁移、不重签）。两处一起关：①脚本侧三处 `BankVerify` 门槛（QQ/gift/I，3676/3680/3684 附近）加常量 `c_bhNoSigVerify = true`（条件前置，`BankVerify` 本身不执行）②`gt_Init2` 银行循环的 `BankOptionSet(gv_bank[lv_a], c_bankOptionSignature, …)` 改 **`false`**（引擎侧不签也不验；若为 `true`，引擎对**原作者签名**的档验签失败并清空内存内容 → 脚本看到空档 → 走新玩家分支 → 界面报「存档已重置」）。**原有的 `<Signature>` 行保留不动做兼容**，防篡改由地图级 Checker 承担（`Math=(points+1)×(points+3)` 等）。
  - 历史（shw134，已被取代）：曾以为引擎 `BankVerify` 失败即清档是唯一根因，只对 `c_bhSoloBuild` 短路放行；BankList 定案证明那只是表象。
- **迁移操作**：把 `key`、`MBank13` 两份档复制到改版作者命名空间即可（私有发布时作者 = 发布者本人 toon），**无需重签**。重签算法（`tools/bank_resign.py` 备查）= SHA1(authorID + playerID + bankName + Σ(按名排序的 section.name + Σ(按名排序的 key.name + "Value" + 类型名 + 值)))，已实测可复现引擎签名。
- **「进图即清档」的根因与实证在记忆里**：搜「bank 清档 BankList BankWait」——包内 `BankList.xml` 必须声明 `MBank13`/`key`（否则 `BankLoad` 永远空档），且 `BankLoad` 后必须 `BankWait` 同步；两件事分别由打包管线的 `banklist_fix.py` 与脚本内 `BankWait` 保证，**漏任一件症状都是每局清档**。

### 打包管线（shw96 事故沉淀，shw141 固化为一键工具）

**boot2 系列只能用「复制上一版 + `sc2map.write` 直写 CustomLogic.galaxy」，绝不能用 `tools/sc2pack.py`**（shw96 事故：触发器读到旧脚本 → 「脚本读取失败：无法找到函数」+ UI layout 红字）。标准做法：

```bash
python3 tools/boot2_build.py --out work/boot2-<name>.SC2Map      # 八件套 + 全部回读断言
python3 tools/boot2_build.py --out work/boot2-<name>-solo.SC2Map --solo  # 单人测试包：只改包内开关，不动源码
```

八件套（BankList 那件的根因见记忆）：①复制基线 `work/boot2-user.SC2Map`（**不要覆盖**）②直写工作区脚本（打包前自动跑 `galaxy_lint.py`，不过不打包）③并入样式表 `work/blackhand/NewFontStyles.SC2Style`（斜体 `ModItalic` 的定义处；漏 = 名字里的 `<i>` 改写后无样式可查、不斜体，shw88–153 一直是这个状态）④并入包内字体 `work/blackhand/fonts/` → `Fonts\*.ttf`（斜体字面，OFL 许可文本一起分发；漏 = 斜体回落到游戏字体）⑤自加贴图 `data/*.dds` → 包内**根目录**（自加胜利图；漏 = 结算画面按图名找不到贴图，shw100–168 一直缺 shw98 那两张）⑥**补丁说明 + 加载页面**：`tools/bh_meta.py` 读 `work/blackhand/patch-notes.txt` 写进 `DocumentInfo`（版本表）+ `DocumentHeader`（条目表），并把 zhCN 行交给下一步合并；同一次写入里还会按 `AUTH_NOTICE` 删掉地图详情页（`DocInfo/DescLong`）里原作者授权后已作废的「未取得授权…会立刻下架」句（与补丁说明共用一个 `set_notes`，避免多写一次 `DocumentHeader` 白胖 8.8 KB） ⑦合并 `strings-*.txt` → 包内 **zhCN** 表（漏 = 界面满是 `Param/Value/XXX` 原始键；`sc2map.GAME_STRINGS` 指的是 enUS，别拿它校验）⑧`banklist_fix.py` 写回 `BankList.xml`（漏 = 每局清档）。

- **MPQ 里每个成员一次构建只能写一次**（2026-09-12 实测）：`sc2map.write` 走 `mpqtool replace`，**旧数据不回收、只追加**——原样重写 zhCN 一次就白胖 306 KB、DocumentHeader 8.8 KB。故 ⑥ 生成 zhCN 行后**必须交给 ⑦ 的合并一起写**，不能自己再写一遍（曾因此一次构建多出 631 KB）。

- **凡是「手工塞进当次产物」的资源都会在下次打包时静默消失**（斜体样式 shw88–153、胜利图 shw100–168 都栽在这里）：任何自加资源必须登记进打包管线 + 回读断言，不能只 `sc2map.write` 一次。
- **编辑器另存过的图不能直接玩 / 发布**（2026-09-12 实证）：编辑器保存会把包内 `BankList.xml` 重写成引擎自带的 5 条，**丢掉 `MBank13` / `key` 声明 → 每局清档**（与 shw137 同源）。用户在编辑器里改完地图信息后的正确流程：① `scp` 把图拉回来 ② **只注入元数据成员**（`DocumentHeader`、`DocumentInfo`、`DocumentInfo.version`、zhCN `GameStrings.txt`；`(attributes)` 是 MPQ 特殊成员，`mpqtool replace` 写不进去、报 `SFileAddFileEx err 10003`，实测只有二进制噪声、可跳过）③ 再跑一次 `boot2_build.py`（第 ⑧ 件把 BankList 写回）④ 部署新文件名。
  - **编辑器另存的整图可以直接当基线**（shw184 起）：打包器写成员前先比字节、相同就跳过（`put()`），实测只比输入多 277 字节。旧结论「会虚胖 1.8 MB」已随 shw183 的内容比较失效。**游戏属性/隐藏属性只能靠这条路**：它们在 XML 成员 `Attributes`（`<AttributeHidden Namespace="999" Id="…"/>`）与二进制 `(attributes)` 里，后者 StormLib 写不了（名字以 `(` 开头一律 `SFileAddFileEx err 10003`）。
  - 注入元数据时先比对 `DocumentHeader` 的可读串差异，确认**只有 `DocInfo/PatchNote*` 与 `DocInfo/Desc*` 变化**（变体、依赖、玩家槽位未动）再落盘。
- 胜利图出图规格：732×376（系命人 377）×24bit 未压缩无 mipmap，文件长 = 128 字节头 + w×h×3；头 128 字节在 732×376 各图间完全一致，可直接复用（`data/*.dds` + 同名 PNG 源文件留档）。**像素必须按 BGR 存放**（DDS 的 mask 是小端 DWORD，24bit 打包内存序为 B,G,R）——写成 RGB 会让红蓝互换（金色→蓝色、血红→蓝、红金小丑帽→紫，shw169 事故）。出图走 `python3 tools/png2windds.py <源图.png> <输出.dds>`，不要手搓 `tobytes()`。
- **字节序验证必须用有颜色的参照图**：灰度/单色图（作者的 `WinPlaguerReal.dds` 是灰字）分不出 RGB/BGR，当年据此误判成 RGB。对照用 `work/mm2.SC2Mod` 的 `WinMafia.dds`（BGR=血红 ✓）/ `WinJester.dds`（BGR=红金小丑帽 ✓）。

- 回读断言：`Triggers` 在、`BankList.xml` 在、脚本含 `BankWait`、**`MUST_HAVE_KEYS` 全部存在**（缺任一即退出码 1）。只有基线已是上一版成品图、且确认键齐全时才用 `--skip-strings`。
- **文案源文件铁律**：`strings-*.txt` 一行一个 `键=值`；**一行粘两个键会静默吞键**——`strings-gcz.txt` 曾把 `GCZBOX2` 与 `GCZTNAME` 粘一行，导致天谴菜单名在所有构建里都显示原始键、`GCZBOX2` 值被污染（正是 `MUST_HAVE_KEYS` 抓出来的）。
- **boot2 包内结构**：`Triggers` + 2.7KB `MapScript.galaxy`（只含 `include "TriggerLibs/NativeLib"` 与 `include "CustomLogic"`）+ 完整 `CustomLogic.galaxy`；**触发器链引用 CustomLogic 里的函数**，故回读校验看包内 `CustomLogic.galaxy`（不是 MapScript）。
- **`sc2pack.py`**（rogue 等独立图用）把 galaxy 塞进 MapScript 并剥触发器 → boot2 缺触发器函数必炸，两条管线不能混。

### 发版（试验线持续更新，主线只收大更新，2026-09-13 起）

平台审核要排队（周末尤其慢），大改动不能直接推给玩家 ⇒ 两条线分工：
**preview = 试验线「黑手：Revision Preview」**（**每版都投这里**，用真实对局验证；想玩最新内容来这条线）、
**main = 稳定主线「黑手：升温 Revision」**（**只收大更新** = `patch-notes.txt` 的 `@promote major`，且必须先在 preview 验证通过）。
**两条线必须用同一个账号发布** —— bank 命名空间取作者 toon（不是地图名），所以玩家存档/成就/积分互通，试验线上测的就是真实线上档。

```bash
python3 tools/release.py status                      # 版本、@promote、各线状态、已发 tag、**下一步该做什么**
python3 tools/release.py build                       # 按状态机出该出的那条线的包，**改名后只投放 D:\StarCraft II\Maps\Test\**
python3 tools/release.py mark --channel preview --status 实测通过
python3 tools/release.py mark --channel main --live 1.108 --status 已通过
python3 tools/release.py tag                         # 发版后打 git tag（= 这一版已出厂的不可变标记）
```

- **状态机**：新版先在 staging（preview）投出 → 等平台过审 + 在那边实测 → `mark 实测通过` →
  若本版 `@promote major` 才轮到 stable（main）；`@promote hold`（默认）就只留在 preview。
  没验证过的版本不会被放行推主线（`status` 会明说原因）。
- **`@promote` 写在 `patch-notes.txt`**（`major` / `hold`）：删掉它就是 `hold`。
- **投放只去 `D:\StarCraft II\Maps\Test\`，而且必须改名**（用户 2026-09-14 定）：`release.py build` 走 **Windows 直连** `scp`，落地名 = `<包名>-<后缀>.SC2Map`（`--deploy-suffix`，默认「月日-时分」）。**不放桌面**；Test 里同名文件常被编辑器锁住（覆盖报 `dest open … Failure`），而新旧同名包混放正是 2026-09-14 误传旧包的根源。平台只看**包内地图名**（`DocInfo/Name`），文件名随便取。
- 台账 `work/release-channels.json`：每线的 `role` / `live`（平台已通过）/ `pending`（在审或待投）/ `status` / 包 md5。
  **版本号唯一真源仍是 `patch-notes.txt` 的 `@release`**。
- 备线的地图名走打包器 `--name`：它在**第 ⑥ 步**与补丁说明同一趟写进 `DocumentHeader`（含 enUS/zhCN 两份副本）+ zhCN；**别事后单独调 `bh_meta set`** —— 那会第二次写 zhCN，白胖约 300 KB。
- 守卫：`build` 拒绝把比线上更旧的版本投回去、拒绝重复投同一版（修包重投用 `--force`）；往还有版本在审的同一条目再投会先警告（平台会怎么处理未验证）；`tag` 要求工作区干净且 tag 名与 `@release` 一致。
- **改过名的线，上传会被平台拒**：报错文案是「发布名称必须与各个地区的前一个版本名称相同」——英文原文 `Publish names must match the previous version for all locales`，**locales = 语言槽，不是服务器大区**（暴雪中译误导）。包内 `DocInfo/Name` 只有 enUS + zhCN 两个槽、`--name` 也只覆盖这两槽；平台另存着每个 locale 的旧名。
  解法：在编辑器 `文件 → 发布…` 的**配置选项 → 更改名称 → 勾「应用到所有语言环境」**改名后再上传（2026-09-14 实测通过）。重启编辑器 / 清缓存 / 改包内名字都没用；实在不行按线上旧名重出包（`--name "<旧名>"`），或新建条目。`.SC2Map` 里没有战网 Document ID（`CaptionId` 恒为 1，是分类 id）。
- 推 main 时打包器会提醒：**补丁说明要覆盖自「主线 live 版本」以来的全部改动**（主线玩家跳过了中间几版）。

## 环境

| 项 | 值 |
|---|---|
| 远程 | `ssh -p 2222 administrator@100.94.140.84`（WSL，`/mnt/d` 即 `D:`）；**WSL 不通时直连 Windows**：`ssh Administrator@100.94.140.84`（22 端口、cmd 外壳），部署 `scp 文件 "Administrator@100.94.140.84:D:/StarCraft II/Maps/Test/"`，校验 `certutil -hashfile "<路径>" MD5` —— 2026-09-13 WSL 那台掉线时这条路仍然可用（快得多） |
| 游戏 | `D:\StarCraft II`，版本 5.0.15.97579 |
| 编辑器 | 必须由用户在交互式桌面手动启动（SSH 启动会 D3D 报错） |
| 打包工具 | `tools/sc2map.py`（读/写 MPQ）、`tools/mpq.py`、`tools/mpqc/mpqtool` |
| 文本工具 | `tools/bh_roles.py`、`tools/bh_text.py` |

## 文档地图

| 文件 | 内容 |
|---|---|
| `AGENTS.md` | 本文件：工程约定、铁律、标准循环 |
| `docs/ROLE-PIPELINE.md` | **加/改角色的完整手册**（收口后的真实流程：spec → 生成器 → 抽取 → 六道打包门 → 实测；附事故对照表） |
| `docs/BLACKHAND-REWRITE.md` | 重写设计与实施进度 |
| `docs/BLACKHAND-ORIGINAL.md` | 原图逆向笔记（流程、计时、数据模型） |
| `docs/GALAXY-PIPELINE.md` | Galaxy 直写、打包、启动链路技术细节 |
| `docs/role-catalog.md` / `docs/PATCH-NOTES.md` / `docs/QUESTIONS.md` | 角色总览 / 各版补丁说明底稿 / 待决问题 |
| `docs/HANDOFF.md` / `docs/HANDOFF-SHADOW.md` / `docs/HANDOFF-NEXT.md` | **历史交接文档（已过期）**：早期影武者接入、槽位误判、自设面板双硬编码、目标转换规则等背景资料，只作追溯（`docs/SHADOW-ROLE.md` 已不存在，内容并入角色手册与记忆） |
