import bs4


def ms_sender_identification(soup: bs4.BeautifulSoup):
    a = soup.find("a", href="https://aka.ms/LearnAboutSenderIdentification")
    if a is not None and a.parent is not None:
        a.parent.decompose()


def link_rewriting(soup: bs4.BeautifulSoup):
    # MS safelinks
    for a in soup("a", originalsrc=True):
        assert isinstance(a, bs4.Tag)
        a["href"] = a["originalsrc"]
