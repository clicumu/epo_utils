# -*- coding: utf-8 -*-
""" This module contain wrapper classes for EPO patent documents. """
import re
from collections import namedtuple


class BaseEPOWrapper:
    """ Base class for wrappers around EPO entries.

    Caches all `property`-attributes in memory automatically.

    Parameters
    ----------
    xml : bs4.element.Tag
        Documents tag-entry.
    clean_tags : bool
        If True, text bodies are cleaned from <tag>:s.

    Attributes
    ----------
    clean_tags : bool
    """
    _id = None
    """ str, optional : Name of ID-attribute """

    def __init__(self, xml, clean_tags=True):
        self.clean_tags = clean_tags
        self.xml = xml
        self.language_code = 'en'

        self.__cache = dict()

    def clean_output(self, text):
        """ If `self.clean_tags` is True, remove markup tags
        using regexp.

        Parameters
        ----------
        text : str
            Input text.

        Returns
        -------
        str
        """
        if self.clean_tags:
            return re.sub(r'<.*>', '', text)
        else:
            return text

    @property
    def id(self):
        try:
            id_ = getattr(self, self._id)
        except TypeError:
            id_ = None

        return id_

    def __getattribute__(self, item):
        if isinstance(getattr(type(self), item, None), property):
            cache_key = '_{}'.format(item)
            try:
                # Try to fetch from cache.
                value = self.__cache[cache_key]
            except KeyError:
                # Else, parse results and substitute ugly unicode-spaces
                # if value is a string.
                value = super(BaseEPOWrapper, self).__getattribute__(item)
                if isinstance(value, str):
                    value = re.sub(r'\s+', ' ', value)
                self.__cache[cache_key] = value
        else:
            value = super(BaseEPOWrapper, self).__getattribute__(item)

        return value

    def __str__(self):
        if self.__class__._id is None:
            return super(BaseEPOWrapper, self).__str__()
        else:
            attr = self.__getattribute__(self._id)
            class_name = self.__class__.__name__
            return '<{0}: {1}>'.format(class_name, attr)

    def __repr__(self):
        if self.__class__._id is None:
            return super(BaseEPOWrapper, self).__repr__()
        else:
            attr = self.__getattribute__(self._id)
            module = self.__class__.__module__
            class_name = self.__class__.__name__
            return '<{0}.{1}: {2}>'.format(module, class_name, attr)


class ExchangeDocument(BaseEPOWrapper):

    _id = 'full_id'

    @property
    def full_id(self):
        """ str : Rendered ID. """
        return self.country + self.doc_number + self.kind

    @property
    def system(self):
        """ str : Document system. """
        return self.xml['system']

    @property
    def family_id(self):
        """ str : Patent family. """
        return self.xml['family-id']

    @property
    def country(self):
        """ str : Country code. """
        return self.xml['country']

    @property
    def doc_number(self):
        """ str : Doc-number string. """
        return self.xml['doc-number']

    @property
    def kind(self):
        """ str : Patent kind code. """
        return self.xml['kind']

    @property
    def publication_reference(self):
        """ list[DocumentID] : Patent publication reference in
        different formats.
        """
        pub_ref = self.xml.findChild('publication-reference')
        return [DocumentID(tag) for tag in pub_ref.find_all('document-id')]

    @property
    def classifications(self):
        """ dict[str, list[str]] : Classification system as keys and list
        of classification codes as values.
        """
        classifications = dict()
        ipc = self.xml.findChild('classification-ipc')
        if ipc is not None:
            classifications['IPC'] = [tag.text for tag in ipc.find_all('text')]

        ipcr = self.xml.findChild('classifications-ipcr')
        if ipcr is not None:
            classifications['IPCR'] = [' '.join(tag.text.split())
                                       for tag in ipcr.find_all('text')]

        others = self.xml.findChild(
            'patent-classifications'
        ).find_all('patent-classification')
        if others is not None:
            cpc_classes = list()
            for other in others:
                cpc_class = '{}{}{}{}{}/{} {}'.format(
                    *[c.text for c in other.children if hasattr(c, 'text')])
                cpc_classes.append(cpc_class)

            classifications['CPC'] = cpc_classes

        return classifications

    @property
    def application_reference(self):
        """ ApplicationReference : Patent application reference. """
        app_ref = self.xml.findChild('application-reference')
        return ApplicationReference(app_ref) if app_ref is not None else None

    @property
    def priority_claims(self):
        """ list[PriorityClaim] : Patent priority claims."""
        return [PriorityClaim(tag) for tag in self.xml.find_all('priority-claim')]

    @property
    def applicants(self):
        """ list[Party] : Applicants ordered according to patent sequence. """
        try:
            return self._find_parties('applicants', 'applicant')
        except AttributeError:  # Applicants missing.
            return []

    @property
    def inventors(self):
        """ list[Party] : Inventors ordered according to patent sequence """
        try:
            return self._find_parties('inventors', 'inventor')
        except AttributeError:  # Inventors missing.
            return []

    @property
    def title(self):
        """ dict[str, str] : Language code - title."""
        return {tag['lang']: re.sub(r'\s', ' ', tag.text.strip())
                for tag in self.xml.find_all('invention-title')}

    @property
    def citations(self):
        """ list[Citation] : Citations ordered according to patent sequence. """
        citation_tags = self.xml.findChild(
            'references-cited').find_all('citation')
        citations = list()

        for tag in citation_tags:
            if tag.findChild('patcit') is not None:
                citation = PatentCitation(tag)
            else:
                citation = NonPatentCitation(tag)
            citations.append(citation)

        return citations

    @property
    def abstract(self):
        """ dict[str, str] : Language code, abstract pairs."""
        return {tag['lang']: self.clean_output(tag.text.strip())
                for tag in self.xml.find_all('abstract')}

    def _find_parties(self, root, sub):
        """ Parse exchange-documents parties-tags.

        Parameters
        ----------
        root : str
            Base-tag.
        sub : str
            Sub element-tag.

        Returns
        -------
        list[Party]
        """
        names = dict()
        epodocs = dict()
        for tag in self.xml.find(root).find_all(sub):
            name = re.sub(r'\s', ' ', tag.findChild('name').text).strip()
            seq = tag['sequence']
            if tag['data-format'] == 'original':
                names[seq] = name if name[-1] != ',' else name[:-1]
            else:
                epodocs[seq] = name

        return [Party(names[key], epodocs.get(key, None))
                for key in sorted(names.keys())]


class FullTextDocument(BaseEPOWrapper):

    """ Wrapper around `ftxt:fulltext-document`-tag. """
    _id = 'full_id'

    @property
    def full_id(self):
        return self.publication_reference.full_id

    @property
    def publication_reference(self):
        """ PublicationReference: Patent reference."""
        return PublicationReference(self.xml.findChild('publication-reference'))

    @property
    def description(self):
        """ str: `description-tag`"""
        all_descriptions = self.xml.find_all('description')

        if not all_descriptions:
            return None

        description = next(
            (desc for desc in all_descriptions
             if desc.get('lang', '').lower() == self.language_code),
            all_descriptions[0]
        )
        return self.clean_output(description.text)

    @property
    def claims(self):
        """ list[str]: Patent claims. """
        all_claims = self.xml.find_all('claims')
        if not all_claims:
            return None

        right_language = (tag for tag in all_claims if
                          tag['lang'].lower() == self.language_code)
        claims = next(right_language, all_claims[0])
        return [claim.text for claim in claims.find_all('claim-text')]


class FullTextInquiry(BaseEPOWrapper):

    """ Wraps `ops:fulltext-inquiry`-tags. """

    _id = 'doc_number'

    @property
    def doc_number(self):
        """ str: Publication document number. """
        return self.ops_publication_reference.doc_number

    @property
    def ops_publication_reference(self):
        """ OPSPublicationReference: `ops:publication-reference`-tag. """
        tag = self.xml.findChild('ops:publication-reference')
        return OPSPublicationReference(tag)

    @property
    def document_id(self):
        """ OPSPublicationReference: `ops:publication-reference`-tag. """
        tag = self.xml.findChild('document-id')
        return DocumentID(tag)

    @property
    def full_text_instances(self):
        """ list[namedtuple]: `ops:fulltext-instance`-tags. """
        instance_tags = self.xml.find_all('ops:fulltext-instance')
        instance_tag = namedtuple('InstanceTag', ['desc', 'format'])
        instances = list()
        for tag in instance_tags:
            instances.append(instance_tag(
                tag['desc'],
                tag.findChild('ops:fulltext-format').text
            ))
        return instances


class DocumentID(BaseEPOWrapper):
    """
    Wrapper around `document-id`-tag.
    """
    _id = 'full_id'

    @property
    def full_id(self):
        return ''.join(filter(None, [self.country, self.doc_number, self.kind]))

    @property
    def id_type(self):
        """ str: `document-id-type`-attribute. """
        return self.xml['document-id-type']

    @property
    def country(self):
        """ str: Country code. """
        try:
            return self.xml.findChild('country').text.strip()
        except AttributeError:
            return None

    @property
    def doc_number(self):
        """ str: Document code. """
        try:
            return self.xml.findChild('doc-number').text.strip()
        except AttributeError:
            return None

    @property
    def kind(self):
        """ str: Kind code. """
        try:
            return self.xml.findChild('kind').text.strip()
        except AttributeError:
            return None

    @property
    def date(self):
        try:
            return self.xml.findChild('date').text.strip()
        except AttributeError:
            return None


class InquiryResult(DocumentID):

    def __init__(self, xml, **kwargs):
        super(InquiryResult, self).__init__(xml.findChild('document-id'),
                                            **kwargs)
        doc_number = super(InquiryResult, self).doc_number
        if doc_number[:2].isalpha():
            self._country = doc_number[:2]
            self._doc_number = doc_number[2:]
        else:
            self._country = super(InquiryResult, self).country
            self._doc_number = doc_number

    @property
    def country(self):
        """ str: Country code. """
        return self._country

    @property
    def doc_number(self):
        """ str: Document number. """
        return self._doc_number


class OPSPublicationReference(DocumentID):
    """
    Wrapper class around EPO publication reference
    (`ops:publication-reference`-tags.)

    Flattens out `document-id`-tag.
    """
    @property
    def id_type(self):
        """ str: `document-id-type`-attribute. """
        return self.xml.findChild('document-id')['document-id-type']


class PublicationReference(DocumentID):

    """ Wraps `publication-reference`-tag. """

    @property
    def id_type(self):
        """ str: ID-type. """
        return self.xml['data-format']


class ApplicationReference(BaseEPOWrapper):
    """
    Wrapper around `application-reference`-tag.
    """
    _id = 'doc_id'

    @property
    def doc_id(self):
        """ str : Patent RID. """
        return self.xml['doc-id']

    @property
    def document_ids(self):
        """ list[DocumentID] : Document ID:s in different formats. """
        return [DocumentID(tag) for tag in self.xml.find_all('document-id')]


class PriorityClaim(BaseEPOWrapper):
    """
    Wrapper around `priority-claim`-tag.
    """
    _id = 'sequence'

    @property
    def sequence(self):
        """ str: claim `sequence`-attribute."""
        return self.xml['sequence']

    @property
    def kind(self):
        """ str: claim `kind`-attribute. """
        return self.xml['kind']

    @property
    def document_ids(self):
        """ list[DocumentID] : Claim document-ids. """
        return [DocumentID(tag) for tag in self.xml.find_all('document-id')]


class Citation(BaseEPOWrapper):
    """
    Wraps `citation`-tag.
    """
    @property
    def cited_phase(self):
        """ str : Citation phase. """
        return self.xml['cited-phase']

    @property
    def cited_by(self):
        """ str : Who cited the document during the citation phase. """
        return self.xml['cited-by']

    @property
    def category(self):
        """ str : Citation category-code."""
        return self.xml.findChild('category').text
    
    @property
    def office(self):
        """ str, None : citation office."""
        try:
            office = self.xml['office']
        except KeyError:
            office = None
        return office


class PatentCitation(Citation):
    """
    Wraps a `citation` with `patcit`-child.
    """
    _id = 'num'

    @property
    def num_type(self):
        """ str : """
        return self.xml.findChild('patcit')['dnum-type']

    @property
    def num(self):
        """ int : `patcit`:s `num`-attribute. """
        return int(self.xml.findChild('patcit')['num'])

    @property
    def document_ids(self):
        """ list[DocumentID] : ID:s ordered according to patent order. """
        return [DocumentID(tag) for tag in self.xml.find_all('document-id')]


class NonPatentCitation(Citation):
    """
    Wraps a `citation` with `nlpcit`-child.
    """
    _id = 'num'

    @property
    def num(self):
        """ int : `patcit`:s `num`-attribute. """
        return int(self.xml.findChild('nplcit')['num'])

    @property
    def text(self):
        return self.xml.findChild('text').text


class Party:
    """
    Applicant or inventor.

    Parameters
    ----------
    name : str
        Name in `original`-format.
    epodic : str
        Name in `epodoc`-format.
    """
    def __init__(self, name, epodoc):
        self.name = name
        self.epodoc = epodoc

    def __repr__(self):
        return '<{}.{}: {}>'.format(self.__class__.__module__,
                                    self.__class__.__name__, self.name)
