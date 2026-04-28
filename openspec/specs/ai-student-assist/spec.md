## ADDED Requirements

### Requirement: Student can ask questions about their tasks
The system SHALL allow students to submit questions about tasks assigned to them. The AI SHALL only access context from the student's enrolled courses and assigned tasks. The AI SHALL NOT access other students' submissions or data outside the student's scope.

**User story:** As a student, I want to ask questions about my task requirements so I understand what to do.

**Permission boundary:** Student only, for tasks assigned to their class.

#### Scenario: Ask question about assigned task
- **WHEN** student submits POST /api/ai/student/qa with task_id=assigned task, question="评分标准是什么？"
- **THEN** system assembles context (task requirements + task description + course info), calls AIService.generate(), returns answer text. Usage logged with endpoint="student_qa".

#### Scenario: Ask question about unassigned task
- **WHEN** student submits POST /api/ai/student/qa with task_id not in their class
- **THEN** system returns 403

#### Scenario: AI cannot find relevant information
- **WHEN** student asks a question not covered by the task context
- **THEN** AI responds with "根据任务要求，我没有找到相关信息" rather than inventing information

#### Scenario: Budget exceeded
- **WHEN** student has exceeded daily token budget
- **THEN** system returns 429 with message "今日 AI 调用额度已用完，请明天再试"

### Requirement: Student Q&A context boundary
The system SHALL enforce a strict context boundary for student Q&A. Context SHALL include ONLY: task title, task description, task requirements, course name, course description. Context SHALL NOT include: other students' submissions, other tasks, data from other courses, or any information the student is not authorized to view.

**User story:** As a platform operator, I need to guarantee that AI responses only reference information the student is authorized to see.

#### Scenario: Context excludes other students' work
- **WHEN** student asks "其他同学是怎么做的？" (how did other students do it?)
- **THEN** AI responds that it cannot access other students' work, per the system prompt constraint

#### Scenario: Context scoped to enrolled course
- **WHEN** student asks about a topic outside their course materials
- **THEN** AI responds based only on the task context provided, acknowledges limitation if information is not in context

### Requirement: Student can generate training summary draft
The system SHALL allow students to generate a draft training summary based on their submission history for a specific course. The summary SHALL synthesize what the student learned across all their submissions in that course.

**User story:** As a student, I want AI to help me write a training summary based on my work so I can focus on reflection rather than formatting.

**Permission boundary:** Student only, for their own submissions in courses they are enrolled in.

#### Scenario: Generate summary with submissions
- **WHEN** student submits POST /api/ai/student/summary with course_id=enrolled course
- **THEN** system assembles context (course info + student's submission history for that course), calls AIService.generate(), returns draft summary text. Usage logged with endpoint="training_summary".

#### Scenario: Generate summary with no submissions
- **WHEN** student requests summary for a course where they have no submissions
- **THEN** system returns 400 with message "该课程暂无提交记录，无法生成总结"

#### Scenario: Generate summary for unenrolled course
- **WHEN** student requests summary for a course they are not enrolled in
- **THEN** system returns 403

### Requirement: Student Q&A prompt template
The system SHALL use a configurable prompt template for student Q&A. The template SHALL receive variables: task_title, task_description, task_requirements, course_name, question. The system prompt SHALL instruct the AI to only answer based on provided context and to refuse answering about other students' work.

#### Scenario: System prompt enforces boundaries
- **WHEN** student Q&A call is made
- **THEN** the system prompt includes instructions to: only use provided context, say "根据任务要求，我没有找到相关信息" if context is insufficient, and refuse to discuss other students' work

### Requirement: Training summary prompt template
The system SHALL use a configurable prompt template for training summary generation. The template SHALL receive variables: course_name, course_description, submission_count, submission_summaries (truncated text of each submission).

#### Scenario: Summary template produces structured output
- **WHEN** AI generates summary using default template
- **THEN** output includes sections: 学习概述 (overview), 主要收获 (key learnings), 不足与改进 (areas for improvement)
