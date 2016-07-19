import unittest
from unittest import mock
import re
import requests
import requests_mock
import hypothesis.strategies as st
import string
from hypothesis.extra import datetime as hyp_datetime
from hypothesis import given, assume
from epo_utils.ops import api
from epo_utils.ops.tests import utils


_date_formats = ['%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d',
                 '%y-%m-%d', '%Y%m%d', '%d%m%Y', '%y%m%d']


class APIInputTestCase(unittest.TestCase):

    @given(id_type=st.one_of(st.text(), st.sampled_from(api.VALID_IDTYPES)),
           number=utils.doc_numbers(),
           kind=st.one_of(st.characters(), st.none()),
           country=st.one_of(st.text(max_size=2), st.none()),
           raw_date=st.one_of(hyp_datetime.datetimes(min_year=1900), st.none()),
           date_format=st.sampled_from(_date_formats))
    def test_api_input_raises_ValueError_on_bad_input(self, id_type, number,
                                                      kind, country, raw_date,
                                                      date_format):
        invalid = date_format != '%Y%m%d' and raw_date is not None
        invalid |= (id_type not in api.VALID_IDTYPES)
        invalid |= country is not None and not country.strip()
        invalid |= kind is not None and not kind.strip()

        date = raw_date.strftime(date_format) if raw_date is not None else None

        if invalid:
            self.assertRaises(ValueError, api.APIInput,
                              id_type, number, kind, country, date)
        else:
            # Assert no error.
            api_input = api.APIInput(id_type, number, kind, country, date)
            self.assertIsInstance(api_input, api.APIInput)

    @given(utils.valid_api_input_args())
    def test_to_id_produces_correct_output(self, args):

        id_type, number, kind, country, date = args
        api_input = api.APIInput(id_type, number, kind, country, date)

        if re.match(r'(\d+[.,/]\d+)+', number) and id_type != 'classification':
            number = '({})'.format(number)

        parts = map(str, [i for i in (country, number, kind, date)
                          if i is not None])
        if id_type == 'epodoc':
            expected = ''.join(parts)
        elif id_type == 'classification':
            expected = str(number)
        else:
            expected = '.'.join(parts)

        self.assertEqual(expected, api_input.to_id())

    @given(utils.APIInputs, st.text())
    def test_to_id_raises_ValueError_on_bad_type(self, api_input, new_type):
        assume(new_type not in api.VALID_IDTYPES)
        api_input.id_type = new_type
        self.assertRaises(ValueError, api_input.to_id)


class EPOClientTestCase(unittest.TestCase):

    def mock_auth(self, expires_in=10, succeed=True, token='token'):
        _mock = requests_mock.mock()
        _mock.post(api.AUTH_URL, status_code=200 if succeed else 401,
                   json={'access_token': token, 'expires_in': expires_in})

        return _mock


class TestEPOClientCreation(EPOClientTestCase):

    @given(utils.valid_epo_client_args(enable_cache=False))
    def test_creation_doesnt_raise(self, args):
        api.EPOClient.authenticate = mock.MagicMock()
        client = api.EPOClient(*args)
        self.assertIsInstance(client, api.EPOClient)

    @given(utils.valid_epo_client_args())
    def test_create_with_cache_calls_requests_cache(self, args):
        api.EPOClient.authenticate = mock.MagicMock()
        api.requests_cache.install_cache = mock.MagicMock()
        accept_type, key, secret, _, cache_kwargs = args
        cache = True

        api.EPOClient(accept_type, key, secret, cache, cache_kwargs)
        kwargs = cache_kwargs or dict()
        self.assertTrue(api.requests_cache.install_cache.called_with(**kwargs))

    @given(utils.valid_epo_client_args(enable_cache=False),
           st.text(min_size=1, alphabet=string.ascii_letters),
           st.text(min_size=1, alphabet=string.ascii_letters))
    def test_client_auto_auths_with_key_and_secret(self, args, key, secret):
        accept_type, _, _, cache, cache_kwargs = args
        api.EPOClient.authenticate = mock.MagicMock()
        client = api.EPOClient(accept_type, key, secret, cache, cache_kwargs)
        self.assertTrue(api.EPOClient.authenticate.called)


class TestEPOClientAuth(EPOClientTestCase):

    def setUp(self):
        self.__cache = api.requests_cache
        api.requests_cache = mock.MagicMock()

    def tearDown(self):
        api.requests_cache = self.__cache

    @given(args=utils.valid_epo_client_args(),
           key=st.text(min_size=1, alphabet=string.ascii_letters),
           secret=st.text(min_size=1, alphabet=string.ascii_letters))
    def test_returns_token_on_success(self, args, key, secret):
        accept_type, _, _, cache, cache_kwargs = args
        token_content = 'success'
        with self.mock_auth(succeed=True, token=token_content):
            client = api.EPOClient(accept_type, key, secret,
                                   cache, cache_kwargs)
            token = client.authenticate()
            self.assertIsInstance(token, api.Token)
            self.assertEqual(token.token, token_content)

    @given(args=utils.valid_epo_client_args())
    def test_returns_none_on_missing_creds(self, args):
        _, key, secret, _, _ = args
        assume(key is None or secret is None)
        with self.mock_auth(succeed=True):
            client = api.EPOClient(*args)
            token = client.authenticate()
            self.assertIsNone(token)

    @given(args=utils.valid_epo_client_args(),
           key=st.text(min_size=1, alphabet=string.ascii_letters),
           secret=st.text(min_size=1, alphabet=string.ascii_letters)
           )
    def test_raises_on_failed_auth(self, args, key, secret):
        accept_type, _, _, cache, cache_kwargs = args
        # Omit key and secret to prevent auto-auth.
        client = api.EPOClient(accept_type, None, None, cache, cache_kwargs)

        with self.mock_auth(succeed=False):
            client.key = key
            client.secret = secret
            self.assertRaises(requests.HTTPError, client.authenticate)