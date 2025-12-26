**1）目标与边界**

- **主区域（MainArea）应分为状态（mainarea_state）与 UI （mainarea_view）**：状态（mainarea_state）是唯一数据源**：负责扫描/刷新、维护设备列表、维护文件管理页缓存、负责页面切换与全局禁用。
- **侧边栏（Sidebar）是唯一导航入口**：点击“总览/设备”直接触发切页；不与总览页选择联动。
- **总览页（Overview）是展示 + 意图发射**：显示设备列表/扫描状态；按钮只有 `刷新/详情/安全弹出`；不提供“管理文件”，不触发页面切换。
- **刷新期间**：禁止除“关闭窗口”外的所有交互（禁用侧边栏 + 可变区域整体）。
- **关闭语义**：允许关闭，但丢弃异步结果、不更新 UI。

**2）MainArea 的内部状态（即mainarea_state）（建议字段）**

- `is_scanning: bool`：全局扫描态唯一来源
- `devices: tuple[UsbBaseDeviceInfo|UsbStorageDeviceInfo, ...]`：总览页展示用
- `storages: dict[UsbDeviceId, UsbStorageDeviceInfo]`：以 `instance_id` 为 key 的存储设备字典（侧边栏/文件管理页使用）
- `file_pages: dict[UsbDeviceId, FileManagerPageView]`：设备 -> 文件管理页缓存
- `current_view: Literal["overview","file"]` + `current_device_id: Optional[str]`（可选，但实现更清晰）
- `_is_closing: bool`：窗口关闭后丢弃结果
- `_refresh_generation: int`：可选；若你采用“刷新重入忽略”，这项可以不需要，但建议保留用于安全丢弃过期结果

**3）MainArea 的 UI 结构（即mainarea_view）**

- 水平布局：`SidebarWidget` + “可变区域容器”
- 可变区域容器使用 `QStackedWidget`（推荐）
  - index0：`OverviewPageView`
  - 其他：按 `UsbDeviceId` 缓存创建的 `FileManagerPageView`
- 切页语义：`setCurrentWidget(...)`（隐藏旧页、展示新页，不销毁）

**4）信号/事件流（谁发给谁）**

- Sidebar -> MainArea
  - `overviewRequested` -> `MainArea.show_overview()`
  - `deviceRequested(UsbDeviceId)` -> `MainArea.show_device(device_id)`
- Overview -> MainArea（用户意图）
  - `refreshRequested`（来自刷新按钮）-> `MainArea.refresh()`
  - `detailsRequested`（来自详情按钮）-> `MainArea.open_details_for_overview_selection()`
  - `ejectRequested`（来自弹出按钮）-> `MainArea.eject_for_overview_selection()`
  - Overview 内部仍可保留 `selectedDeviceChanged` 供 MainArea 读取当前选中（但不驱动导航）
- MainArea -> Overview / Sidebar（数据与状态分发）
  - `stateChanged` -> `overview.set_devices(devices)`
  - `stateChanged` -> `overview.set_scanning(is_scanning)`
  - `stateChanged` -> `sidebar.set_devices(storages.values())`
  - `refreshFailed`（扫描失败） -> `overview.set_error_text(...)` 

**5）刷新流程（MainArea 全权负责）**

1. `Overview` 刷新按钮点击 -> 发 `refreshRequested`
2. `MainArea.refresh()`：
   - 若 `is_scanning=True`：直接忽略（你已确定）
   - 置 `is_scanning=True`，并执行全局禁用：`main_area_container.setEnabled(False)`（但允许关闭窗口）
   - 启动后台任务（QThreadPool/QRunnable）：
     - 线程内创建/使用 WMI/COM 资源（线程内初始化）
     - 扫描得到 `devices` 与 `storages`
3. 后台完成回主线程回调：
   - 若 `_is_closing=True`：丢弃结果，不更新 UI
   - 更新 `devices/storages`
   - 更新 `Sidebar` 与 `Overview`
   - 清空总览选中（你已规定不保留选中）
   - 清理缓存：不存在的 `UsbDeviceId` 对应的 `FileManagerPageView` 立即销毁并从 dict 移除
   - `is_scanning=False`，解除全局禁用
4. 失败回调同理：
   - 若 `_is_closing=True`：丢弃
   - `is_scanning=False`，解除全局禁用
   - 通过唯一出口显示“刷新失败”

**6）页面切换流程**

- `show_overview()`：
  - `stack.setCurrentWidget(overview_page)`
- `show_device(device_id)`：
  - 若 `UsbDeviceId` 不在 `storages`：回到总览（并让侧边栏选中总览）
  - 否则从 `file_pages` 取页；没有则创建并缓存：
    - `filesystem` 注入到 `FileManagerPageView`
    - `initial_directory` 从当前 `UsbStorageDeviceInfo` 推导（mount_path/drive_letter）
  - 切到该页
  - 盘符变化策略：切页前校验/重置目录（你已确认）

**7）设备操作（详情/弹出）**

- 只在总览页存在按钮，且操作对象来自“总览当前选中”：
  - 点击时 MainArea 读取 Overview 选中的 `instance_id`
  - 再从 MainArea 的最新字典取快照执行；取不到则提示“设备已不存在/请刷新”

这份整理的要点是：MainArea 负责“数据 + 导航 + 全局交互控制”，Overview/Sidebar 只负责“展示与发出用户意图”。如果你希望我再把它转成一份更像接口文档的形式（类方法列表、信号命名、参数类型），我也可以继续细化。
