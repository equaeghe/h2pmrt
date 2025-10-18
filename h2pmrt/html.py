from typing_extensions import Dict
import bs4
import re


BLOCKS = {
    "address", "article", "aside",
    "blockquote",
    "canvas",
    "dd", "div", "dl", "dt",
    "fieldset", "figcaption", "figure", "footer", "form",
    "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr",
    "li",
    "main",
    "nav", "noscript",
    "ol",
    "p", "pre",
    "section",
    "table", "tbody", "tfoot", "thead",
    "ul",
    "video"
}


def sweat_whitespace(soup: bs4.BeautifulSoup):
    """Iteratively move trimmable whitespace outside of tags"""
    SWEATABLE = {"a", "b", "strong", "i", "em", "u", "s"}
    sweating = True
    while sweating:
        sweating = False
        for string in soup(string=True):
            parent = string.parent
            if isinstance(parent, bs4.Tag) and parent.name in SWEATABLE:
                # Strip
                unstripped = str(string)
                strippable = unstripped
                # Add left
                lws = unstripped[:len(unstripped)-len(unstripped.lstrip())]
                if lws and not string.previous_sibling:
                    lws = bs4.NavigableString(lws)
                    parent.insert_before(lws)
                    strippable = strippable.lstrip()
                    sweating = True
                # Add right
                rws = unstripped[len(unstripped.rstrip()):]
                if rws and not string.next_sibling:
                    rws = bs4.NavigableString(rws)
                    parent.insert_after(rws)
                    strippable = strippable.rstrip()
                    sweating = True
                # Add properly stripped back
                string.replace_with(strippable)


def linebreak_blocks(soup: bs4.BeautifulSoup):
    """Add a linebreak between sibling block-like elements"""
    parents = set()
    for tag in soup(BLOCKS):
        parents.add(tag.parent)
    for parent in parents:
        for whitespace in parent(string=re.compile(" *"), recursive=False):
            whitespace.decompose()
        siblings = list(parent.children)
        siblings.pop()
        for sibling in siblings:
            linebreak = bs4.NavigableString("\n")
            sibling.insert_after(linebreak)


def unwrap_spans(soup: bs4.BeautifulSoup):
    """Unwrap all span-like tags"""
    SPAN_LIKE = {"span", "font"}
    for tag in soup(SPAN_LIKE):
        assert isinstance(tag, bs4.Tag)
        tag.unwrap()


def unwrap_msoffice_tags(soup: bs4.BeautifulSoup):
    """Unwrap all MS Office-specific tags"""
    for tag in soup(re.compile("^o:")):
        assert isinstance(tag, bs4.Tag)
        tag.unwrap()


def direct_unwraps(soup: bs4.BeautifulSoup):
    """Unwrap some classes of tags directly"""
    unwrap_spans(soup)
    unwrap_msoffice_tags(soup)


def remove_empty(soup: bs4.BeautifulSoup):
    """Iteratively remove empty tags"""
    VOIDS = {"br", "hr", "img", "col"}
    maybe_some_empty_still = True
    while maybe_some_empty_still:
        maybe_some_empty_still = False
        for tag in soup.find_all(lambda tag: tag.name not in VOIDS,
                                 string=None):
            assert isinstance(tag, bs4.Tag)
            if list(tag.children) == []:
                tag.decompose()
                maybe_some_empty_still = True # decompose may create empty tags


def merge_markup(soup: bs4.BeautifulSoup):
    """Merge adjacent markup tags"""
    MERGEABLE = {"b", "strong", "i", "em"}
    soup.smooth()  # make sure there are no adjacent NavigableStrings
    for tag_name in MERGEABLE:
        # Group by parent
        sibling_map = dict()
        for tag in soup(tag_name):
            parent = tag.parent
            if parent not in sibling_map:
                sibling_map[parent] = [tag]
            else:
                sibling_map[parent].append(tag)
        # Go over all parents and discover mergeable tags
        for parent, siblings in sibling_map.items():
            siblings.reverse()  # to pop off left to right
            while len(siblings) >= 2:
                tag = siblings.pop()
                mergeable_tags = []
                next_tag = tag.next_sibling
                assert next_tag is not None
                if (isinstance(next_tag, bs4.NavigableString)
                    and str(next_tag).isspace()):
                    # deal with whitespace
                    ws_tag = next_tag
                    mergeable_tags.append(ws_tag)
                    next_tag = ws_tag.next_sibling
                    ws_tag.decompose()
                if next_tag is not None and next_tag == siblings[-1]:
                    assert isinstance(next_tag, bs4.Tag)
                    # we can merge something
                    mergeable_tags.extend(next_tag.contents)
                    siblings.pop()
                    next_tag.decompose()
                    tag.extend(mergeable_tags)
                    siblings.append(tag)  # may be more to merge in later
            parent.smooth()


def replace_hrs(soup: bs4.BeautifulSoup):
    """Replace hr tags with 79 box-building lines"""
    for tag in soup("hr"):
        tag.replace_with("─" * 79)


def replace_brs(soup: bs4.BeautifulSoup):
    """Replace br tags with a linebreak"""
    for tag in soup("br"):
        if (tag.parent and tag.parent.name in BLOCKS
            and len(list(tag.parent.children)) == 1):
            # deal with implicit linebreak
            tag.decompose()
        else:
            tag.replace_with("\n")


def replace_imgs(soup: bs4.BeautifulSoup):
    """Replace img tags with approprate text representation"""
    for img in soup("img"):
        assert isinstance(img, bs4.Tag)
        img_src = str(img.get("src", ""))
        alt_text = str(img.get("alt", ""))
        img.replace_with("{" + alt_text + ": " + img_src + "}")


def direct_replacements(soup: bs4.BeautifulSoup):
    """Replace some classes of tags directly"""
    replace_hrs(soup)
    replace_brs(soup)
    replace_imgs(soup)


def markup2text(soup: bs4.BeautifulSoup):
    """Transform markup into text with delimiters"""
    MARKUP_MAP = {
        ("b", "strong"): "*",
        ("i", "em"): "/",
        ("u"): "_",
        ("s"): "~"
    }
    for tag_names, delimiter in MARKUP_MAP.items():
        for tag_name in tag_names:
            for tag in soup(tag_name):
                assert isinstance(tag, bs4.Tag)
                tag.insert(0, delimiter)
                tag.append(delimiter)
                tag.smooth()
                tag.unwrap()


def tags2text(soup: bs4.BeautifulSoup):
    """Replace tags by poor man's rich text"""
    link_counter : int = 1
    link_map : Dict[str, int] = dict()

    def process_tag(tag: bs4.Tag):
        """Recursively replace composite tags by poor man's rich texts"""
        # print(f".{tag.name.upper()}", end="")
        children = list(tag.children)
        # Recurse
        if len(children) > 0:
            # print(len(children), end="")
            for child in children:
                if isinstance(child, bs4.Tag):
                    process_tag(child)
                else:
                    pass
                    # print("_", end="")
            # Merge strings
            tag.smooth()
        # Before continuing make really sure tags have a single string
        # Remove empty tags
        if list(tag.children) == []:
            # print(f"/{tag.name}", end="")
            tag.decompose()
            return
        else:
            pass
            # print(f"+{tag.name}", end="")
        # It is a bug if tag does not have a (single) string at this point
        # Vertical placement
        if tag.name == "sup":
            tag.replace_with("^" + tag.string)
        if tag.name == "sub":
            tag.replace_with("_" + tag.string)
        # Headings
        if tag.name.startswith('h') and tag.name[1:].isdigit():
            level = int(tag.name[1:])
            tag.replace_with(f"{'#' * level} *{tag.string}*")
            return
        # Quotes
        if tag.name == "blockquote":
            quoted_lines = tag.string.splitlines()
            tag.replace_with("> " + "\n> ".join(quoted_lines))
            return
        # Anchors
        if tag.name == "a":
            href = str(tag.get("href", ""))
            text = str(tag.string)
            if href.startswith("mailto:") or href.startswith("phone:"):
                if href.endswith(":" + text):
                    tag.replace_with(text)
                    return
            elif href == text or href.endswith("://" + text):
                tag.replace_with(href)
                return
            title = tag.get("title")
            if not title or title == href:
                ref = href
            else:
                ref = href + f" ({title})"
            if ref not in link_map:
                nonlocal link_counter
                link_map[ref] = link_counter
                link_counter += 1
            tag.replace_with(f"[{text}][{link_map[ref]}]")
            return
        # Tables
        if tag.name == "table":
            tag.unwrap()
            return
        if tag.name in {"thead", "tbody", "tfoot"}:
            tag.unwrap()
            return
        if tag.name == "tr":
            if (isinstance(tag.next_sibling, bs4.Tag)
                and tag.next_sibling.name == "tr"):
                tag.replace_with(tag.string + "\n")
            else:
                tag.unwrap()
            return
        if tag.name in {"th", "td"}:
            if (isinstance(tag.next_sibling, bs4.Tag)
                and tag.next_sibling.name in {"th", "td"}):
                tag.replace_with(tag.string + "\t")
            else:
                tag.unwrap()
            return
        # Lists
        if tag.name == "li":
            tag.unwrap()
            return
        # TBD with link blocks
        if tag.name in {"body", "section", "div", "p", "ol", "ul"}:
            text = str(tag.string)
            if (link_map and (tag.name == "body" or
                tag.parent.name in {"body", "section", "div", "p", "ol", "ul"})):
                # Add list of tags after large enough bodies of text
                link_list = [f"\t[{index}]: {ref}"
                    for ref, index in sorted(link_map.items(),
                                             key=lambda pair: pair[1])]
                link_block = "\n".join(link_list)
                text += "\n\n" + link_block + "\n"
                link_map.clear()
            tag.replace_with(text)
            return

    process_tag(soup)
