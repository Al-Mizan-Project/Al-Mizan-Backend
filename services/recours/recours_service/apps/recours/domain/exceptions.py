class RecoursException(Exception):
    pass


class InvalidStateTransition(RecoursException):
    pass


class DeadlineExceeded(RecoursException):
    pass


class DuplicateRecours(RecoursException):
    pass


class UnauthorizedAction(RecoursException):
    pass


class RecoursNotModifiable(RecoursException):
    pass