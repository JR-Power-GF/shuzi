## ADDED Requirements

### Requirement: Admin can view prompt templates
The system SHALL provide an admin endpoint to list all prompt templates with their names, descriptions, variables, and current content.

**User story:** As an admin, I want to see what prompt templates exist and what they contain.

**Permission boundary:** Admin only.

#### Scenario: List all templates
- **WHEN** admin submits GET /api/prompts
- **THEN** system returns all prompt templates with name, description, variables (JSON array of variable names), template_text, updated_at, updated_by

#### Scenario: Non-admin access
- **WHEN** non-admin submits GET /api/prompts
- **THEN** system returns 403

### Requirement: Admin can edit prompt templates
The system SHALL allow admin to update the template text of any prompt template. Changes take effect on the next AI call that uses that template.

**User story:** As an admin, I want to tune AI prompts to improve output quality without deploying code.

**Permission boundary:** Admin only.

#### Scenario: Update template text
- **WHEN** admin submits PUT /api/prompts/:name with template_text="新的模板内容 {course_name} {topic}"
- **THEN** system updates the prompt_templates row, records updated_by and updated_at

#### Scenario: Template with invalid variables
- **WHEN** admin submits template_text containing a variable not listed in the template's variables array
- **THEN** system returns 400 with message listing the invalid variables

#### Scenario: Template name is read-only
- **WHEN** admin attempts to change the name of a template
- **THEN** system returns 400. Template names are immutable identifiers.

### Requirement: Default prompt templates seeded on deployment
The system SHALL include seed data for default prompt templates: "task_description", "student_qa", "training_summary". Each template SHALL declare its expected variables.

**User story:** As a developer, I want the system to work out of the box with sensible default prompts.

#### Scenario: Fresh deployment has default templates
- **WHEN** system is freshly deployed
- **THEN** prompt_templates table contains templates: task_description (variables: course_name, course_description, topic, language), student_qa (variables: task_title, task_description, task_requirements, course_name, question), training_summary (variables: course_name, course_description, submission_count, submission_summaries)

### Requirement: AIService reads templates from database
The system SHALL read prompt templates from the prompt_templates table when composing AI calls. The template SHALL be filled using `str.format()` with validated context variables.

**User story:** As a developer, I want prompt changes to take effect immediately without code changes.

#### Scenario: Template applied to context
- **WHEN** AI feature calls AIService.generate() with context={"course_name": "Python", "topic": "网络编程"}
- **THEN** AIService reads the relevant template from DB, fills variables, passes composed prompt to provider

#### Scenario: Missing context variable
- **WHEN** context dict is missing a variable required by the template
- **THEN** AIService raises ValueError with message indicating which variable is missing
