"""
gitlab3
~~~~~~~

Python wrapper for GitLab API v3

:copyright: (c) 2013 by Alex Van't Hof.
:license: LGPLv3, see LICENSE for more details.
"""


import json
import re
import requests
from datetime import tzinfo, timedelta, datetime
from math import ceil

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

from . import exceptions
from ._api_definition import GitLab as _GitLabAPIDefinition
from ._api_definition import _LIST, _GET, _ADD, _EDIT, _DELETE, \
                             _HTTP_GET, _HTTP_PUT, _HTTP_POST, _HTTP_DELETE

# Access level constants
ACCESS_LEVEL_GUEST = 10
ACCESS_LEVEL_REPORTER = 20
ACCESS_LEVEL_DEVELOPER = 30
ACCESS_LEVEL_MASTER = 40
ACCESS_LEVEL_OWNER = 50

# Maximum 'per_page' value allowed by GitLab when listing
_MAX_PER_PAGE = 100


def _query_list(api_cls, parent, data):
    """Helper for find and list functions. Queries GitLab for an entire
       listing of objects '_MAX_PER_PAGE' objects at a time.
    """
    data['per_page'] = _MAX_PER_PAGE
    page = 0
    last_objs = None
    while True:
        data['page'] = page
        objs = parent._get(api_cls._uq_url, data=data)
        # GitLab doesn't always return empty list at end, may repeat last...
        if not objs or str(objs) == last_objs:
            # Some listings start with page 0, others with 1...
            # (in the latter case, page 0 will be the same as page 1
            if page == 1:  # If page 0 == page 1, try page 2
                page += 1
                continue
            break
        # "hash" the list as a string for comparison to prevent deep copy
        # (would be modified when converting date strings to datetime objects)
        last_objs = str(objs)
        page += 1
        for obj in objs:
            yield api_cls(parent, obj)


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
            for i in range(1, num_pages+1):
                data['page'] = i
                objs = parent._get(api._uq_url, data=data)
                if remainder and i == num_pages:  # Final request
                    objs = objs[:remainder]
                for obj in objs:
                    ret.append(api(parent, obj))
        else:  # Obtain full list
            for api_obj in _query_list(api, parent, data):
                ret.append(api_obj)
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
        for param, val in list(kwargs.items()):
            if not getattr(obj, param) == val:
                match = False
                break
        if match:
            if find_all:
                ret.append(obj)
            else:
                return obj
    if not find_all:
        return None
    return ret


def _add_find_fn(api, name, parent):
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
        try:
            query_data = {}
            query_data['sudo'] = kwargs['sudo']
            del kwargs['sudo']
        except KeyError:
            pass
        if not objects:
            objects = _query_list(api, parent, query_data)

        return _find_matches(objects, kwargs, find_all)
    setattr(parent, 'find_' + name, fn)


def _add_get_fn(api, name, parent):
    """Create a <PARENT_API>.get_<name>() function"""
    fixed_url = api._q_url.replace('merge_requests', 'merge_request')
    def fn(key=[], **kwargs):
        if key and '/' in key:
            key = key.replace('/', '%2F')
        if key != []:
            key = [key]
        data = parent._get(fixed_url, addl_keys=key, data=kwargs)
        ret = api(parent, data)
        return ret
    setattr(parent, 'get_' + name, fn)
    setattr(parent, name, fn)


def _add_create_fn(api, api_definition, parent):
    """Create a <PARENT_API>.add_<name>() function"""
    fn_name = "add_" + api_definition.name()
    required_params = api_definition.required_params
    optional_params = api_definition.optional_params
    def fn(*args, **kwargs):
        if len(args) < len(required_params):
            raise TypeError("%s() takes at least %d arguments (%d given)" \
                            % (fn_name, len(required_params), len(args)))
        max_args = len(required_params) + len(optional_params)
        if len(args) > max_args:
            raise TypeError("%s() takes at most %d arguments (%d given)" \
                            % (fn_name, max_args, len(args)))
        idx = -1
        # Load kwargs with required params
        for idx, param in enumerate(required_params):
            kwargs[param] = args[idx]
        idx += 1
        # Load kwargs with unnamed optional params
        for i in range(idx, len(args)):
            kwargs[optional_params[i-idx]] = args[i]

        data = parent._post(api._uq_url, data=kwargs)
        ret = api(parent, data)
        return ret
    setattr(parent, fn_name, fn)


def _add_edit_fn(api, name, parent):
    """Create <PARENT_API>.update_name(obj) and <API>.save() functions"""
    fixed_url = api._q_url.replace('merge_requests', 'merge_request')
    def parent_fn(obj):
        if not isinstance(obj, api):
            raise TypeError("Expected instance of %s" % api)
        return obj.save()
    def self_fn(self):
        return self._put(fixed_url, data=self._get_data())
    setattr(parent, 'update_' + name, parent_fn)
    setattr(api, 'save', self_fn)


def _add_delete_fn(api, name, parent):
    """Create <PARENT_API>.delete_name(obj) and <API>.delete() functions"""
    def parent_fn(obj):
        if not isinstance(obj, api):
            raise TypeError("Expected instance of %s" % api)
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
    url_params = re.findall(':(\w+)', action_def.url)
    http_method = action_def.method
    url = api._q_url  # XXX: do any extra fns need unqualified url?
    url += action_def.url
    req_fn = _get_http_request_fn(api, http_method)
    num_req_params = len(url_params) + len(required_params) + 1  # + _self
    url = url.replace('merge_requests', 'merge_request')

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
    # 'sudo' is an optional parameter for all functions
    definition.optional_params.append('sudo')

    cls_attrs = {
        '_key_name': definition.key_name,
        '_q_url': q_url,
        '_uq_url': uq_url,
        '_sub_apis': sub_apis,
    }
    cls_name = definition.class_name()
    cls = type(cls_name, (_GitLabAPI,), cls_attrs)

    if _LIST in definition.actions:
        _add_list_fn(cls, definition, parent)
        _add_find_fn(cls, name, parent)
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
        if self._convert_dates_enabled:
            self._convert_dates(json_data)
        for key, val in list(json_data.items()):
            setattr(self, key, val)
        self._parent = parent
        self._data_keys = list(json_data.keys())
        for sub_api in self._sub_apis:
            _add_api(sub_api, self)
        self._sub_apis = None

    _date_fields = {
        'created_at': True,
        'updated_at': True,
        'expires_at': True,
        'last_activity_at': True,
        'timestamp': True,
        'authored_date': True,
        'committed_date': True,
    }
    def _convert_dates(self, data):
        if type(data) == list:
            for item in data:
                self._convert_dates(item)
            return
        for key, val in list(data.items()):
            if type(val) == dict:
                self._convert_dates(val)
            if self._date_fields.get(key) and val:
                data[key] = self._convert_gitlab_date(val)

    def _convert_gitlab_date(self, datetime_str):
        """Convert GitLab datetime string to datetime object"""
        fmt = '%Y-%m-%dT%H:%M:%S'
        offset = None
        if datetime_str.endswith('Z'):
            datetime_str = datetime_str[:-1]
        else:
            offset = datetime_str[-6:]
            datetime_str = datetime_str[:-6]
        if re.search(r'\.[0-9]{3}$', datetime_str):
            fmt += '.%f'  # microseconds are included
        dt = datetime.strptime(datetime_str, fmt)
        if not offset:
            return dt
        class GitLabTzInfo(tzinfo):
            def __init__(self, utcoffset):
                self.utcoffset_val = timedelta(minutes=utcoffset)
            def utcoffset(self, dt):
                return self.utcoffset_val
            def dst(self):
                return None
        sign = offset[0]
        hours = int(offset[1:3])
        minutes = int(offset[-2:])
        offset = hours*60 + minutes
        if sign == '-':
            offset = -offset
        return dt.replace(tzinfo=GitLabTzInfo(offset))

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

    _code_to_exc = {
        400: exceptions.MissingRequiredAttribute,
        401: exceptions.UnauthorizedRequest,
        403: exceptions.ForbiddenRequest,
        404: exceptions.ResourceNotFound,
        405: exceptions.RequestNotSupported,
        409: exceptions.ResourceConflict,
        500: exceptions.ServerError,
    }
    def _check_status_code(self, status_code, url, data):
        if status_code < 400:
            return
        msg = "URL: %s, Data: %s" % (url, data)
        raise self._code_to_exc[status_code](msg)

    def _get(self, api_url, addl_keys=[], data=None):
        """get or list"""
        return self._request(requests.get, api_url, addl_keys, data)

    def _post(self, api_url, addl_keys=[], data=None):
        return self._request(requests.post, api_url, addl_keys, data)

    def _put(self, api_url, addl_keys=[], data=None):
        return self._request(requests.put, api_url, addl_keys, data)

    def _delete(self, api_url, addl_keys=[], data=None):
        return self._request(requests.delete, api_url, addl_keys, data)

    def _request(self, request_fn, api_url, addl_keys, data):
        url = self._get_url(api_url, addl_keys)
        #print "%s %s, data=%s" % (request_fn.__name__.upper(), url, str(data))
        try:
            if request_fn == requests.get or request_fn == requests.head:
              url = url + '?' + urlencode(data,doseq=True)
              data=None
            r = request_fn(url, headers=self._headers, data=data,
                           **self._requests_kwargs)
        except requests.exceptions.RequestException:
            msg = "'%s' request to '%s' failed" % (request_fn.__name__, url)
            raise exceptions.ConnectionError(msg)
        self._check_status_code(r.status_code, url, data)
        try:
            return json.loads(r.content.decode())
        except ValueError:  # XXX: assume we're returning plain text
            return r.content

    def __repr__(self):
        """__repr__ function for new API class"""
        return str(self._get_data())


class GitLab(_GitLabAPI):
    """A GitLab API connection."""

    def __init__(self, gitlab_url, token=None, convert_dates=True,
                 ssl_verify=True, ssl_cert=None):
        if gitlab_url[-1:] == '/':
            gitlab_url = gitlab_url[:-1]
        setattr(_GitLabAPI, '_base_url', gitlab_url + "/api/v3")
        setattr(_GitLabAPI, '_headers', {'PRIVATE-TOKEN': token})
        setattr(_GitLabAPI, '_convert_dates_enabled', convert_dates)
        requests_kwargs = { 'verify': ssl_verify }
        if ssl_cert is not None:
            requests_kwargs['cert'] = ssl_cert
        setattr(_GitLabAPI, '_requests_kwargs', requests_kwargs)

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

    class sudo:
        """Alternative sudo usage. To be used with the 'with' statement"""
        def __init__(self, username_or_id):
            self.user = username_or_id
        def __enter__(self):
            headers = getattr(_GitLabAPI, '_headers')
            headers['SUDO'] = self.user
        def __exit__(self, type, value, traceback):
            headers = getattr(_GitLabAPI, '_headers')
            del headers['SUDO']
