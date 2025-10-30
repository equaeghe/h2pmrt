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
    "table", "tbody", "tfoot", "thead", "tr",
    "ul",
    "video"
}


def sanitize_tree(soup: bs4.BeautifulSoup):
    """Remove tags that can only get in the way"""
    for tag in soup.select("head, style, meta"):
        tag.decompose()
    for comment in soup(string=lambda elem: isinstance(elem, bs4.Comment)):
        comment.decompose()


def br_type_original(soup: bs4.BeautifulSoup):
    """Add ’original’ type to br tags in original html"""
    for br in soup.select("br"):
        br["type"] = "original"


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


def unwrap_vertical_placement(soup: bs4.BeautifulSoup):
    """Unwrap all sub and sup tags"""
    REPLACEABLE = "0123456789+-n"
    SUB_REPLACEMENTS = "₀₁₂₃₄₅₆₇₈₉₊₋ₙ"
    SUP_REPLACEMENTS = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ"
    SUP_NO_CARET = {"st", "nd", "rd", "ste", "de", "e"}
    for sub in soup.select("sub"):
        if sub.string and len(sub.string) == 1 and sub.string in REPLACEABLE:
            sub.replace_with(SUB_REPLACEMENTS[REPLACEABLE.find(sub.string)])
        else:
            sub.insert(0, "_")
            sub.unwrap()
    for sup in soup.select("sup"):
        if sup.string and len(sup.string) == 1 and sup.string in REPLACEABLE:
            sup.replace_with(SUP_REPLACEMENTS[REPLACEABLE.find(sup.string)])
        elif sup.string in SUP_NO_CARET:
            sup.replace_with(sup.string)
        else:
            sup.insert(0, "^")
            sup.unwrap()


def unwrap_table_cells(soup: bs4.BeautifulSoup):
    """Unwrap all th an td tags, separating with tabs"""
    for cell_name in {"th", "td"}:
        cells = soup.select(cell_name)
        for cell in cells:
            next = cell.next_sibling
            if next and next in cells:
                next.insert(0, "\t")
            cell.unwrap()


def direct_unwraps(soup: bs4.BeautifulSoup):
    """Unwrap some classes of tags directly"""
    unwrap_spans(soup)
    unwrap_msoffice_tags(soup)
    unwrap_vertical_placement(soup)
    unwrap_table_cells(soup)
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
        for tag in soup.select(
            ",".join([tag + ":has(> br)" for tag in SWEATABLE])
        ):
            children = list(tag.children)
            outer = (children[0], children[-1])
            if outer[0].name == "br":
                tag.insert_before(outer[0].extract())
                sweating = True
            if outer[0] is outer[-1]:
                continue
            if outer[-1].name == "br":
                tag.insert_after(outer[1].extract())
                sweating = True
    soup.smooth()


def sweat_markup(soup: bs4.BeautifulSoup):
    """Move single child markup outside of anchor tags"""
    MARKUP = {"b", "strong", "i", "em", "u", "s"}
    for markup_name in MARKUP:
        for markup in soup.select(f"a > {markup_name}:only-child"):
            markup.parent.wrap(soup.new_tag(markup_name))
            markup.unwrap()


def sweat(soup: bs4.BeautifulSoup):
    """Move all kinds of material outwards"""
    sweat_whitespace(soup)
    sweat_markup(soup)


def linebreak_blocks(soup: bs4.BeautifulSoup):
    """Add a linebreak between sibling block-like elements"""
    parents = set()
    for tag in soup(BLOCKS):
        parents.add(tag.parent)
    for parent in parents:
        for whitespace in parent(string=re.compile(r"^[  \t]*$"),
                                 recursive=False):
            whitespace.decompose()
        for block_sibling in parent(BLOCKS, recursive=False):
            previous = block_sibling.previous_sibling
            next = block_sibling.next_sibling
            if previous:
                br = soup.new_tag("br")
                br["type"] = f"blocks-previous-{block_sibling.name}"
                block_sibling.insert_before(br)
            if next and next.name not in BLOCKS:
                br = soup.new_tag("br")
                br["type"] = f"blocks-next-{block_sibling.name}"
                block_sibling.insert_after(br)


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
                    next_tag.extract()
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


def replace_headings(soup: bs4.BeautifulSoup):
    """Replace headings with simpler markup"""
    HEADINGS = "h1, h2, h3, h4, h5, h6"
    for h in soup.select(HEADINGS):
        level = int(h.name[1:])
        b = h.wrap(soup.new_tag("b"))
        h.unwrap()
        signpost = bs4.NavigableString("#" * level + " ")
        b.insert_before(signpost)


def replace_anchors(soup: bs4.BeautifulSoup):
    """Replace anchors with coinciding text and href"""
    for a in soup.select("a"):
        if not a.string:
            continue
        href = str(a.get("href", ""))
        text = str(a.string)
        href_parts = href.split(text)
        if len(href_parts) == 2:
            head = href_parts[0]
            tail = href_parts[-1]
            if head in {"mailto:", "phone:"} and tail == "":
                a.replace_with(text)
            elif (head == "" or head.endswith("://")) and tail in {"", "/"}:
                a.replace_with(href)


def replace_blockquotes(soup: bs4.BeautifulSoup):
    """Replace blockquotes by preceding lines with poor man's quote chars"""
    for blockquote in soup.select("blockquote"):
        blockquote.insert(0, "> ")
        for br in blockquote("br", recursive=False):
            next = br.next
            if next:
                next.insert(0, "> ")


def direct_replacements(soup: bs4.BeautifulSoup):
    """Replace some classes of tags directly"""
    replace_hrs(soup)
    replace_headings(soup)
    replace_anchors(soup)
    replace_blockquotes(soup)


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
    """Compile ul"""
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
    soup.smooth()


def ol_compilation(soup: bs4.BeautifulSoup):
    """Compile ol"""
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
    soup.smooth()


def list_compilations(soup: bs4.BeautifulSoup):
    """Compile lists"""
    ul_compilation(soup)
    ol_compilation(soup)
    # Indent lists
    for somel in soup.select("ul, ol"):
        somel.insert(0, "\t")
        for br in somel("br"):
            if br.next:
                br.insert_after("\t")


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
    LINKBLOCKABLE = {"body", "section", "div", "p", "ol", "ul"}
    link_counter : int = 1
    link_block_tag = None
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
        # Anchors
        if tag.name == "a":
            href = str(tag.get("href", ""))
            title = tag.get("title")
            if not title or title == href:
                ref = href
            else:
                ref = href + f" ({title})"
            if ref not in link_map:
                nonlocal link_counter
                nonlocal link_block_tag
                candidate = tag
                if not link_block_tag:
                    linkblockable_found = False
                    while not linkblockable_found:
                        if (candidate.name == "body" or
                            (candidate.name in LINKBLOCKABLE and
                             candidate.parent.name in LINKBLOCKABLE)):
                            link_block_tag = candidate
                            linkblockable_found = True
                        else:
                            candidate = candidate.parent
                link_map[ref] = link_counter
                link_counter += 1
            tag.insert(0, "[")
            tag.append(f"][{link_map[ref]}]")
            tag.unwrap()
            return
        # link blocks
        if tag is link_block_tag:
            br = soup.new_tag("br")
            br["type"] = "linkblock-pre"
            tag.append(br)
            for ref, k in sorted(link_map.items(), key=lambda pair: pair[1]):
                br = soup.new_tag("br")
                br["type"] = "linkref"
                tag.append(br)
                tag.append(f"\t[{k}]: {ref}")
            br = soup.new_tag("br")
            br["type"] = "linkblock-post"
            tag.append(br)
            link_map.clear()
            link_block_tag = None

    process_tag(soup)


def unwrap_blocks(soup: bs4.BeautifulSoup):
    """Unwrap all block tags"""
    for tag in soup(BLOCKS):
        tag.unwrap()


def brs2linebreaks(soup: bs4.BeautifulSoup):
    """Replace br tags with linebreaks"""
    # Decompose whitespace between br tags
    for ws in soup(string=re.compile(r"^[  \t]*$")):
        prev = ws.previous_sibling
        next = ws.next_sibling
        if prev and next and {prev.name, next.name} == {"br"}:
           ws.decompose()
    # Decompose some br tags considered superfluous
    for br in soup.select("br"):
        prev = br.previous_sibling
        next = br.next_sibling
        if prev and next and {prev.name, next.name} == {"br"}:
            # print(prev, br, next)
            prev_type = str(prev.get("type"))
            br_type = str(br.get("type"))
            next_type = str(next.get("type"))
        else:
            continue
        # "br[type^='blocks'] + br[type='original'] + br[type^='blocks']"
        if (prev_type.startswith("blocks")
            and br_type == "original"
            and next_type.startswith("blocks")):
                prev.decompose()
        # "br[type='linkblock-post'] + br[type^='blocks'] + br[type^='blocks']"
        elif (prev_type == "linkblock-post"
              and br_type.startswith("blocks")
              and next_type.startswith("blocks")):
                prev.decompose()
        # "br[type^='blocks'] + br[type='original'] + br[type='original']"
        elif (prev_type.startswith("blocks")
              and br_type == "original"
              and next_type == "original"):
                prev.decompose()
    for br in soup.select("br"):
        # br.replace_with(f"\n[{br.get('type')}]")
        br.replace_with("\n")
    soup.smooth()
