# shw318：侦探信息复用独立审计

审计基点：`9830e59`（shw317 职业转换特性完成后）。本次只改四个既有反馈函数，新增一个 helper 和前向声明；集成测试、打包及回读已完成，未做引擎实测，见文末。

## 1. 根因：侦探不是探员

- **侦探 = 城镇 1/15，Tracker**：[反馈入口](<../work/blackhand/CustomLogic.galaxy#L93608-L93611>)。
- **探员 = 城镇 1/4，Investigator**：职业/武器线索入口 `gf_SKF_1_tanyuan`，不属于本次修复。联邦探员和两帮探员对应分支也未修改。
- 新版侦探早已使用 `DT*` 原因提示、第二访问槽、`gv_bhVisitMoved` 权威干扰标记。密探 2/10、先锋 5/10 却各复制了一整段旧版侦探推断，**并未调用新版**。
- 旧副本漏第二访问槽、凭 `action != visitation` 猜干扰、限制后仍泄露原计划目标；无访问时两家的 `||`/`&&` 条件不一致，先锋无行动时可能错误声称「本计划出门」。调查免疫也只在部分旧分支生效，实际访问非零时可能泄露去向。
- 副手 1/21 **学会技能位 `[3]` 后本来就调用新版侦探**，没有第二份详细旧副本。问题在未学会时独有的粗略出门判断：只读第一槽，漏第二槽。

旧函数原文保存在[真实旧函数夹具](<../tools/fixtures/detective-feedback-before.galaxy>)，包含源脚本 SHA256 和四条原反馈调用守卫；四个反馈函数逐字等于 `9830e59`，不是为测试重写的逻辑。

## 2. 当前统一规则

[唯一详细反馈 helper](<../work/blackhand/CustomLogic.galaxy#L93533-L93605>) 为 `gf_BHDetectiveFeedback(observer, target, ignoreImmune)`，只负责发给调查者的私密提示，不负责角色资格、冷却、案底和访问写入。

优先级由高到低：

1. **目标被囚禁**：报告无法外出。
2. **目标被限制**：报告「迷人的人接近」及限制原因；不泄露其原计划目标。
3. **目标调查免疫且未获穿透权限**：按「没有行动」及通用原因处理，不暴露去向或免疫身份。
4. **两个非零且不同的实际访问槽**：按槽顺序报告两人及多访问原因；优先于干扰解释。
5. **确有 `gv_bhVisitMoved` 且实际第一去向与 `action[target][0]` 不同**：报告原计划/实际去向及干扰原因。支持「原想不行动却被迫出门」和「原计划出门却未出门」。仅选中目标不同，不足以推断干扰。
6. **访问自己**：有所行动、未访问他人，附原因。
7. **单个外部访问**：报告编号、带色名字。
8. **无实际访问**：报告没有行动及通用原因；不会拿未执行的面板选择冒充访问。

防御性边界：若只有第二槽非零，则将它作为唯一实际访问，避免旧新版组合文案打印「玩家 0」；重复双槽只报一次。无效调查目标 `0` 或 `>15` 静默返回。这不增加角色资格。

`action[target][1]` 不是第二访问槽；只看面板选了两人，不代表登门两家。目标实际位置 `gv_location` 也不是本反馈的数据源。

## 3. 分发与开关：保留原资格，不扩权

[原反馈分发表](<../work/blackhand/CustomLogic.galaxy#L14374-L14470>) **逐字未改**：

| 路径 | 原资格 | 本次如何复用 |
|---|---|---|
| [侦探 1/15](<../work/blackhand/CustomLogic.galaxy#L14424-L14428>) | `visitation != 0`、当夜未死、职业池 1/角色 15 | 调统一 helper，穿透权限仍为 `roleOptions[1][15][0]` |
| [副手自身粗报/身份](<../work/blackhand/CustomLogic.galaxy#L14374-L14378>) | 职业池 1/角色 21、当夜未死；内部再判断访问、学会位和成长层数 | 未学 `[3]` 仍仅报告出没住所，增加 vis2；不报名字、原因或详细计划 |
| [副手学会侦探](<../work/blackhand/CustomLogic.galaxy#L14424-L14428>) | `visitation != 0`、当夜未死、职业池 1/角色 21、学会位 `[3]` | 原来就调用侦探入口；继续继承侦探的穿透开关 |
| [密探 2/10](<../work/blackhand/CustomLogic.galaxy#L14459-L14463>) | `visitation != 0`、当夜未死、职业池 2/角色 10、冷却 0 | helper 固定传 `false`，**不借用城镇侦探穿透开关** |
| [先锋 5/10](<../work/blackhand/CustomLogic.galaxy#L14466-L14470>) | 同上，职业池改为 5 | 同密探，固定 `false` |

- 分发仍按职业数组 `gv_roles`，不是 `gf_BHFaction` 的真实阵营；本项不改 shw317 的职业转换/学徒学习规则，也不另给转换后玩家制造一条信息分发。
- 调查者被限制时，既有 `gf_BHBlock` 经 `gf_BHVisitNone` 清两个槽；原守卫因此阻止反馈。原守卫没有额外的调查者限制检查，本项不擅自补一套不同资格。
- 被跟踪的对象用**调查者最终 `gv_visitation`**，不是调查者面板原目标。调查者被重定向后，应查看新对象当晚的访问。
- 城镇侦探 `[1][15][0]` =「无视调查免疫」，默认 true。密探/先锋 `[pool][10][0]` 是无杀人职业时转党徒/暴徒，**不是**无视调查免疫；`[1]`/`[2]` 是影随 1/2 晚间隔，分别写冷却 2/3（原来的后者覆盖前者逻辑不变）。
- 副手 `[1][21][0..3]` 仍是不会被随机抽中、从首晚获得能力、开局自带能力、提前知道身份；不是新增调查穿透权限。成长、随机学会、五层身份与六层全名单及成就完全保留，包括原成长条件的既有语义。
- 副手学会 `[3]` 时原分发表还另行调用 `gf_SKF_1_jianshizhe`，仍保留监视者反馈，不因收口侦探而消失。

## 4. 调用链盘点与不变部分

| 阶段 | 函数/位置 | 审计结果 |
|---|---|---|
| 点击 | [侦探](<../work/blackhand/CustomLogic.galaxy#L89539-L89561>) / [副手](<../work/blackhand/CustomLogic.galaxy#L89675-L89697>) | 各自写 `action[0]`，点击自己取消；仅行动确认，不生成调查结果 |
| 点击 | [密探](<../work/blackhand/CustomLogic.galaxy#L90809-L90877>) / [先锋](<../work/blackhand/CustomLogic.galaxy#L91782-L91850>) | 按各自 `variableOptions[2]` 保留队友行动确认广播；不是把调查结果公开给全队 |
| 夜间准备 | [侦探](<../work/blackhand/CustomLogic.galaxy#L95914-L95917>) / [副手](<../work/blackhand/CustomLogic.galaxy#L95948-L95951>) / [密探](<../work/blackhand/CustomLogic.galaxy#L96375-L96378>) / [先锋](<../work/blackhand/CustomLogic.galaxy#L96458-L96461>) | 四者均为 `gf_BHVisitAction`；外层存活/有行动判定未改 |
| 设置 | [侦探](<../work/blackhand/CustomLogic.galaxy#L98147-L98150>) / [副手](<../work/blackhand/CustomLogic.galaxy#L98197-L98240>) | 前者接 Tracker 面板；后者首夜随机能力与 Deputy 面板不变 |
| 帮派设置 | [密探](<../work/blackhand/CustomLogic.galaxy#L100596-L100618>) / [先锋](<../work/blackhand/CustomLogic.galaxy#L100936-L100958>) | 各自冷却决定行动可用；普通阵营设置和转换设置均调用同一设置函数，不是反馈副本 |
| 缺刀继任 | [密探](<../work/blackhand/CustomLogic.galaxy#L101329-L101350>) / [先锋](<../work/blackhand/CustomLogic.galaxy#L101741-L101762>) | `[pool][10][0]` 控制转党徒/暴徒；不产生侦探反馈，未改 |
| 结算 | [副手自身](<../work/blackhand/CustomLogic.galaxy#L92909-L92940>) / [侦探包装](<../work/blackhand/CustomLogic.galaxy#L93608-L93611>) / [密探](<../work/blackhand/CustomLogic.galaxy#L93715-L93752>) / [先锋](<../work/blackhand/CustomLogic.galaxy#L93755-L93792>) | 四个既有函数各只有一个分发表调用点；新增 helper 只由侦探包装与两帮反馈调用 |

保留情况：

- 密探/先锋的**监视来客、来客免疫屏蔽、排除调查者本人、按玩家只报一次、原来客文案、无来客提示、冷却、案底触发器、免疫案底回退、等候标记**，从 `lv_c = false` 起的整个尾部逐字未改。
- 来客检测本来已使用 `gf_BHWentTo`（vis 或 vis2），本次不再复制来客扫描。
- 详细信息统一沿用现有金黄色「你的目标……／这是因为……」`DT*` 口吻；普通访问仍用现有编号与带色名字格式。保留 `gf_CBSystemMessage`、`UI_TipSelect`，不改聊天缩放、收件人、队友广播和公屏渠道。没有新增文案键。
- 未学会侦探的副手仍沿用原 `E338915A` / `BBABB1F7` 粗提示；不会因为共享 helper 得到目标名字或行动原因。
- helper 的实现位于 `gf_BHDetName` 之后，侦探原抽取溯源注释仍紧贴 `gf_SKF_1_zhentan`；[前向声明](<../work/blackhand/CustomLogic.galaxy#L2172-L2175>) 保证单遍解析。

修改证明：相对 `9830e59`，按完整 Galaxy 函数元数据核验全部 **1644 个既有函数，其中 1640 个逐字未变，仅 `gf_SKF_1_fushou`、`gf_SKF_1_zhentan`、`gf_SKF_2_mitan`、`gf_SKF_5_xianfeng` 四个反馈函数改变**。新增 `gf_BHDetectiveFeedback`；不动 `gf_BHApprenticeNativeInit`、`gf_JJRefreshAbilities`、`gf_SKG_1_xuetu`、义警、护林人、急救、角色卡或已有转换专项。

## 5. 验证与明确边界

运行[专项测试](<../tools/test_detective_feedback.py>)：

```bash
python3 tools/test_detective_feedback.py --negative-tests
python3 tools/test_faction_investigation.py
python3 tools/galaxy_lint.py
python3 tools/sk_verify.py
python3 tools/role_card_check.py --strict
python3 tools/role_list_gen.py --check
python3 tools/role_gen.py
python3 tools/wait_graph_check.py
```

结果：

- 侦探专项：**15,938 fixtures / 717,265 checks**，抽取当前 **25 个完整生产函数 + 4 个真实旧函数 + 4 条原调用守卫**，用 C++17、UBSan/bounds 执行。
- 覆盖无行动、未执行的面板计划、访问自己/他人、双访问、重复槽、仅第二槽、玩家 15、囚禁/限制优先级、调查免疫与城镇开关、干扰三种方向、无干扰标记的计划差异；比较新版侦探重构前后正常域逐条消息相同。
- 两帮详细输出对照统一规则；监视/案底尾部与真实旧函数逐条相同，覆盖来客 vis2、免疫来客排除、双槽同一来客去重、全部冷却组合、案底第 10 槽。
- 覆盖副手学会/未学 `[3]`、粗报双槽、五/六层身份和名单/清访问/成就保留；错误职业池、当夜死亡、无访问、冷却中不发反馈。实际执行准备访问和 `gf_BHBlock` 清槽；另测调查者被重定向后追踪最终新目标。
- **6 项负向突变均被拒**：①还原密探旧平行体；②密探借用城镇无视免疫开关；③改两帮冷却尾部；④删第二访问槽；⑤不看干扰标记、仅凭计划差异推断干扰；⑥限制目标报错原因。突变只在内存/临时 C++ 文件，未写生产脚本。
- 独立重跑[探员专项](<../tools/test_faction_investigation.py>)：**26,430 fixtures / 637,212 assertions**，确认本次没有把探员身份/武器线索逻辑当成侦探修改。
- 六道静态门全部退出 0；lint **1645 函数/0 问题**，sk_verify **474 抽取函数通过**（结构模式，未启用历史溯源模式）。角色登记门保留其既有镜头覆盖提示，不是本项引入的新角色缺失。

验证边界：引擎 text/color/playergroup/TriggerExecute 为明确的测试替身；后者实际调用生产案底触发器。访问、清访问、限制、访问读侧、身份/伪装名称 helper 使用真实生产函数。四条守卫从原分发表抽取执行，**没有声称执行整个 `gf_SequenceAfter`、副手另行监视阶段、女巫/司机完整时序或 SC2 调度**；目标干扰矩阵直接构造其权威状态。没有用 C++ 编译成功冒充 Galaxy 引擎编译成功，没有 SC2 客户端实测、渲染/多人实测或发布验证。

## 6. 集成打包结果

- 再次运行本专项、调查/身份及 shw317 三专项，全部通过。
- 完整六门、八件套与打包回读完成；[shw318 本地单人测试包](<../work/boot2-shw318-solo.SC2Map>) **39,338,029 bytes**，MD5 `5b88e2648b7696c6a9025b016a202400`。
- 包内对照生产脚本仅两个 solo 布尔值不同；三个调用入口共用新 helper，既有 `DT*` 及 shw317 五项特性键齐全。
- 未部署：最近一次检测客户端及编辑器均在运行，尚未确认退出；没有关闭进程或上传战网。上述结果不等于 SC2 引擎实测。
