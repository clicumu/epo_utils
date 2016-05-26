import epo_ops
from epo_ops import middlewares
from epo_ops import models
from bs4 import BeautifulSoup

from epo_utils.api import documents


class EPOClient:
    """ A higher level wrapper of :class:`epo_ops.RegisteredClient`.

    Default middlewares used:

    * :class:`epo_ops.middlewares.Throttler`

    Parameters
    ----------
    key : str
        Client key.
    secret : str
        Client secret
    **kwargs
        Keyword arguments passed to :class:`epo_ops.RegisteredClient`-
        constructor.
    """
    def __init__(self, key, secret, **kwargs):
        middleware = kwargs.pop('middlewares', None) or [middlewares.Throttler()]
        self._client = epo_ops.RegisteredClient(
            key=key,
            secret=secret,
            middlewares=middleware,
            **kwargs
        )

    def get_publication(self, number, country_code=None,
                        kind_code=None, date=None, **kwargs):
        """ Retrieve publication and unfold response text into `dict`.

        Returns contents inside top-level `"ops:world-patent-data"`-tag.

        Parameters
        ----------
        number : str, int
            Publication number.
        country_code : str, optional
            Publication country code.
        kind_code : str, optional
            Pubication kind.
        date : str, optional
            YYYYMMDD-date.
        **kwargs
            Keyword arguments passed to
            :meth:`epo_ops.RegisteredClient.published_data`.
        Returns
        -------
        documents : dict[str, ExchangeDocument]
            Documents in response.
        response : requests.Response
            Response-object.
        """
        if not all([country_code, kind_code]):
            model = models.Original(str(number), country_code, kind_code, date)
        else:
            model = models.Docdb(str(number), country_code, kind_code, date)

        response = self._client.published_data(
            reference_type='publication',
            input=model, **kwargs
        )
        soup = BeautifulSoup(response.text, 'lxml')
        inner = soup.find('ops:world-patent-data')

        if inner is None:
            return None, response

        docs_xml = inner.find_all('exchange-document')

        documents = dict()
        for doc in docs_xml:
            # '\nEP\n1000000\nA1\n20000517\n' => 'EP.1000000.A1.20000517'
            id_ = '.'.join(doc.find('document-id').text.strip().split())
            documents[id_] = documents.ExchangeDocument(doc)

        return documents, response