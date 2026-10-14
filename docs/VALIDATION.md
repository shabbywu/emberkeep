# 验证记录

测试环境：macOS 27.0.1 ARM64，Python 3.10.20，`ultralight-py==0.5.0`。

| 验证 | 结果 |
| --- | --- |
| pytest 规则与桥接测试 | 123 项通过 |
| 原生 CPU 完整战役 | 种子 7、19、42 均通过四层并胜利 |
| 原生自然失败 | 玩家正常探索后等待，被敌人击败，进入失败结算 |
| 默认 AppCore 渲染 | 原生启动、资源、实例方法、只读属性、异步保存和加载冒烟测试通过 |
| 跨进程继续 | 关闭应用后在新进程恢复；完整状态、RNG 与下一回合结果一致 |
| 输入与界面 | WASD、鼠标、升级选择、暂停、失焦暂停及 F5 保存通过 |
| 窗口布局 | 实际创建 800×600、1280×800、1600×1000 原生窗口验证 |

CPU 原生战役结果：

| 种子 | 结果 | 回合 | 击败敌人 |
| --- | --- | --- | --- |
| 7 | 胜利 | 396 | 24 |
| 19 | 胜利 | 334 | 23 |
| 42 | 胜利 | 375 | 28 |
| 7 | 失败 | 56 | 0 |

完整战役使用与 UI 相同的迷雾快照，通过原生 `View.key_down/key_up/click` 输入；未读取隐藏地图、修改生命、传送或跳关。截图来自实际 Ultralight CPU View 像素。

## 重现

```bash
python -m pytest -q
python run.py --smoke
python tests/native_acceptance.py --cpu
python tests/native_restart.py
```

运行报告生成在 `docs/reports/`，已加入 `.gitignore`。游戏截图位于 `docs/screenshots/`。

## 验证边界

Windows/Linux、默认渲染下的完整战役、人工物理键鼠操作、实时拖动窗口和跨显示器 DPI 未完成验证。小窗口的长对话框与侧栏允许内部滚动。
