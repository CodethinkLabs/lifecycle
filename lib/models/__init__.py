""" Lifecycle User Model """

from dataclasses import dataclass


@dataclass
class User:
    """internal representation of a user"""

    # pylint: disable-msg=too-many-arguments

    username = ""
    forename = ""
    surname = ""
    fullname = ""
    email = []
    groups = []

    def __init__(
        self,
        username,
        forename=None,
        surname=None,
        fullname=None,
        email=None,
        groups=None,
    ):
        self.username = username
        self.email = email or []
        self.groups = groups or []

        # this section will get a bit into 'fallacies programmers believe about names'
        # but our basic assumptions for this logic are: forename is first word in
        # full name, surname is last word in fullname, and full name can be put
        # together by assembling the two.  For our purposes, these assumptions
        # plus the ability to specify each of forename, surname, and fullname
        # should cover almost all our cases.

        self.fullname = fullname
        self.forename = forename
        self.surname = surname
        if fullname:
            if not forename:
                self.forename = fullname.split(" ")[0]
            if not surname:
                self.surname = fullname.split(" ")[-1]
        else:
            tmp_fullname = []
            if forename:
                tmp_fullname.append(forename)
            if surname:
                tmp_fullname.append(surname)
            self.fullname = " ".join(tmp_fullname)


@dataclass
class Group:
    """internal representation of a group"""

    name = ""
    description = ""
    email = []

    def __init__(
        self,
        name,
        description="",
        email=None,
    ):
        self.name = name
        self.description = description
        self.email = email or []
