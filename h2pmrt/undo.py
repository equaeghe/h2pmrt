import bs4


def ms_sender_identification(soup: bs4.BeautifulSoup):
    tag = soup.find("a", href="https://aka.ms/LearnAboutSenderIdentification")
    tag.parent.decompose()


def link_rewriting(soup: bs4.BeautifulSoup):
    # MS safelinks
    for a in soup("a", originalsrc=True):
        a["href"] = a["originalsrc"]
