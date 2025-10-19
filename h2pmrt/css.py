import bs4
import tinycss2 as tc2


def cssprops2htmlattrs(soup: bs4.BeautifulSoup):
    """Convert CSS properties to HTML attributes"""
    PROPERTIES_OF_INTEREST = {
        "border", "border-top", "border-bottom",
        "font-weight", "font-style", "text-decoration",
        "list-style-type"
    }
    UNINTERESTING_TOKENS = {
        tc2.ast.WhitespaceToken, tc2.ast.LiteralToken, tc2.ast.FunctionBlock
    }

    # Inline style blocks
    # TODO: use Python bindings of https://github.com/Stranger6667/css-inline

    for tag in soup.css.select("[style]"):
        # Find rules applied
        declarations = tc2.parse_blocks_contents(tag["style"],
            skip_comments=True, skip_whitespace=True)
        for decl in declarations:
            if (decl.type == "declaration" and
                decl.name in PROPERTIES_OF_INTEREST):
                tag["css-" + decl.name] = " ".join(
                    str(value.value) for value in decl.value
                    if not isinstance(value, tuple(UNINTERESTING_TOKENS))
                )
        del tag["style"]


def css2html_markup(soup: bs4.BeautifulSoup):
    """Convert CSS markup to HTML markup tags"""
    CSS_MARKUP = {
        "b": "[css-font-weight^=bold]:not(b, strong)",
        "i": ",".join(f"[css-font-style={style}]:not(i, em)"
                      for style in {"italic", "oblique"}),
        "u": "[css-text-decoration^=underline]:not(u, a)"
    }
    for markup_tag_name, selection in CSS_MARKUP.items():
        for tag in soup.select(selection):
            wrapper = soup.new_tag(markup_tag_name)
            wrapper.extend(tag.contents)
            tag.clear()
            tag.append(wrapper)


def cssborder2hr(soup: bs4.BeautifulSoup):
    """Convert CSS border properties to styled hr tags"""
    STYLES = {"dotted",	"dashed", "solid", "double",
              "groove", "ridge", "inset", "outset"}
    CSS_BORDERS = {property: ",".join(f"[css-{property}*={style}]:not(hr)"
                                      for style in STYLES)
                   for property in {"border", "border-top", "border-bottom"}}
    for property, selection in CSS_BORDERS.items():
        for tag in soup.select(selection):
            if property in {"border", "border-top"}:
                hr = soup.new_tag("hr")
                hr[f"css-{property}"] = tag[f"css-{property}"]
                tag.insert_before(hr)
            if property in {"border", "bordor-bottom"}:
                hr = soup.new_tag("hr")
                hr[f"css-{property}"] = tag[f"css-{property}"]
                tag.insert_after(hr)
