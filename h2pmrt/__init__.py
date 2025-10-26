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
    css.cssmargin2br(soup)
    css.cssborder2hr(soup)
    html.sanitize_tree(soup)
    html.br_type_original(soup)
    undo.ms_sender_identification(soup)
    undo.link_rewriting(soup)
    html.direct_unwraps(soup)
    html.sweat(soup)
    html.linebreak_blocks(soup)
    html.direct_replacements(soup)
    html.merge_markup(soup)
    html.remove_empty(soup)
    html.markup2text(soup)
    img_refs = html.replace_imgs(soup)
    html.list_compilations(soup)
    html.tags2text(soup)
    output = str(soup.string)
    if img_refs:
        output += "\n" + img_refs
    return output
