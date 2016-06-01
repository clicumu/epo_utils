# -*- coding: utf-8 -*-
""" Module for making calls to EPO-OPS REST-API.

This module contain classes and functions to get data from
[EPO-OPS API](http://www.epo.org/searching-for-patents/technical/espacenet/ops.html)
"""
import requests
import enum
try:
    import requests_cache
except ImportError:
    _HAS_CACHE = False
else:
    _HAS_CACHE = True

import logging
from datetime import datetime, timedelta
from collections import namedtuple
from base64 import b64encode


AUTH_URL = 'https://ops.epo.org/3.1/auth/accesstoken'
""" str : Authorization URL. """

URL_PREFIX = 'https://ops.epo.org/3.1/rest-services'
""" str: Base URL for all calls to API. """


class Services(enum.Enum):
    """ EPO-OPS service - service url-infix mapping."""
    Family = 'family'
    Numbers = 'number-service'
    Published = 'published-data'
    PublishedSearch = 'published-data/search'
    Register = 'register'
    RegisterSearch = 'register/search'


class ReferenceType(enum.Enum):
    """ EPO-OPS API-call reference-types. """
    Publication = 'publication'
    Application = 'application'
    Priority = 'priority'


class APIInput:
    """
    Simple wrapper around API-input.
    """
    def __init__(self, id_type, number, kind=None, country=None, date=None):
        if id_type not in ('epodoc', 'docdb', 'original'):
            raise ValueError('invalid id_type: {}'.format(id_type))
        if date is not None:
            date = str(date)
            try:
                datetime.strptime(date, '%Y%M%d')
            except ValueError:
                raise ValueError('date must be in YYYYMMDD-format')
            else:
                if len(date) != 8:
                    raise ValueError('date must be in YYYYMMDD-format')

        self.id_type = id_type
        self.number = str(number)
        self.kind = kind
        self.country = country
        self.date = date

    def to_id(self):
        """ Format as valid API-input ID.

        Returns
        -------
        str
        """
        if ',' in self.number or '.' in self.number or '/' in self.number:
            number = '({})'.format(self.number)
        else:
            number = self.number

        parts = filter(None, [self.country, number,
                              self.kind, self.date])

        if self.id_type == 'original':
            id_ = '.'.join(parts).replace(' ', '%20')
        elif self.id_type == 'docdb':
            id_ = '.'.join(parts)
        elif self.id_type == 'epodoc':
            id_ = ''.join(parts)
        else:
            raise ValueError('invalid id_type: {}'.format(self.id_type))

        return id_


Token = namedtuple('Token', ['token', 'expires'])


class EPOClient:
    """ A simple client to call EPO-OPS REST-API using `requests`.

    Parameters
    ----------
    accept_type : str
        Http accept type.
    key : str, optional
        EPO OPS user key.
    secret : str, optional
        EPO OPS user secret.
    cache : bool
        If True, try to use `requests_cache` for caching. Default False.
    cache_kwargs : dict, optional.
        Passed to :py:func:`requests_cache.install_cache` as keyword
        arguments if provided.

    Attributes
    ----------
    secret : str
    key : str
    token : Token or None
    """

    def __init__(self, accept_type='xml', key=None, secret=None, cache=False,
                 cache_kwargs=None):
        if accept_type.startswith('application/'):
            self.accept_type = accept_type
        else:
            self.accept_type = 'application/{}'.format(accept_type)

        if cache and _HAS_CACHE:
            logging.info('Installs cache.')
            requests_cache.install_cache(**(cache_kwargs or dict()))
        elif cache:
            raise ValueError('cache is set to True but requests_cache '
                             'is not available.')

        self.secret = secret
        self.key = key
        if all([secret, key]):
            logging.debug('Auth provided.')
            self.token = self.authenticate()
        else:
            logging.debug('Auth not provided')
            self.token = None

    def fetch_published_data(self, ref_type, input, endpoint='biblio', options=None):
        """

        Parameters
        ----------
        ref_type : ReferenceType
            OPS-reference type of data to fetch.
        input : APIInput
            Input to API-call.
        endpoint : str
            API-endpoint to call.
        options : list, optional
            API-call constitents.

        Returns
        -------
        requests.Response
        """
        if not isinstance(ref_type, ReferenceType):
            raise ValueError('invalid service: {}'.format(ref_type))

        options = options or list()
        url = build_ops_url(Services.Published, ref_type,
                            input, endpoint, options)

        headers = self._make_headers()

        logging.debug('Makes request to: {}\nheaders: {}'.format(url, headers))
        response = requests.get(url, headers=headers)
        return response

    def search(self, *args, **kwargs):
        pass

    def authenticate(self):
        """ If EPO-OPS customer key and secret is available
        get access-token.

        Returns
        -------
        token : Token
            Token and expiration time.
        """
        if not all([self.secret, self.key]):
            return None

        logging.info('Attempts to authenticate.')

        # Post base 64-encoded credentials to get access-token.
        credentials = '{0}:{1}'.format(self.key, self.secret)
        encoded_creds = b64encode(credentials.encode('ascii')).decode('ascii')
        headers = {'Authorization': 'Basic {}'.format(encoded_creds)}
        payload = {'grant_type': 'client_credentials'}
        response = requests.post(AUTH_URL, headers=headers, data=payload)
        response.raise_for_status()
        logging.info('Authentication succeeded.')

        # Parse response.
        content = response.json()
        token = content['access_token']
        expires_in = int(content['expires_in'])
        expires = datetime.now() + timedelta(seconds=expires_in)
        token = Token(token, expires)
        return token

    def _make_headers(self):
        """ Prepare request headers.

        Returns
        -------
        dict
        """
        headers = {'Accept': self.accept_type}
        if self.token is not None:
            if self.token is None or datetime.now() > self.token.expires:
                # Refresh token if is expired or missing.
                self.authenticate()

            headers['Authorization'] = 'Bearer {}'.format(self.token.token)

        return headers


def build_ops_url(service, reference_type, input,
                  endpoint, options, only_input_format=False):
    """ Prepare an url for calling the OPS-API.

    If `only_input_format` is False the URL will be formatted as::

    :py:const:`URL_PREFIX`/service/reference-type/inputformat/input/[endpoint]/[constituent(s)]

    Otherwise it will be formatted::

    :py:const:`URL_PREFIX`/service/reference-type/inputformat/[endpoint]/[constituent(s)]

    Parameters
    ----------
    service : Services
        OPS-service.
    reference_type : ReferenceType
        Reference type to call.
    input : APIInput or None
        Call input.
    endpoint : str or None
        Optional endpoint.
    options : list
        Optional constituents.

    Returns
    -------
    url : str
        Formatted url.
    """
    url_parts = [
        URL_PREFIX,
        service.value,
        reference_type.value,
        input.id_type,
        input.to_id() if not only_input_format else None,
        endpoint,
        ','.join(options)
    ]
    present_parts = filter(None, url_parts)
    url = '/'.join(present_parts)
    logging.debug('Built url: {}'.format(url))
    return url
