## ADDED Requirements

### Requirement: Authenticated users can upload files
The system SHALL provide a file upload endpoint. Files are written to a temp path with UUID prefix, then atomically renamed to final location. File type MUST match allowed extension list. File size MUST NOT exceed configured maximum.

**User story:** As a student, I want to upload my assignment files so that I can submit them for my task.

**Permission boundary:** Any authenticated user. File type and size validated against task constraints.

#### Scenario: Upload valid file
- **WHEN** user submits POST /api/files/upload with a 5MB PDF file
- **THEN** system writes file to /uploads/{uuid}_{filename}, returns file_id and metadata

#### Scenario: Upload oversized file
- **WHEN** user uploads a file exceeding max_file_size_mb
- **THEN** system rejects upload and returns 422 with error "文件大小超过限制"

#### Scenario: Concurrent uploads
- **WHEN** two users upload files simultaneously
- **THEN** UUID prefix prevents filename collision, both uploads succeed

#### Edge case: Upload succeeds but submission creation fails
- **WHEN** file is written to disk but the database transaction for submission fails
- **THEN** file remains on disk as orphan, cleaned up by daily cron within 24 hours

#### Edge case: Upload with filename containing special characters
- **WHEN** user uploads a file named "作业(最终版) - 副本.pdf"
- **THEN** system stores with UUID prefix, original_filename preserves the original name for download headers

### Requirement: Authorized users can download files
The system SHALL serve files with correct Content-Type and Content-Disposition headers. Download requires ownership validation.

**User story:** As a student, I want to download my submitted files. As a teacher, I want to download student submissions for offline review.

**Permission boundary:** Student downloads own files only. Teacher downloads files from tasks they created. Admin downloads any file.

#### Scenario: Download with correct headers
- **WHEN** authorized user submits GET /api/files/:id
- **THEN** system returns file with Content-Type matching extension and Content-Disposition: attachment; filename="original_filename"

#### Scenario: Download without authorization
- **WHEN** user attempts to download a file they don't own (not their submission and not their task)
- **THEN** system returns 403

### Requirement: File storage uses local filesystem
The system SHALL store files on the local filesystem under /uploads/. Files are served via Nginx X-Accel-Redirect header for efficient download.

**User story:** As the system operator, I want file storage to be simple (local disk, no cloud dependencies) and efficient (Nginx serves files, not the application server).

**Permission boundary:** Application validates ownership, Nginx handles file serving. No direct URL access to /uploads/ (Nginx internal location).

#### Scenario: Download via Nginx
- **WHEN** authorized download request reaches FastAPI
- **THEN** FastAPI validates ownership and returns X-Accel-Redirect header, Nginx serves the file directly

### Requirement: Orphan files are cleaned up
The system SHALL clean up uploaded files that are not linked to any submission within 24 hours.

**User story:** As the system operator, I want disk space reclaimed from abandoned uploads so that the server doesn't run out of storage.

**Permission boundary:** System cron job, no user interaction. Runs daily.

#### Scenario: Cleanup orphan files
- **WHEN** periodic cleanup runs (cron, daily)
- **THEN** system deletes files older than 24 hours from /uploads/tmp/ that have no corresponding submission_files record

#### Edge case: File cleanup while submission is being created
- **WHEN** cron job runs while a file is being linked to a submission (race window)
- **THEN** file in /uploads/ (not /uploads/tmp/) is not affected; only /uploads/tmp/ files are cleaned
