import re
from collections import namedtuple


class BaseEPOWrapper:
    """ Base class for wrappers around EPO entries.

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

    def __init__(self, xml, clean_tags=True):
        self.clean_tags = clean_tags
        self.xml = xml

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
        return self.clean_output(self.xml.find('abstract').text).strip()

    @property
    def bibliographic_data(self):
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
        return self.xml.find_next('text').text


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
        return self.xml.find_next('class').text

    @property
    def main_group(self):
        """ str : Patent classification main-group. """
        return self.xml.find_next('main-group').text

    @property
    def sub_group(self):
        """ str: Patent classification sub-group. """
        return self.xml.find_next('sub-group').text

    @property
    def classification_value(self):
        """ str: Value of classification. """
        return self.xml.find_next('classification-value').text

    @property
    def section(self):
        """ str: Patent classification section. """
        return self.xml.find_next('section').text


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
        return self.xml.find_next('country').text

    @property
    def doc_number(self):
        """ str: Document code. """
        return self.xml.find_next('doc-number').text

    @property
    def kind(self):
        """ str: Kind code. """
        return self.xml.find_next('kind').text


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