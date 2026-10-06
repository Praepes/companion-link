# Morning Panel for Home Assistant

此集成把晨间面板 app 的本机状态与控制功能接入 Home Assistant，包括电量、充电、网络、屏幕状态、系统信息、下次闹钟和最近控制结果。Home Assistant 可唤醒或休眠屏幕、调整 Android 系统亮度，并在闹钟响铃时贪睡或停止闹钟。

## 从 HACS 安装

1. 在 HACS 右上角菜单打开 **自定义存储库**。
2. 添加 `https://github.com/Praepes/ha-morning-panel`，类型选 **Integration**。
3. 安装 **Morning Panel** 并重启 Home Assistant。
4. 到 **设置 → 设备与服务 → 添加集成** 搜索并添加 **Morning Panel**。
5. 在 app 的 **设置 → Home Assistant 与本机设备** 中填入 HA 地址和长期访问令牌并保存。
6. 等待最多 30 秒，或点击 **测试本机状态上报**。实体先创建为不可用状态，收到 app 的第一条状态事件后上线。

也可以手动安装：将 `custom_components/xperia_touch` 复制到 HA 的 `config/custom_components/xperia_touch`，重启 HA 后添加集成。

## 控制能力

- 唤醒屏幕：Android 电源唤醒锁，无需 Root。
- 休眠屏幕：应用级 `su` 授权后发送固定的 `input keyevent 223`。Root 不可用时实体会显示不可用。
- 亮度：需要在 app **设置 → 屏幕与后台保活** 中授权“修改系统设置”。此控制调整 Android 系统屏幕亮度；Xperia Touch 投影光学引擎是否跟随该值仍需实机验证。
- 闹钟响铃时，HA 会显示 **贪睡闹钟 10 分钟** 和 **停止闹钟** 按钮；非响铃期间按钮不可用。
- 控制结果会出现在 **最近控制结果** 传感器中，并触发一次即时状态上报。

## 设备没有出现时

- 确认 HACS 外部仓库地址是 `https://github.com/Praepes/ha-morning-panel`，类型为 **Integration**；或确认手动安装目录是 `config/custom_components/xperia_touch`。
- 重启 Home Assistant 后，到 **设置 → 设备与服务 → 添加集成** 搜索并添加 **Morning Panel**。app 填写 HA 地址不会自动安装集成。
- 在 app 中保存 HA 地址和长期访问令牌，再点击 **测试本机状态上报**。若集成已添加但设备仍不可用，检查 app 地址、令牌及 HA 日志中的集成错误。
- 设备实体建立后，即使 app 尚未上报，也应能在集成设备页看到实体；收到状态事件后实体从不可用转为在线。

HA 令牌只保存在 app 端，不随本机闹钟备份导出。集成沿用既有 `xperia_touch` 内部域名与事件名，以免破坏已经配对的设备数据；HA 界面显示名称为 **Morning Panel / 晨间面板**。
