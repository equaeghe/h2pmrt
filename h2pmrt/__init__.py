import bs4

import h2pmrt.text as text
import h2pmrt.css as css
import h2pmrt.undo as undo
import h2pmrt.html as html


def convert(html_string: str) -> str:
    """Convert html to poor man's rich text"""
    soup = bs4.BeautifulSoup(text.cleanup(html_string), "html5lib")
    if isinstance(soup.contents[0], bs4.Doctype):
        soup.contents[0].decompose()
    css.cssprops2htmlattrs(soup)
    css.css2html_markup(soup)
    css.cssborder2hr(soup)
    soup.head.decompose()
    undo.ms_sender_identification(soup)
    undo.link_rewriting(soup)
    html.direct_unwraps(soup)
    html.sweat_whitespace(soup)
    html.linebreak_blocks(soup)
    html.remove_empty(soup)
    html.merge_markup(soup)
    html.direct_replacements(soup)
    img_refs = html.replace_imgs(soup)
    html.ul_compilation(soup)
    html.ol_compilation(soup)
    html.markup2text(soup)
    html.tags2text(soup)
    output = str(soup.string)
    if img_refs:
        output += "\n" + img_refs
    return output
