import sys
import re

from HTMLParser import HTMLParser
from wburlrewriter import ArchivalUrlRewriter



# create a subclass and override the handler methods
class WBHtml(HTMLParser):
    """
    >>> WBHtml(rewriter).feed('<HTML><A Href="page.html">Text</a></hTmL>')
    <HTML><a href="/web/20131226101010/http://example.com/some/path/page.html">Text</a></html>

    >>> WBHtml(rewriter).feed('<body x="y"><img src="../img.gif"/><br/></body>')
    <body x="y"><img src="/web/20131226101010im_/http://example.com/some/img.gif"/><br/></body>

    >>> WBHtml(rewriter).feed('<body x="y"><img src="/img.gif"/><br/></body>')
    <body x="y"><img src="/web/20131226101010im_/http://example.com/img.gif"/><br/></body>

    >>> WBHtml(rewriter).feed('<META http-equiv="refresh" content="10; URL=/abc/def.html">')
    <meta http-equiv="refresh" content="10; URL=/web/20131226101010/http://example.com/abc/def.html">
    """

    REWRITE_TAGS = {
        'a':       {'href': ''},
        'applet':  {'codebase': 'oe_',
                    'archive': 'oe_'},
        'area':    {'href': ''},
        'base':    {'href': ''},
        'blockquote': {'cite': ''},
        'body':    {'background': 'im_'},
        'del':     {'cite': ''},
        'embed':   {'src': 'oe_'},
        'iframe':  {'src': 'if_'},
        'img':     {'src': 'im_'},
        'ins':     {'cite': ''},
        'input':   {'src': 'im_'},
        'form':    {'action': ''},
        'frame':   {'src': 'fr_'},
        'link':    {'href': 'oe_'},
        'meta':    {'content': ''},
        'object':  {'codebase': 'oe_',
                    'data': 'oe_'},
        'q':       {'cite': ''},
        'script':  {'src': 'js_'},
        'div':     {'data-src' : '',
                    'data-uri' : ''},
        'li':      {'data-src' : '',
                    'data-uri' : ''},
    }

    STATE_TAGS = ['head', 'body', 'script', 'style']


    def __init__(self, rewriter, outstream = None):
        HTMLParser.__init__(self)

        self.rewriter = rewriter
        self._wbParseContext = None
        self.out = outstream if outstream else sys.stdout


    # ===========================
    META_REFRESH_REGEX = re.compile('^[\\d.]+\\s*;\\s*url\\s*=\\s*(.+?)\\s*$', re.IGNORECASE | re.MULTILINE)

    def _rewriteMetaRefresh(self, metaRefresh):
        m = WBHtml.META_REFRESH_REGEX.match(metaRefresh)
        if not m:
            return metaRefresh

        try:
            metaRefresh = metaRefresh[:m.start(1)] + self._rewriteURL(m.group(1)) + metaRefresh[m.end(1):]
        except Exception:
            pass

        return metaRefresh
    # ===========================

    NO_REWRITE_PREFIX = ['javascript:', 'data:', 'mailto:']

    def _rewriteURL(self, value, mod = None):
        if any (value.startswith(x) for x in WBHtml.NO_REWRITE_PREFIX):
            return value

        return self.rewriter.rewrite(value, mod)


    def _rewriteCSS(self, cssContent):
        return cssContent

    def _rewriteScript(self, scriptContent):
        return scriptContent

    def hasAttr(self, tagAttrs, attr):
        name, value = attr
        for attrName, attrValue in tagAttrs:
            if attrName == name:
                return value.lower() == attrValue.lower()
        return False

    def rewriteTagAttrs(self, tag, tagAttrs, isStartEnd):
        handler = WBHtml.REWRITE_TAGS.get(tag)
        if not handler:
            handler = WBHtml.REWRITE_TAGS.get('')

        if not handler:
            return False

        # special case: base tag
        if (tag == 'base'):
            newBase = tagAttrs.get('href')
            if newBase:
                self.rewriter.setBaseUrl(newBase[1])

        # special case: script or style parse context
        elif ((tag == 'script') or (tag == 'style')) and (self._wbParseContext == None):
            self._wbParseContext = tag

        self.out.write('<' + tag)

        for attr in tagAttrs:
            attrName, attrValue = attr

            # special case: inline JS/event handler
            if attrValue.startswith('javascript:') or attrName.startswith("on"):
                attrValue = self._rewriteScript(attrValue)

            # special case: inline CSS/style attribute
            elif attrName == 'style':
                attrValue = self._rewriteCSS(attrValue)

            # special case: meta tag
            elif (tag == 'meta') and (attrName == 'content') and self.hasAttr(tagAttrs, ('http-equiv', 'refresh')):
                attrValue = self._rewriteMetaRefresh(attrValue)

            else:
                rwMod = handler.get(attrName)
                if rwMod is not None:
                    attrValue = self._rewriteURL(attrValue, rwMod)

            self.out.write(' {0}="{1}"'.format(attrName, attrValue))

        self.out.write('/>' if isStartEnd else '>')

        return True

    def handle_starttag(self, tag, attrs):
        if not self.rewriteTagAttrs(tag, attrs, False):
            self.out.write(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        if not self.rewriteTagAttrs(tag, attrs, True):
            self.out.write(self.get_starttag_text())

    def handle_endtag(self, tag):
        if (tag == self._wbParseContext):
            self._wbParseContext = None

        self.out.write('</' + tag + '>')

    def parseData(self, data):
        if self._wbParseContext == 'script':
            data = self._rewriteScript(data)
        elif self._wbParseContext == 'style':
            data = self._rewriteCSS(data)

        self.out.write(data)

    def handle_data(self, data):
        self.parseData(data)

    def handle_entityref(self, data):
        self.out.write('&' + data)

    def handle_charref(self, data):
        self.out.write('&#' + data)

    def handle_comment(self, data):
        self.out.write('<!--')
        self.parseData(data)
        self.out.write('-->')

    def handle_decl(self, data):
        self.out.write('<!' + data + '>')

    def handle_pi(self, data):
        self.out.write('<?' + data + '>')

    def unknown_decl(self, data):
        self.out.write('<![')
        self.parseData(data)
        self.out.write(']>')


# instantiate the parser and fed it some HTML
#parser = WBHtml()
#instr = '<HTML X=\'a\' B=\'234\' some="other"><a href="Test"><BR/><head><title>Test</title></head>\n<body><h1>Parse me!</h1></body></HTML>'
#print instr
#print
#parser.feed(instr)
#print
if __name__ == "__main__":
    import doctest

    rewriter = ArchivalUrlRewriter('/20131226101010/http://example.com/some/path/index.html', '/web/')

    doctest.testmod()