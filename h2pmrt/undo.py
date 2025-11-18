import bs4


def ms_sender_identification(soup: bs4.BeautifulSoup):
    """Remove MS SenderIdentification string(s)"""
    for a in soup.select("a[href='https://aka.ms/LearnAboutSenderIdentification']"):
        # find first br before (or first sibling) and after (or last sibling)
        before = a
        while not (before and before.name == "br"):
            if before.previous_sibling is None:
                break
            else:
                before = before.previous_sibling
        after = a
        while not (after and after.name == "br"):
            if after.next_sibling is None:
                break
            else:
                after = after.next_sibling
        # decompose all tags between before and after
        match (before.name, after.name):
            case ("br", "br"):
                tag = before.next_sibling
            case (_, "br") | ("br", _):
                tag = before
            case (_, _):
                a.parent.decompose()
                return
        completed = False
        while not completed:
            if tag is after:
                completed = True
            tag = tag.next_sibling
            tag.previous_sibling.decompose()


def link_rewriting(soup: bs4.BeautifulSoup):
    # MS safelinks
    for a in soup("a", originalsrc=True):
        assert isinstance(a, bs4.Tag)
        a["href"] = a["originalsrc"]
        del a["originalsrc"]


def tue_phising_note(soup: bs4.BeautifulSoup):
    """Remove phishing warning note added by TU/e LIS"""
    STYLE = (
        "border:solid #FFCACA 1.0pt; "
        "padding:12.0pt 12.0pt 12.0pt 12.0pt; "
        "background:lightyellow"
    )
    for div in soup.select(f"div[style='{STYLE}']"):
        div.decompose()
