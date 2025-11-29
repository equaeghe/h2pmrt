import bs4
import tinycss2 as tc2


def inline_style_blocks(soup: bs4.BeautifulSoup):
    """Inline style blocks (ad hoc hacks, for now)"""
    # Option 1: use Python bindings of https://github.com/Stranger6667/css-inline
    # Option 2: inline styles myself using tinycss2 and bs4

    # MS styles often encountered (hack until style blocks are inlined)
    MS_STYLES = (
        ".MsoNormal, .MsoListParagraph, "
        ".x_MsoNormal, .x_MsoListParagraph"  # class renaming in some replies
    )
    for tag in soup.select(MS_STYLES):
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
        "padding",
        "padding-left",
        "padding-top",
        "padding-bottom",
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
                values = []
                for token in decl.value:
                    if isinstance(token, tuple(UNINTERESTING_TOKENS)):
                        continue
                    if token.type == "dimension":
                        # express all lengths as approximate line heights (https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/length)
                        match token.lower_unit:
                            case "px":
                                values.append(str(token.value / 16))
                            case "pt":
                                values.append(str(token.value / 12))
                            case "pc":
                                values.append(str(token.value))
                            case "ch" | "ex":
                                values.append(str(token.value / 2))
                            case "cap" | "em" | "ic" | "lh":
                                values.append(str(token.value))
                            case "rch" | "rex":
                                values.append(str(token.value / 2))
                            case "rcap" | "rem" | "ric" | "rlh":
                                values.append(str(token.value))
                            case "in":
                                values.append(str(token.value * 6))
                            case "cm":
                                values.append(str(token.value * 6 / 2.54))
                            case "mm":
                                values.append(str(token.value * 6 / 25.4))
                            case "Q":
                                values.append(str(token.value * 6 / 25.4 / 4))
                    else:
                        values.append(str(token.value))
                tag["css-" + decl.name] = " ".join(values)
        del tag["style"]


def add_defaults(soup: bs4.BeautifulSoup):
    """Add some default styles that have a consequence in later processing"""
    # https://www.w3.org/TR/CSS2/sample.html
    ZERO_VERTICAL_MARGIN = "ol ol, ol ul, ul ol, ul ul"
    NONZERO_VERTICAL_MARGIN = (
        "h1, h2, h3, h4, h5, h6, p, blockquote, ul, ol, dl, dir, menu, fieldset, form"
    )
    for tag in soup.select(ZERO_VERTICAL_MARGIN):
        if not tag.get("css-margin"):
            if not tag.get("css-margin-top"):
                tag["css-margin-top"] = "0"
            if not tag.get("css-margin-bottom"):
                tag["css-margin-bottom"] = "0"
    for tag in soup.select(NONZERO_VERTICAL_MARGIN):
        if not tag.get("css-margin"):
            if not tag.get("css-margin-top"):
                tag["css-margin-top"] = "1"
            if not tag.get("css-margin-bottom"):
                tag["css-margin-bottom"] = "1"


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


def cssws2br(ws, soup: bs4.BeautifulSoup):
    """Convert CSS margin and padding properties to br tags"""
    # Transform margin/padding to left, top, and bottom specializations
    for tag in soup.select(f"[css-{ws}]"):
        styles = str(tag[f"css-{ws}"]).split()
        if not tag.get(f"css-{ws}-top"):
            tag[f"css-{ws}-top"] = styles[0]
        if not tag.get(f"css-{ws}-bottom"):
            tag[f"css-{ws}-bottom"] = styles[2 * (len(styles) > 2)]
    # Deal with top and bottom
    for position in {"top", "bottom"}:
        for tag in soup.select(f"[css-{ws}-{position}][block]"):
            size = attr2float(tag[f"css-{ws}-{position}"])
            if size and size > 0.34:
                br = soup.new_tag("br")
                br["type"] = f"{ws}-{position}"
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
