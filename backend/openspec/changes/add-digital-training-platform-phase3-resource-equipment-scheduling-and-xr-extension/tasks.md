## 1. 数据模型与迁移

- [ ] 1.1 创建 Venue 模型 (`app/models/venue.py`)：id, name, capacity, location, description, status (active/inactive/maintenance), external_id, created_at, updated_at。注册到 `app/models/__init__.py`
- [ ] 1.2 创建 Equipment 模型 (`app/models/equipment.py`)：id, name, category, serial_number (unique), status, venue_id (nullable FK → venues), external_id, description, created_at, updated_at。注册到 `__init__.py`
- [ ] 1.3 创建 Booking 模型 (`app/models/booking.py`)：id, venue_id (FK, NOT NULL), title, purpose, start_time, end_time, booked_by (FK → users), status, course_id (nullable FK), class_id (nullable FK), task_id (nullable FK), client_reference (unique nullable), created_at, updated_at。注册到 `__init__.py`
- [ ] 1.4 创建 BookingEquipment 关联模型 (`app/models/booking.py` 内)：booking_id + equipment_id 联合主键。注册到 `__init__.py`
- [ ] 1.5 创建 Migration A：venues + equipment 表（含索引 external_id、equipment.serial_number 唯一索引）
- [ ] 1.6 创建 Migration B：bookings + booking_equipment 表（含组合索引 venue_id+start_time+end_time、client_reference 唯一索引）
- [ ] 1.7 验证 migration upgrade/downgrade 正常，`alembic upgrade head` && `alembic downgrade -1 && alembic upgrade head`
- [ ] 1.8 回归：现有 232 个测试全部通过

**迁移要求**: 每个 migration 提供 downgrade（drop table）。Migration B 的 down_revision 指向 Migration A。

## 2. Schema 定义

- [ ] 2.1 创建 Venue schemas (`app/schemas/venue.py`)：VenueCreate, VenueUpdate, VenueResponse, VenueListResponse。status 字段使用 Literal["active", "inactive", "maintenance"]
- [ ] 2.2 创建 Equipment schemas (`app/schemas/equipment.py`)：EquipmentCreate, EquipmentUpdate, EquipmentResponse, EquipmentListResponse。serial_number 可选
- [ ] 2.3 创建 Booking schemas (`app/schemas/booking.py`)：BookingCreate（含 equipment_ids 列表），BookingUpdate（时间、设备可改），BookingResponse（含 equipment 列表），BookingListResponse。时间校验 start_time < end_time

## 3. 场地管理 (venue-management)

- [ ] 3.1 创建 Venue CRUD 路由 (`app/routers/venues.py`)：POST create, GET list, GET /{id}, PUT /{id}, PATCH /{id}/status
- [ ] 3.2 权限：写操作 require_role(["admin", "facility_manager"])，读操作 require_role(["admin", "facility_manager", "teacher"])
- [ ] 3.3 审计集成：create/update/status_change 调用 audit_log()，entity_type="venue"
- [ ] 3.4 注册路由到 main.py
- [ ] 3.5 测试：`tests/test_venues.py` — CRUD 正常、权限拒绝（teacher 写、student 读）、状态转换、审计日志验证。目标 ≥8 个测试用例

## 4. 设备管理 (equipment-management)

- [ ] 4.1 创建 Equipment CRUD 路由 (`app/routers/equipment.py`)：POST create, GET list, GET /{id}, PUT /{id}, PATCH /{id}/status
- [ ] 4.2 权限：同场地管理
- [ ] 4.3 审计集成：create/update/status_change 调用 audit_log()，entity_type="equipment"
- [ ] 4.4 注册路由到 main.py
- [ ] 4.5 测试：`tests/test_equipment.py` — CRUD 正常、serial_number 唯一约束、权限、审计日志。目标 ≥8 个测试用例

## 5. 预约排期 (booking-management)

- [ ] 5.1 创建 Booking 服务层 (`app/services/booking_service.py`)：create_booking, update_booking, cancel_booking, get_booking, list_bookings
- [ ] 5.2 实现冲突检测逻辑：对 venue 执行 acquire_row_lock + check_time_overlap，对每台 equipment 同样操作。All-or-nothing：任一冲突回滚整个事务并抛 409
- [ ] 5.3 实现资源可用性检查：验证 venue.status == "active" 和所有 equipment.status == "active"，否则 400
- [ ] 5.4 实现 client_reference 幂等：创建前查询是否存在相同 client_reference，存在则返回已有记录
- [ ] 5.5 实现 booked_by 自动填充：从 current_user 注入，teacher 只能为自己预约
- [ ] 5.6 实现状态管理：cancel 时检查 start_time 是否已过（已过则 400），更新时检查原预约是否已开始
- [ ] 5.7 创建 Booking 路由 (`app/routers/bookings.py`)：POST create, GET list, GET /{id}, PUT /{id}, POST /{id}/cancel
- [ ] 5.8 权限：创建 require_role(["admin", "facility_manager", "teacher"])，查看/取消使用 require_role_or_owner（admin/facility_manager 全量，teacher 仅自己的）
- [ ] 5.9 审计集成：create/update/cancel 调用 audit_log()，entity_type="booking"
- [ ] 5.10 注册路由到 main.py
- [ ] 5.11 测试：`tests/test_bookings.py` — CRUD 正常、时间冲突检测（同场地重叠、同设备跨场地重叠、相邻不重叠）、并发冲突（双 session）、幂等 client_reference、资源不可用拒绝、权限控制（teacher 不能取消他人预约）、审计日志。目标 ≥15 个测试用例
- [ ] 5.12 回归：现有全部测试通过

## 6. 利用率统计 (resource-statistics)

- [ ] 6.1 在 `app/routers/dashboard.py` 新增统计端点：GET /api/v1/dashboard/venue-utilization, GET /api/v1/dashboard/equipment-usage, GET /api/v1/dashboard/peak-hours
- [ ] 6.2 实现场地利用率查询：按自然周聚合，分子=approved 预约时长，分母=active 天数×24h，cancelled 不计入
- [ ] 6.3 实现设备使用频次查询：按自然周统计 approved booking 中各设备出现次数，cancelled 不计入，跨日按日拆分归属周
- [ ] 6.4 实现高峰时段查询：最近 30 天每小时段 approved 预约计数
- [ ] 6.5 参数：默认最近 7 天，LIMIT 100 资源，需 start_date/end_date 参数
- [ ] 6.6 权限：require_role(["admin", "facility_manager"])
- [ ] 6.7 测试：`tests/test_resource_statistics.py` — 利用率计算正确（含 maintenance 扣分母）、取消不计入、LIMIT 生效、权限拒绝。目标 ≥8 个测试用例

## 7. XR 扩展预留 (xr-extension-stubs)

- [ ] 7.1 创建 XRProvider 协议 (`app/services/xr_provider.py`)：Protocol class，方法 on_booking_created / on_booking_updated / on_booking_cancelled
- [ ] 7.2 创建 NullXRProvider：所有方法返回 None，无外部调用
- [ ] 7.3 在 booking_service 中注入 xr_provider，创建/更新/取消时调用对应方法
- [ ] 7.4 测试：`tests/test_xr_provider.py` — NullXRProvider 调用无异常、不影响 booking 主流程。目标 ≥3 个测试用例

## 8. 集成验证与收口

- [ ] 8.1 全量测试：`pytest -v` 全部通过（目标 ≥270 个测试）
- [ ] 8.2 Migration 链验证：从空库 `alembic upgrade head` 无报错
- [ ] 8.3 API 回归：现有 43 个端点无破坏性变更
- [ ] 8.4 审计完整性：所有新写操作均产生 AuditLog 条目
- [ ] 8.5 external_id / client_reference 字段存在且可查询（手动验证或集成测试）
- [ ] 8.6 文档：更新 CLAUDE.md 中项目状态说明（如需要）

## PR 分解建议

| PR | 覆盖 Tasks | 内容 |
|----|-----------|------|
| PR 5a | 1.1-1.5, 2.1, 3.1-3.5 | Venue 模型 + 迁移 + Schema + CRUD 路由 + 测试 |
| PR 5b | 1.2, 1.4, 1.6, 2.2, 4.1-4.5 | Equipment 模型 + 迁移 + Schema + CRUD 路由 + 测试 |
| PR 5c | 1.3-1.4, 1.6, 2.3, 5.1-5.12 | Booking 模型 + 迁移 + 服务层 + 冲突检测 + CRUD 路由 + 测试 |
| PR 5d | 6.1-6.7 | 利用率统计端点 + 测试 |
| PR 5e | 7.1-7.4 | XR Provider 协议 + NullXRProvider + 测试 |
| PR 5f | 8.1-8.6 | 集成验证 + 收口 |

每个 PR 独立可测试、可部署、可回滚。
