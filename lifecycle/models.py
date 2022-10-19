""" Lifecycle User Model """

from dataclasses import dataclass, field


@dataclass
class Group:
    """internal representation of a group"""

    name: str
    description: str = ""
    email: list[str] = field(default_factory=list)


@dataclass
class User:
    """internal representation of a user"""

    # pylint: disable-msg=too-many-arguments

    username: str
    forename: str = ""
    surname: str = ""
    fullname: str = ""
    email: list[str] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)

    def __post_init__(self):

        # this section will get a bit into 'fallacies programmers believe about names'
        # but our basic assumptions for this logic are: forename is first word in
        # full name, surname is last word in fullname, and full name can be put
        # together by assembling the two.  For our purposes, these assumptions
        # plus the ability to specify each of forename, surname, and fullname
        # should cover almost all our cases.

        if self.fullname:
            if not self.forename:
                self.forename = self.fullname.split(" ")[0]
            if not self.surname:
                self.surname = self.fullname.split(" ")[-1]
        else:
            tmp_fullname = []
            if self.forename:
                tmp_fullname.append(self.forename)
            if self.surname:
                tmp_fullname.append(self.surname)
            self.fullname = " ".join(tmp_fullname)
