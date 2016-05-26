import re


class ExchangeDocument:
    """
    Wrapper class around a EPO-OPS exchange document.

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
    def __init__(self, xml, clean_tags=True):
        self.clean_tags = clean_tags

        self._xml = xml

    @property
    def abstract(self):
        """ str: Document abstract."""
        return self._clean_tags(self._xml.find('abstract').text).strip()

    def _clean_tags(self, text):
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


