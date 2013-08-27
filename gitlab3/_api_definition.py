import re

# Actions
_LIST = 0
_GET = 1
_ADD = 2
_EDIT = 3
_DELETE = 4

# HTTP Methods
_HTTP_GET = 0
_HTTP_PUT = 1
_HTTP_POST = 2
_HTTP_DELETE = 3


# Note: optional_params are only included for documentation purposes

def uncamel(name):
    """un-camelcase string. From http://stackoverflow.com/questions/
       1175208/elegant-python-function-to-convert-camelcase-to-camel-case
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class APIDefinition(object):
    url = ''
    key_name = 'id'
    actions = []
    extra_actions = []
    required_params = []
    optional_params = []
    sub_apis = []

    @classmethod
    def name(cls):
        return uncamel(cls.__name__)

    @classmethod
    def class_name(cls):
        return cls.__name__

    @classmethod
    def plural_name(cls):
        return cls.name() + 's'


class ExtraActionDefinition(object):
    """Definition of a "non-standard" function"""
    url = None
    url_params = []
    required_params = []
    optional_params = []

    @classmethod
    def name(cls):
        # Strip "Action" suffix and uncamel
        return uncamel(cls.__name__[:-6])


class SSHKey(APIDefinition):
    url = '/keys/:id'
    actions = [ _LIST, _GET, _ADD, _DELETE ]
    required_params = [
        'title',
        'key',
    ]


class CurrentUser(APIDefinition):
    url = '/user'
    actions = [ _GET ]
    sub_apis = [ SSHKey ]


class Group(APIDefinition):
    url = '/groups/:id'
    actions = [ _LIST, _GET, _ADD ]
    required_params = [
        'name',
        'path',
    ]

    class TransferProjectAction(ExtraActionDefinition):
        """gl.Group.transfer_project(project_id)"""
        url = '/groups/:id/projects/:project_id'
        method = _HTTP_POST
        url_params = [
            'project_id',
        ]
    extra_actions = [ TransferProjectAction ]


class SystemHook(APIDefinition):
    url = '/hooks/:id'
    actions = [ _LIST, _ADD, _DELETE ]
    required_params = [
        'url',
    ]

    class TestAction(ExtraActionDefinition):
        """gl.Hook.test()"""
        url = '/hooks/:id'
        method = _HTTP_GET
    extra_actions = [ TestAction ]


class Issue(APIDefinition):
    url = '/issues'
    actions = [ _LIST ]


class Member(APIDefinition):
    url = '/members/:user_id'
    actions = [ _LIST, _GET, _ADD, _EDIT, _DELETE ]
    required_params = [
        'user_id',
        'access_level',
    ]


class Note(APIDefinition):
    url = '/notes/:note_id'
    actions = [ _LIST, _GET, _ADD ]
    required_params = [
        'body',
    ]


class Project(APIDefinition):
    url = '/projects/:id'
    actions = [ _LIST, _GET, _ADD ]
    required_params = [
        'name',
    ]
    optional_params = [
        'description',
        'default_branch',
        'issues_enabled',
        'wall_enabled',
        'merge_requests_enabled',
        'wiki_enabled',
        'snippets_enabled',
        'public',
    ]

    ####
    # Extra Actions
    class ForkFromAction(ExtraActionDefinition):
        """gl.Project.fork_from(forked_from_id)"""
        url = '/fork/:forked_from_id'
        method = _HTTP_POST
        url_params = [
            'forked_from_id',
        ]
    class DeleteForkAction(ExtraActionDefinition):
        """gl.Project.delete_fork()"""
        url = '/fork'
        method = _HTTP_DELETE
    class GetBlobAction(ExtraActionDefinition):
        """gl.Project.get_blob()"""
        url = '/repository/commits/:sha/blob'
        method = _HTTP_GET
        url_params = [
            'sha_or_ref_name',
        ]
        required_params = [
            'filepath',
        ]
    class ProtectBranchAction(ExtraActionDefinition):
        """gl.Project.protect_branch()"""
        url = '/repository/branches/:branch/protect'
        method = _HTTP_PUT
        url_params = [
            'branch',  # GitLab API is branch name
        ]
        @staticmethod
        def wrapper(extra_action_fn, parent):
            """Accept a Branch object instead of a branch name"""
            def wrapped(self, branch):
                name = getattr(branch, 'name', branch)  # allow passing name
                extra_action_fn(self, name)
                try: # If passed a branch object, update it
                    setattr(branch, 'protected', True)
                except AttributeError:
                    pass
            return wrapped
    class UnprotectBranchAction(ExtraActionDefinition):
        """gl.Project.unprotect_branch()"""
        url = '/repository/branches/:branch/unprotect'
        method = _HTTP_PUT
        url_params = [
            'branch',  # GitLab API is branch name
        ]
        @staticmethod
        def wrapper(extra_action_fn, parent):
            """Accept a Branch object instead of a branch name"""
            def wrapped(self, branch):
                name = getattr(branch, 'name', branch)  # allow passing name
                extra_action_fn(self, name)
                try: # If passed a branch object, update it
                    setattr(branch, 'protected', False)
                except AttributeError:
                    pass
            return wrapped

    extra_actions = [
        ForkFromAction,
        DeleteForkAction,
        GetBlobAction,
        ProtectBranchAction,
        UnprotectBranchAction,
    ]

    ###
    # Sub APIs
    class DeployKey(SSHKey):
        pass

    class Event(APIDefinition):
        url = '/events'
        actions = [ _LIST ]

    class Hook(APIDefinition):
        url = '/hooks/:id'
        actions = [ _LIST, _GET, _ADD, _EDIT, _DELETE ]
        required_params = [
            'url',
        ]

    class Issue(APIDefinition):
        url = '/issues/:issue_id'
        actions = [ _LIST, _GET, _ADD, _EDIT ]
        required_params = [
            'title',
        ]
        optional_params = [
            'description',
            'assignee_id',
            'milestone_id',
            'labels',
            'state_event',
        ]
        sub_apis = [ Note ]

    class Branch(APIDefinition):
        url = '/repository/branches/:branch'
        key_name = 'name'
        actions = [ _LIST, _GET ]

        @classmethod
        def plural_name(cls):
            return cls.name() + 'es'

        ###
        # Extra Actions
        class ProtectAction(ExtraActionDefinition):
            """gl.Project.Branch.protect()"""
            url = '/protect'
            method = _HTTP_PUT
            @staticmethod
            def wrapper(extra_action_fn, parent):
                """Accept a Branch object instead of a branch name"""
                def wrapped(self):
                    extra_action_fn(self)
                    setattr(self, 'protected', True)
                return wrapped
        class UnprotectAction(ExtraActionDefinition):
            """gl.Project.Branch.unprotect()"""
            url = '/unprotect'
            method = _HTTP_PUT
            @staticmethod
            def wrapper(extra_action_fn, parent):
                """Accept a Branch object instead of a branch name"""
                def wrapped(self):
                    extra_action_fn(self)
                    setattr(self, 'protected', False)
                return wrapped
        extra_actions = [ ProtectAction, UnprotectAction ]

    class MergeRequest(APIDefinition):
        url = '/merge_requests/:merge_request_id'
        actions = [ _LIST, _GET, _ADD, _EDIT ]
        required_params = [
            'source_branch',
            'target_branch',
            'assignee_id', # TODO: is this required or not?
            'title',
        ]

        class PostCommentAction(ExtraActionDefinition):
            """gl.Project.MergeRequest.post_comment(note)"""
            url = '/merge_request/:merge_request_id/comments'
            method = _HTTP_POST
            required_args = [
                'note',
            ]

        extra_actions = [ PostCommentAction ]
        sub_apis = [ Note ]

    class Milestone(APIDefinition):
        url = '/milestones/:milestone_id'
        actions = [ _LIST, _GET, _ADD, _EDIT ]
        required_params = [
            'title',
        ]
        optional_params = [
            'description',
            'due_date',
            'state_event',
        ]

    class Snippet(APIDefinition):
        url = '/snippets/:snippet_id'
        actions = [ _LIST, _GET, _ADD, _EDIT, _DELETE ]
        required_params = [
            'title',
            'file_name',
            'code',
        ]
        optional_params = [
            'lifetime',
        ]

        class GetRawAction(ExtraActionDefinition):
            """gl.Project.Snippet.get_raw()"""
            url = '/snippets/:snippet_id/raw'
            method = _HTTP_GET

        extra_actions = [ GetRawAction ]
        sub_apis = [ Note ]

    class Tag(APIDefinition):
        url = '/repository/tags'
        actions = [ _LIST ]

    class File(APIDefinition):
        # Note: differs from GitLab API documentation
        url = '/repository/tree'
        actions = [ _LIST ]
        optional_params = [
            'path',
            'ref_name',
        ]

    class Commit(APIDefinition):
        url = '/repository/commits'
        actions = [ _LIST ]
        optional_params = [
            'ref_name',
        ]

    class WallNote(Note):
        @classmethod
        def name(cls):
            return 'wall_note'

    sub_apis = [
        Branch,
        DeployKey,
        Event,
        Hook,
        Issue,
        Member,
        MergeRequest,
        Milestone,
        Snippet,
        Tag,
        File,
        Commit,
        WallNote,
    ]


class User(APIDefinition):
    url = '/users/:id'
    actions = [ _LIST, _GET, _ADD, _EDIT, _DELETE ]
    required_params = [
        'email',
        'password',
        'username',
        'name',
    ]
    optional_params = [
        'skype',
        'linkedin',
        'twitter',
        'projects_limit',
        'extern_uid',
        'provider',
        'bio',
    ]

    class SSHKey(SSHKey):
        actions = [ _ADD ]

    sub_apis = [ SSHKey ]


class Team(APIDefinition):
    actions =  [ _LIST, _GET, _ADD ]
    required_params = [
        'name',
        'path',
    ]

    class Project(APIDefinition):
        url = '/projects/:project_id'
        actions = [ _LIST, _GET, _ADD, _DELETE ]
        required_params = [
            'project_id',
            'greatest_access_level',
        ]

    sub_apis = [ Member, Project ]


class GitLab(APIDefinition):
    class AddProjectForUserAction(ExtraActionDefinition):
        """gl.add_project_for_user(user_id, name)"""
        url = '/projects/user/:user_id'
        method = _HTTP_POST
        url_params = [
            'user_id',
        ]
        required_params = [
            'name',
        ]
        optional_params = [
            'description',
            'default_branch',
            'issues_enabled',
            'wall_enabled',
            'merge_requests_enabled',
            'wiki_enabled',
            'snippets_enabled',
            'public',
        ]

        @staticmethod
        def wrapper(extra_action_fn, parent):
            def wrapped(*args, **kwargs):
                """Return the created Project"""
                import gitlab3
                project_data = extra_action_fn(*args, **kwargs)
                return gitlab3.Project(parent, project_data)
            return wrapped

    extra_actions = [ AddProjectForUserAction ]

    sub_apis = [
        CurrentUser,
        Issue,
        Group,
        SystemHook,
        Project,
        User,
        Team,
    ]
