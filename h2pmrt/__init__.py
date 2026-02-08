import bs4

import h2pmrt.text as text
import h2pmrt.css as css
import h2pmrt.undo as undo
import h2pmrt.html as html


def convert(html_string: str) -> str:
    """Convert html to poor man's rich text"""
    soup = bs4.BeautifulSoup(text.cleanup(html_string), "html5lib")
    undo.tue_phising_note(soup)
    html.mark_blocks(soup)
    css.cssprops2htmlattrs(soup)
    css.inline_style_blocks(soup)
    css.add_defaults(soup)
    css.css2html_markup(soup)
    html.provide_alt_text(soup)
    html.sanitize_tree(soup)
    html.br_type_original(soup)
    undo.link_rewriting(soup)
    html.direct_unwraps(soup)
    css.cssws2br("margin", soup)
    html.sweat(soup)
    css.borderstyle2border(soup)
    css.border2tag(soup)
    html.linebreak_blocks(soup)
    css.cssws2br("padding", soup)
    undo.ms_sender_identification(soup)
    html.remove_empty(soup)
    html.direct_replacements(soup)
    html.merge_markup(soup)
    html.markup2text(soup)
    html.list_compilations(soup)
    html.tags2text(soup)
    html.unwrap_remaining(soup)
    html.cull_brs(soup)
    html.replace_blockquotes(soup)
    html.brs2linebreaks(soup)
    return str(soup.string).strip()
