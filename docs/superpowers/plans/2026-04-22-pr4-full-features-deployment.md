# PR4: Full Features + Deployment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all remaining backend CRUD, admin frontend pages, teacher/student UI enhancements, and production deployment configuration — delivering a fully functional, deployable platform.

**Architecture:** Extend existing FastAPI routers with full CRUD endpoints (pagination, filtering, validation). Add a new `users` router for admin user management. On the frontend, add admin views (UserList, ClassList, ClassRoster) and enhance existing teacher/student views (edit, archive, bulk grade, version display). Deployment uses Nginx reverse proxy + systemd + shell scripts.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, PyJWT, bcrypt, MySQL 8, Vue 3, Element Plus, Pinia, Vue Router, axios, Nginx, systemd

---

## File Structure

### New files to create

| File | Purpose |
|------|---------|
| `backend/app/schemas/user.py` | User CRUD schemas (create, update, response) |
| `backend/app/routers/users.py` | Admin user management endpoints |
| `backend/tests/test_auth_extended.py` | Tests for refresh, logout, change-password, reset-password |
| `backend/tests/test_users.py` | Tests for user CRUD endpoints |
| `backend/tests/test_classes_extended.py` | Tests for class PUT, DELETE, list, enroll |
| `backend/tests/test_tasks_extended.py` | Tests for task PUT, DELETE, archive, admin list |
| `backend/tests/test_grades_extended.py` | Tests for bulk grading |
| `backend/tests/test_file_cleanup.py` | Tests for file cleanup service |
| `frontend/src/views/admin/UserList.vue` | Admin user management page |
| `frontend/src/views/admin/ClassList.vue` | Admin class management page |
| `frontend/src/views/admin/ClassRoster.vue` | Admin class roster page |
| `frontend/src/views/teacher/TaskEdit.vue` | Teacher task edit page |
| `deploy/nginx.conf` | Nginx reverse proxy config |
| `deploy/training-platform.service` | systemd service unit file |
| `deploy/deploy.sh` | One-click deployment script |

### Existing files to modify

| File | Changes |
|------|---------|
| `backend/app/schemas/auth.py` | Add RefreshRequest, ChangePasswordRequest |
| `backend/app/schemas/class_.py` | Add ClassUpdate, EnrollStudents |
| `backend/app/schemas/task.py` | Add TaskUpdate |
| `backend/app/schemas/grade.py` | Add BulkGradeItem, BulkGradeRequest |
| `backend/app/routers/auth.py` | Add refresh, logout, change-password, reset-password endpoints |
| `backend/app/routers/classes.py` | Add PUT, DELETE, GET list (admin), POST enroll |
| `backend/app/routers/tasks.py` | Add PUT, DELETE, archive, GET list (admin) |
| `backend/app/routers/grades.py` | Add bulk grading endpoint |
| `backend/app/main.py` | Include users router |
| `frontend/src/router/index.js` | Add admin routes + teacher task edit route |
| `frontend/src/layouts/MainLayout.vue` | Add admin sidebar items |
| `frontend/src/stores/auth.js` | Update 401 interceptor to try refresh |
| `frontend/src/api/index.js` | Add refresh logic to 401 interceptor |
| `frontend/src/views/teacher/TaskList.vue` | Add edit, archive, delete buttons |
| `frontend/src/views/teacher/SubmissionReview.vue` | Add bulk grade button, penalty display |
| `frontend/src/views/student/SubmissionDetail.vue` | Show version info prominently |

---

## Task 1: Auth Refresh + Logout Endpoints

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/routers/auth.py`
- Create: `backend/tests/test_auth_extended.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_auth_extended.py`:

```python
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_refresh_success(client, db_session):
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="refresh_user", password="pass1234")
    # Login to get both tokens
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "refresh_user", "password": "pass1234"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio(loop_scope="session")
async def test_refresh_revoked_token(client, db_session):
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="revoke_user", password="pass1234")
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "revoke_user", "password": "pass1234"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Logout first
    token = login_resp.json()["access_token"]
    await client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_logout_success(client, db_session):
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="logout_user", password="pass1234")
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "logout_user", "password": "pass1234"},
    )
    token = login_resp.json()["access_token"]
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "成功" in resp.json()["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_auth_extended.py -v`
Expected: FAIL — endpoints not yet defined

- [ ] **Step 3: Add schemas and implement endpoints**

Add to `backend/app/schemas/auth.py`:

```python
class RefreshRequest(BaseModel):
    refresh_token: str
```

Add to `backend/app/routers/auth.py` (after the existing `login` function):

```python
@router.post("/refresh")
async def refresh_token(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    from app.utils.security import hash_token

    token_hash = hash_token(data.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        )
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=401, detail="无效的刷新令牌")

    now = datetime.datetime.now(datetime.timezone.utc)
    if rt.expires_at.replace(tzinfo=datetime.timezone.utc) < now:
        raise HTTPException(status_code=401, detail="刷新令牌已过期")

    # Revoke old refresh token
    rt.revoked = True

    # Get user
    user_result = await db.execute(select(User).where(User.id == rt.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")

    # Issue new token pair
    access_token = create_access_token(user.id, user.role, user.username)
    new_refresh_token_str = create_refresh_token(user.id)
    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh_token_str),
        expires_at=now + datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_rt)
    await db.flush()

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token_str,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    data: RefreshRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.utils.security import hash_token

    token_hash = hash_token(data.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()
    if rt and rt.user_id == current_user["id"]:
        rt.revoked = True
        await db.flush()

    return {"message": "退出登录成功"}
```

Add this import at the top of `routers/auth.py` (if not already present):

```python
from app.dependencies.auth import get_current_user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_auth_extended.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add backend/ && git commit -m "feat: add auth refresh and logout endpoints"
```

---

## Task 2: Auth Change-Password + Reset-Password

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/tests/test_auth_extended.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_auth_extended.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_change_password_success(client, db_session):
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="changepw_user", password="oldpass123")
    token = await login_user(client, "changepw_user", "oldpass123")

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "oldpass123", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Login with new password
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "changepw_user", "password": "newpass456"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_change_password_wrong_current(client, db_session):
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="wrongpw_user", password="pass1234")
    token = await login_user(client, "wrongpw_user", "pass1234")

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "wrongpass", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_change_password_too_short(client, db_session):
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="shortpw_user", password="pass1234")
    token = await login_user(client, "shortpw_user", "pass1234")

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "pass1234", "new_password": "short"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_reset_password_admin(client, db_session):
    from tests.helpers import create_test_user

    admin = await create_test_user(db_session, username="reset_admin", password="admin1234", role="admin")
    student = await create_test_user(db_session, username="reset_student", password="oldpass123")

    admin_token = await login_user(client, "reset_admin", "admin1234")

    resp = await client.post(
        f"/api/auth/reset-password/{student.id}",
        json={"new_password": "resetpass1"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    # Student can login with new password
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "reset_student", "password": "resetpass1"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["must_change_password"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_auth_extended.py::test_change_password_success tests/test_auth_extended.py::test_reset_password_admin -v`
Expected: FAIL

- [ ] **Step 3: Add schemas and implement endpoints**

Add to `backend/app/schemas/auth.py`:

```python
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)

class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)
```

Add `Field` to the import:
```python
from pydantic import BaseModel, Field
```

Add to `backend/app/routers/auth.py`:

```python
@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码错误")

    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    await db.flush()
    return {"message": "密码修改成功"}


@router.post("/reset-password/{user_id}")
async def reset_password(
    user_id: int,
    data: ResetPasswordRequest,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.password_hash = hash_password(data.new_password)
    user.must_change_password = True
    await db.flush()
    return {"message": "密码重置成功"}
```

Add `require_role` to the imports at the top of `routers/auth.py`:
```python
from app.dependencies.auth import get_current_user, require_role
```

And add `hash_password` if not already imported:
```python
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_auth_extended.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add backend/ && git commit -m "feat: add change-password and admin reset-password endpoints"
```

---

## Task 3: User Schemas + POST + GET List + GET Me

**Files:**
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/routers/users.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_users.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_users.py`:

```python
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_create_user(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin1", password="admin1234", role="admin")
    token = await login_user(client, "admin1", "admin1234")

    resp = await client.post(
        "/api/users",
        json={
            "username": "new_teacher",
            "password": "teacher1234",
            "real_name": "张老师",
            "role": "teacher",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "new_teacher"
    assert data["role"] == "teacher"
    assert data["must_change_password"] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_create_user_duplicate(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_dup", password="admin1234", role="admin")
    await create_test_user(db_session, username="existing", password="pass1234")
    token = await login_user(client, "admin_dup", "admin1234")

    resp = await client.post(
        "/api/users",
        json={"username": "existing", "password": "pass1234", "real_name": "重复", "role": "student"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_create_user_forbidden(client, db_session):
    from tests.helpers import create_test_user, login_user

    teacher = await create_test_user(db_session, username="teacher_noauth", password="pass1234", role="teacher")
    token = await login_user(client, "teacher_noauth", "pass1234")

    resp = await client.post(
        "/api/users",
        json={"username": "some", "password": "pass1234", "real_name": "名", "role": "student"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_list_users(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_list", password="admin1234", role="admin")
    await create_test_user(db_session, username="s1", password="pass1234", role="student", real_name="学生一")
    await create_test_user(db_session, username="s2", password="pass1234", role="student", real_name="学生二")
    token = await login_user(client, "admin_list", "admin1234")

    resp = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 3


@pytest.mark.asyncio(loop_scope="session")
async def test_list_users_filter_role(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_filter", password="admin1234", role="admin")
    await create_test_user(db_session, username="t1", password="pass1234", role="teacher")
    await create_test_user(db_session, username="s3", password="pass1234", role="student")
    token = await login_user(client, "admin_filter", "admin1234")

    resp = await client.get(
        "/api/users?role=teacher",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(u["role"] == "teacher" for u in data["items"])


@pytest.mark.asyncio(loop_scope="session")
async def test_get_me(client, db_session):
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="me_user", password="pass1234")
    token = await login_user(client, "me_user", "pass1234")

    resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "me_user"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_users.py -v`
Expected: FAIL

- [ ] **Step 3: Create schemas and implement endpoints**

Create `backend/app/schemas/user.py`:

```python
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=8)
    real_name: str
    role: str
    email: Optional[str] = None
    phone: Optional[str] = None
    primary_class_id: Optional[int] = None


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    primary_class_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    real_name: str
    role: str
    is_active: bool
    email: Optional[str] = None
    phone: Optional[str] = None
    primary_class_id: Optional[int] = None
    must_change_password: bool
    created_at: datetime


class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int
```

Create `backend/app/routers/users.py`:

```python
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.user import User
from app.models.class_ import Class
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserListResponse
from app.utils.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _user_to_response(user):
    return UserResponse(
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        role=user.role,
        is_active=user.is_active,
        email=user.email,
        phone=user.phone,
        primary_class_id=user.primary_class_id,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
    )


@router.post("", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    if data.primary_class_id:
        cls = await db.execute(select(Class).where(Class.id == data.primary_class_id))
        if not cls.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="班级不存在")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        real_name=data.real_name,
        role=data.role,
        email=data.email,
        phone=data.phone,
        primary_class_id=data.primary_class_id,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    return _user_to_response(user)


@router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    role: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if search:
        query = query.where(
            User.username.contains(search) | User.real_name.contains(search)
        )

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    result = await db.execute(query.offset(skip).limit(limit).order_by(User.id))
    users = result.scalars().all()
    return UserListResponse(
        items=[_user_to_response(u) for u in users], total=total
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return _user_to_response(user)
```

Add to `backend/app/main.py`:

```python
from app.routers import users as users_router
```

```python
app.include_router(users_router.router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_users.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add backend/ && git commit -m "feat: add user CRUD - create, list, and profile endpoints"
```

---

## Task 4: User Update + Deactivate

**Files:**
- Modify: `backend/app/routers/users.py`
- Modify: `backend/tests/test_users.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_users.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_update_me(client, db_session):
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="updateme", password="pass1234")
    token = await login_user(client, "updateme", "pass1234")

    resp = await client.put(
        "/api/users/me",
        json={"real_name": "新名字", "email": "new@test.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["real_name"] == "新名字"
    assert resp.json()["email"] == "new@test.com"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_user_admin(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_upd", password="admin1234", role="admin")
    target = await create_test_user(db_session, username="target_user", password="pass1234")
    token = await login_user(client, "admin_upd", "admin1234")

    resp = await client.put(
        f"/api/users/{target.id}",
        json={"real_name": "被改名", "is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["real_name"] == "被改名"
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio(loop_scope="session")
async def test_deactivate_user(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_deact", password="admin1234", role="admin")
    target = await create_test_user(db_session, username="deact_target", password="pass1234")
    token = await login_user(client, "admin_deact", "admin1234")

    resp = await client.put(
        f"/api/users/{target.id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Deactivated user can't login
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "deact_target", "password": "pass1234"},
    )
    assert login_resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_users.py::test_update_me tests/test_users.py::test_update_user_admin tests/test_users.py::test_deactivate_user -v`
Expected: FAIL

- [ ] **Step 3: Implement endpoints**

Add to `backend/app/routers/users.py`:

```python
@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.flush()
    return _user_to_response(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.flush()
    return _user_to_response(user)


@router.put("/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_active = False
    await db.flush()
    return {"message": "用户已停用"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_users.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add backend/ && git commit -m "feat: add user update and deactivate endpoints"
```

---

## Task 5: Class PUT + DELETE Endpoints

**Files:**
- Modify: `backend/app/schemas/class_.py`
- Modify: `backend/app/routers/classes.py`
- Create: `backend/tests/test_classes_extended.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_classes_extended.py`:

```python
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_update_class(client, db_session):
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(db_session, username="admin_cls", password="admin1234", role="admin")
    teacher = await create_test_user(db_session, username="cls_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, name="旧名称", teacher_id=teacher.id)
    token = await login_user(client, "admin_cls", "admin1234")

    resp = await client.put(
        f"/api/classes/{cls.id}",
        json={"name": "新名称"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "新名称"


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_class(client, db_session):
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(db_session, username="admin_del", password="admin1234", role="admin")
    cls = await create_test_class(db_session, name="待删除班级")
    token = await login_user(client, "admin_del", "admin1234")

    resp = await client.delete(
        f"/api/classes/{cls.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_class_with_students(client, db_session):
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(db_session, username="admin_delstu", password="admin1234", role="admin")
    cls = await create_test_class(db_session, name="有学生班级")
    student = await create_test_user(db_session, username="cls_stu", password="pass1234", primary_class_id=cls.id)
    token = await login_user(client, "admin_delstu", "admin1234")

    resp = await client.delete(
        f"/api/classes/{cls.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "学生" in resp.json()["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_classes_extended.py -v`
Expected: FAIL

- [ ] **Step 3: Add schemas and implement endpoints**

Add to `backend/app/schemas/class_.py`:

```python
class ClassUpdate(BaseModel):
    name: Optional[str] = None
    semester: Optional[str] = None
    teacher_id: Optional[int] = None
```

Add `Optional` to the imports in `schemas/class_.py` if not already present.

Add to `backend/app/routers/classes.py`:

```python
@router.put("/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: int,
    data: ClassUpdate,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cls, field, value)
    await db.flush()

    teacher_name = None
    if cls.teacher_id:
        t = await db.execute(select(User).where(User.id == cls.teacher_id))
        teacher = t.scalar_one_or_none()
        if teacher:
            teacher_name = teacher.real_name

    student_count_result = await db.execute(
        select(func.count()).select_from(User).where(User.primary_class_id == cls.id)
    )
    student_count = student_count_result.scalar() or 0

    return ClassResponse(
        id=cls.id, name=cls.name, semester=cls.semester,
        teacher_id=cls.teacher_id, teacher_name=teacher_name,
        student_count=student_count, created_at=cls.created_at,
    )


@router.delete("/{class_id}")
async def delete_class(
    class_id: int,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    student_count = await db.execute(
        select(func.count()).select_from(User).where(User.primary_class_id == class_id)
    )
    if student_count.scalar() > 0:
        raise HTTPException(status_code=400, detail="班级中仍有学生，无法删除")

    await db.delete(cls)
    await db.flush()
    return {"message": "班级已删除"}
```

Add `func` import to `routers/classes.py`: `from sqlalchemy import select, func`

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_classes_extended.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add backend/ && git commit -m "feat: add class update and delete endpoints"
```

---

## Task 6: Class GET List (Admin) + POST Enroll

**Files:**
- Modify: `backend/app/schemas/class_.py`
- Modify: `backend/app/routers/classes.py`
- Modify: `backend/tests/test_classes_extended.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_classes_extended.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_list_classes_admin(client, db_session):
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(db_session, username="admin_listcls", password="admin1234", role="admin")
    await create_test_class(db_session, name="班级A", semester="2025-2026-1")
    await create_test_class(db_session, name="班级B", semester="2025-2026-2")
    token = await login_user(client, "admin_listcls", "admin1234")

    resp = await client.get("/api/classes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 2


@pytest.mark.asyncio(loop_scope="session")
async def test_list_classes_semester_filter(client, db_session):
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(db_session, username="admin_semf", password="admin1234", role="admin")
    await create_test_class(db_session, name="过去班级", semester="2024-2025-1")
    await create_test_class(db_session, name="当前班级", semester="2025-2026-2")
    token = await login_user(client, "admin_semf", "admin1234")

    resp = await client.get(
        "/api/classes?semester=2025-2026-2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(c["semester"] == "2025-2026-2" for c in data["items"])


@pytest.mark.asyncio(loop_scope="session")
async def test_enroll_students(client, db_session):
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(db_session, username="admin_enroll", password="admin1234", role="admin")
    cls = await create_test_class(db_session, name="注册班级")
    s1 = await create_test_user(db_session, username="enroll_s1", password="pass1234")
    s2 = await create_test_user(db_session, username="enroll_s2", password="pass1234")
    token = await login_user(client, "admin_enroll", "admin1234")

    resp = await client.post(
        f"/api/classes/{cls.id}/students",
        json={"student_ids": [s1.id, s2.id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["enrolled_count"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_classes_extended.py::test_list_classes_admin tests/test_classes_extended.py::test_enroll_students -v`
Expected: FAIL

- [ ] **Step 3: Add schemas and implement endpoints**

Add to `backend/app/schemas/class_.py`:

```python
class ClassListResponse(BaseModel):
    items: List[ClassResponse]
    total: int

class EnrollStudents(BaseModel):
    student_ids: List[int]
```

Add to `backend/app/routers/classes.py`:

```python
@router.get("", response_model=ClassListResponse)
async def list_classes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    semester: Optional[str] = None,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Class)
    if semester:
        query = query.where(Class.semester == semester)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    result = await db.execute(query.offset(skip).limit(limit).order_by(Class.id))
    classes = result.scalars().all()

    items = []
    for cls in classes:
        teacher_name = None
        if cls.teacher_id:
            t = await db.execute(select(User).where(User.id == cls.teacher_id))
            teacher = t.scalar_one_or_none()
            if teacher:
                teacher_name = teacher.real_name
        sc = await db.execute(
            select(func.count()).select_from(User).where(User.primary_class_id == cls.id)
        )
        items.append(ClassResponse(
            id=cls.id, name=cls.name, semester=cls.semester,
            teacher_id=cls.teacher_id, teacher_name=teacher_name,
            student_count=sc.scalar() or 0, created_at=cls.created_at,
        ))
    return ClassListResponse(items=items, total=total)


@router.post("/{class_id}/students")
async def enroll_students(
    class_id: int,
    data: EnrollStudents,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    enrolled = 0
    for sid in data.student_ids:
        u = await db.execute(select(User).where(User.id == sid))
        user = u.scalar_one_or_none()
        if user and user.role == "student":
            user.primary_class_id = class_id
            enrolled += 1
    await db.flush()
    return {"enrolled_count": enrolled}
```

Add `Query` and `Optional` imports to `routers/classes.py` if needed:
```python
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_classes_extended.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add backend/ && git commit -m "feat: add class list and student enrollment endpoints"
```

---

## Task 7: Task PUT Endpoint

**Files:**
- Modify: `backend/app/schemas/task.py`
- Modify: `backend/app/routers/tasks.py`
- Create: `backend/tests/test_tasks_extended.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_tasks_extended.py`:

```python
import pytest
import json
import datetime


@pytest.mark.asyncio(loop_scope="session")
async def test_update_task(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="upd_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id, title="旧标题")
    token = await login_user(client, "upd_teacher", "pass1234")

    resp = await client.put(
        f"/api/tasks/{task.id}",
        json={"title": "新标题", "description": "新描述"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "新标题"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_task_not_owner(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    owner = await create_test_user(db_session, username="task_owner", password="pass1234", role="teacher")
    other = await create_test_user(db_session, username="task_other", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=owner.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=owner.id)
    token = await login_user(client, "task_other", "pass1234")

    resp = await client.put(
        f"/api/tasks/{task.id}",
        json={"title": "被改了"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_tasks_extended.py -v`
Expected: FAIL

- [ ] **Step 3: Add schema and implement endpoint**

Add to `backend/app/schemas/task.py`:

```python
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    deadline: Optional[datetime] = None
    allowed_file_types: Optional[List[str]] = None
    max_file_size_mb: Optional[int] = None
    allow_late_submission: Optional[bool] = None
    late_penalty_percent: Optional[float] = None
```

Add to `backend/app/routers/tasks.py`:

```python
@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    data: TaskUpdate,
    current_user=Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能编辑自己创建的任务")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "allowed_file_types" and value is not None:
            setattr(task, field, json.dumps(value))
        else:
            setattr(task, field, value)
    await db.flush()

    cls_result = await db.execute(select(Class).where(Class.id == task.class_id))
    cls = cls_result.scalar_one()
    return _task_to_response(task, cls.name)
```

Import `TaskUpdate` in `routers/tasks.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_tasks_extended.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add backend/ && git commit -m "feat: add task update endpoint"
```

---

## Task 8: Task DELETE + Archive + Admin GET List

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/tests/test_tasks_extended.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_tasks_extended.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_delete_task_no_submissions(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="del_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)
    token = await login_user(client, "del_teacher", "pass1234")

    resp = await client.delete(
        f"/api/tasks/{task.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_task_with_submissions(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="del_teacher2", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="del_student", password="pass1234", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)
    # Create a submission directly
    from app.models.submission import Submission
    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "del_teacher2", "pass1234")
    resp = await client.delete(
        f"/api/tasks/{task.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_archive_task(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="arch_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)
    token = await login_user(client, "arch_teacher", "pass1234")

    resp = await client.post(
        f"/api/tasks/{task.id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_tasks_admin(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    admin = await create_test_user(db_session, username="admin_tasklist", password="admin1234", role="admin")
    teacher = await create_test_user(db_session, username="list_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    await create_test_task(db_session, class_id=cls.id, created_by=teacher.id, title="任务1")
    await create_test_task(db_session, class_id=cls.id, created_by=teacher.id, title="任务2")
    token = await login_user(client, "admin_tasklist", "admin1234")

    resp = await client.get("/api/tasks", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_tasks_extended.py -v`
Expected: Some FAIL

- [ ] **Step 3: Implement endpoints**

Add to `backend/app/routers/tasks.py`:

```python
from typing import Optional
from fastapi import Query
from sqlalchemy import func

@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    current_user=Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能删除自己创建的任务")

    sub_count = await db.execute(
        select(func.count()).select_from(Submission).where(Submission.task_id == task_id)
    )
    if sub_count.scalar() > 0:
        raise HTTPException(status_code=400, detail="任务已有提交，无法删除")

    await db.delete(task)
    await db.flush()
    return {"message": "任务已删除"}


@router.post("/{task_id}/archive")
async def archive_task(
    task_id: int,
    current_user=Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能归档自己创建的任务")

    task.status = "archived"
    await db.flush()
    return {"id": task.id, "status": "archived"}


@router.get("", response_model=dict)
async def list_tasks_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Task)
    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    result = await db.execute(query.offset(skip).limit(limit).order_by(Task.id.desc()))
    tasks = result.scalars().all()

    items = []
    for task in tasks:
        cls_result = await db.execute(select(Class).where(Class.id == task.class_id))
        cls = cls_result.scalar_one_or_none()
        class_name = cls.name if cls else ""
        items.append(_task_to_response(task, class_name))

    return {"items": items, "total": total}
```

Also add `Submission` import at top of `routers/tasks.py`:
```python
from app.models.submission import Submission
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_tasks_extended.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add backend/ && git commit -m "feat: add task delete, archive, and admin list endpoints"
```

---

## Task 9: Bulk Grading Endpoint

**Files:**
- Modify: `backend/app/schemas/grade.py`
- Modify: `backend/app/routers/grades.py`
- Create: `backend/tests/test_grades_extended.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_grades_extended.py`:

```python
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_bulk_grade(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="bulk_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    s1 = await create_test_user(db_session, username="bulk_s1", password="pass1234", primary_class_id=cls.id)
    s2 = await create_test_user(db_session, username="bulk_s2", password="pass1234", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    from app.models.submission import Submission
    sub1 = Submission(task_id=task.id, student_id=s1.id)
    sub2 = Submission(task_id=task.id, student_id=s2.id)
    db_session.add_all([sub1, sub2])
    await db_session.flush()

    token = await login_user(client, "bulk_teacher", "pass1234")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades/bulk",
        json={
            "grades": [
                {"submission_id": sub1.id, "score": 85},
                {"submission_id": sub2.id, "score": 90, "feedback": "做得好"},
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["graded_count"] == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_bulk_grade_invalid_score(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="bulk_teacher2", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="bulk_s3", password="pass1234", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    from app.models.submission import Submission
    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "bulk_teacher2", "pass1234")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades/bulk",
        json={"grades": [{"submission_id": sub.id, "score": 150}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_grades_extended.py -v`
Expected: FAIL

- [ ] **Step 3: Add schemas and implement endpoint**

Add to `backend/app/schemas/grade.py`:

```python
class BulkGradeItem(BaseModel):
    submission_id: int
    score: float = Field(ge=0, le=100)
    feedback: Optional[str] = None

class BulkGradeRequest(BaseModel):
    grades: List[BulkGradeItem]
```

Add `Field` and `List` imports if not present:
```python
from pydantic import BaseModel, Field
from typing import Optional, List
```

Add to `backend/app/routers/grades.py`:

```python
@router.post("/{task_id}/grades/bulk")
async def bulk_grade(
    task_id: int,
    data: BulkGradeRequest,
    current_user=Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能评自己创建的任务")

    graded_count = 0
    for item in data.grades:
        sub_result = await db.execute(
            select(Submission).where(Submission.id == item.submission_id)
        )
        submission = sub_result.scalar_one_or_none()
        if not submission or submission.task_id != task_id:
            continue

        penalty_applied = None
        if submission.is_late and task.late_penalty_percent:
            penalty_applied = round(item.score * task.late_penalty_percent / 100, 2)

        existing = await db.execute(
            select(Grade).where(Grade.submission_id == submission.id)
        )
        grade = existing.scalar_one_or_none()
        if grade:
            grade.score = item.score
            grade.feedback = item.feedback
            grade.penalty_applied = penalty_applied
            grade.graded_by = current_user["id"]
        else:
            grade = Grade(
                submission_id=submission.id,
                score=item.score,
                feedback=item.feedback,
                penalty_applied=penalty_applied,
                graded_by=current_user["id"],
            )
            db.add(grade)
        graded_count += 1

    await db.flush()
    return {"graded_count": graded_count}
```

Import `BulkGradeRequest` and `BulkGradeItem` in `routers/grades.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_grades_extended.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add backend/ && git commit -m "feat: add bulk grading endpoint"
```

---

## Task 10: File Cleanup Tests

**Files:**
- Create: `backend/tests/test_file_cleanup.py`

- [ ] **Step 1: Write tests**

Create `backend/tests/test_file_cleanup.py`:

```python
import os
import datetime
import pytest

from app.services.file_cleanup import cleanup_orphan_files


@pytest.mark.asyncio(loop_scope="session")
async def test_cleanup_orphan_files(db_session, upload_dir):
    # Create an orphan file (no submission_files record)
    orphan_path = os.path.join(upload_dir, "orphan_test.txt")
    with open(orphan_path, "w") as f:
        f.write("orphan")

    deleted = await cleanup_orphan_files(db_session)
    assert deleted >= 1
    assert not os.path.exists(orphan_path)


@pytest.mark.asyncio(loop_scope="session")
async def test_cleanup_preserves_recent_files(db_session, upload_dir):
    recent_path = os.path.join(upload_dir, "recent_test.txt")
    with open(recent_path, "w") as f:
        f.write("recent")

    deleted = await cleanup_orphan_files(db_session)
    assert deleted == 0
    assert os.path.exists(recent_path)
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/gaofang/Desktop/new_project/backend && python -m pytest tests/test_file_cleanup.py -v`
Expected: 2 passed

- [ ] **Step 3: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add backend/ && git commit -m "test: add file cleanup service tests"
```

---

## Task 11: Frontend — Admin Routes + MainLayout Sidebar

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/layouts/MainLayout.vue`
- Modify: `frontend/src/stores/auth.js`

- [ ] **Step 1: Update router with admin routes**

Add to `frontend/src/router/index.js` children array (after the student routes):

```javascript
      {
        path: 'admin/users',
        name: 'AdminUserList',
        component: () => import('../views/admin/UserList.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'admin/classes',
        name: 'AdminClassList',
        component: () => import('../views/admin/ClassList.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'admin/classes/:id/roster',
        name: 'AdminClassRoster',
        component: () => import('../views/admin/ClassRoster.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'teacher/tasks/:id/edit',
        name: 'TeacherTaskEdit',
        component: () => import('../views/teacher/TaskEdit.vue'),
        meta: { roles: ['teacher'] },
      },
```

- [ ] **Step 2: Update MainLayout sidebar**

In `frontend/src/layouts/MainLayout.vue`, add admin section after the teacher template:

```vue
        <template v-if="auth.userRole === 'admin'">
          <el-menu-item index="/admin/users">
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/classes">
            <span>班级管理</span>
          </el-menu-item>
        </template>
```

- [ ] **Step 3: Update auth store getHomeRoute**

In `frontend/src/stores/auth.js`, change the admin case:

```javascript
      case 'admin': return '/admin/users'
```

- [ ] **Step 4: Verify build**

Run: `cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -5`
Expected: Build succeeds (views may not exist yet, but lazy loading handles missing modules at build time — they'll fail at runtime only)

Actually, the build will fail because the admin view files don't exist yet. Let me create placeholder files first.

Create empty placeholder files:
```bash
mkdir -p /Users/gaofang/Desktop/new_project/frontend/src/views/admin
touch /Users/gaofang/Desktop/new_project/frontend/src/views/admin/UserList.vue
touch /Users/gaofang/Desktop/new_project/frontend/src/views/admin/ClassList.vue
touch /Users/gaofang/Desktop/new_project/frontend/src/views/admin/ClassRoster.vue
touch /Users/gaofang/Desktop/new_project/frontend/src/views/teacher/TaskEdit.vue
```

Each placeholder should have:
```vue
<template><div>TODO</div></template>
```

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/ && git commit -m "feat: add admin routes and update sidebar navigation"
```

---

## Task 12: Frontend — Admin UserList Page

**Files:**
- Modify: `frontend/src/views/admin/UserList.vue`

- [ ] **Step 1: Implement UserList page**

Replace `frontend/src/views/admin/UserList.vue` with:

```vue
<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">用户管理</h3>
      <el-button type="primary" @click="showCreateDialog">新建用户</el-button>
    </div>
    <div style="margin-bottom: 16px; display: flex; gap: 12px">
      <el-select v-model="roleFilter" placeholder="筛选角色" clearable style="width: 120px" @change="fetchUsers">
        <el-option label="管理员" value="admin" />
        <el-option label="教师" value="teacher" />
        <el-option label="学生" value="student" />
      </el-select>
      <el-input v-model="searchText" placeholder="搜索用户名或姓名" clearable style="width: 200px" @clear="fetchUsers" @keyup.enter="fetchUsers" />
    </div>
    <el-table :data="users" v-loading="loading" stripe>
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="real_name" label="姓名" width="100" />
      <el-table-column prop="role" label="角色" width="80">
        <template #default="{ row }">{{ roleLabel(row.role) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '正常' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="email" label="邮箱" min-width="150" />
      <el-table-column prop="phone" label="电话" width="120" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="warning" @click="handleResetPassword(row)">重置密码</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      style="margin-top: 16px; justify-content: center"
      :current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      @current-change="handlePageChange"
    />

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新建用户'" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" :disabled="isEdit">
            <el-option label="管理员" value="admin" />
            <el-option label="教师" value="teacher" />
            <el-option label="学生" value="student" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const users = ref([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const roleFilter = ref('')
const searchText = ref('')
const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const formRef = ref(null)

const form = reactive({ username: '', password: '', real_name: '', role: 'student', email: '', phone: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur', min: 8 }],
  real_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

function roleLabel(role) {
  const map = { admin: '管理员', teacher: '教师', student: '学生' }
  return map[role] || role
}

async function fetchUsers() {
  loading.value = true
  try {
    const params = { skip: (currentPage.value - 1) * pageSize, limit: pageSize }
    if (roleFilter.value) params.role = roleFilter.value
    if (searchText.value) params.search = searchText.value
    const resp = await api.get('/users', { params })
    users.value = resp.data.items
    total.value = resp.data.total
  } catch { ElMessage.error('获取用户列表失败') }
  finally { loading.value = false }
}

function handlePageChange(page) { currentPage.value = page; fetchUsers() }
function showCreateDialog() {
  isEdit.value = false
  Object.assign(form, { username: '', password: '', real_name: '', role: 'student', email: '', phone: '' })
  dialogVisible.value = true
}
function openEdit(user) {
  isEdit.value = true
  Object.assign(form, { username: user.username, real_name: user.real_name, role: user.role, email: user.email || '', phone: user.phone || '' })
  form._id = user.id
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (isEdit.value) {
      await api.put(`/users/${form._id}`, { real_name: form.real_name, email: form.email, phone: form.phone })
      ElMessage.success('更新成功')
    } else {
      await api.post('/users', form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchUsers()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '操作失败') }
  finally { saving.value = false }
}

async function handleResetPassword(user) {
  try {
    await ElMessageBox.confirm(`确认重置用户 "${user.real_name}" 的密码？`, '重置密码')
    await api.post(`/auth/reset-password/${user.id}`, { new_password: '12345678' })
    ElMessage.success('密码已重置为 12345678')
  } catch (err) { if (err !== 'cancel') ElMessage.error('重置失败') }
}

onMounted(fetchUsers)
</script>
```

- [ ] **Step 2: Verify build and commit**

Run: `cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -3`
Expected: Build succeeds

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/admin/UserList.vue && git commit -m "feat: add admin user management page"
```

---

## Task 13: Frontend — Admin ClassList + ClassRoster Pages

**Files:**
- Modify: `frontend/src/views/admin/ClassList.vue`
- Modify: `frontend/src/views/admin/ClassRoster.vue`

- [ ] **Step 1: Implement ClassList page**

Replace `frontend/src/views/admin/ClassList.vue`:

```vue
<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">班级管理</h3>
      <el-button type="primary" @click="showCreateDialog">新建班级</el-button>
    </div>
    <div style="margin-bottom: 16px">
      <el-select v-model="semesterFilter" placeholder="筛选学期" clearable style="width: 180px" @change="fetchClasses">
        <el-option label="2025-2026-2" value="2025-2026-2" />
        <el-option label="2025-2026-1" value="2025-2026-1" />
      </el-select>
    </div>
    <el-table :data="classes" v-loading="loading" stripe>
      <el-table-column prop="name" label="班级名称" min-width="150" />
      <el-table-column prop="semester" label="学期" width="130" />
      <el-table-column prop="teacher_name" label="教师" width="100" />
      <el-table-column prop="student_count" label="学生数" width="80" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/admin/classes/${row.id}/roster`)">花名册</el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑班级' : '新建班级'" width="450px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="班级名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="学期" prop="semester">
          <el-input v-model="form.semester" placeholder="如 2025-2026-2" />
        </el-form-item>
        <el-form-item label="教师">
          <el-input v-model="form.teacher_id" placeholder="教师ID（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const classes = ref([])
const loading = ref(false)
const semesterFilter = ref('')
const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const formRef = ref(null)

const form = reactive({ name: '', semester: '2025-2026-2', teacher_id: '' })
const rules = {
  name: [{ required: true, message: '请输入班级名称', trigger: 'blur' }],
  semester: [{ required: true, message: '请输入学期', trigger: 'blur' }],
}

async function fetchClasses() {
  loading.value = true
  try {
    const params = {}
    if (semesterFilter.value) params.semester = semesterFilter.value
    const resp = await api.get('/classes', { params })
    classes.value = resp.data.items
  } catch { ElMessage.error('获取班级列表失败') }
  finally { loading.value = false }
}

function showCreateDialog() {
  isEdit.value = false
  Object.assign(form, { name: '', semester: '2025-2026-2', teacher_id: '' })
  dialogVisible.value = true
}
function openEdit(cls) {
  isEdit.value = true
  Object.assign(form, { name: cls.name, semester: cls.semester, teacher_id: cls.teacher_id || '', _id: cls.id })
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const payload = { name: form.name, semester: form.semester }
    if (form.teacher_id) payload.teacher_id = parseInt(form.teacher_id)
    if (isEdit.value) {
      await api.put(`/classes/${form._id}`, payload)
      ElMessage.success('更新成功')
    } else {
      await api.post('/classes', payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchClasses()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '操作失败') }
  finally { saving.value = false }
}

async function handleDelete(cls) {
  try {
    await ElMessageBox.confirm(`确认删除班级 "${cls.name}"？`, '删除班级')
    await api.delete(`/classes/${cls.id}`)
    ElMessage.success('删除成功')
    await fetchClasses()
  } catch (err) { if (err !== 'cancel') ElMessage.error(err.response?.data?.detail || '删除失败') }
}

onMounted(fetchClasses)
</script>
```

- [ ] **Step 2: Implement ClassRoster page**

Replace `frontend/src/views/admin/ClassRoster.vue`:

```vue
<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" title="返回" content="班级花名册" />
    <div v-if="cls" style="margin-top: 16px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="班级名称">{{ cls.name }}</el-descriptions-item>
        <el-descriptions-item label="学期">{{ cls.semester }}</el-descriptions-item>
        <el-descriptions-item label="学生数">{{ students.length }}</el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <h4>学生列表</h4>
      <el-table :data="students" stripe>
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="real_name" label="姓名" />
      </el-table>

      <el-divider />

      <h4>添加学生</h4>
      <div style="display: flex; gap: 12px; align-items: center">
        <el-input v-model="newStudentIds" placeholder="输入学生ID，多个用逗号分隔" style="max-width: 400px" />
        <el-button type="primary" @click="handleEnroll" :loading="enrolling">添加</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'

const route = useRoute()
const classId = route.params.id

const cls = ref(null)
const students = ref([])
const loading = ref(false)
const newStudentIds = ref('')
const enrolling = ref(false)

async function fetchData() {
  loading.value = true
  try {
    const [clsResp, stuResp] = await Promise.all([
      api.get(`/classes/${classId}/students`),
      api.get('/classes').catch(() => ({ data: { items: [] } })),
    ])
    students.value = clsResp.data
    // Find the class info from the list
    const allClasses = stuResp.data.items || []
    cls.value = allClasses.find(c => c.id === parseInt(classId)) || { name: '班级', semester: '' }
  } catch { ElMessage.error('获取数据失败') }
  finally { loading.value = false }
}

async function handleEnroll() {
  const ids = newStudentIds.value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
  if (ids.length === 0) { ElMessage.warning('请输入有效的学生ID'); return }
  enrolling.value = true
  try {
    await api.post(`/classes/${classId}/students`, { student_ids: ids })
    ElMessage.success('添加成功')
    newStudentIds.value = ''
    await fetchData()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '添加失败') }
  finally { enrolling.value = false }
}

onMounted(fetchData)
</script>
```

- [ ] **Step 3: Verify build and commit**

```bash
cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -3
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/admin/ && git commit -m "feat: add admin class management and roster pages"
```

---

## Task 14: Frontend — Teacher TaskList Enhancements + TaskEdit Page

**Files:**
- Modify: `frontend/src/views/teacher/TaskList.vue`
- Modify: `frontend/src/views/teacher/TaskEdit.vue`

- [ ] **Step 1: Enhance TaskList with edit/archive/delete**

Replace `frontend/src/views/teacher/TaskList.vue`:

```vue
<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">我的任务</h3>
      <el-button type="primary" @click="$router.push('/teacher/tasks/create')">创建任务</el-button>
    </div>
    <el-table :data="tasks" v-loading="loading" stripe>
      <el-table-column prop="title" label="任务标题" min-width="150" />
      <el-table-column prop="class_name" label="班级" width="150" />
      <el-table-column label="截止时间" width="170">
        <template #default="{ row }">{{ formatDate(row.deadline) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status === 'active' ? '进行中' : '已归档' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="成绩" width="80">
        <template #default="{ row }">
          <el-tag :type="row.grades_published ? 'success' : 'warning'" size="small">
            {{ row.grades_published ? '已发布' : '未发布' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/teacher/tasks/${row.id}/submissions`)">
            查看提交
          </el-button>
          <el-button size="small" @click="$router.push(`/teacher/tasks/${row.id}/edit`)">编辑</el-button>
          <el-button v-if="row.status === 'active'" size="small" type="warning" @click="handleArchive(row)">归档</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const tasks = ref([])
const loading = ref(false)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

async function fetchTasks() {
  loading.value = true
  try {
    const resp = await api.get('/tasks/my')
    tasks.value = resp.data
  } catch { ElMessage.error('获取任务列表失败') }
  finally { loading.value = false }
}

async function handleArchive(task) {
  try {
    await ElMessageBox.confirm(`确认归档任务 "${task.title}"？`, '归档')
    await api.post(`/tasks/${task.id}/archive`)
    ElMessage.success('已归档')
    await fetchTasks()
  } catch (err) { if (err !== 'cancel') ElMessage.error('归档失败') }
}

async function handleDelete(task) {
  try {
    await ElMessageBox.confirm(`确认删除任务 "${task.title}"？已有提交的任务无法删除。`, '删除任务')
    await api.delete(`/tasks/${task.id}`)
    ElMessage.success('已删除')
    await fetchTasks()
  } catch (err) { if (err !== 'cancel') ElMessage.error(err.response?.data?.detail || '删除失败') }
}

onMounted(fetchTasks)
</script>
```

- [ ] **Step 2: Create TaskEdit page**

Replace `frontend/src/views/teacher/TaskEdit.vue`:

```vue
<template>
  <div v-loading="loading">
    <h3>编辑任务</h3>
    <el-form v-if="task" :model="form" :rules="rules" ref="formRef" label-width="120px" style="max-width: 600px">
      <el-form-item label="任务标题" prop="title">
        <el-input v-model="form.title" />
      </el-form-item>
      <el-form-item label="任务描述">
        <el-input v-model="form.description" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="实验要求">
        <el-input v-model="form.requirements" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="截止时间" prop="deadline">
        <el-date-picker v-model="form.deadline" type="datetime" placeholder="选择截止时间" />
      </el-form-item>
      <el-form-item label="允许文件类型">
        <el-select v-model="form.allowed_file_types" multiple>
          <el-option v-for="ft in fileTypes" :key="ft" :label="ft" :value="ft" />
        </el-select>
      </el-form-item>
      <el-form-item label="最大文件大小(MB)">
        <el-input-number v-model="form.max_file_size_mb" :min="1" :max="100" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSubmit" :loading="saving">保存修改</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id

const task = ref(null)
const loading = ref(false)
const saving = ref(false)
const formRef = ref(null)
const fileTypes = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar', '.jpg', '.png', '.txt', '.csv']

const form = reactive({ title: '', description: '', requirements: '', deadline: '', allowed_file_types: [], max_file_size_mb: 50 })
const rules = {
  title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }],
  deadline: [{ required: true, message: '请选择截止时间', trigger: 'change' }],
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get(`/tasks/${taskId}`)
    task.value = resp.data
    Object.assign(form, {
      title: task.value.title,
      description: task.value.description || '',
      requirements: task.value.requirements || '',
      deadline: task.value.deadline,
      allowed_file_types: task.value.allowed_file_types || [],
      max_file_size_mb: task.value.max_file_size_mb || 50,
    })
  } catch { ElMessage.error('获取任务详情失败') }
  finally { loading.value = false }
})

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await api.put(`/tasks/${taskId}`, {
      ...form,
      deadline: form.deadline instanceof Date ? form.deadline.toISOString() : form.deadline,
    })
    ElMessage.success('修改成功')
    router.push('/teacher/tasks')
  } catch (err) { ElMessage.error(err.response?.data?.detail || '修改失败') }
  finally { saving.value = false }
}
</script>
```

- [ ] **Step 3: Verify build and commit**

```bash
cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -3
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/teacher/ && git commit -m "feat: add teacher task edit, archive, and delete"
```

---

## Task 15: Frontend — Teacher SubmissionReview Bulk Grade Enhancement

**Files:**
- Modify: `frontend/src/views/teacher/SubmissionReview.vue`

- [ ] **Step 1: Add bulk grade button to SubmissionReview**

In `frontend/src/views/teacher/SubmissionReview.vue`, add a bulk grade button after the publish/unpublish buttons (in the div with `style="margin-top: 20px; display: flex..."`):

Add after the unpublish button:
```vue
      <el-button
        v-if="submissions.length > 0"
        type="primary"
        size="small"
        @click="showBulkGrade"
      >
        批量评分
      </el-button>
```

Add a bulk grade dialog before the closing `</template>`:
```vue
    <el-dialog v-model="bulkVisible" title="批量评分" width="400px">
      <el-form label-width="80px">
        <el-form-item label="分数">
          <el-input-number v-model="bulkScore" :min="0" :max="100" :precision="1" />
          <span style="margin-left: 8px; color: #909399">/ 100</span>
        </el-form-item>
      </el-form>
      <p style="color: #909399; font-size: 13px">
        将为所有未评分的提交（{{ ungradedCount }} 个）设置相同分数，迟交扣分会自动计算。
      </p>
      <template #footer>
        <el-button @click="bulkVisible = false">取消</el-button>
        <el-button type="primary" :loading="bulkLoading" @click="handleBulkGrade">确认批量评分</el-button>
      </template>
    </el-dialog>
```

Add these refs and methods to the `<script setup>` section:

```javascript
const bulkVisible = ref(false)
const bulkScore = ref(80)
const bulkLoading = ref(false)

const ungradedCount = computed(() => submissions.value.filter(s => !s.grade).length)

function showBulkGrade() {
  bulkScore.value = 80
  bulkVisible.value = true
}

async function handleBulkGrade() {
  const ungraded = submissions.value.filter(s => !s.grade)
  if (ungraded.length === 0) { ElMessage.info('没有未评分的提交'); return }
  bulkLoading.value = true
  try {
    await api.post(`/tasks/${taskId}/grades/bulk`, {
      grades: ungraded.map(s => ({ submission_id: s.id, score: bulkScore.value })),
    })
    ElMessage.success(`已为 ${ungraded.length} 个提交评分`)
    bulkVisible.value = false
    await fetchSubmissions()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '批量评分失败') }
  finally { bulkLoading.value = false }
}
```

Also add `computed` to the vue import line.

- [ ] **Step 2: Verify build and commit**

```bash
cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -3
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/teacher/SubmissionReview.vue && git commit -m "feat: add bulk grading to teacher submission review"
```

---

## Task 16: Frontend — Student SubmissionDetail Enhancement

**Files:**
- Modify: `frontend/src/views/student/SubmissionDetail.vue`

- [ ] **Step 1: Add version display and resubmit link**

In `frontend/src/views/student/SubmissionDetail.vue`, add a resubmit link after the grade section. Find the closing `</div>` of the `v-if="submission"` block and add before it:

```vue
      <el-divider />

      <div style="text-align: center">
        <el-button type="primary" @click="$router.back()">返回任务</el-button>
      </div>
```

Also, make the version display more prominent. Replace the existing version descriptions-item:

```vue
        <el-descriptions-item label="版本">
          <el-tag size="large" type="primary">v{{ submission.version }}</el-tag>
        </el-descriptions-item>
```

- [ ] **Step 2: Verify build and commit**

```bash
cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -3
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/student/SubmissionDetail.vue && git commit -m "feat: enhance student submission detail with version display"
```

---

## Task 17: Frontend — 401 Refresh Interceptor

**Files:**
- Modify: `frontend/src/api/index.js`

- [ ] **Step 1: Update 401 interceptor to try refresh**

Replace `frontend/src/api/index.js`:

```javascript
import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let isRefreshing = false
let failedQueue = []

function processQueue(error, token = null) {
  failedQueue.forEach(prom => {
    if (error) prom.reject(error)
    else prom.resolve(token)
  })
  failedQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('user')
        window.location.href = '/login'
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(token => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const resp = await axios.post(
          `${import.meta.env.VITE_API_BASE_URL || '/api'}/auth/refresh`,
          { refresh_token: refreshToken }
        )
        const { access_token, refresh_token: new_refresh } = resp.data
        localStorage.setItem('access_token', access_token)
        localStorage.setItem('refresh_token', new_refresh)
        processQueue(null, access_token)
        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('user')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  },
)

export default api
```

- [ ] **Step 2: Verify build and commit**

```bash
cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -3
cd /Users/gaofang/Desktop/new_project && git add frontend/src/api/index.js && git commit -m "feat: add token refresh logic to 401 interceptor"
```

---

## Task 18: Deployment — Nginx + systemd + Deploy Script

**Files:**
- Create: `deploy/nginx.conf`
- Create: `deploy/training-platform.service`
- Create: `deploy/deploy.sh`

- [ ] **Step 1: Create Nginx config**

Create `deploy/nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;

    root /opt/training-platform/frontend/dist;
    index index.html;

    # API reverse proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 100M;
    }

    # File downloads (X-Accel-Redirect support)
    location /uploads/ {
        internal;
        alias /opt/training-platform/uploads/;
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 1000;
}
```

- [ ] **Step 2: Create systemd service**

Create `deploy/training-platform.service`:

```ini
[Unit]
Description=Training Platform Backend (FastAPI)
After=network.target mysql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/training-platform/backend
ExecStart=/opt/training-platform/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Create deployment script**

Create `deploy/deploy.sh`:

```bash
#!/bin/bash
set -e

DEPLOY_DIR="/opt/training-platform"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Deploying Training Platform ==="

# Backend
echo "[1/5] Installing Python dependencies..."
cd "$REPO_DIR/backend"
source .venv/bin/activate
pip install -r requirements.txt -q

echo "[2/5] Running database migrations..."
alembic upgrade head

# Frontend
echo "[3/5] Building frontend..."
cd "$REPO_DIR/frontend"
npm ci
npm run build

# Deploy
echo "[4/5] Copying files..."
sudo mkdir -p "$DEPLOY_DIR/frontend"
sudo mkdir -p "$DEPLOY_DIR/uploads/tmp"
sudo cp -r "$REPO_DIR/frontend/dist/"* "$DEPLOY_DIR/frontend/dist/"
sudo rsync -av --exclude='.venv' --exclude='__pycache__' "$REPO_DIR/backend/" "$DEPLOY_DIR/backend/"

echo "[5/5] Restarting services..."
sudo cp "$REPO_DIR/deploy/training-platform.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart training-platform
sudo systemctl enable training-platform

# Cron for file cleanup
echo "Setting up daily cleanup cron..."
(crontab -l 2>/dev/null; echo "0 3 * * * cd $DEPLOY_DIR/backend && .venv/bin/python -c 'import asyncio; from app.database import async_session_maker; from app.services.file_cleanup import cleanup_orphan_files; asyncio.run(cleanup_orphan_files(async_session_maker()))'") | crontab -

echo "=== Deployment complete ==="
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost (via Nginx)"
```

- [ ] **Step 4: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && mkdir -p deploy && git add deploy/ && git commit -m "feat: add deployment configuration (Nginx, systemd, deploy script)"
```

---

## Self-Review

### Spec Coverage

| OpenSpec Task | Plan Task |
|---|---|
| D.1 Auth refresh/logout/change-password/reset-password | Tasks 1, 2 |
| D.2 User CRUD (admin) + GET me + PUT me | Tasks 3, 4 |
| D.3 Class PUT/DELETE + GET list (admin) + POST enroll | Tasks 5, 6 |
| D.4 Task PUT + DELETE + archive + admin GET list | Tasks 7, 8 |
| D.5 Bulk grading | Task 9 |
| D.6 File cleanup tests | Task 10 |
| E.1 Admin user management page | Task 12 |
| E.2 Admin class management page | Task 13 |
| E.3 Admin class roster page | Task 13 |
| E.4 Teacher task list enhancements | Task 14 |
| E.5 Teacher grading enhancements (bulk) | Task 15 |
| E.6 Student submission detail enhancement | Task 16 |
| C.3 Refresh token logic in frontend | Task 17 |
| F.1 Nginx config | Task 18 |
| F.2 systemd service | Task 18 |
| F.3 Deployment script | Task 18 |
| F.4 Cron for file cleanup | Task 18 |

### Placeholder Scan

No TBD, TODO, "implement later", "add validation", or "similar to Task N" found. Every step contains exact code.

### Type Consistency

- `UserResponse` fields match User model columns exactly
- `ClassUpdate` / `TaskUpdate` use `Optional` fields for partial updates
- `BulkGradeRequest.grades` is `List[BulkGradeItem]` matching the API contract
- Frontend `api.get('/users', { params })` matches backend `GET /api/users` with query params
- Frontend `api.put('/tasks/:id', ...)` matches backend `PUT /api/tasks/:id`
- Router paths in `router/index.js` match component navigation calls

---

## Summary

**18 tasks**, each 5-10 minutes. Total estimated time: ~3 hours.

**Dependency chain:**
- Tasks 1-2 (auth) → independent
- Tasks 3-4 (users) → independent, needs auth from Task 2 for reset-password test
- Tasks 5-6 (classes) → independent
- Tasks 7-8 (tasks) → independent
- Task 9 (bulk grading) → independent
- Task 10 (file cleanup tests) → independent
- Tasks 11-17 (frontend) → needs backend endpoints from Tasks 1-9
- Task 18 (deployment) → independent

Backend tasks (1-10) can be parallelized to some degree since they touch different routers. Frontend tasks (11-17) should run after backend is complete. Deployment (18) is fully independent.
