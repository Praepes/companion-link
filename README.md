# Companion Link for Home Assistant

此集成把 Morning Panel 等配套客户端连接到 Home Assistant。每台客户端设备各添加一个配置项；每个设备的状态与命令按设备配对 ID 独立路由，多个客户端可共用此集成。

## 从 HACS 安装

1. 在 HACS 右上角菜单打开 **自定义存储库**。
2. 添加 `https://github.com/Praepes/companion-link`，类型选 **Integration**。
3. 安装 **Companion Link** 并重启 Home Assistant。
4. 在 app 的 **设置 → Home Assistant 与本机设备** 中复制 **Companion Link 配对 ID**，同时填入 HA 地址和长期访问令牌并保存。
5. 在 Home Assistant 的 **设置 → 设备与服务 → 添加集成** 中添加 **Companion Link**，填入该配对 ID。
6. 等待最多 30 秒，或点击 app 中的 **测试本机状态上报**。收到首条状态事件后，设备实体上线。

也可以手动安装：将 `custom_components/companion_link` 复制到 HA 的 `config/custom_components/companion_link`，重启 HA 后添加集成。

## 客户端协议

配套 app 共用以下本地事件协议。每个客户端在状态与命令事件中都必须带相同的 `device_id`；命令接收方只执行发给自身 ID 的命令。

- `companion_link_update`：状态上报，至少包含 `device_id`、`device_name`、`client_name`、`manufacturer`、`device_model` 和 `app_version`。各 app 可继续上报自己的状态字段。
- `companion_link_command`：HA 下发命令，包含目标 `device_id`、`command` 和可选参数。
- `companion_link_command_result`：命令执行结果，包含 `device_id`、`command`、`success` 和 `message`。

HA 配置流程按 `device_id` 创建独立配置项，状态、实体和命令都会按 ID 隔离。新增 app 时，先选用现有字段和命令；确需增加能力时再扩展协议。

## 控制能力

- 唤醒屏幕：Android 电源唤醒锁，无需 Root。
- 休眠屏幕：应用级 `su` 授权后发送固定的 `input keyevent 223`。Root 不可用时实体会显示不可用。
- 亮度：需要在 app **设置 → 屏幕与后台保活** 中授权“修改系统设置”。此控制调整 Android 系统屏幕亮度；Xperia Touch 投影光学引擎是否跟随该值仍需实机验证。
- 闹钟响铃时，HA 会显示 **贪睡闹钟 10 分钟** 和 **停止闹钟** 按钮；非响铃期间按钮不可用。
- 控制结果会出现在 **最近控制结果** 传感器中，并触发一次即时状态上报。

## 设备没有出现时

- 确认 HACS 外部仓库地址是 `https://github.com/Praepes/companion-link`，类型为 **Integration**；或确认手动安装目录是 `config/custom_components/companion_link`。
- 每个客户端 app 在 **Home Assistant 与本机设备** 设置中显示自己的配对 ID。对每台客户端分别添加一个 Companion Link 配置项。
- 在 app 中保存 HA 地址和长期访问令牌，再点击 **测试本机状态上报**。若该设备仍不可用，检查配对 ID、app 地址、令牌及 HA 日志中的集成错误。
- 设备实体建立后，即使 app 尚未上报，也应能在集成设备页看到实体；收到状态事件后实体从不可用转为在线。

HA 令牌只保存在 app 端，不随本机闹钟备份导出。集成使用 `companion_link` 域名和 `companion_link_*` 事件协议，并按配对 ID 区分设备。由 Morning Panel 2.x 升级时，请删除旧集成并重新添加客户端；实体历史和旧实体 ID 不会迁移。
