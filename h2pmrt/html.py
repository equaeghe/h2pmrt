from typing_extensions import Dict
import bs4

import h2pmrt.undo as undo


VOIDS = {"br", "hr", "img", "col"}
MERGEABLE = {"b", "strong", "i", "em"}
SWEATABLE = {"a", "b", "strong", "i", "em", "u", "s"}
REPLACEMENTS = {
    "br": "\n",
    "hr": "\n" + "_" * 79 + "\n"
}
MARKUP_MAP = {
    ("b", "strong"): "*",
    ("i", "em"): "/",
    ("u"): "_",
    ("s"): "~"
}


def remove_empty(soup: bs4.BeautifulSoup):
    """Iteratively remove empty tags"""
    maybe_some_empty_still = True
    while maybe_some_empty_still:
        maybe_some_empty_still = False
        for tag in soup.find_all(lambda tag: tag.name not in VOIDS,
                                 string=None):
            if list(tag.children) == []:
                tag.decompose()
                maybe_some_empty_still = True # decompose may create empty tags


def unwrap_spans(soup: bs4.BeautifulSoup):
    """Unwrap all spans"""
    for tag in soup("span"):
        tag.unwrap()


def merge_markup(soup: bs4.BeautifulSoup):
    """Merge adjacent markup tags"""
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
                if (isinstance(next_tag, bs4.NavigableString)
                    and str(next_tag).isspace()):
                    # deal with whitespace
                    ws_tag = next_tag
                    mergeable_tags.append(ws_tag)
                    next_tag = ws_tag.next_sibling
                    ws_tag.decompose()
                mergeable = next_tag == siblings[-1]
                if mergeable:
                    # we can merge something
                    print(next_tag)
                    mergeable_tags.extend(next_tag.contents)
                    siblings.pop()
                    next_tag.decompose()
                    tag.extend(mergeable_tags)
                    siblings.append(tag)  # may be more to merge in later
            parent.smooth()


def sweat_whitespace(soup: bs4.BeautifulSoup):
    """Iteratively move trimmable whitespace outside of tags"""
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


def tags2text(soup: bs4.BeautifulSoup):
    """Replace tags by poor man's rich text"""
    link_counter : int = 1
    link_map : Dict[str, int] = dict()

    # Directly replaceable tags
    for tag_name, replacement in REPLACEMENTS.items():
        for tag in soup(tag_name):
            tag.replace_with(replacement)

    # Images
    for tag in soup("img"):
        img_src = str(tag.get("src", ""))
        alt_text = str(tag.get("alt", ""))
        tag.replace_with("{" + alt_text + ": " + img_src + "}")

    # Other tags
    def process_tag(tag: bs4.Tag):
        """Recursively replace composite tags by poor man's rich texts"""
        print(f".{tag.name.upper()}", end="")
        children = list(tag.children)
        # Recurse
        if len(children) > 0:
            print(len(children), end="")
            for child in children:
                if isinstance(child, bs4.Tag):
                    process_tag(child)
                else:
                    print("_", end="")
            # Merge strings
            tag.smooth()
        # Before continuing make really sure tags have a single string
        # Remove empty tags
        if list(tag.children) == []:
            print(f"/{tag.name}", end="")
            tag.decompose()
            return
        else:
            print(f"+{tag.name}", end="")
        # Check whether there is a single string (if not, it is a bug)
        if not tag.string:
            raise ValueError(f"string missing from {tag.name}:\n{tag.prettify()}with parent {tag.parent.name} and as children {[child.name for child in tag.children]}")
        # Markup
        for tags, delimiter in MARKUP_MAP.items():
            if tag.name in tags:
                tag.replace_with(delimiter + tag.string + delimiter)
                return
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
            if href.endswith(text):
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
            tag.replace_with(tag.string + "\n")
            return
        if tag.name in {"th", "td"}:
            tag.replace_with(tag.string + "\t")
            return
        # TBD with link blocks
        if tag.name in {"body", "section", "div", "p", "ol", "ul"}:
            text = str(tag.string)
            if link_map:
                # Add list of tags after large enough bodies of text
                link_list = [f"\t[{index}]: {ref}"
                    for ref, index in sorted(link_map.items(),
                                             key=lambda pair: pair[1])]
                link_block = "\n".join(link_list)
                text += "\n\n" + link_block + "\n\n"
            tag.replace_with(text)
            link_map.clear()
            return

    process_tag(soup)
