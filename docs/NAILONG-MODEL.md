# 奶龙模型：待机与导出轴

2026-10-04 更新：[Nailong.m3](</home/mon3tr/dev/blackhand-rewrite/data/Nailong.m3>) 已整份重新导出，不沿用旧文件的 Origin 修补。贴图与游戏资源路径保持不变。

- **正前方 -Y，向上 +Z**。用户已在黑手党地图中实测：这是让奶龙朝向站位圆心的方向。
- 导出的 `GAME = Matrix.Translation(Vector((0, 0, -ground)))` **只做贴地平移**；Z 旋转为 0。顶点、静置骨架、Stand/Walk 都使用这个变换。
- **不能再叠加 Origin -90° 补丁，不能再旋转 IREF**。那是历史 +X 前向版本的临时修补；对新文件再做会转错方向。
- M3Studio 自身有骨骼坐标基转换，不能仅凭序列化 Origin 四元数不是单位四元数就判断需要再补旋转。

## 动画

| 动画 | 播放范围 | 帧率 | 时长 |
|---|---|---|---|
| Stand | 1–120，121 为闭合帧 | 30 fps | 4 秒 |
| Walk | 1–40，41 为闭合帧 | 30 fps | 约 1.33 秒 |

Stand 包含呼吸、轻微重心摇摆、头部回望、手臂延迟跟随。Walk 保持原动作，只统一导出轴。无攻击、死亡、大笑；不改 Unit/Actor 或 Galaxy 脚本。

游戏路径沿用 `Assets\Units\Nailong\Nailong.m3` 与 `Assets\Textures\Nailong_Diffuse.dds`，打包器直接读取 [Nailong.m3](</home/mon3tr/dev/blackhand-rewrite/data/Nailong.m3>)，不要在打包时再施加旋转。

## 源工程与验证

源工作区在 `/home/mon3tr/data/blender/nailong_idle_20261004`：

- [游戏版 Blender 工程](</home/mon3tr/data/blender/nailong_idle_20261004/deliver/Nailong_Idle.blend>)：骨骼烘焙 Stand/Walk，贴图 packed，Blender 5.2 无插件即可播放。
- [IK 编辑工程](</home/mon3tr/data/blender/nailong_idle_20261004/deliver/Nailong_Idle_Editable.blend>)：新待机独立 Action，96 帧/24 fps，97 为闭合帧。
- [提取脚本](</home/mon3tr/data/blender/nailong_idle_20261004/extract_nailong.py>) 与 [构建脚本](</home/mon3tr/data/blender/nailong_idle_20261004/build_nailong.py>)：5.2 制作、4.2/M3Studio 导出，Z 旋转为 0。
- [循环与接地验证](</home/mon3tr/data/blender/nailong_idle_20261004/idle_verification.json>)：待机/行走网格接缝误差 0；待机最低顶点 z≈0.001987；脚骨 XY 漂移约 0.0000093。
- [M3 往返验证](</home/mon3tr/data/blender/nailong_idle_20261004/m3_validation.json>)：实际文件重新导入，检查所有 121 个待机采样和 6 个行走采样、39 骨、36001 三角面、4 权重、DDS 路径。

**本轮未在 SC2 编辑器或游戏中实测新文件，也未重新打包/发布地图。** 下次正常地图构建会读取新模型。历史源工程保持不变。
