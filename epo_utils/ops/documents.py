# -*- coding: utf-8 -*-
""" This module contain wrapper classes for EPO patent documents. """
import re
import unicodedata


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

        chars = (chr(i) for i in range(0x110000))
        space_chars = (c for c in chars if unicodedata.category(c) == 'Zs')
        self.__space_re = re.compile(r'[%s]' % re.escape(''.join(space_chars)))
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
                    value = re.sub(self.__space_re, ' ', value)
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
    """
    Wrapper class around a EPO-OPS exchange document.
    """

    _id = 'doc_number'

    @property
    def doc_number(self):
        """ str: Document number. """
        return self.xml['doc-number']

    @property
    def family_id(self):
        """ str: `family-id` attribute. """
        return self.xml.get('family-id', None)

    @property
    def system(self):
        """ str: `system`-attribute. """
        return self.xml.get('system', None)

    @property
    def country(self):
        """ str: Country code. """
        return self.xml.get('country', None)

    @property
    def kind(self):
        """ str: Document kind. """
        return self.xml['kind']

    @property
    def abstract(self):
        """ str: Document abstract."""
        abstracts = self.xml.find_all('abstract')

        if not abstracts:
            return ''

        for abstract in abstracts:
            try:
                lang = abstract['lang']
            except KeyError:
                continue
            else:
                # Return if language is desired language.
                if lang == self.language_code:
                    return self.clean_output(abstract.text).strip()

        # If no matching language was found, return first abstract found.
        return self.clean_output(abstracts[0].text).strip()

    @property
    def bibliographic_data(self):
        """ dict: Bibliographic information.
        `{"bibliographic-data": list[OPSPublicationReference]
        "classification-ipcr": list[ClassificationIPCR]}`
        """
        bib = self.xml.find('bibliographic-data')
        pub_refs = [OPSPublicationReference(tag)
                    for tag in bib.find_all('publication-reference')]
        ipcr = [ClassificationIPCR(tag)
                for tag in bib.find_all('classification-ipcr')]

        return {
            'publication-reference': pub_refs,
            'classification-ipcr': ipcr
        }

    @property
    def application_reference(self):
        """ ApplicationReference: Documents `application-reference`"""
        return ApplicationReference(self.xml.find_next('application-reference'))

    @property
    def priority_claims(self):
        """ list[PriorityClaim]: Patent priority claims. """
        return [PriorityClaim(tag) for tag in self.xml.find_all('priority-claim')]

    @property
    def applicants(self):
        """ list[Applicant]: Patent applicants."""
        return [Applicant(tag) for tag in self.xml.find_all('applicant')]

    @property
    def inventors(self):
        """ list[Inventor]: Patent inventors."""
        return [Inventor(tag) for tag in self.xml.find_all('inventor')]


class ClassificationIPCR(BaseEPOWrapper):

    """
    Wrapper around `classification-ipcr`-tag.
    """
    _id = 'sequence'

    @property
    def sequence(self):
        """ str: Sequence. """
        return self.xml['sequence']

    @property
    def text(self):
        """ str: IPCR text content. """
        try:
            return self.xml.find_next('text').text
        except AttributeError:
            return None


class PatentClassification(BaseEPOWrapper):
    """
    Wrapper around `patent-classfication`.
    """
    _id = 'sequence'

    @property
    def sequence(self):
        return self.xml['sequence']

    @property
    def classification_scheme(self):
        """ list[dict] : Schemes with office and scheme-id of classification."""
        schemes = self.xml.find_all('classification-scheme')
        return [{'office': scheme['office'], 'scheme': scheme['scheme']}
                for scheme in schemes]

    @property
    def klass(self):
        """ str: Class."""
        try:
            return self.xml.find_next('class').text
        except AttributeError:
            return None

    @property
    def main_group(self):
        """ str : Patent classification main-group. """
        try:
            return self.xml.find_next('main-group').text
        except AttributeError:
            return None

    @property
    def sub_group(self):
        """ str: Patent classification sub-group. """
        try:
            return self.xml.find_next('sub-group').text
        except AttributeError:
            return None

    @property
    def classification_value(self):
        """ str: Value of classification. """
        try:
            return self.xml.find_next('classification-value').text
        except AttributeError:
            return None

    @property
    def section(self):
        """ str: Patent classification section. """
        try:
            return self.xml.find_next('section').text
        except AttributeError:
            return None


class DocumentID(BaseEPOWrapper):
    """
    Wrapper around `document-id`-tag.
    """
    _id = 'doc_number'

    @property
    def id_type(self):
        """ str: `document-id-type`-attribute. """
        return self.xml['document-id-type']

    @property
    def country(self):
        """ str: Country code. """
        try:
            return self.xml.find_next('country').text
        except AttributeError:
            return None

    @property
    def doc_number(self):
        """ str: Document code. """
        try:
            return self.xml.find_next('doc-number').text
        except AttributeError:
            return None

    @property
    def kind(self):
        """ str: Kind code. """
        try:
            return self.xml.find_next('kind').text
        except AttributeError:
            return None

    @property
    def date(self):
        try:
            return self.xml.find_next('date').text
        except AttributeError:
            return None


class OPSPublicationReference(DocumentID):
    """
    Wrapper class around EPO publication reference
    (`ops:publication-reference`-tags.)

    Flattens out `document-id`-tag.
    """
    @property
    def id_type(self):
        """ str: `document-id-type`-attribute. """
        return self.xml.find_next('document-id')['document-id-type']


class ApplicationReference(BaseEPOWrapper):
    """
    Wrapper around `application-reference`-tag.
    """
    _id = 'doc_id'

    @property
    def doc_id(self):
        """ str: `doc-id`-attribute. """
        return self.xml['doc-id']

    def document_ids(self):
        """ list[DocumentID] : Application-reference's `document-id`-tags. """
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


class Applicant(BaseEPOWrapper):
    """
    Wrapper around `applicant`-tag.
    """
    _id = 'name'

    @property
    def name(self):
        """ str: Applicant name. """
        try:
            return self.xml.find_next('name').text.strip()
        except AttributeError:
            return ''

    @property
    def data_format(self):
        """ str: `data-format`-attribute. """
        return self.xml['data-format']

    @property
    def sequence(self):
        """ str: `sequence`-attribute. """
        return self.xml['sequence']


class Inventor(Applicant):
    """
    Wrapper around `inventor`-tag.
    """