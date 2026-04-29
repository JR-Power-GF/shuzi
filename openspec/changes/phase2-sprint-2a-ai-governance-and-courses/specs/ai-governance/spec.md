## ADDED Requirements

### Requirement: AI service layer with provider abstraction
The system SHALL provide an `AIService` class that wraps LLM provider calls. All AI features SHALL call `AIService.generate()` instead of calling providers directly. The service SHALL support swapping providers via configuration without code changes.

**User story:** As a developer, I want a single entry point for AI calls so that logging, rate limiting, and provider switching are centralized.

#### Scenario: Successful AI generation call
- **WHEN** code calls `AIService.generate(prompt, user_id, context)` with a valid configuration
- **THEN** service checks budget, calls provider, logs the call to `ai_usage_logs`, returns generated text

#### Scenario: Provider returns error
- **WHEN** LLM provider returns an error (rate limit, timeout, invalid request)
- **THEN** service logs the call with status=error to `ai_usage_logs`, raises `HTTPException(502)` with generic message "AI 服务暂时不可用"

#### Scenario: Provider configuration changed
- **WHEN** admin changes AI model or budget config via the admin settings page
- **THEN** subsequent AI calls use the new configuration. Changes to env vars require application restart; changes via the admin config API take effect on the next call.

### Requirement: AI usage logging
The system SHALL log every AI call to the `ai_usage_logs` table with: user_id, endpoint (which feature triggered it), model, prompt_tokens, completion_tokens, cost_cents (estimated), latency_ms, status (success/error), created_at.

**User story:** As an admin, I want to know exactly how AI is being used: who called it, how much it cost, and whether it succeeded.

#### Scenario: Successful call logged
- **WHEN** AI call completes successfully with 500 prompt tokens and 200 completion tokens
- **THEN** `ai_usage_logs` row is created with status=success, token counts, calculated cost, and latency

#### Scenario: Failed call logged
- **WHEN** AI call fails due to provider error
- **THEN** `ai_usage_logs` row is created with status=error, prompt_tokens=0, completion_tokens=0, latency recorded

#### Scenario: Cost calculation
- **WHEN** gpt-4o-mini call uses 500 prompt tokens and 200 completion tokens at $0.15/$0.60 per million tokens
- **THEN** cost is calculated as: cost_dollars = (prompt_tokens x prompt_price_per_million + completion_tokens x completion_price_per_million) / 1_000_000 = (500 x 0.15 + 200 x 0.60) / 1_000_000 = $0.000195. Stored as microdollars (cost_microdollars = cost_dollars x 1_000_000 = 195) in an INTEGER column.

### Requirement: Per-user daily token budget enforcement
The system SHALL enforce a daily token budget per user based on their role. Default budgets: admin 500K, teacher 200K, student 50K. When budget is exceeded, the system SHALL return 429.

**User story:** As a platform operator, I need to prevent runaway AI costs from a single user consuming the entire budget.

#### Scenario: User within budget
- **WHEN** student with 50K daily budget has used 30K tokens today
- **THEN** AI call proceeds normally

#### Scenario: User exceeds budget
- **WHEN** student with 50K daily budget has used 50K+ tokens today
- **THEN** system returns HTTP 429 with message "今日 AI 调用额度已用完，请明天再试"

#### Scenario: Budget not yet used today
- **WHEN** user makes first AI call of the day (no ai_usage_logs rows exist)
- **THEN** budget query uses COALESCE(SUM(tokens), 0) to return 0, call proceeds

#### Scenario: Admin views user budget status
- **WHEN** admin queries GET /api/ai/usage?user_id=123&date=2026-04-24
- **THEN** system returns total tokens used, budget limit, and remaining tokens for that user on that date

### Requirement: AI feedback collection
The system SHALL allow users to submit feedback (thumbs up/down + optional comment) on any AI output. Feedback SHALL be linked to the specific `ai_usage_log` entry.

**User story:** As a platform operator, I want to track AI output quality over time based on user feedback.

#### Scenario: Submit positive feedback
- **WHEN** user submits POST /api/ai/feedback with ai_usage_log_id and rating=1
- **THEN** system creates `ai_feedback` row linked to the usage log

#### Scenario: Submit negative feedback with comment
- **WHEN** user submits POST /api/ai/feedback with ai_usage_log_id, rating=-1, comment="回答不准确"
- **THEN** system creates `ai_feedback` row with all fields

#### Scenario: Submit feedback for another user's log
- **WHEN** user submits feedback for an ai_usage_log_id belonging to a different user
- **THEN** system returns 403

#### Scenario: Submit duplicate feedback
- **WHEN** user submits feedback for an ai_usage_log_id they already rated
- **THEN** system returns 409 with message "已经评价过"

### Requirement: Admin AI usage dashboard
The system SHALL provide admin endpoints for aggregated AI usage statistics: total calls, total tokens, total cost, breakdown by user/endpoint/model, and feedback summary.

**User story:** As an admin, I want a dashboard of AI usage to understand costs and quality trends.

#### Scenario: View aggregate usage
- **WHEN** admin submits GET /api/ai/stats?start_date=2026-04-01&end_date=2026-04-30
- **THEN** system returns total calls, tokens, cost, success rate, and average latency for the period

#### Scenario: View usage by user
- **WHEN** admin submits GET /api/ai/stats?group_by=user
- **THEN** system returns per-user breakdown of calls, tokens, and cost

#### Scenario: View feedback summary
- **WHEN** admin submits GET /api/ai/stats/feedback
- **THEN** system returns total positive/negative feedback count, and recent negative feedback with comments

#### Scenario: Non-admin access
- **WHEN** non-admin user submits GET /api/ai/stats
- **THEN** system returns 403
