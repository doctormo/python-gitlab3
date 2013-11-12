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
    url = ''
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


class Member(APIDefinition):
    url = '/members/:user_id'
    actions = [ _LIST, _GET, _ADD, _EDIT, _DELETE ]
    required_params = [
        'user_id',
        'access_level',
    ]


class CurrentUser(APIDefinition):
    url = '/user'
    actions = [ _GET ]
    sub_apis = [ SSHKey ]


class Group(APIDefinition):
    url = '/groups/:id'
    actions = [ _LIST, _GET, _ADD, _DELETE ]
    required_params = [
        'name',
        'path',
    ]

    ####
    # Extra Actions
    class TransferProjectAction(ExtraActionDefinition):
        """gl.Group.transfer_project(project_id)"""
        url = '/projects/:project_id'
        method = _HTTP_POST
        url_params = [
            'project_id',
        ]
    extra_actions = [ TransferProjectAction ]

    ###
    # Sub APIs
    class Member(Member):  # Group API has limited Member actions...
        actions = [ _LIST, _ADD, _DELETE ]
    sub_apis = [ Member ]


class SystemHook(APIDefinition):
    url = '/hooks/:id'
    actions = [ _LIST, _ADD, _DELETE ]
    required_params = [
        'url',
    ]

    class TestAction(ExtraActionDefinition):
        """gl.Hook.test()"""
        method = _HTTP_GET
    extra_actions = [ TestAction ]


class Issue(APIDefinition):
    url = '/issues'
    actions = [ _LIST ]


class Note(APIDefinition):
    url = '/notes/:note_id'
    actions = [ _LIST, _GET, _ADD ]
    required_params = [
        'body',
    ]


class Project(APIDefinition):
    url = '/projects/:id'
    actions = [ _LIST, _GET, _ADD, _DELETE ]
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
    class DeleteForkAction(ExtraActionDefinition):
        """gl.Project.delete_fork()"""
        url = '/fork'
        method = _HTTP_DELETE
    class GetBlobAction(ExtraActionDefinition):
        """gl.Project.get_blob()"""
        url = '/repository/commits/:sha_or_ref_name/blob'
        method = _HTTP_GET
        required_params = [
            'filepath',
        ]
    class ProtectBranchAction(ExtraActionDefinition):
        """gl.Project.protect_branch()"""
        url = '/repository/branches/:branch/protect'
        method = _HTTP_PUT
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
        class CloseAction(ExtraActionDefinition):
            """gl.Project.Issue.close()"""
            method = _HTTP_PUT
            required_params = [ 'state_event' ]
            _state_after = 'closed'
            @classmethod
            def wrapper(cls, extra_action_fn, parent):
                def wrapped(self):
                    extra_action_fn(self, cls.name())
                    setattr(self, 'state', cls._state_after)
                return wrapped
        class ReopenAction(CloseAction):
            _state_after = 'reopened'

        extra_actions = [ CloseAction, ReopenAction ]


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
            'title',
        ]
        optional_params = [ 'assignee_id' ]

        class PostCommentAction(ExtraActionDefinition):
            """gl.Project.MergeRequest.post_comment(note)"""
            url = '/comments'
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

        class RawAction(ExtraActionDefinition):
            """gl.Project.Snippet.raw()"""
            url = '/raw'
            method = _HTTP_GET
        class GetRawAction(RawAction):
            pass

        extra_actions = [ RawAction, GetRawAction ]
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
        url = '/repository/commits/:sha'
        actions = [ _LIST, _GET ]
        optional_params = [
            'ref_name',
        ]
        class DiffAction(ExtraActionDefinition):
            """gl.Project.Commit.diff()"""
            url = '/diff'
            method = _HTTP_GET
        class GetDiffAction(DiffAction):
            pass
        extra_actions = [ DiffAction, GetDiffAction ]

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
        'admin',
        'can_create_group',
    ]

    class SSHKey(SSHKey):
        actions = [ _ADD ]

    sub_apis = [ SSHKey ]


class Team(APIDefinition):
    url = '/user_teams/:id'
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
    class FindProjectsByNameAction(ExtraActionDefinition):
        """gl.find_projects_by_name(query)"""
        url = '/projects/search/:query'
        method = _HTTP_GET
        optional_params = [
            'per_page',
            'page',
        ]
        @staticmethod
        def wrapper(extra_action_fn, parent):
            def wrapped(*args, **kwargs):
                """Return a list of Projects"""
                import gitlab3
                ret = []
                projects = extra_action_fn(*args, **kwargs)
                for project_data in projects:
                    ret.append(gitlab3.Project(parent, project_data))
                return ret
            return wrapped

    extra_actions = [ AddProjectForUserAction, FindProjectsByNameAction ]

    sub_apis = [
        CurrentUser,
        Issue,
        Group,
        SystemHook,
        Project,
        User,
        Team,
    ]
