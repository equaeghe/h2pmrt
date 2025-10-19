import minify_html as mh
import re


re_brn = re.compile(r"(<br ?/?>)\n+")


def cleanup(html_string: str) -> str:
    """Clean up whitespace"""
    html_string = re_brn.sub(r"\1", html_string)
    html_string = mh.minify(html_string)
    return html_string
