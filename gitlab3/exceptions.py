class GitLabException(Exception):
    """Base exception class"""

class MissingRequiredAttribute(GitLabException):  # 400 Bad Request
    """A required attribute of the API request is missing,
       e.g. the title of an issue is not given
    """

class UnauthorizedRequest(GitLabException):  # 401 Unauthorized
    """The user is not authenticated, a valid user token is necessary"""

class ForbiddenRequest(GitLabException):  # 403 Forbidden
    """The request is not allowed, e.g. the user is not
       allowed to delete a project
    """

class ResourceNotFound(GitLabException):  # 404 not Found
    """A resource could not be accessed, e.g. an ID for a
       resource could not be found
    """

class RequestNotSupported(GitLabException):  # 405 Method Not Allowed
    """The request is not supported"""

class ResourceConflict(GitLabException):  # 409 Conflict
    """A conflicting resource already exists, e.g. creating a project
       with a name that already exists
    """

class ServerError(GitLabException):  # 500 Server Error
    """While handling the request something went wrong on the server side"""

class ConnectionError(GitLabException):
    """A connection to GitLab could not be established due to a
       network problem, e.g. DNS failure, network is down, etc.
    """
