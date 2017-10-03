from __future__ import print_function

import contextlib
import functools
import os
import sys
import random
import re
import time
import subprocess

from lxml import etree
from lxml.cssselect import CSSSelector, SelectorSyntaxError, ExpressionError

try:
    from urllib.parse import urljoin
    from urllib.request import urlopen
except ImportError:
    from urlparse import urljoin
    from urllib import urlopen


try:
    unicode
except NameError:
    unicode = str


INLINE = 'inline'
LINK = 'link'

RE_FIND_MEDIA = re.compile('(@media.+?)(\{)', re.DOTALL | re.MULTILINE)
RE_NESTS = re.compile('@(-|keyframes).*?({)', re.DOTALL | re.M)
RE_CLASS_DEF = re.compile('\.([\w-]+)')
RE_SELECTOR_TAGS = re.compile('(^|\s)(\w+)')
RE_ID_DEF = re.compile('#([\w-]+)')
MOUSE_PSEUDO_CLASSES = re.compile(
    ':(link|hover|active|focus|visited)$', re.M | re.I
)
BEFOREAFTER_PSEUDO_CLASSES = re.compile(
    ':(before|after)$', re.M | re.I
)
VENDOR_PREFIXED_PSEUDO_CLASSES = re.compile(
    ':-(webkit|moz)-'
)

EXCEPTIONAL_SELECTORS = (
    'html',
)


DOWNLOAD_JS = os.path.join(
    os.path.dirname(__file__),
    'download.js'
)


class ParserError(Exception):

    """happens when we fail to parse the HTML."""


class DownloadError(Exception):

    """happens when we fail to down the URL."""


def _get_random_string():
    p = 'abcdefghijklmopqrstuvwxyz'
    pl = list(p)
    random.shuffle(pl)
    return ''.join(pl)


class Processor(object):

    def __init__(self,
                 debug=False,
                 preserve_remote_urls=True,
                 phantomjs=False,
                 phantomjs_options=None,
                 optimize_lookup=True):
        self.debug = debug
        self.preserve_remote_urls = preserve_remote_urls
        self.blocks = {}
        self.inlines = []
        self.links = []
        self._bodies = []
        self.optimize_lookup = optimize_lookup
        self._all_ids = set()
        self._all_classes = set()
        self._all_tags = set()
        self.phantomjs = phantomjs
        self.phantomjs_options = phantomjs_options
        self._downloaded = {}



    def readfile(self, url):
        if url in self._downloaded:
            return self._downloaded[url]
        try:
            with open(url, "rb") as response:
                content = response.read()
                content = unicode(content, 'utf-8')
                self._downloaded[url] = content
                return content
        except IOError:
            raise IOError(url)
        
        
    def download(self, url):
        if url in self._downloaded:
            return self._downloaded[url]
        try:
            with contextlib.closing(urlopen(url)) as response:
                if response.getcode() is not None:
                    if response.getcode() != 200:
                        raise DownloadError(
                            '%s -- %s ' % (url, response.getcode())
                        )
                content = response.read()
                content = unicode(content, get_charset(response))
                self._downloaded[url] = content
                return content
        except IOError:
            raise IOError(url)

    def download_with_phantomjs(self, url):
        if self.phantomjs is True:
            # otherwise, assume it's a path
            phantomjs = 'phantomjs'
        elif not os.path.isfile(self.phantomjs):
            raise IOError('%s is not a path to phantomjs' % self.phantomjs)
        else:
            phantomjs = self.phantomjs

        command = [phantomjs]
        if self.phantomjs_options:
            if 'load-images' not in self.phantomjs_options:
                # not entirely sure if this helps but there can't be any point
                # at all to download image for mincss
                self.phantomjs_options['load-images'] = 'no'
            for key, value in self.phantomjs_options.items():
                command.append('--%s=%s' % (key, value))

        command.append(DOWNLOAD_JS)
        assert ' ' not in url
        command.append(url)

        t0 = time.time()
        process = subprocess.Popen(
            ' '.join(command),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        out, err = process.communicate()
        t1 = time.time()
        if self.debug:
            print('Took', t1 - t0, 'seconds to download with PhantomJS')

        return unicode(out, 'utf-8')

    def process(self, *urls):
        for url in urls:
            
            #if "http://" in url or "https://" in url:
            self.process_url(url)

        for identifier in sorted(self.blocks.keys()):
            content = self.blocks[identifier]
            processed = self._process_content(content, self._bodies)

            if identifier[1] == INLINE:
                line, _, url, no_mincss = identifier
                if no_mincss:
                    processed = content
                self.inlines.append(
                    InlineResult(
                        line,
                        url,
                        content,
                        processed,
                    )
                )
            else:
                _, _, url, href, no_mincss = identifier
                if no_mincss:
                    processed = content
                self.links.append(
                    LinkResult(
                        href,
                        content,
                        processed
                    )
                )

    def process_url(self, url):
        if self.phantomjs:
            html = self.download_with_phantomjs(url)
        else:
            if "http://" in url and "https://" in url:
                html = self.download(url)
            else:
                html = self.readfile(url)
                
        self.process_html(html.strip(), url=url)

    def _find_all_ids_classes_and_tags(self, element):
        for each in element:
            identifier = each.attrib.get('id')
            if identifier:
                self._all_ids.add(identifier)
            classes = each.attrib.get('class')
            if classes:
                for class_ in classes.split():
                    self._all_classes.add(class_)

            self._all_tags.add(each.tag)

            # recurse!
            self._find_all_ids_classes_and_tags(each)

    def process_html(self, html, url):
        parser = etree.HTMLParser(encoding='utf-8')
        tree = etree.fromstring(html.encode('utf-8'), parser).getroottree()
        page = tree.getroot()

        if page is None:
            print(repr(html))
            raise ParserError('Could not parse the html')

        lines = html.splitlines()
        body, = CSSSelector('body')(page)
        self._bodies.append(body)
        if self.optimize_lookup:
            self._all_tags.add('body')
            self._find_all_ids_classes_and_tags(body)

        for style in CSSSelector('style')(page):
            try:
                first_line = style.text.strip().splitlines()[0]
            except IndexError:
                # meaning the inline style tag was just whitespace
                continue
            except AttributeError:
                # happend when the style tag has absolute nothing it
                # not even whitespace
                continue
            no_mincss = False
            try:
                data_attrib = style.attrib['data-mincss'].lower()
                if data_attrib == 'ignore':
                    continue
                elif data_attrib == 'no':
                    no_mincss = True

            except KeyError:
                # happens if the attribute key isn't there
                pass

            for i, line in enumerate(lines, start=1):
                if line.count(first_line):
                    key = (i, INLINE, url, no_mincss)
                    self.blocks[key] = style.text
                    break

        i = 0
        for link in CSSSelector('link')(page):
            if (
                link.attrib.get('rel', '') == 'stylesheet' or
                link.attrib['href'].lower().split('?')[0].endswith('.css')
            ):
                no_mincss = False
                try:
                    data_attrib = link.attrib['data-mincss'].lower()
                    if data_attrib == 'ignore':
                        continue
                    if data_attrib == 'no':
                        no_mincss = True
                except KeyError:
                    # happens if the attribute key isn't there
                    pass

                link_url = self.make_absolute_url(url, link.attrib['href'])
                key = (i, LINK, link_url, link.attrib['href'], no_mincss)
                i += 1
                self.blocks[key] = self.download(link_url)
                if self.preserve_remote_urls:
                    self.blocks[key] = self._rewrite_urls(
                        self.blocks[key],
                        link_url
                    )

    def _rewrite_urls(self, content, link_url):
        """Suppose you run mincss on www.example.org and it references:

            <link href="http://cdn.example.org">

        and in the CSS it references an image as:

            background: url(/foo.png)

        Then rewrite this to become:

            background: url(http://cdn.example.org/foo.png)

        """
        css_url_regex = re.compile('url\(([^\)]+)\)')

        def css_url_replacer(match, href=None):
            filename = match.groups()[0]
            bail = match.group()
            if (
                (filename.startswith('"') and filename.endswith('"')) or
                (filename.startswith("'") and filename.endswith("'"))
            ):
                filename = filename[1:-1]
            if 'data:image' in filename or '://' in filename:
                return bail
            if filename == '.':
                # this is a known IE hack in CSS
                return bail

            new_filename = urljoin(href, filename)
            return 'url("%s")' % new_filename

        content = css_url_regex.sub(
            functools.partial(css_url_replacer, href=link_url),
            content
        )
        return content

    def _process_content(self, content, bodies):
        # Find all of the unique media queries

        comments = []
        _css_comments = re.compile(r'/\*.*?\*/', re.MULTILINE | re.DOTALL)
        no_mincss_blocks = []

        def commentmatcher(match):
            whole = match.group()
            # are we in a block or outside
            nearest_close = content[:match.start()].rfind('}')
            nearest_open = content[:match.start()].rfind('{')
            next_close = content[match.end():].find('}')
            next_open = content[match.end():].find('{')

            outside = False
            if nearest_open == -1 and nearest_close == -1:
                # it's at the very beginning of the file
                outside = True
            elif next_open == -1 and next_close == -1:
                # it's at the very end of the file
                outside = True
            elif nearest_close == -1 and nearest_open > -1:
                outside = False
            elif nearest_close > -1 and nearest_open > -1:
                outside = nearest_close > nearest_open
            else:
                raise Exception('can this happen?!')

            if outside:
                temp_key = '@%scomment{}' % _get_random_string()
            else:
                temp_key = '%sinnercomment' % _get_random_string()
                if re.findall(r'\bno mincss\b', match.group()):
                    no_mincss_blocks.append(temp_key)

            comments.append(
                (temp_key, whole)
            )
            return temp_key

        content = _css_comments.sub(commentmatcher, content)
        if no_mincss_blocks:
            no_mincss_regex = re.compile(
                '|'.join(re.escape(x) for x in no_mincss_blocks)
            )
        else:
            no_mincss_regex = None

        nests = [(m.group(1), m) for m in RE_NESTS.finditer(content)]
        _nests = []
        for _, m in nests:
            __, whole = self._get_contents(m, content)
            _nests.append(whole)
        # once all nests have been spotted, temporarily replace them

        queries = [(m.group(1), m) for m in RE_FIND_MEDIA.finditer(content)]
        inner_improvements = []

        for nest in _nests:
            temp_key = '@%snest{}' % _get_random_string()
            inner_improvements.append(
                (temp_key, nest, nest)
            )

        # Consolidate the media queries
        for (query, m) in queries:
            inner, whole = self._get_contents(m, content)
            improved_inner = self._process_content(inner, bodies)
            if improved_inner.strip():
                improved = query.rstrip() + ' {' + improved_inner + '}'
            else:
                improved = ''
            temp_key = '@%s{}' % _get_random_string()
            inner_improvements.append(
                (temp_key, whole, improved)
            )

        for temp_key, old, __ in inner_improvements:
            assert old in content, old
            content = content.replace(old, temp_key, 1)

        _regex = re.compile('((.*?){(.*?)})', re.DOTALL | re.M)

        _already_found = set()
        _already_tried = set()

        def matcher(match):
            whole, selectors, bulk = match.groups()
            selectors = selectors.split('*/')[-1].lstrip()
            if selectors.strip().startswith('@'):
                return whole
            if no_mincss_regex and no_mincss_regex.findall(bulk):
                return no_mincss_regex.sub('', whole)

            improved = selectors
            perfect = True
            selectors_split = [
                x.strip() for x in
                selectors.split(',')
                if x.strip() and not x.strip().startswith(':')
            ]
            for selector in selectors_split:
                s = selector.strip()
                if s in EXCEPTIONAL_SELECTORS:
                    continue
                simplified = self._simplified_selector(s)

                if simplified.endswith('>'):
                    # Things like "foo.bar > :first-child" is valid,
                    # but once simplified you're left with
                    # "foo.bar >" which can never be found because
                    # it's an invalid selector. Best to avoid.
                    found = True
                elif simplified in _already_found:
                    found = True
                elif simplified in _already_tried:
                    found = False
                else:
                    found = self._found(bodies, simplified)

                if found:
                    _already_found.add(simplified)
                else:
                    _already_tried.add(simplified)
                    perfect = False
                    improved = re.sub(
                        '%s,?\s*' % re.escape(s),
                        '',
                        improved,
                        count=1
                    )

            if perfect:
                return whole
            if improved != selectors:
                if not improved.strip():
                    return ''
                else:
                    improved = re.sub(',\s*$', ' ', improved)
                    whole = whole.replace(selectors, improved)
            return whole

        fixed = _regex.sub(matcher, content)

        for temp_key, __, improved in inner_improvements:
            assert temp_key in fixed
            fixed = fixed.replace(temp_key, improved)
        for temp_key, whole in comments:
            # note, `temp_key` might not be in the `fixed` thing because the
            # comment could have been part of a selector that is entirely
            # removed
            fixed = fixed.replace(temp_key, whole)
        return fixed

    def _get_contents(self, match, original_content):
        # we are starting the character after the first opening brace
        open_braces = 1
        position = match.end()
        content = ''
        while open_braces > 0:
            c = original_content[position]
            if c == '{':
                open_braces += 1
            if c == '}':
                open_braces -= 1
            content += c
            position += 1
        return (
            content[:-1].strip(),
            # the last closing brace gets captured, drop it
            original_content[match.start():position]
        )

    def _found(self, bodies, selector):
        if self._all_ids:
            try:
                id_ = RE_ID_DEF.findall(selector)[0]
                if id_ not in self._all_ids:
                    # don't bother then
                    return False
            except IndexError:
                pass

        if self._all_classes:
            for class_ in RE_CLASS_DEF.findall(selector):
                if class_ not in self._all_classes:
                    # don't bother then
                    return False

        # If the last part of the selector is a tag like
        # ".foo blockquote" or "sometag" then we can look for it
        # in plain HTML as a form of optimization
        last_part = selector.split()[-1]
        # if self._all_tags and '"' not in selector:
        if not re.findall('[^\w \.]', selector):
            # It's a trivial selector. Like "tag.myclass",
            # or ".one.two". Let's look for some cheap wins
            if self._all_tags:
                # If the selector is quite simple, we can fish out
                # all tags mentioned in it and do a quick lookup using
                # simply the tag name.
                for prefix, tag in RE_SELECTOR_TAGS.findall(selector):
                    if tag not in self._all_tags:
                        # If the tag doesn't even exist in the HTML,
                        # don't bother.
                        return False

        return self._selector_query_found(bodies, selector)

    @staticmethod
    def _simplified_selector(selector):
        # If the select has something like :active or :hover,
        # then evaluate it as if it's without that pseudo class
        return selector.split(':')[0].strip()

    def _selector_query_found(self, bodies, selector):
        if '}' in selector:
            # XXX does this ever happen any more?
            return

        if selector.endswith('>'):
            # It's
            return False

        for body in bodies:
            try:
                for _ in CSSSelector(selector)(body):
                    return True
            except SelectorSyntaxError:
                print('TROUBLEMAKER', file=sys.stderr)
                print(repr(selector), file=sys.stderr)
                return True  # better be safe and let's keep it
            except ExpressionError:
                print('EXPRESSIONERROR', file=sys.stderr)
                print(repr(selector), file=sys.stderr)
                return True  # better be safe and let's keep it
        return False

    @staticmethod
    def make_absolute_url(url, href):
        return urljoin(url, href)


class _Result(object):

    def __init__(self, before, after):
        self.before = before
        self.after = after


class InlineResult(_Result):

    def __init__(self, line, url, *args):
        self.line = line
        self.url = url
        super(InlineResult, self).__init__(*args)


class LinkResult(_Result):

    def __init__(self, href, *args):
        self.href = href
        super(LinkResult, self).__init__(*args)


def get_charset(response, default='utf-8'):
    """Return encoding."""
    try:
        # Python 3.
        return response.info().get_param('charset', default)
    except AttributeError:
        # Python 2.
        content_type = response.headers['content-type']
        split_on = 'charset='
        if split_on in content_type:
            return content_type.split(split_on)[-1]
        else:
            return default
