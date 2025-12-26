# USB Manager UI 开发 Copilot Instruction

## 项目概述

**项目名称**: USB Manager (umanager)  
**目标**: 开发一个类似 Windows 资源管理器的 USB 设备管理工具  
**UI 框架**: PySide6  
**开发模式**: 增量开发 - 先实现基础框架，逐步完善各个模块

---

## 架构设计

### 整体布局

```
┌─────────────────────────────────────┐
│  菜单栏 (File, View, Help)          │
├─────────────────────────────────────┤
│ [概览] [设备1] [设备2] [...]        │  ← 多标签页
├─────────────────────────────────────┤
│                                     │
│         标签页内容区域              │
│                                     │
├─────────────────────────────────────┤
│ 状态栏 (设备数量、状态信息)         │
└─────────────────────────────────────┘
```

### 标签页结构

#### 1. 概览标签页 (Overview Tab)
- **功能**: 显示所有 USB 设备的汇总信息
- **布局**: 树形结构或列表视图
- **显示信息**:
  - 设备制造商 (Manufacturer)
  - 产品名称 (Product)
  - 序列号 (Serial Number)
  - USB 版本 (USB Version)
  - 传输速度 (Speed)
  - 卷标和文件系统信息
  - 存储容量和可用空间
- **交互**:
  - 双击设备打开对应的文件浏览器标签页
  - 右键菜单 (打开、刷新、弹出等)
  - 刷新按钮或自动监听设备变化

#### 2. 文件浏览器标签页 (Storage Explorer Tab)
- **功能**: 对单个 USB 存储设备进行文件管理
- **布局**: 分为三部分
  - 导航栏: 地址栏 + 前进/后退/刷新按钮
  - 侧边栏: 收藏夹、卷标列表 (可选)
  - 主视图: 文件列表 + 详细信息
- **文件列表视图**:
  - 显示列: 名称、类型、大小、修改日期
  - 支持排序和过滤
  - 图标显示 (文件夹、文件类型)
- **交互操作**:
  - 双击打开文件夹或启动文件
  - 右键菜单: 复制、剪切、粘贴、删除、重命名、属性
  - 拖放操作 (从外部拖入、拖出)
  - 选中多个文件进行批量操作
  - 键盘快捷键: Ctrl+C (复制)、Ctrl+X (剪切)、Ctrl+V (粘贴)、Delete (删除)

---

## 数据模型和接口

### 现有后端接口

```python
# 设备信息获取
from src.umanager.backend.device.protocol import (
    UsbBaseDeviceProtocol,
    UsbStorageDeviceProtocol,
    UsbDeviceId,
    UsbBaseDeviceInfo,
    UsbStorageDeviceInfo,
    UsbVolumeInfo
)

# 文件系统操作
from src.umanager.backend.filesystem.protocol import FileSystemServiceProtocol
```

### UI 层需要实现的接口

```python
# UI 控制器层 (拟设计)
class OverviewController:
    """概览标签页控制器"""
    - get_all_devices() -> list[UsbStorageDeviceInfo]
    - refresh_devices() -> None
    - open_device_explorer(device_id: UsbDeviceId) -> None
    - listen_device_changes() -> Observable[DeviceChangeEvent]

class StorageExplorerController:
    """文件浏览器控制器"""
    - list_files(path: Path) -> list[FileInfo]
    - navigate_to(path: Path) -> None
    - get_current_path() -> Path
    - copy_files(source: list[Path], dest: Path) -> None
    - delete_files(paths: list[Path]) -> None
    - rename_file(path: Path, new_name: str) -> None
    - refresh() -> None
```

---

## 功能需求分解

### 第一阶段：基础框架
- [ ] 创建主窗口类 `MainWindow`
- [ ] 实现标签页容器 `TabWidget`
- [ ] 实现菜单栏和工具栏
- [ ] 设计基础的状态栏

### 第二阶段：概览标签页
- [ ] 创建 `OverviewTab` 组件
- [ ] 实现设备列表显示
- [ ] 实现设备信息详情视图
- [ ] 实现刷新和监听设备变化
- [ ] 右键菜单和打开操作

### 第三阶段：文件浏览器基础
- [ ] 创建 `StorageExplorerTab` 组件
- [ ] 实现导航栏和地址栏
- [ ] 实现文件列表视图
- [ ] 实现基础文件浏览 (打开文件夹、返回)
- [ ] 实现基础的右键菜单

### 第四阶段：文件操作
- [ ] 实现文件复制/粘贴
- [ ] 实现文件删除
- [ ] 实现文件重命名
- [ ] 实现拖放操作

### 第五阶段：优化和完善
- [ ] 快捷键支持
- [ ] 搜索和过滤
- [ ] 性能优化 (大文件夹加载)
- [ ] 错误处理和用户提示

---

## 代码规范和架构要求

### 目录结构
```
src/umanager/ui/
├── __init__.py
├── main.py              # 应用入口
├── widgets/
│   ├── __init__.py
│   ├── main_window.py   # 主窗口
│   ├── overview_tab.py  # 概览标签页
│   └── explorer_tab.py  # 文件浏览器标签页
├── controllers/
│   ├── __init__.py
│   ├── overview_controller.py
│   └── explorer_controller.py
└── models/
    ├── __init__.py
    └── ui_models.py     # UI 相关的数据模型
```

### 设计原则

1. **分层架构**: 将 UI、业务逻辑、数据访问严格分离
   - UI 层: 纯界面呈现和用户交互
   - 控制器层: 事件处理和业务逻辑
   - 模型层: 数据定义和转换

2. **响应式设计**: 支持窗口大小变化，自适应布局
   - 使用相对布局而非硬编码坐标
   - 支持最小化窗口大小设置

3. **异步操作**: 文件操作应异步执行，不阻塞 UI
   - 使用线程或事件循环处理耗时操作
   - 提供进度提示和取消功能

4. **错误处理**: 完善的异常捕获和用户提示
   - 文件操作失败显示对话框
   - 后端接口异常应优雅降级

5. **增量开发**: 每个模块独立但可集成
   - 使用接口定义而非具体实现
   - 支持模块的独立测试
   - 保持向后兼容

### 命名规范

- **窗口/组件类**: PascalCase，后缀为组件类型
  - `MainWindow`, `OverviewTab`, `FileListWidget`
- **方法**: snake_case，动词开头
  - `refresh_devices()`, `list_files()`, `open_explorer()`
- **信号/事件**: snake_case，描述事件
  - `device_selected`, `file_double_clicked`, `refresh_completed`
- **常量**: UPPER_SNAKE_CASE
  - `DEFAULT_WINDOW_WIDTH`, `COLUMN_WIDTH_NAME`

---

## 交互流程

### 用户场景 1: 查看 USB 设备信息
1. 打开应用，进入"概览"标签页
2. 自动显示所有已连接的 USB 设备
3. 用户可查看各设备的详细信息
4. 双击某个设备，打开该设备的文件浏览器标签页

### 用户场景 2: 浏览和管理 USB 文件
1. 在文件浏览器标签页中打开目标文件夹
2. 查看文件列表，可排序和过滤
3. 执行文件操作:
   - 复制/粘贴: Ctrl+C/Ctrl+V 或右键菜单
   - 删除: Delete 键或右键菜单
   - 重命名: F2 快捷键或右键菜单
4. 上传文件: 拖放或右键粘贴

### 用户场景 3: 设备变化监听
1. 应用自动监听设备连接/断开事件
2. 连接新设备时，概览中自动刷新
3. 移除设备时，对应的文件浏览器标签页自动关闭 (可选)
4. 状态栏实时显示当前设备数量

---

## 测试需求

### UI 测试
- 窗口正常创建和显示
- 标签页正常切换
- 菜单和按钮功能正常
- 响应式布局测试

### 功能测试
- 设备列表正确显示
- 文件列表正确加载和刷新
- 文件操作成功执行
- 错误场景的处理

### 集成测试
- 后端接口的正确调用
- 控制器与 UI 的交互
- 事件传递的正确性

---

## 技术选型建议

### UI 框架对比

| 框架 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **PySide6** | 功能完整、性能好、原生风格、官方支持 Qt | 初期学习曲线 | ⭐⭐⭐⭐⭐ |
| **PyQt6** | 功能完整、性能好、原生风格 | 学习曲线陡、许可证问题 | ⭐⭐⭐⭐ |
| **PySimpleGUI** | 简单易用、快速原型 | 功能有限、定制性差 | ⭐⭐⭐ |
| **Tkinter** | Python 内置、轻量级 | 样式受限、功能基础 | ⭐⭐ |

**推荐**: PySide6 - 官方 Qt Python 绑定，提供最好的平台原生外观、完整的功能支持和长期维护保证

---

## 开发流程

### 每次开发前
1. 选择本阶段要实现的功能
2. 设计组件接口和数据模型
3. 实现 UI 组件的骨架 (不含逻辑)
4. 编写对应的控制器逻辑
5. 集成到主窗口

### 编码时
1. 优先保证功能正确性
2. 逐步优化性能和用户体验
3. 添加适当的错误处理
4. 编写单元测试

### 完成后
1. 手工测试所有功能
2. 测试边界情况和错误场景
3. 代码审查和重构
4. 更新文档

---

## 依赖项

当前需要检查或安装的依赖：
- PySide6 (核心 UI 框架)
- 任何额外的库 (根据需要选择)

**安装指令**:
```bash
pip install PySide6
```

更新 `pyproject.toml` 中的依赖配置。

---

## 注意事项

1. **线程安全**: UI 操作必须在主线程，长时操作应在工作线程
2. **资源管理**: 及时关闭文件句柄，释放内存
3. **平台兼容性**: 处理不同操作系统的路径差异 (已有 Path 支持)
4. **用户友好**: 提供清晰的反馈和错误提示
5. **性能**: 避免阻塞 UI，大量数据需分页或虚拟滚动

---

## 相关文件和接口

- 后端设备管理: `src/umanager/backend/device/`
- 后端文件系统: `src/umanager/backend/filesystem/`
- 应用主文件: `src/umanager/app.py`
- 现有协议定义: `src/umanager/backend/device/protocol.py`

