# Conway Life Simulator

一个基于 Tkinter 的康威生命游戏桌面模拟器。

功能：

- 启动时显示康威生命游戏规则
- 左键点击或拖动修改初始细胞
- 开始、暂停、单步、清空和随机生成
- 调整倍速，每一代都会显示，不跳代
- 鼠标滚轮缩放画布
- 右键拖动画布
- 保存和载入 `.life` 初始图案
- 检测到循环状态后提示并自动暂停
- 小缩放下合并绘制连续细胞，减少卡顿

运行源码：

```bat
python conway_life.py
```

打包后的软件位于 `dist\ConwayLifeSimulator.exe`。
