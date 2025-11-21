import bs4
import tinycss2 as tc2


def inline_style_blocks(soup: bs4.BeautifulSoup):
    """Inline style blocks (ad hoc hacks, for now)"""
    # Option 1: use Python bindings of https://github.com/Stranger6667/css-inline
    # Option 2: inline styles myself using tinycss2 and bs4

    # MS styles often encountered (hack until style blocks are inlined)
    for tag in soup.select(".MsoNormal, .MsoListParagraph"):
        if not tag.get("css-margin"):
            if not tag.get("css-margin-top"):
                tag["css-margin-top"] = "0"
            if not tag.get("css-margin-bottom"):
                tag["css-margin-bottom"] = "0"


def cssprops2htmlattrs(soup: bs4.BeautifulSoup):
    """Convert CSS properties to HTML attributes"""
    PROPERTIES_OF_INTEREST = {
        "border",
        "border-top",
        "border-bottom",
        "border-style",
        "margin",
        "margin-left",
        "margin-top",
        "margin-bottom",
        "font-weight",
        "font-style",
        "text-decoration",
        "list-style-type",
    }
    UNINTERESTING_TOKENS = {
        tc2.ast.WhitespaceToken,
        tc2.ast.LiteralToken,
        tc2.ast.FunctionBlock,
    }

    for tag in soup.css.select("[style]"):
        # Find rules applied
        declarations = tc2.parse_blocks_contents(
            tag["style"], skip_comments=True, skip_whitespace=True
        )
        for decl in declarations:
            if decl.type == "declaration" and decl.name in PROPERTIES_OF_INTEREST:
                tag["css-" + decl.name] = " ".join(
                    str(value.value)
                    for value in decl.value
                    if not isinstance(value, tuple(UNINTERESTING_TOKENS))
                )
        del tag["style"]


def add_defaults(soup: bs4.BeautifulSoup):
    """Add some default styles that have a consequence in later processing"""
    # https://www.w3.org/TR/CSS2/sample.html
    NONZERO_VERTICAL_MARGIN = (
        "h1, h2, h3, h4, h5, h6, "
        "p, blockquote, *:not(ul, ol) ul, *:not(ul, ol) ol, dl, dir, menu "
        "fieldset, form"
    )
    for tag in soup.select(NONZERO_VERTICAL_MARGIN):
        if not tag.get("css-margin"):
            if not tag.get("css-margin-top"):
                tag["css-margin-top"] = "6"
            if not tag.get("css-margin-bottom"):
                tag["css-margin-bottom"] = "6"


def css2html_markup(soup: bs4.BeautifulSoup):
    """Convert CSS markup to HTML markup tags"""
    CSS_MARKUP = {
        "b": "[css-font-weight^=bold]:not(b, strong)",
        "i": ",".join(
            f"[css-font-style={style}]:not(i, em)" for style in {"italic", "oblique"}
        ),
        "u": "[css-text-decoration^=underline]:not(u, a)",
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
        if not tag.get("css-margin-top"):
            tag["css-margin-top"] = styles[0]
        if not tag.get("css-margin-bottom"):
            tag["css-margin-bottom"] = styles[2 * (len(styles) > 2)]
    # Deal with margin-top and margin-bottom
    for position in {"top", "bottom"}:
        for tag in soup.select(f"[css-margin-{position}]"):
            margin_size = attr2float(tag[f"css-margin-{position}"])
            if margin_size and margin_size > 0:
                br = soup.new_tag("br")
                br["type"] = f"margin-{position}"
                match position:
                    case "top":
                        tag.insert_before(br)
                    case "bottom":
                        tag.insert_after(br)


def borderstyle2border(soup: bs4.BeautifulSoup):
    """Transform border-style to border/border-top/border-bottom"""
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


def border2tag(soup: bs4.BeautifulSoup):
    """Convert CSS border properties to styled tags"""
    STYLES = {
        "dotted",
        "dashed",
        "solid",
        "double",
        "groove",
        "ridge",
        "inset",
        "outset",
    }
    CSS_BORDERS = {
        property: ",".join(
            f"[block][css-{property}*={style}]:not(hr)" for style in STYLES
        )
        for property in {"border", "border-top", "border-bottom"}
    }
    for property, selection in CSS_BORDERS.items():
        for tag in soup.select(selection):
            before = after = False
            match property:
                case "border":
                    before = after = True
                case "border-top":
                    before = True
                case "border-bottom":
                    after = True
            for position in {"before", "after"}:
                hr = soup.new_tag("hr")
                hr["block"] = "inherent"
                attr_name = "css-" + property
                if property == "border":
                    attr_name += "-" + position
                hr[attr_name] = tag[f"css-{property}"]
                if before and position == "before":
                    tag.insert_before(hr)
                if after and position == "after":
                    tag.insert_after(hr)
