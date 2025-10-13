import bs4

import h2pmrt.text as text
import h2pmrt.css as css
import h2pmrt.undo as undo
import h2pmrt.html as html


def convert(html_string: str) -> str:
    """Convert html to poor man's rich text"""
    soup = bs4.BeautifulSoup(text.cleanup(html_string), "html5lib")
    soup = css.css2tags(soup)
    if soup.body:
        soup = soup.body
    undo.ms_sender_identification(soup)
    undo.link_rewriting(soup)
    html.remove_empty(soup)
    html.direct_unwraps(soup)
    html.sweat_whitespace(soup)
    html.remove_empty(soup)
    html.merge_markup(soup)
    soup = bs4.BeautifulSoup(text.cleanup(str(soup)), "html5lib")
    html.direct_replacements(soup)
    html.linebreak_blocks(soup)
    html.tags2text(soup)
    return str(soup.string)
