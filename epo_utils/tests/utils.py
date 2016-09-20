"""
Util-function and Hypothesis builders.
"""
import string

import epo_utils.ops.constants
from hypothesis import strategies as st
from hypothesis.extra import datetime as hyp_datetime

from epo_utils.ops import api

_non_whitespace = string.printable.replace(string.whitespace, '')


def doc_numbers():
    parts = st.lists(st.integers(0), min_size=1)
    sep = st.sampled_from((',', '.', '/'))

    return st.builds(lambda s, p: s.join(map(str, p)), sep, parts)


def valid_api_input_args():
    """ Args-tuple builder for `epo_utils.ops.api.APIInput` """
    id_type = st.sampled_from(epo_utils.constants.VALID_IDTYPES)
    number = doc_numbers()
    kind = st.one_of(
        st.text(min_size=1, alphabet=_non_whitespace),
        st.none())
    country = st.one_of(st.text(alphabet=string.ascii_letters,
                                min_size=1, max_size=2), st.none())
    raw_date = st.one_of(hyp_datetime.datetimes(min_year=1900), st.none())

    def date_builder(raw):
        if raw is None:
            return raw
        else:
            return raw.strftime('%Y%m%d')

    date = st.builds(date_builder, raw_date)
    return st.tuples(id_type, number, kind, country, date)


def valid_epo_client_args(enable_cache=True, must_have_auth=False):
    """ Args-tuple builder for `epo_utils.ops.api.EPOClient` """
    data_type = st.sampled_from(
        ('xml', 'json', 'cpc+xml', 'fulltext+xml', 'exchange+xml',
         'ops+xml', 'cpc+xml', 'javascript'))
    stems = st.sampled_from(('application', ''))
    accept_type = st.builds(lambda stem, d_type: '/'.join((stem, d_type)),
                            stems, data_type)

    if must_have_auth:
        key = st.text(alphabet=string.ascii_letters, min_size=1)
        secret = st.text(alphabet=string.ascii_letters, min_size=1)
    else:
        key = st.one_of(st.none(),
                        st.text(alphabet=string.ascii_letters, min_size=1))
        secret = st.one_of(st.none(),
                           st.text(alphabet=string.ascii_letters, min_size=1))
    cache = st.booleans() if enable_cache else st.just(False)
    cache_kwargs = st.one_of(st.none(), st.dictionaries(st.text(), st.text()))
    return st.tuples(accept_type, key, secret, cache, cache_kwargs)


def build_variable_tuples(strategy, max_length=100):
    """ Build variable length tuples of strategy. """
    return st.builds(lambda n: tuple(strategy for i in range(n)),
                     st.integers(min_value=0, max_value=max_length))


APIInputs = st.builds(lambda args: api.APIInput(*args), valid_api_input_args())


Clients = st.builds(lambda args: api.EPOClient(*args), valid_epo_client_args())