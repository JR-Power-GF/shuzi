def test_all_models_imported_in_init():
    from app.models import User, Class, Task, Submission, SubmissionFile, Grade, RefreshToken

    assert User.__tablename__ == "users"
    assert Class.__tablename__ == "classes"
    assert Task.__tablename__ == "tasks"
    assert Submission.__tablename__ == "submissions"
    assert SubmissionFile.__tablename__ == "submission_files"
    assert Grade.__tablename__ == "grades"
    assert RefreshToken.__tablename__ == "refresh_tokens"


def test_all_models_registered_with_base():
    from app.database import Base
    import app.models  # noqa: triggers registration

    table_names = set(Base.metadata.tables.keys())
    expected = {"users", "classes", "tasks", "submissions", "submission_files", "grades", "refresh_tokens"}
    assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"
