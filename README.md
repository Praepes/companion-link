# Companion Link for Home Assistant

此集成把 Morning Panel 等配套客户端连接到 Home Assistant。每台客户端设备各添加一个配置项；每个设备的状态与命令按设备配对 ID 独立路由，多个客户端可共用此集成。

## 从 HACS 安装

1. 在 HACS 右上角菜单打开 **自定义存储库**。
2. 添加 `https://github.com/Praepes/companion-link`，类型选 **Integration**。
3. 安装 **Companion Link** 并重启 Home Assistant。
4. 打开 app 的 Home Assistant 设置，找到设备 IP 地址和 8 位配对码。
5. 在 Home Assistant 的 **设置 → 设备与服务 → 添加集成** 中添加 **Companion Link**，填入设备 IP 和配对码。
6. HA 每 10 秒查询本机状态；此方式不需要在 app 中填写 HA 长期访问令牌。

也可以手动安装：将 `custom_components/companion_link` 复制到 HA 的 `config/custom_components/companion_link`，重启 HA 后添加集成。

旧版按设备 ID 配对的连接会继续使用原有事件方式，已有实体 ID 保持不变。
如需切换到 IP 配对，重新添加同一设备的 IP 和配对码即可原位更新连接信息。

## 客户端协议

配套 app 共用以下本地事件协议。每个客户端在状态与命令事件中都必须带相同的 `device_id`；命令接收方只执行发给自身 ID 的命令。

- `companion_link_update`：状态上报，至少包含 `device_id`、`device_name`、`client_name`、`manufacturer`、`device_model` 和 `app_version`。各 app 可继续上报自己的状态字段。
- `companion_link_command`：HA 下发命令，包含目标 `device_id`、`command` 和可选参数。
- `companion_link_command_result`：命令执行结果，包含 `device_id`、`command`、`success` 和 `message`。

HA 配置流程按 `device_id` 创建独立配置项，状态、实体和命令都会按 ID 隔离。新增 app 时，先选用现有字段和命令；确需增加能力时再扩展协议。

## 控制能力

- G1109 唤醒：恢复风扇 → 光机电源 → 光源 → 唤醒 Android；需要应用级 Root。其他 Android 设备仍使用电源唤醒锁。
- G1109 休眠：Android 熄屏 → 关闭光源 → 光机电源 → 风扇；需要应用级 Root。其他设备发送固定的 `input keyevent 223`。Root 不可用时实体会显示不可用。
- 亮度：需要在 app **设置 → 屏幕与后台保活** 中授权“修改系统设置”。此控制调整 Android 系统屏幕亮度；Xperia Touch 投影光学引擎是否跟随该值仍需实机验证。
- 闹钟响铃时，HA 会显示 **贪睡闹钟 10 分钟** 和 **停止闹钟** 按钮；非响铃期间按钮不可用。
- 控制结果会出现在 **最近控制结果** 传感器中，并触发一次即时状态上报。

G1109 更新 App 和此目录下的集成、重启 HA 后，会增加 **休眠并关闭投影**、**唤醒并恢复投影** 按钮以及 **投影输入** 选择实体：
`Android` 返回晨间面板并恢复投影，`HDMI` 恢复投影并切到已连接的 HDMI 输入。
实体根据机型／`input_source_supported` 建立，Root 不可用时仍会显示为不可用，支持 App 后续取得授权。
3.1.1 修复状态轮询反复调用 Root：当前输入读取原厂公开属性 `persist.service.hdmi.state`，
不会在每次 HA 轮询时启动 `su`。HDMI 接线状态在免 Root 查询中为未知，实际切换时才由 Root 检查；未接线会返回失败。
HA 发往本机的固定命令为 `{"command":"input_source","source":"HDMI"}` 或 `Android`，
命令等待上限为 60 秒。现有休眠、唤醒入口会先退出 HDMI，再执行光机电源流程。
App 和集成的本地 API 已验证；真实 HA 新实体联测需完成集成更新。

手动升级：把 ZIP 中的 `custom_components/companion_link` 完整覆盖到 HA 的
`config/custom_components/companion_link`，然后重启 Home Assistant；仅重新配对不会载入新增平台。
原有配对可以保留，升级后集成详情应显示版本 **3.1.2**。

## 设备没有出现时

- 确认 HACS 外部仓库地址是 `https://github.com/Praepes/companion-link`，类型为 **Integration**；或确认手动安装目录是 `config/custom_components/companion_link`。
- 每个客户端 app 在 **Home Assistant 与本机设备** 设置中显示自己的配对 ID。对每台客户端分别添加一个 Companion Link 配置项。
- 在 app 中保存 HA 地址和长期访问令牌，再点击 **测试本机状态上报**。若该设备仍不可用，检查配对 ID、app 地址、令牌及 HA 日志中的集成错误。
- 设备实体建立后，即使 app 尚未上报，也应能在集成设备页看到实体；收到状态事件后实体从不可用转为在线。

HA 令牌只保存在 app 端，不随本机闹钟备份导出。集成使用 `companion_link` 域名和 `companion_link_*` 事件协议，并按配对 ID 区分设备。由 Morning Panel 2.x 升级时，请删除旧集成并重新添加客户端；实体历史和旧实体 ID 不会迁移。

## 投影留言（集成 3.1.2 / Morning Panel 0.3.3）

设备页面新增 **留言内容**、**留言铃声**、**发送留言**：先填写内容（最多 255 字），再选择是否播放提示音，最后点击发送。
编辑内容和切换铃声只保存草稿，不会立即投影。也可以在自动化中调用：

```yaml
action: companion_link.send_message
data:
  device_id: "填写 App 的 Companion Link 配对 ID"
  text: "晚饭做好了，请来吃饭。"
  play_sound: true
```

- 休眠时自动恢复风扇、光机和 Android，显示三分钟后恢复休眠；原本唤醒则返回首页。
- 新留言覆盖上一条并重新计时三分钟，点击画面或返回键可提前结束。
- 铃声使用系统通知提示音，跟随闹钟音量循环播放约十秒（App 0.3.4 起）；静音留言不播放声音。
- 闹钟优先，留言等待闹钟结束后再显示三分钟。HA 主动休眠、唤醒或切换输入会结束当前留言。
- 只有上报 `message_supported: true` 的客户端会建立这三个实体，保留旧版本设备兼容性。
- 本机 API 命令：`set_message_config` 保存 `text` / `play_sound`；`send_message` 省略参数时使用已保存草稿。
