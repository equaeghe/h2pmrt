import bs4
import tinycss2 as tc2


def cssprops2htmlattrs(soup: bs4.BeautifulSoup):
    """Convert CSS properties to HTML attributes"""
    PROPERTIES_OF_INTEREST = {
        "border", "border-top", "border-bottom", "border-style",
        "margin", "margin-left", "margin-top", "margin-bottom",
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


def attr2float(attr):
    """Convert attribute to float, or None if not possible"""
    try:
        float(str(attr))
    except ValueError:
        return None
    else:
        return float(str(attr))


def cssmargin2br(soup: bs4.BeautifulSoup):
    """Convert CSS margin properties to br tags"""
    # Transform margin to margin-left, margin-top, and margin-bottom
    for tag in soup.select("[css-margin]"):
        styles = str(tag["css-margin"]).split()
        if len(styles) <= 2:
            tag["css-margin-top"] = styles[0]
            tag["css-margin-bottom"] = styles[0]
        else:
            tag["css-margin-top"] = styles[0]
            tag["css-margin-bottom"] = styles[2]
    # Deal with margin-top and margin-bottom
    for tag in soup.select("[css-margin-top]"):
        margin_size = attr2float(tag["css-margin-top"])
        if margin_size and margin_size > 0:
            br = soup.new_tag("br")
            br["type"] = f"margin-top-{tag.name}"
            tag.insert_before(br)
    for tag in soup.select("[css-margin-bottom]"):
        margin_size = attr2float(tag["css-margin-bottom"])
        if margin_size and margin_size > 0:
            br = soup.new_tag("br")
            br["type"] = f"margin-bottom-{tag.name}"
            tag.insert_after(br)


def cssborder2hr(soup: bs4.BeautifulSoup):
    """Convert CSS border properties to styled hr tags"""
    STYLES = {"dotted",	"dashed", "solid", "double",
              "groove", "ridge", "inset", "outset"}
    CSS_BORDERS = {property: ",".join(f"[css-{property}*={style}]:not(hr)"
                                      for style in STYLES)
                   for property in {"border", "border-top", "border-bottom"}}
    # Transform border-style to border/border-top/border-bottom
    for tag in soup.select("[css-border-style]"):
        styles = str(tag["css-border-style"]).split()
        if len(styles) <= 2:
            tag["css-border"] = styles[0]
        else:
            top = styles[0]
            bottom = styles[2]
            if top == bottom:
                tag["css-border"] = styles[0]
            else:
                tag["css-border-top"] = top
                tag["css-border-bottom"] = bottom
    # Deal with border, border-top, and border-bottom
    for property, selection in CSS_BORDERS.items():
        for tag in soup.select(selection):
            if property in {"border", "border-top"}:
                hr = soup.new_tag("hr")
                attr_name = ("css-" + property
                             + "-before" if property == "border" else "")
                hr[attr_name] = tag[f"css-{property}"]
                tag.insert_before(hr)
            if property in {"border", "bordor-bottom"}:
                hr = soup.new_tag("hr")
                attr_name = ("css-" + property
                             + "-after" if property == "border" else "")
                hr[attr_name] = tag[f"css-{property}"]
                tag.insert_after(hr)
