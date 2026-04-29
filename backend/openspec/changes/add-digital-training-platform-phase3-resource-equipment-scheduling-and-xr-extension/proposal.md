## Why

一二期已建立核心教学闭环（用户管理 → 课程/班级/任务 → 学生提交 → 教师评分），但实训教学依赖物理场地和设备的协调使用。当前系统无法管理场地、设备资源，也无法支持教学排期预约。随着平台从线上管理走向线上线下一体化，资源排期成为必须解决的能力缺口。同时，XR 实训正在成为趋势，需要在架构层面预留扩展接口，避免未来集成时重构核心预约域。

## What Changes

- 新增场地（Venue）管理：支持场地基础信息 CRUD、状态管理（active/inactive/maintenance）、容量记录
- 新增设备（Equipment）管理：支持设备台账 CRUD、状态管理（active/inactive/maintenance）、分类与序列号
- 新增预约排期（Booking）管理：支持面向教学场景的场地预约，包含时间冲突检测、并发控制、all-or-nothing 的场地+设备联合预约
- 新增利用率统计：场地利用率、高峰时段分布、设备使用频次，明确时间窗口、分子分母定义
- 激活 facility_manager 角色：作为资源管理的核心操作者，配合 admin 管理场地和设备
- 预留 XR 扩展底座：external_id 字段、client_reference 幂等键、provider/adapter 抽象、事件追踪模型
- 所有写操作接入审计日志（AuditLog）

## Capabilities

### New Capabilities
- `venue-management`: 场地基础信息 CRUD、状态管理、可用性查询
- `equipment-management`: 设备台账 CRUD、状态管理、分类
- `booking-management`: 预约排期 CRUD、时间冲突检测、并发一致性、all-or-nothing 设备绑定、状态流转
- `resource-statistics`: 场地利用率、设备使用频次、高峰时段统计查询
- `xr-extension-stubs`: XR provider 抽象、external_id 绑定、client_reference 幂等、事件记录模型

### Modified Capabilities
（无已有 spec 需要修改，facility_manager 角色已在二期 CHECK 约束中预留）

## Impact

- **新增数据库表**: venues、equipment、bookings、booking_equipment（共 4 张表 + 索引）
- **新增路由模块**: venues.py、equipment.py、bookings.py，统计端点扩展到 dashboard.py
- **权限变更**: facility_manager 角色首次获得实际路由权限（admin 亦可操作资源管理）
- **依赖**: 复用已有 booking_utils.py（check_time_overlap、acquire_row_lock）、audit.py（audit_log）
- **迁移**: 4 张新表的 Alembic migration，venue/equipment 上需新增 external_id 列（nullable, indexed）
- **测试**: 每个新模块需 CRUD 测试、权限测试、并发冲突测试、统计查询测试
