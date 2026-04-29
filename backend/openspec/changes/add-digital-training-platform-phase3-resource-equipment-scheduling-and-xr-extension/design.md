## Context

系统已完成一期（核心教学闭环）和二期（课程管理 + AI 辅助），当前用户体系包含 admin、teacher、student、facility_manager 四种角色。二期已在 DB CHECK 约束中预留 facility_manager，但无实际路由。前置冲刺已完成：时间函数统一（_utcnow_naive）、角色常量（UserRole）、admin-or-owner 权限（require_role_or_owner）、并发原语（check_time_overlap / acquire_row_lock）、审计日志（AuditLog）、双 session 测试基础设施。

现有数据模型围绕 User → Class/Course → Task → Submission → Grade 的教学链路，无任何资源/场地/设备/预约概念。

## Goals / Non-Goals

**Goals:**
- 建立场地（Venue）和设备（Equipment）的基础 CRUD 与状态管理
- 建立预约排期（Booking）能力，支持场地 + 设备联合预约，all-or-nothing 策略
- 实现场地利用率、设备使用频次、高峰时段三项统计
- 激活 facility_manager 角色的实际路由权限
- 为 XR 平台对接预留数据契约（external_id、client_reference、provider 抽象、事件追踪）
- 所有写操作接入审计日志

**Non-Goals:**
- 不做设备维修、报废、折旧、采购等资产全生命周期
- 不做 IoT 实时监控和在线状态采集
- 不做审批流、通知中心、外部日历同步
- 不做 XR 厂商深度集成，仅预留接口
- 不做 BI 级报表，仅三项基础统计
- 不做学生自助预约（通过教师/课程间接关联）

## Decisions

### D1: 场地模型 — 扁平结构，无嵌套层级

**决策**: Venue 为扁平表（name, capacity, location, description, status, external_id），不设 building/floor/room 嵌套。

**理由**: 现有系统无组织架构层级（无 department/building 表）。嵌套层级引入树结构，复杂度远超 MVP 需求。如果未来需要层级，通过 parent_id 自引用即可扩展，当前不做。

**替代方案**: Location 层级表（building → floor → room）。被否决：增加 2-3 张表和树查询，无业务需求驱动。

### D2: 设备模型 — 独立目录，不与 Venue 强绑定

**决策**: Equipment 为独立目录表（name, category, serial_number, status, external_id），通过 venue_id 可选 FK 记录常驻位置，但不作为预约的必要关联。

**理由**: 设备可能移动（便携设备），强绑定场地会导致设备迁移时数据不一致。设备在预约时通过 booking_equipment 关联，而非通过场地间接关联。

### D3: 预约模型 — 单 Booking 实体 + join table

**决策**:
```
Booking:
  id, venue_id (FK, NOT NULL), title, purpose
  start_time, end_time (NOT NULL, naive UTC)
  booked_by (FK → users), status
  course_id (FK, nullable), class_id (FK, nullable), task_id (FK, nullable)
  client_reference (unique, nullable) — XR 幂等键
  created_at, updated_at

booking_equipment:
  booking_id (FK → bookings), equipment_id (FK → equipment)
  PK(booking_id, equipment_id)
```

**理由**: 场地是预约的必需资源（每个预约必须有一个场地），设备是可选的。Join table 而非 JSON 数组，因为需要外键约束和冲突检测查询。

**All-or-nothing 策略**: 创建预约时，在事务内依次锁定场地和所有设备行（acquire_row_lock），任一冲突则整个事务回滚并返回 409。修改同理。

### D4: 冲突检测 — 逐资源悲观锁 + 半开区间

**决策**: 使用 `check_time_overlap()` + `acquire_row_lock()` 组合：
1. 对目标 venue 执行 `SELECT ... FOR UPDATE` 获取行锁
2. 检查 `start_time < new_end AND end_time > new_start`（半开区间）
3. 对每台设备重复上述操作
4. 任一冲突 → 回滚整个事务
5. 全部无冲突 → 插入 booking + booking_equipment 行

**理由**: 半开区间 `[start, end)` 是排期系统标准做法，避免相邻预约被误判重叠。悲观锁保证并发安全，与已有 `get_db_with_savepoint()` 配合使用。

**替代方案**: 乐观锁（version 字段）。被否决：排期场景写冲突概率高，乐观锁会导致大量重试，用户体验差。

### D5: 预约状态机 — 简化四态

**决策**:
```
approved → active → completed
approved → cancelled
approved → cancelled (by admin/facility_manager override)
```

状态：`approved`（已确认）、`active`（进行中）、`completed`（已结束）、`cancelled`（已取消）

**理由**: V1 不做审批流程。所有预约创建即 `approved`。`active`/`completed` 可通过定时任务或查询时判断（start_time <= now < end_time 为 active，end_time <= now 为 completed），不需要持久化状态机驱动。

**V1 简化**: 仅持久化 `approved` 和 `cancelled`。`active`/`completed` 由查询时按时间推导。避免引入定时状态迁移任务。

### D6: 利用率统计 — 明确定义

| 统计项 | 时间窗口 | 分子 | 分母 | 取消单 | 停用资源 | 跨日 |
|--------|---------|------|------|--------|---------|------|
| 场地利用率 | 自然周（Mon 00:00 - Sun 23:59） | 已批准预约的总时长（小时） | 场地 active 状态天数 × 24h | 不计入分子 | 停用期间从分母扣除（按天） | 按日拆分计入各自然周 |
| 设备使用频次 | 自然周 | 已批准预约中使用该设备的次数 | 不适用（频次，非比率） | 不计入 | 不适用 | 按日拆分 |
| 高峰时段 | 最近 30 天 | 每小时段的预约数量 | 不适用 | 不计入 | 不适用 | 不拆分 |

**查询实现**: 实时聚合查询（与二期 D6 一致），不加物化视图。venue_id/equipment_id + start_time/end_time 上的索引支撑查询性能。

**性能保护**: 统计查询加 `LIMIT 100`（最多返回 100 个资源），防止一次查询全量数据。

### D7: 权限矩阵

| 操作 | admin | facility_manager | teacher | student |
|------|-------|-----------------|---------|---------|
| 场地 CRUD | 全部 | 全部 | 只读查看 | 无权限 |
| 设备 CRUD | 全部 | 全部 | 只读查看 | 无权限 |
| 创建预约 | 全部 | 全部 | 可创建（自己为 booked_by） | 无权限 |
| 查看预约 | 全部 | 全部 | 自己创建的 + 关联自己课程的 | 无权限 |
| 取消预约 | 全部 | 全部 | 自己创建的 | 无权限 |
| 统计查看 | 全部 | 全部 | 无权限 | 无权限 |

**实现**: 使用 `require_role(["admin", "facility_manager"])` 控制写操作，`require_role_or_owner()` 控制教师对自己预约的修改/取消。学生暂无资源相关权限。

### D8: XR 扩展预留

**决策**: 最小预留，不引入 XR 相关表或外部依赖。

预留项：
1. Venue/Equipment 上的 `external_id` 字段（VARCHAR nullable, indexed）— 存储 XR 系统中的对应 ID
2. Booking 上的 `client_reference` 字段（VARCHAR unique nullable, indexed）— XR 系统的幂等键
3. `app/services/xr_provider.py` — 定义 XRProvider 协议接口（Protocol class），V1 提供 NullXRProvider（no-op 实现）
4. AuditLog 追踪所有预约状态变更 — XR 系统未来可通过审计日志轮询同步

**理由**: XR 集成高度依赖具体厂商 SDK，过早引入表结构会与厂商绑定。Protocol + no-op 实现 保证代码路径存在但不影响主流程。

**失败策略**: 本地预约不依赖 XR 成功。V1 的 NullXRProvider 不做任何外部调用。未来接入厂商时，实现 XRProvider 并注入即可，预约主流程不变。

### D9: 审计集成

**决策**: 所有预约写操作（创建、修改、取消）调用 `audit_log()` 服务，记录到已有 AuditLog 表。

entity_type 取值：`"booking"`、`"venue"`、`"equipment"`
action 取值：`"create"`、`"update"`、`"cancel"`、`"status_change"`
changes 字段：记录变更前后的关键字段（JSON）

### D10: 迁移策略

**决策**: 4 张新表分 2 个 migration：
1. Migration A: venues + equipment（资源基础表，无依赖）
2. Migration B: bookings + booking_equipment（依赖 venues 和 equipment）

**理由**: 分开 migration 便于部分回滚。如果 booking 表有问题，可以单独 downgrade 不影响资源表。

**Rollback**: 每个 migration 提供 downgrade（drop table）。无数据迁移风险（全新表）。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|---------|
| 教师预约后场地状态变更（如标记 maintenance），导致已批准预约与实际不符 | V1 不做预约-状态联动。预约创建时检查资源 status=active，后续状态变更不自动取消预约，由 facility_manager 人工处理 |
| 并发预约创建在极端并发下可能死锁 | MySQL InnoDB 默认死锁检测会自动回滚一个事务，返回 409 让客户端重试。acquire_row_lock 按 venue_id → equipment_id 顺序获取，减少死锁概率 |
| 统计查询在大数据量下可能变慢 | 利用率统计加时间范围过滤 + LIMIT 100。booking 表在 (venue_id, start_time, end_time) 上建组合索引 |
| external_id / client_reference 字段预留但 V1 未使用，可能被遗忘 | 在 schema 注释中标注 "Phase 3 XR extension stub"，tasks.md 中有明确的验证步骤 |
| facility_manager 角色权限范围大，可能误操作 | 所有写操作有 AuditLog 追踪。V1 不做细粒度权限（如限制只能管理特定场地） |
| 设备无实时在线状态，预约时无法确认设备实际可用 | V1 只检查设备 status 字段（active/inactive/maintenance）。实时状态需要 IoT 集成，属于 Non-Goal |
