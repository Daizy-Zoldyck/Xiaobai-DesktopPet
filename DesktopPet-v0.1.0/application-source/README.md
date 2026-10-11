# DesktopPet · PNG 桌面伙伴

项目位置：`E:\DesktopPet`。

**第一版 EXE：`release\DesktopPet-v0.1.0.exe`。** 单文件 Windows x64 版本，人物和图标内置，无需另装 Python。EXE 的设置、缓存和日志保存在 `%LOCALAPPDATA%\DesktopPet`。旧 Python 版仍保留，两版请勿同时启动；切换后如需开机启动，请在 EXE 菜单里重新设置。

这是新的 PNG 版本，使用用户提供的图 4 作为人物参考。当前没有接入 Live2D，没有拆图绑定、眨眼骨骼或模型物理。透明素材经过 AI 辅助处理，与原图可能存在细节差异；六张原始图片保留在 `assets/references`。

## 启动与使用

推荐双击 **release\DesktopPet-v0.1.0.exe**。原来的 **启动桌宠.lnk** 或 **DesktopPet.vbs** 仍启动 Python 源码版。两种方式都不需要手动输入命令，也不会弹出终端窗口。同一版本重复启动会提示已经运行。

- 鼠标停在人物上约半秒：显示 Codex 额度卡。
- 左键拖动：移动人物；接近屏幕可用区域边缘时吸附。
- 单击人物：短暂向上轻跳；拖动结束不会误触发点击动画。
- 右键人物：查看额度、刷新、调节大小、开启轻微浮动、切换边缘吸附、设置开机启动、恢复位置、退出。
- 托盘图标单击：显示或隐藏宠物；右键打开同样的菜单。Windows 可能把它收进托盘的隐藏图标区。
- **开机启动默认关闭**，需要时在菜单中勾选。取消勾选即可移除本程序的启动项。
- 若找不到人物，托盘菜单选择“恢复到屏幕右下角”。

默认人物高度 300 个逻辑像素，适配 Windows DPI。默认静止时没有持续动画计时器；点击动画最高约 30 FPS；可选轻微浮动约 10 FPS。隐藏时停止绘制动画。

## 额度

通过本机 Codex 的 `app-server` 标准输入输出通道，调用官方 `account/rateLimits/read`。使用 Codex 自己的登录状态，程序不读取、复制或保存登录令牌，不发起模型对话，不消费重置次数。

默认每 5 分钟在后台线程查询。手动刷新有 10 秒间隔限制。卡片分别显示 5 小时和周额度的剩余百分比、各自的重置时间（系统本地时区）和最近成功更新时间。数据属于账户共享额度。

服务返回多种额度桶时，卡片提供选择框。按实际 `windowDurationMins` 匹配 300 和 10080 分钟，而不假设 primary 永远代表 5 小时。缺失数据显示暂不可用。网络失败保留上次成功数据并标记“旧”；到达重置时间后显示待更新，不自行假定恢复到 100%。

额度状态事件已预留：剩余大于 50% 为 normal，20% 到 50%（含边界）为 low，低于 20% 为 critical。两个窗口分别处理，只有状态变化才发事件。**此 PNG 版本不把额度事件绑定为动画、提醒或使用建议。**

若额度不可用，先打开 Codex 确认已登录且网络正常，再使用菜单刷新。本程序不会代你更改登录方式。

官方协议：[Codex App Server](https://learn.chatgpt.com/docs/app-server)。

## 配置与文件

Python 版设置保存在 `runtime/config.json`；上次成功额度快照在 `runtime/usage-cache.json`；运行日志在 `runtime/desktop-pet.log`，自动限制体积。EXE 使用 `%LOCALAPPDATA%\DesktopPet` 下的同名文件，避免写入单文件程序的临时解压目录。

`renderer` 目前仅实现 `png`。未知 renderer 会回退 PNG，并记录日志，不冒充 Live2D。`event_bindings` 是未来扩展占位，目前不解释 motion 或 expression。

主要模块：

| 文件 | 职责 |
|---|---|
| `desktop_pet/renderers/base.py` | 基于控件的渲染抽象、事件与暂停接口 |
| `desktop_pet/renderers/png.py` | PNG 绘制、透明区域命中、轻跳与可选浮动 |
| `desktop_pet/window.py` | 透明置顶窗口、鼠标交互与屏幕位置 |
| `desktop_pet/controller.py` | 事件协调、后台工作线程、托盘 |
| `desktop_pet/card.py` | 额度信息卡与数据时效显示 |
| `desktop_pet/usage.py` | Codex 程序发现、只读协议与额度解析 |
| `desktop_pet/startup.py` | 当前 Windows 用户的开机启动项 |

## 环境与恢复

源码开发环境使用项目内 `.venv` 和 PySide6 Essentials 6.10.3，Python 3.12 来自已安装的 Codex 本地运行环境。**发布的 EXE 已内置所需 Python 和 Qt 运行库，不依赖这个开发环境。** Codex 额度查询仍需本机安装并登录 Codex。

重新构建使用 `build.ps1`（PyInstaller 6.22.3）。构建仅打包程序和正式人物/图标，不包含原图集、账号信息、个人配置或额度缓存。`DesktopPet.spec` 隔离宿主 PATH，防止混入 Poppler 等其他软件的同名 ICU DLL。

如果迁移电脑或底层 Python 被卸载，需要 Python 3.10 或更高版本并重新创建 `.venv`。`setup.ps1` 可以在环境不存在时创建环境并安装依赖，支持 `-PythonPath` 指定 Python。不要在程序运行时移动项目或重建环境。迁移后重新设置开机启动。

## 验证范围

已通过 `tests` 中 12 项检查：额度边界、空值与异常值、多额度桶、实际窗口长度、缓存时间、失效路径、负坐标屏幕吸附、点击/拖动互斥、隐藏停绘、额度事件去重、过期显示、慢查询不阻塞界面。

已用本机真实账户验证后台额度查询；Windows 当前 150% 缩放下，通过同一渲染/窗口代码的预览窗口检查透明背景、人物显示、额度卡排版、右键菜单和实际拖动。正常常驻窗口采用不占任务栏的 Tool 类型，检查工具不能直接枚举该类型，因此使用临时预览窗口完成视觉检查。

尚未实测多显示器跨屏、其他 DPI、重启后的自启动、全天运行，以及其他机器上的表现。没有将短时检查描述为长期稳定性认证。
