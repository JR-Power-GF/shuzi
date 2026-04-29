## ADDED Requirements

### Requirement: Teacher can generate task description with AI
The system SHALL allow teachers to trigger AI-assisted task description generation. The AI SHALL receive course context (name, description) and the task title/topic as input, and produce a structured task description with objectives, steps, and grading criteria.

**User story:** As a teacher, I want AI to draft a task description so I spend less time on boilerplate writing.

**Permission boundary:** Teacher only, for their own courses.

#### Scenario: Generate description for owned course
- **WHEN** teacher submits POST /api/ai/teacher/task-description with course_id=own course, topic="网络协议分析"
- **THEN** system assembles context (course info + topic), calls AIService.generate(), returns generated description text. Usage logged with endpoint="task_description".

#### Scenario: Generate description for unowned course
- **WHEN** teacher submits POST /api/ai/teacher/task-description with course_id belonging to another teacher
- **THEN** system returns 403

#### Scenario: Generate description with budget exceeded
- **WHEN** teacher has exceeded daily token budget
- **THEN** system returns 429 with message "今日 AI 调用额度已用完，请明天再试"

#### Scenario: Teacher applies generated description
- **WHEN** teacher reviews generated description and clicks "应用到任务" (apply to task)
- **THEN** system populates the task creation form's description field with the generated text. Teacher can edit before saving.

### Requirement: Task description prompt template
The system SHALL use a configurable prompt template for task description generation. The template SHALL receive variables: course_name, course_description, topic, language (default "中文").

**User story:** As an admin, I want to tune the task description prompt template to improve output quality.

#### Scenario: Default template produces structured output
- **WHEN** AI generates task description using the default template
- **THEN** output includes sections: 目标 (objectives), 步骤 (steps), 评分标准 (grading criteria)

#### Scenario: Admin edits template
- **WHEN** admin edits the "task_description" template via PUT /api/prompts/:name
- **THEN** next task description generation uses the updated template
