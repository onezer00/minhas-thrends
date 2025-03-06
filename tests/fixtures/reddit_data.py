"""
Fixtures com dados de exemplo do Reddit para testes.
"""

class MockRedditSubmission:
    """Mock para um post do Reddit."""
    
    def __init__(self, id, title, score, num_comments, url, created_utc, author, selftext="", 
                 subreddit_name_prefixed="r/test", link_flair_text=None, is_self=False, 
                 thumbnail="https://reddit.com/thumb.jpg"):
        self.id = id
        self.title = title
        self.score = score
        self.num_comments = num_comments
        self.url = url
        self.created_utc = created_utc
        self.author = MockRedditAuthor(author) if author else None
        self.selftext = selftext
        self.subreddit_name_prefixed = subreddit_name_prefixed
        self.link_flair_text = link_flair_text
        self.is_self = is_self
        self.thumbnail = thumbnail
        self.permalink = f"/r/test/comments/{id}/title"

class MockRedditAuthor:
    """Mock para um autor do Reddit."""
    
    def __init__(self, name):
        self.name = name

# Lista de posts simulados do Reddit
REDDIT_TRENDING_POSTS = [
    MockRedditSubmission(
        id="abcd123",
        title="Post de teste do Reddit 1",
        score=5000,
        num_comments=300,
        url="https://www.reddit.com/r/test/comments/abcd123/post_de_teste_1",
        created_utc=1673784000,  # 15/01/2023
        author="user123",
        selftext="Este é o conteúdo do post de teste 1 #noticias #politica",
        subreddit_name_prefixed="r/noticias",
        link_flair_text="Política",
        is_self=True
    ),
    MockRedditSubmission(
        id="efgh456",
        title="Post de teste do Reddit 2",
        score=8000,
        num_comments=500,
        url="https://www.reddit.com/r/test/comments/efgh456/post_de_teste_2",
        created_utc=1673870400,  # 16/01/2023
        author="user456",
        selftext="Este é o conteúdo do post de teste 2 #tecnologia #programacao",
        subreddit_name_prefixed="r/tecnologia",
        link_flair_text="Programação",
        is_self=True
    ),
    MockRedditSubmission(
        id="ijkl789",
        title="Post de teste do Reddit 3",
        score=3000,
        num_comments=200,
        url="https://exemplo.com/artigo",
        created_utc=1673956800,  # 17/01/2023
        author="user789",
        selftext="",
        subreddit_name_prefixed="r/links",
        link_flair_text="Link Externo",
        is_self=False,
        thumbnail="https://exemplo.com/thumb.jpg"
    )
] 