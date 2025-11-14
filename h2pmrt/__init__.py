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
    html.mark_blocks(soup)
    css.cssprops2htmlattrs(soup)
    css.css2html_markup(soup)
    css.cssmargin2br(soup)
    css.borderstyle2border(soup)
    css.border2tag(soup)
    html.sanitize_tree(soup)
    html.br_type_original(soup)
    undo.link_rewriting(soup)
    html.direct_unwraps(soup)
    html.sweat(soup)
    html.linebreak_blocks(soup)
    undo.ms_sender_identification(soup)
    html.direct_replacements(soup)
    html.remove_empty(soup)
    html.merge_markup(soup)
    html.markup2text(soup)
    img_refs = html.replace_imgs(soup)
    html.list_compilations(soup)
    html.tags2text(soup)
    html.unwrap_remaining(soup)
    html.cull_brs(soup)
    html.replace_blockquotes(soup)
    html.brs2linebreaks(soup)
    output = str(soup.string)
    if img_refs:
        output += "\n" + img_refs
    return output
