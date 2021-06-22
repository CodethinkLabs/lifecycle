""" Basic functionality tests for user model """

from lifecycle.models import Group


def test_basic_group():
    """Test a group model can be created"""
    group = Group("testgroup")
    assert group.name == "testgroup"
