import bs4
import tinycss2 as tc2


def css2tags(soup: bs4.BeautifulSoup) -> bs4.BeautifulSoup:
    """Convert CSS styles to html markup"""

    # Inline style blocks
    # TODO: use Pyhon bindings of https://github.com/Stranger6667/css-inline

    for tag in soup.css.select("[style]"):
        # Find rules applied
        applied = {}
        declarations = tc2.parse_blocks_contents(tag["style"],
            skip_comments=True, skip_whitespace=True)
        for decl in declarations:
            if decl.type == "declaration":
                applied[decl.name] = [value.lower_value for value in decl.value
                                      if isinstance(value, tc2.ast.IdentToken)]
        del tag["style"]
        # Apply formatting
        if any(value.startswith("bold")
               for value in applied.get("font-weight", [])):
            wrap_children(soup, tag, "b")
        if any(value in {"italic", "oblique"}
               for value in applied.get("font-style", [])):
            wrap_children(soup, tag, "i")
        if any(value.startswith("underline")
               for value in applied.get("text-decoration", [])):
            wrap_children(soup, tag, "u")
        for border_key in {"border", "border-top"}:
            if any(value in {"solid", "dashed", "double"}
                   for value in applied.get(border_key, [])):
                tag.insert_before(soup.new_tag("hr"))
        for border_key in {"border", "border-bottom"}:
            if any(value in {"solid", "dashed", "double"}
                   for value in applied.get(border_key, [])):
                tag.insert_after(soup.new_tag("hr"))
    return soup


def wrap_children(soup: bs4.BeautifulSoup,
                  parent_tag: bs4.Tag, wrapping_tag_name: str):
    wrapper = soup.new_tag(wrapping_tag_name)
    for content in reversed(parent_tag.contents):
        wrapper.insert(0, content.extract())
    parent_tag.append(wrapper)
