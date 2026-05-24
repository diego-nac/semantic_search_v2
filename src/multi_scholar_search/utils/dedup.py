from ..models.article import Article


def deduplicate(articles: list[Article]) -> list[Article]:
    seen: set[str] = set()
    result = []
    for article in articles:
        key = article.doi or article.title.lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(article)
    return result
