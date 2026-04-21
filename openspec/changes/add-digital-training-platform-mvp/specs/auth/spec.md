## ADDED Requirements

### Requirement: User can log in with username and password
The system SHALL provide a login endpoint that accepts username and password, validates credentials, and returns a JWT access token (15-min expiry) and refresh token (7-day expiry).

**User story:** As any user (admin/teacher/student), I want to log in with my username and password so that I can access the platform with my role's capabilities.

**Permission boundary:** Public endpoint, no authentication required.

#### Scenario: Successful login
- **WHEN** user submits valid username and password to POST /api/auth/login
- **THEN** system returns 200 with access_token and refresh_token

#### Scenario: Wrong password
- **WHEN** user submits valid username with incorrect password
- **THEN** system returns 401 with error "用户名或密码错误" and increments failed_login_attempts

#### Scenario: Account locked
- **WHEN** user with failed_login_attempts >= 5 attempts to log in
- **THEN** system returns 403 with error "账户已锁定，请30分钟后重试"
- **AND** locked_until is set to NOW + 30 minutes

#### Scenario: Account deactivated
- **WHEN** user with is_active=false attempts to log in
- **THEN** system returns 403 with error "账户已停用"

#### Scenario: Must change password
- **WHEN** user with must_change_password=true logs in successfully
- **THEN** system returns 200 with tokens AND must_change_password=true flag

#### Edge case: Lockout expires at exact moment of login
- **WHEN** user's locked_until equals NOW (not greater)
- **THEN** system allows login to proceed (lockout check uses strict greater-than)

#### Edge case: Concurrent login from multiple devices
- **WHEN** user logs in from two devices simultaneously
- **THEN** both receive valid token pairs, both sessions work independently

### Requirement: User can log out
The system SHALL invalidate the refresh token on logout. The access token expires naturally (15-min max).

**User story:** As any user, I want to log out so that my session is terminated on this device.

**Permission boundary:** Any authenticated user.

#### Scenario: Successful logout
- **WHEN** user submits POST /api/auth/logout with valid refresh token
- **THEN** system marks refresh token as revoked and returns 200

### Requirement: User can change their own password
The system SHALL allow any authenticated user to change their password. New password MUST be at least 8 characters.

**User story:** As any user, I want to change my password so that I can keep my account secure.

**Permission boundary:** Any authenticated user, own account only.

#### Scenario: Successful password change
- **WHEN** user submits current_password and new_password (>=8 chars) to POST /api/auth/change-password
- **THEN** system updates password hash and returns 200

#### Scenario: Wrong current password
- **WHEN** user submits incorrect current_password
- **THEN** system returns 401 with error "当前密码错误"

#### Scenario: New password too short
- **WHEN** user submits new_password shorter than 8 characters
- **THEN** system returns 422 with error "密码长度不能少于8位"

#### Edge case: Password change during active session on another device
- **WHEN** user changes password while another session is active
- **THEN** other session's access token remains valid for up to 15 minutes (acceptable for internal system)

### Requirement: Admin can reset any user's password
The system SHALL allow admin to set a temporary password for any user. The target user MUST change password on next login.

**User story:** As an admin, I want to reset a user's password so that they can regain access if they forget it.

**Permission boundary:** Admin only.

#### Scenario: Successful reset
- **WHEN** admin submits POST /api/auth/reset-password/:id with new temporary password
- **THEN** system updates password hash, sets must_change_password=true for target user, returns 200

#### Scenario: Non-admin attempts reset
- **WHEN** non-admin user attempts POST /api/auth/reset-password/:id
- **THEN** system returns 403

### Requirement: Token refresh
The system SHALL allow clients to exchange a valid refresh token for a new access token and refresh token pair.

**User story:** As a user with an expired access token, I want to refresh my session so that I don't have to log in again.

**Permission boundary:** Any client with a valid (non-revoked) refresh token.

#### Scenario: Successful refresh
- **WHEN** client submits valid refresh token to POST /api/auth/refresh
- **THEN** system returns new access_token and refresh_token, old refresh token is revoked

#### Scenario: Revoked refresh token
- **WHEN** client submits a revoked refresh token
- **THEN** system returns 401

#### Edge case: Access token expires mid-request
- **WHEN** user's access token expires while a request is in-flight
- **THEN** response is 401, frontend axios interceptor catches it, refreshes token, retries the original request transparently
