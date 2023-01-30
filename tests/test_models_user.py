""" Basic functionality tests for user model """

from lifecycle.models import Group, User


def test_basic_user():
    """Test a user model can be created"""
    user = User("testuser")
    assert user.username == "testuser"


def test_fullname_split():
    """Test a user's fullname is split into forename & surname when not supplied"""
    user = User("testuser", fullname="test user")
    assert user.forename == "test"
    assert user.surname == "user"


def test_fullname_assembled():
    """Test a user's fullname is assembled from forename & surname when not supplied"""
    user = User("testuser", forename="test", surname="user")
    assert user.fullname == "test user"


def test_name_specified():
    """Test a user's fullname is not assembled from forename & surname when supplied"""
    user = User(
        "testuser", fullname="test user", forename="testington", surname="user-smythe"
    )
    assert user.fullname == "test user"
    assert user.forename == "testington"
    assert user.surname == "user-smythe"


def test_group_user():
    """Test a user model can be created and added to a group"""
    user = User("testuser", groups=[Group("testgroup")])
    assert user.groups[0].name == "testgroup"
