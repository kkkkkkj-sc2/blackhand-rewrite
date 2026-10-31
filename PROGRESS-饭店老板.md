# 饭店老板 进度（每次断线从这里接）

工作目录：`I:\大肥鱼\外部项目\blackhand-饭店老板`（原仓库是 `blackhand-rewrite-main`）

## 已完成（lint 全绿）

```
1. roles/fandianlaoban.json          spec：城镇 1/36、探员两条、图鉴犯罪无
2. roles/fandianlaoban.md            设计稿（全部规则与裁剪口径）
3. work/blackhand/strings-fd.txt     文案键（名称暖橙 E0862C）
4. 注册                              gv_townMax 35→36、[1][36] 名称/描述/探员/犯罪/权重
                                    gv_roleNameInput[1][36] = "fandianlaoban"
5. 全局变量                          gv_fdStock / gv_fdFood[16] / gv_fdGrace[16]
                                    gv_fdLootCried / gv_fdRecoverCried
                                    gv_fdCorpse / gv_fdCorpseTell[16]（10-13 步新增）
6. 探员线索全局                      text gv_investigatorFDINV1/FDINV2 + 赋值
7. 自设列表                          work/roles-list.json 追加 1/36
                                    tools/role_list_gen.py --apply 已重写两段
8. 角色卡                            gf_RTTownRoleText 内加 1/36 五栏块
9. 票权加成                          gf_BHVoteWeight 内：gv_fdFood 加成，老板本人排除
10. 夜间函数                         gf_SKK_1_fandianlaoban：出门送 / 在家做；
                                    gf_SKP_1_fandianlaoban_2 写访问（送饭→目标家，做饭→自己家）
11. 发放规则                         gf_FDVisitorsClaim：生存者白贴（不扣库存、标 gv_fdGrace）；
                                    其余 城镇→黑手→三合→中立 分档，同档超额随机抽
12. 行动面板                         gf_RAFDLaobanActions + gf_SKR_1_fandianlaoban
                                    + gf_SKA_1_fandianlaoban（自己那一格＝做饭/取消）
13. 死亡三路                         gf_FDOnDeath（挂在 gf_GSKillPlayerDirect 入口）
                                    击杀→凶手夺取（FDLOOT）；自杀/处刑/白天死→回老板（FDRECOVER）；
                                    处刑记 gv_fdCorpse，下一夜写进老板访问（侦探专门播报 FDDET1/4、FDDET2/3）
14. 白天报数                         gf_FDMorning + gt_FDMorning 延迟 1.5s 私发持有数（FDCOUNT）
                                    第一行是老板自己的库存，后面每个有食物的人一行
另. 审查页可猜                      gf_ASGuessRole 城镇下标 33→36（原来 33 起返回 0）；
                                    gf_ASE5AEA1E69FA5E98089E9A1B92 城镇池循环 32→33
另. 打包门                          tools/boot2_build.py 的 MUST_HAVE_KEYS 加 29 个 FD 键
```

改动用的补丁脚本（留档在仓库 tools/ 下）：
`_step_fd_register.py`、`_fix_fd_inv.py`、`_fd_card.py`、`_fd_vote3.py`、`_step_fd_night.py`

## 还没做（按顺序）

```
15. 打包       云端跑（Windows 的 mpqtool 是 ELF，跑不了；基线 work/boot2-user.SC2Map 也不在本机）：
               python3 tools/boot2_build.py --out work/boot2-饭店老板.SC2Map
               打包前先 python3 tools/galaxy_lint.py（本机已跑：1762 函数 0 问题）
16. 生存者恩惠结算（设计稿写了、本轮只做了标记）
               「第一次给城镇角色投有罪票 → 按无罪算」要落在投票统计上；
               广播文案 FDGRACE 已备好。落点候选：各投票分支（约 80960–81460 一长串）
               逐处减 gv_bhNominationWeight，风险高，等能实测再做。
17. 实测       File → Test Document，看 GameLogs\*ScriptError.txt；重点验：
               面板两档、领饭分档随机、击杀夺取/处刑回收播报各一次、侦探看收尸两种措辞
```

## 关键口径（别改错）

- 票权：一份食物 +1，**老板自己不享受**，别人的加成照算
- 送出的饭当夜到手，**第二个白天生效**
- 被抽中领饭的人当夜死了 → 饭当场转给凶手
- 播报文字：击杀用「一名杀人犯在行使罪恶时发现了意外之喜……」，
  回收用「一名饭店老板摇了摇头叹了口气……」——**都写「杀」，不写「爱」**
- 做饭是默认档（gv_action=0），面板自己那一格显示「在家做饭」，点它回做饭；
  被舞娘/陪侍限制仍可做饭，被关进牢里则整夜无事
- 送饭登记在 gv_action，**实际给谁按最终 gv_visitation**（女巫/巴士改过的照改）
- 领饭看的是「谁最终访问了老板家」（gv_visitation[p] == 老板）
- 处刑尸首：白天记 gv_fdCorpse，下一夜访问段消费；做饭+收尸只写第一访问，
  送饭+收尸用第二访问槽（visitation2 = 送饭目标）
- deathMethod / 死因字母码没动，本角色不新增字母码
