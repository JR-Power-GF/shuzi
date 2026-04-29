from app.constants import UserRole


def test_user_role_all_contains_four_values():
    assert len(UserRole.ALL) == 4


def test_user_role_all_current_contains_three_values():
    assert len(UserRole.ALL_CURRENT) == 3


def test_user_role_values_are_strings():
    for role in UserRole.ALL:
        assert isinstance(role, str)


def test_user_role_existing_values_unchanged():
    assert UserRole.ADMIN == "admin"
    assert UserRole.TEACHER == "teacher"
    assert UserRole.STUDENT == "student"


def test_user_role_facility_manager_in_all():
    assert UserRole.FACILITY_MANAGER == "facility_manager"
    assert UserRole.FACILITY_MANAGER in UserRole.ALL


def test_all_current_subset_of_all():
    assert UserRole.ALL_CURRENT.issubset(UserRole.ALL)
