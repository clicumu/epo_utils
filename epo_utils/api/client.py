import epo_ops
from epo_ops import middlewares
from epo_ops import models
from bs4 import BeautifulSoup
import enum
import requests
import requests_cache

from epo_utils.api.documents import ExchangeDocument, OPSPublicationReference


class ResourceNotFound(Exception):
    pass


class SearchFields(enum.Enum):
    """
    CQL search field identifiers accordint to:
    https://worldwide.espacenet.com/help?locale=en_EP&method=handleHelpTopic&topic=fieldidentifier
    """

    Inventor = 'in'
    Applicant = 'pa'
    Title = 'ti'
    Abstract = 'ab'
    PriorityNumber = 'pr'
    PublicationNumber = 'pn'
    ApplicationNumber = 'ap'
    PublicationDate = 'pd'
    CitedDocument = 'ct'
    CooperateivePatentClassification = 'cpc'
    InventorAndApplicant = 'ia'
    TitleAbstract = 'ta'
    TitleAbstractInventorApplicant = 'txt'
    ApplicationPublicationPriority = 'num'
    IPC = 'ipc'
    ICPCPC = 'cl'
    CQL = 'cql'


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
    cache : bool, optional
        If True, cache API-calls using `requests-cache`. Default False.
    cache_kwargs: dict, optional
        If provided, keyword arguments will be passed to
        `requests_cache.install_cache`
    **kwargs
        Keyword arguments passed to :class:`epo_ops.RegisteredClient`-
        constructor.
    """
    def __init__(self, key, secret, cache=False, cache_kwargs=None, **kwargs):
        if cache:
            requests_cache.install_cache(**(cache_kwargs or dict()))
        middleware = kwargs.pop('middlewares', [middlewares.Throttler()])
        self._client = epo_ops.RegisteredClient(
            key=key,
            secret=secret,
            middlewares=middleware,
            **kwargs
        )

    def get_publication(self, number, country_code=None, id_type=None,
                        kind_code=None, date=None, input_model=None, **kwargs):
        """ Retrieve publication and unfold response text into `dict`.

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
        input_model : type, optional
            Subclass of :class:`epo_ops.models.BaseInput`
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
        if input_model is not None:
            if not issubclass(input_model, models.BaseInput):
                raise ValueError('input_model must inherit'
                                 ' epo_ops.models.BaseInput')
            model = input_model(str(number), country_code, kind_code, date)

        elif not all([id_type, country_code]) or id_type == 'original':
            model = models.Original(str(number), country_code, kind_code, date)
        elif id_type == 'epodoc':
            model = models.Epodoc(str(number), kind_code, date)
        elif id_type == 'docdb':
            model = models.Docdb(str(number), country_code, kind_code, date)
        else:
            model = models.Docdb(str(number), country_code, kind_code, date)

        try:
            response = self._client.published_data(
                reference_type='publication',
                input=model, **kwargs
            )
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                # Raise separate error if nothing was found.
                raise ResourceNotFound(str(e))
            else:
                raise

        soup = BeautifulSoup(response.text, 'lxml')
        inner = soup.find('ops:world-patent-data')

        # No documents were fetched.
        if inner is None:
            return None, response

        docs_xml = inner.find_all('exchange-document')

        documents = dict()
        for doc in docs_xml:
            # '\nEP\n1000000\nA1\n20000517\n' => 'EP.1000000.A1.20000517'
            id_ = '.'.join(doc.find('document-id').text.strip().split())
            documents[id_] = ExchangeDocument(doc)

        return documents, response

    def search_published(self, field, query, range_begin=1, range_end=25):
        """ Search EPO `field` after `query`.

        If `field` is `SearchFields.CQL` `query` will be interpreted
        as a free form search string and executed as is.

        Parameters
        ----------
        field : SearchFields
            EPO-OPS search field.
        query : str
            Query-parameter of full query if  `field` is `SearchFields.CQL`.
        range_begin, range_end : int
            Specification of number of search results to receive.
            Results `range_begin` to `range_end` are retrieved.

        Returns
        -------
        list[OPSPublicationReference]
            Parsed references in search results.
        requests.Response
            Response object.
        """
        def search(query):
            return self._client.published_data_search(query, range_begin, range_end)

        # Perform search.
        if field == SearchFields.CQL:
            response = search(query)
        else:
            query_string = '{0}={1}'.format(field.value, query)
            response = search(query_string)

        # Parse results.
        soup = BeautifulSoup(response.text, 'lxml')
        results = [OPSPublicationReference(tag)
                   for tag in soup.find_all('ops:publication-reference')]

        return results, response
