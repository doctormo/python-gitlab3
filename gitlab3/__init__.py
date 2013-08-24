"""
Python wrapper for GitLab API v3
"""

__title__ = "gitlab3"
__version__ = "0.2"
__author__ = "Alex Van't Hof"
__license__ = "LGPLv3"
__copyright__ = "Copyright 2013 Alex Van't Hof"


import json
import re
import requests
from math import ceil

import exceptions
from _api_definition import GitLab as _GitLabAPIDefinition
from _api_definition import _LIST, _GET, _ADD, _EDIT, _DELETE, _HTTP_GET, \
                            _HTTP_PUT, _HTTP_POST, _HTTP_DELETE

# Access level constants
ACCESS_LEVEL_GUEST = 10
ACCESS_LEVEL_REPORTER = 20
ACCESS_LEVEL_DEVELOPER = 30
ACCESS_LEVEL_MASTER = 40

# Maximum 'per_page' value allowed by GitLab when listing
_MAX_PER_PAGE = 100

def _add_list_fn(api, api_definition, parent):
    """Create a <PARENT_API>.<name>s() function"""
    def fn(limit=None, page=None, per_page=None, **data):
        ret = []
        if limit:  # Give limit precedence over other params if misused
            page = None
            per_page = None
        if limit and limit <= _MAX_PER_PAGE:
            per_page = limit
            limit = None

        if page or per_page:
            if page:
                data['page'] = page
            if per_page:
                data['per_page'] = per_page
            objs = parent._get(api._uq_url, data=data)
            for obj in objs:
                ret.append(api(parent, obj))
        elif limit:
            data['per_page'] = _MAX_PER_PAGE
            num_pages = int(ceil(float(limit) / _MAX_PER_PAGE))
            remainder = limit % _MAX_PER_PAGE
            for i in xrange(1, num_pages+1):
                data['page'] = i
                objs = parent._get(api._uq_url, data=data)
                if remainder and i == num_pages:  # Final request
                    objs = objs[:remainder]
                for obj in objs:
                    ret.append(api(parent, obj))
        else:  # Obtain full list
            data['per_page'] = _MAX_PER_PAGE
            data['page'] = 1
            last_objs = None  # GitLab doesn't always return empty list at end
            while True:
                objs = parent._get(api._uq_url, data=data)
                if not objs or objs == last_objs:  # ouch...pricey
                    break
                for obj in objs:
                    ret.append(api(parent, obj))
                last_objs = objs
                data['page'] += 1
        return ret
    setattr(parent, api_definition.plural_name(), fn)
    return fn


def _find_matches(objects, kwargs, find_all):
    """Helper function for _add_find_fn. Find objects whose properties
       match all key, value pairs in kwargs.
    """
    ret = []
    for obj in objects:
        match = True
        # Match all supplied parameters
        for param, val in kwargs.iteritems():
            if not getattr(obj, param, None) == val:
                match = False
                break
        if match:
            if find_all:
                ret.append(obj)
            else:
                return obj
    return ret


def _add_find_fn(name, list_fn, parent):
    """Create a <PARENT_API>.find_<name>() function"""
    def fn(**kwargs):
        if not kwargs:
            raise TypeError("find_%s() requires at least one named argument" \
                            % (name))
        try:
            objects = kwargs['cached']
            del kwargs['cached']
        except KeyError:
            objects = None
        try:
            find_all = kwargs['find_all']
            del kwargs['find_all']
        except KeyError:
            find_all = False

        if objects:  # A cached list was supplied
            return _find_matches(objects, kwargs, find_all)
        elif find_all:  # Have to search entire list of objects
            return _find_matches(list_fn(), kwargs, find_all)
        # Optimize slightly and don't obtain whole object list if not necessary
        ret = []
        page = 1
        while True:
            objects = list_fn(page=page, per_page=_MAX_PER_PAGE)
            if not objects:
                break
            match = _find_matches(objects, kwargs, find_all)
            if match:
                return match
            page += 1
        return ret
    setattr(parent, 'find_' + name, fn)


def _add_get_fn(api, name, parent):
    """Create a <PARENT_API>.get_<name>() function"""
    def fn(key=[], **kwargs):
        if key != []:
            key = [key]
        data = parent._get(api._q_url, addl_keys=key, data=kwargs)
        ret = api(parent, data)
        return ret
    setattr(parent, 'get_' + name, fn)
    setattr(parent, name, fn)


def _add_create_fn(api, api_definition, parent):
    """Create a <PARENT_API>.add_<name>() function"""
    fn_name = "add_" + api_definition.name()
    required_params = api_definition.required_params
    def fn(*args, **kwargs):
        if len(args) != len(required_params):
            raise TypeError("%s() takes exactly %d arguments (%d given)" \
                            % (fn_name, len(required_params), len(args)))
        args = list(args)
        for param in required_params:
            kwargs[param] = args.pop(0)
        data = parent._post(api._uq_url, data=kwargs)
        ret = api(parent, data)
        return ret
    setattr(parent, fn_name, fn)


def _add_edit_fn(api, name, parent):
    """Create <PARENT_API>.update_name(obj) and <API>.save() functions"""
    def parent_fn(obj):
        return obj.save()
    def self_fn(self):
        return self._put(api._q_url, data=self._get_data())
    setattr(parent, 'update_' + name, parent_fn)
    setattr(api, 'save', self_fn)


def _add_delete_fn(api, name, parent):
    """Create <PARENT_API>.delete_name(obj) and <API>.delete() functions"""
    def parent_fn(obj):
        return obj.delete()
    def self_fn(self):
        return self._delete(api._q_url)
    setattr(parent, 'delete_' + name, parent_fn)
    setattr(api, 'delete', self_fn)


def _get_http_request_fn(api, method):
    if method == _HTTP_GET:
        return api._get
    elif method == _HTTP_PUT:
        return api._put
    elif method == _HTTP_POST:
        return api._post
    elif method == _HTTP_DELETE:
        return api._delete


def _add_extra_fn(api, action_def, parent=None):
    required_params = action_def.required_params
    # url_params are required params, but get passed as part of url
    url_params = action_def.url_params
    http_method = action_def.method
    url = api._q_url  # XXX: do any extra fns need unqualified url?
    url += action_def.url
    req_fn = _get_http_request_fn(api, http_method)
    num_req_params = len(url_params) + len(required_params) + 1  # + _self

    def fn(*args, **kwargs):
        if len(args) != num_req_params:
            raise TypeError("%s() takes exactly %d arguments (%d given)" \
                            % (action_def.name(), num_req_params, len(args)))
        args = list(args)
        _self = args.pop(0)
        arg_keys = []
        for param in url_params:
            arg_keys.append(args.pop(0))
        for param in required_params:
            kwargs[param] = args.pop(0)
        return req_fn(_self, url, addl_keys=arg_keys, data=kwargs)

    # Apply a decorator to the extra action function if one is defined
    wrapper = getattr(action_def, 'wrapper', None)
    if wrapper:
        fn = wrapper(fn, parent)

    setattr(api, action_def.name(), fn)


def _add_api(definition, parent):
    """Create a new class for an api"""
    name = definition.name()
    sub_apis = definition.sub_apis
    url = definition.url
    q_url = "%s%s" % (parent._q_url, url)
    if parent._id:
        uq_url = parent._q_url
    else:
        uq_url = parent._uq_url
    uq_url += re.sub(r'/\:.*', '', url)  # "unqualify" the url

    cls_attrs = {
        '_key_name': definition.key_name,
        '_q_url': q_url,
        '_uq_url': uq_url,
        '_sub_apis': sub_apis,
    }
    cls_name = definition.class_name()
    cls = type(cls_name, (_GitLabAPI,), cls_attrs)

    if _LIST in definition.actions:
        list_fn = _add_list_fn(cls, definition, parent)
        _add_find_fn(name, list_fn, parent)
    if _GET in definition.actions:
        _add_get_fn(cls, name, parent)
    if _ADD in definition.actions:
        _add_create_fn(cls, definition, parent)
    if _EDIT in definition.actions:
        _add_edit_fn(cls, name, parent)
    if _DELETE in definition.actions:
        _add_delete_fn(cls, name, parent)
    for action_def in definition.extra_actions:
        _add_extra_fn(cls, action_def, parent)

    for definition in sub_apis:
        _add_api(definition, cls)

    setattr(parent, cls_name, cls)
    return cls


class _GitLabAPI(object):
    """Base API template"""
    _id = None
    _q_url = ''
    _uq_url = ''
    _data_keys = []
    _headers = {}

    def __init__(self, parent, json_data={}):
        try:
            setattr(self, '_id', json_data[self._key_name])
        except KeyError:  # some objects don't give us an id (e.g. events)
            pass
        for key, val in json_data.iteritems():
            setattr(self, key, val)
        self._parent = parent
        self._data_keys = json_data.keys()
        for sub_api in self._sub_apis:
            _add_api(sub_api, self)
        self._sub_apis = None

    def _get_url(self, api_url, addl_keys=[]):
        keys = self._get_keys(addl_keys)
        # Handle annoying case of CurrentUser (wherein we have more keys
        # than we need) by stripping away excess keys...
        num_url_keys = len(re.findall(r':[^/]+', api_url))
        keys = keys[-num_url_keys:]
        for key in keys:
            api_url = re.sub(r':[^/]+', str(key), api_url, 1)
        return self._base_url + api_url

    def _get_data(self):
        data = {}
        for key in self._data_keys:
            data[key] = getattr(self, key, '')
        return data

    def _get_keys(self, addl_keys=[]):
        ret = []
        ret += addl_keys  # want copy of addl_keys
        api = self
        while api and api._id:
            ret.append(api._id)
            api = api._parent
        ret.reverse()  # Need to modify this later so no reversed()
        return ret

    def _check_status_code(self, status_code, url, data):
        if status_code < 400:
            return
        msg = "URL: %s, Data: %s" % (url, data)
        if status_code == 400:
            raise exceptions.MissingRequiredAttribute(msg)
        elif status_code == 401:
            raise exceptions.UnauthorizedRequest(msg)
        elif status_code == 403:
            raise exceptions.ForbiddenRequest(msg)
        elif status_code == 404:
            raise exceptions.ResourceNotFound(msg)
        elif status_code == 405:
            raise exceptions.RequestNotSupported(msg)
        elif status_code == 409:
            raise exceptions.ResourceConflict(msg)
        elif status_code == 500:
            raise exceptions.ServerError(msg)

    def _get(self, api_url, addl_keys=[], data=None):
        """get or list"""
        url = self._get_url(api_url, addl_keys)
        try:
            r = requests.get(url, headers=self._headers, data=data)
        except requests.exceptions.RequestException:
            raise exceptions.ConnectionError("Failed to get " + url)
        self._check_status_code(r.status_code, url, data)
        try:
            return json.loads(r.content)
        except ValueError:  # XXX: assume we're returning plain text
            return r.content

    def _post(self, api_url, addl_keys=[], data=None):
        url = self._get_url(api_url, addl_keys)
        try:
            r = requests.post(url, headers=self._headers, data=data)
        except requests.exceptions.RequestException:
            raise exceptions.ConnectionError("Failed to post " + url)
        self._check_status_code(r.status_code, url, data)
        return json.loads(r.content)

    def _put(self, api_url, addl_keys=[], data=None):
        url = self._get_url(api_url, addl_keys)
        try:
            r = requests.put(url, headers=self._headers, data=data)
        except requests.exceptions.RequestException:
            raise exceptions.ConnectionError("Failed to put " + url)
        self._check_status_code(r.status_code, url, data)
        return json.loads(r.content)

    def _delete(self, api_url, addl_keys=[], data=None):
        url = self._get_url(api_url, addl_keys)
        try:
            r = requests.delete(url, headers=self._headers, data=data)
        except requests.exceptions.RequestException:
            raise exceptions.ConnectionError("Failed to delete " + url)
        self._check_status_code(r.status_code, url, data)
        return json.loads(r.content)

    def __repr__(self):
        """__repr__ function for new API class"""
        return str(self._get_data())


class GitLab(_GitLabAPI):
    """A GitLab API connection."""

    def __init__(self, gitlab_url, token=None):
        setattr(_GitLabAPI, '_base_url', gitlab_url + "/api/v3")
        setattr(_GitLabAPI, '_headers', {'PRIVATE-TOKEN': token})

        for sub_api in _GitLabAPIDefinition.sub_apis:
            cls = _add_api(sub_api, self)
            cls_name = sub_api.class_name()
            # Populate the module namespace with core classes
            globals()[cls_name] = cls
        for action_def in _GitLabAPIDefinition.extra_actions:
            _add_extra_fn(GitLab, action_def)

    def login(self, login_or_email, password):
        """Log in to GitLab. This is unnecessary if a token was given
           when creating this GitLab object.
        """
        data = {'password': password}
        if '@' in login_or_email:
            data['email'] = login_or_email
        else:
            data['login'] = login_or_email
        try:
            ret = self._post('/session', data=data)
        except exceptions.UnauthorizedRequest:
            return False
        headers = {'PRIVATE-TOKEN': ret['private_token']}
        setattr(_GitLabAPI, '_headers', headers)
        return True
