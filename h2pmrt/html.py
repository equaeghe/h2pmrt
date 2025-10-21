from typing_extensions import Dict
import bs4
import re
import os.path as op
import urllib.parse as up


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


def sanitize_tree(soup: bs4.BeautifulSoup):
    """Remove tags that can only get in the way"""
    for tag in soup.select("head, style, meta"):
        tag.decompose()


def unwrap_spans(soup: bs4.BeautifulSoup):
    """Unwrap all span-like tags"""
    SPAN_LIKE = "span, font, center"
    for tag in soup.select(SPAN_LIKE):
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
    soup.smooth()


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
    soup.smooth()


def linebreak_blocks(soup: bs4.BeautifulSoup):
    """Add a linebreak between sibling block-like elements"""
    parents = set()
    for tag in soup(BLOCKS):
        parents.add(tag.parent)
    for parent in parents:
        for whitespace in parent(string=re.compile("^ *$"), recursive=False):
            whitespace.decompose()
        for block_sibling in parent(BLOCKS, recursive=False):
            previous = block_sibling.previous_sibling
            next = block_sibling.next_sibling
            if previous:
                linebreak = bs4.NavigableString("\n")
                block_sibling.insert_before(linebreak)
            if next and next.name not in BLOCKS:
                linebreak = bs4.NavigableString("\n")
                block_sibling.insert_after(linebreak)


def remove_empty(soup: bs4.BeautifulSoup):
    """Iteratively remove empty tags"""
    VOIDS = {"br", "hr", "img", "col"}
    maybe_some_empty_still = True
    while maybe_some_empty_still:
        maybe_some_empty_still = False
        for tag in soup(lambda tag: tag.name not in VOIDS, string=None):
            assert isinstance(tag, bs4.Tag)
            if list(tag.children) in ([], [""]):
                tag.decompose()
                maybe_some_empty_still = True # decompose may create empty tags
        soup.smooth()


def merge_markup(soup: bs4.BeautifulSoup):
    """Merge adjacent markup tags"""
    EQUIVALENT = {"strong": "b", "em": "i"}
    MERGEABLE = {"b", "i"}
    soup.smooth()  # make sure there are no adjacent NavigableStrings
    # Eliminate use of equivalent tag names for markup
    for tag_name, equivalent_tag_name in EQUIVALENT.items():
        for tag in soup.select(tag_name):
            tag.name = equivalent_tag_name
    for tag_name in MERGEABLE:
        # Unwrap markup that is implied by ancestor markup
        for tag in soup.select(tag_name + " " + tag_name):
            tag.unwrap()
        # Group by parent
        sibling_map = dict()
        for tag in soup.select(tag_name):
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
    """Replace hr tags with box-building lines"""
    for hr in soup.select("hr"):
        if hr.get("css-border-before"):
            hr.replace_with("┌" + "─" * 39)
        elif hr.get("css-border-after"):
            hr.replace_with("─" * 39 + "┘")
        else:
            hr.replace_with("─" * 40)


def replace_brs(soup: bs4.BeautifulSoup):
    """Replace br tags with a linebreak"""
    for tag in soup("br"):
        if (tag.parent and tag.parent.name in BLOCKS
            and len(list(tag.parent.children)) == 1):
            # deal with implicit linebreak
            tag.decompose()
        else:
            next = tag.next
            tag.replace_with("\n")
            if next and isinstance(next, bs4.NavigableString):
                next.replace_with(next.lstrip())
    soup.smooth()


def replace_headings(soup: bs4.BeautifulSoup):
    """Replace headings with simpler markup"""
    HEADINGS = "h1, h2, h3, h4, h5, h6"
    for h in soup.select(HEADINGS):
        level = int(h.name[1:])
        b = h.wrap(soup.new_tag("b"))
        h.unwrap()
        signpost = bs4.NavigableString("#" * level + " ")
        b.insert_before(signpost)


def direct_replacements(soup: bs4.BeautifulSoup):
    """Replace some classes of tags directly"""
    replace_hrs(soup)
    replace_brs(soup)
    replace_headings(soup)


def replace_imgs(soup: bs4.BeautifulSoup) -> str:
    """Replace img tags with approprate text representation"""
    img_refs = {}
    ref_counter = 0
    for img in soup.select("img"):
        img_ref = str(img.get("src", ""))
        if img_ref not in img_refs:
            ref_counter += 1
            img_refs[img_ref] = ref_counter
        alt_text = img.get("alt")
        if alt_text:
            alt_text = str(alt_text)
        else:
            alt_text = up.unquote(op.basename(up.urlparse(img_ref).path))
            alt_text = alt_text.split(".")[0].replace("_", " ")
        img.replace_with("{" + alt_text + "}{" + str(img_refs[img_ref]) + "}")
    img_refs_text = (
        "\n" + "═" * 40 + "\n" +
        "\n".join("{" + str(i) + "}: " + ref for ref, i in img_refs.items()) +
        "\n" + "═" * 40
    ) if img_refs else ""
    return img_refs_text


def ul_compilation(soup: bs4.BeautifulSoup):
    """Compile ul to div"""
    UL_SYMBOLS = {
        "disc": "•",
        "circle": "◦",
        "square": "▪"
    }
    for menu in soup.select("menu"):
        menu.name = "ul"
    for ul in soup.select("ul"):
        symbol_string = "disc"
        if ul.get("type"):
            symbol_string = str(ul["type"])
        if ul.get("css-list-style-type"):
            symbol_string = str(ul["css-list-style-type"])
        for li in ul("li", recursive=False):
            assert isinstance(li, bs4.Tag)
            if li.get("css-list-style-type"):
                symbol_string = str(li["css-list-style-type"])
            if symbol_string in UL_SYMBOLS:
                symbol = UL_SYMBOLS[symbol_string]
            else:
                symbol = symbol_string
            li.insert(0, symbol + " ")


def ol_compilation(soup: bs4.BeautifulSoup):
    """Compile ol to div"""
    TYPEATTR2LST = {
        "1": "decimal",
        "a": "lower-latin",
        "A": "upper-latin",
        "i": "lower-roman",
        "I": "upper-roman"
    }
    LST2INSDICES = {
        "decimal": [str(k) for k in range(1,27)],
        "lower-latin": "abcdefghijklmnopqrstuvw",
        "upper-latin": "ABCDEFGHIJKLMNOPQRSTUVW",
        "lower-roman": [
            "i", "ii", "iii", "iv", "v",
            "vi", "vii", "viii", "ix", "x",
            "xi", "xii", "xiii", "xiv", "xv",
            "xvi", "xvii", "xviii", "xix", "xx"
        ],
        "upper-roman": [
            "i", "ii", "iii", "iv", "v",
            "vi", "vii", "viii", "ix", "x",
            "xi", "xii", "xiii", "xiv", "xv",
            "xvi", "xvii", "xviii", "xix", "xx"
        ],
        "upper-roman": [
            "I", "II", "III", "IV", "V",
            "VI", "VII", "VIII", "IX", "X",
            "XI", "XII", "XIII", "XIV", "XV",
            "XVI", "XVII", "XVIII", "XIX", "XX"
        ],
    }
    for ol in soup.select("ol"):
        lst = TYPEATTR2LST[str(ol["type"])] if ol.get("type") else "decimal"
        counter = (int(str(ol["start"])) if ol.get("start") else 1) - 1
        for li in ol("li", recursive=False):
            assert isinstance(li, bs4.Tag)
            li_lst = LST2INSDICES[lst][counter] + ". "
            if li.get("css-list-style-type"):
                li_lst = str(li["css-list-style-type"])
            li.insert(0, li_lst)
            counter += 1


def markup2text(soup: bs4.BeautifulSoup):
    """Transform markup into text with delimiters"""
    MARKUP_MAP = {
        "b, strong": "*",
        "i, em": "/",
        "a > u, u:has(> a)": "",
        "u": "_",
        "s": "~"
    }
    for selector, delimiter in MARKUP_MAP.items():
        for tag in soup.select(selector):
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
        if tag.name in {"ul", "ol", "dl"}:
            list_lines = tag.string.splitlines()
            tag.string = "\t" + "\n\t".join(list_lines)
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
