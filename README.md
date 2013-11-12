# python-gitlab3

A Python wrapper for GitLab API v3.

There are existing python wrappers (notably, http://github.com/gpocentek/python-gitlab and http://github.com/Itxaka/python-gitlab), but I'm not fond of their interface/usage. In addition, this provides complete coverage of the GitLab API (and is easily maintainable).

# Dependencies
* [python-requests](http://docs.python-requests.org/en/latest/)

# Installation

```bash
$ sudo pip install gitlab3
```

# Documentation
See http://alexvh.github.io/python-gitlab3/ for complete API information (also contained in the `doc` directory). Ancient-looking, Epydoc-generated html since it organizes this project more clearly than Sphinx does.

# Example Usage
```python
import gitlab3

gl = gitlab3.GitLab('http://example.com/', 'token')
# Alternatively:
gl = gitlab3.GitLab('http://example.com/')
if not gl.login('username_or_email', 'password'):
    print "Login failed"

#
# Example usage involving listing objects
#
for project in gl.projects():  # all of the current user's projects
    print project.name

for event in gl.project(1).events(limit=10):  # 10 most recent events
    print event.action_name

for project in gl.projects(page=1, per_page=10):  # pagination
    print project.issues(limit=1)[0].title  # (assume issue[0] exists...)

#
# Sudo usage examples (GitLab v6.1+)
# All functions accept an optional, undocumented, 'sudo' argument
# specifiying a username or user id to act as.
#
gl.get_current_user(sudo='other_user')  # => 'other_user' CurrentUser object
gl.projects(sudo=2)  # => list of user 2's projects
with gl.sudo('other_user'):
    gl.get_current_user()  # => 'other_user' CurrentUser object
    gl.projects()  # => list of 'other_users's projects

#
# Example usage involving users
#
user = gl.add_user('user@example.com', 'passwd', 'username',
                   'real name', project_limit=50, bio='bio')
print type(user)  # => '<class 'gitlab3.User'>'
print type(user.created_at)  # => '<type 'datetime.datetime'>'

user = gl.user(1)  # or gl.get_user(1) - get_<name>() aliases <name>()
user.email = 'change@example.com'
user.save()  # or gl.update_user(user)

user.delete()  # or gl.delete_user(user)


#
# Example usage involving projects
#
project = gl.project(1)  # or gl.get_project(1)
print project.description
project.events(limit=10)

# Adding projects
gl.add_project('my project', description='description', public=True)
gl.add_project_for_user('user_id', 'test project', description='description')

# Branches and tags
branch = project.branch('master')
branch.protect()
project.unprotect_branch('master')
tags = project.tags()

# Members
member = project.add_member('user_id', gitlab3.ACCESS_LEVEL_GUEST)
member.access_level = gitlab3.ACCESS_LEVEL_DEVELOPER
member.save()  # or project.update_member(member)
project.delete_member('user_id')

# Issues
issues = project.issues(limit=10)
issue = project.add_issue('title', description='description')
issue.add_note('note body')
issue.close()
issue.reopen()

# Snippets
snippet = project.add_snippet('title', 'file_name', 'code')
snippet.delete()  # or project.delete_snippet(snippet)
snippet = project.snippet(1)
snippet_notes = snippet.notes()

# Files and commits
project.commits() # list of commits in master branch
project.files()  # list of files in master branch
project.files(ref_name='other_branch')
readme_contents = project.get_blob('master', 'README')


#
# Example usage involving user teams
#
teams = gl.teams()

team = gl.add_team('team name', 'path')
team.add_member('user_id', gitlab3.ACCESS_LEVEL_GUEST)
team.add_project('project_id', gitlab3.ACCESS_LEVEL_MASTER)


#
# Find function examples
# All objects that can be listed and obtained by an id have find functions.
#
# The find functions are simple, o(n), mostly unoptimized, and will request a
# listing of objects on every call unless given a cached list.
#
gl.find_project(name='python-gitlab3')  # params can be any property of object

projects = gl.projects()
gl.find_project(cached=projects, name='python-gitlab3')
gl.find_project(cached=projects, find_all=True, public=True)  # public projects
gl.find_project(cached=projects, find_all=True,
                public=True, wiki_enabled=True)  # public projects with wikis

gl.find_user(email='user@example.com')

project = gl.project(1)
project.find_member(username='user')
```
