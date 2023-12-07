""" Lifecycle User Model """

from dataclasses import MISSING, dataclass, field, fields


class ModelBase:
    """Common class of Groups and Users"""

    @classmethod
    def mandatory_fields(cls):
        """Mandatory fields have no default and *must* be passed into the dataclass' constructor"""
        return {
            field.name
            for field in fields(cls)
            if field.default is MISSING and field.default_factory is MISSING
        }

    @classmethod
    def optional_fields(cls):
        """Optional fields have defaults and *may* be passed into the dataclass' constructor"""
        return {
            field.name
            for field in fields(cls)
            if field.default is not MISSING or field.default_factory is not MISSING
        }

    @classmethod
    def supported_fields(cls):
        """Supported fields are any field that is present in the data model"""
        return {field.name for field in fields(cls)}


@dataclass(unsafe_hash=True, order=True)
class Group(ModelBase):
    """internal representation of a group"""

    name: str
    description: str = ""
    email: tuple[str] = field(default_factory=tuple)

    def __post_init__(self):
        self.email = tuple(self.email)


@dataclass(unsafe_hash=True, order=True)
class User(ModelBase):
    """internal representation of a user"""

    # pylint: disable-msg=too-many-arguments

    username: str
    forename: str = ""
    surname: str = ""
    fullname: str = ""
    email: tuple[str] = field(default_factory=tuple)
    groups: tuple[Group] = field(default_factory=tuple)
    locked: bool = False

    def __post_init__(self):

        # this section will get a bit into 'fallacies programmers believe about names'
        # but our basic assumptions for this logic are: forename is first word in
        # full name, surname is last word in fullname, and full name can be put
        # together by assembling the two.  For our purposes, these assumptions
        # plus the ability to specify each of forename, surname, and fullname
        # should cover almost all our cases.

        if self.fullname:
            if not self.forename:
                self.forename = self.fullname.split(" ", maxsplit=1)[0]
            if not self.surname:
                self.surname = self.fullname.split(" ", maxsplit=1)[-1]
        else:
            tmp_fullname = []
            if self.forename:
                tmp_fullname.append(self.forename)
            if self.surname:
                tmp_fullname.append(self.surname)
            self.fullname = " ".join(tmp_fullname)

        self.email = tuple(self.email)
        self.groups = tuple(self.groups)
