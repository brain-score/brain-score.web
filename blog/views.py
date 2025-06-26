import os
import frontmatter
import markdown
from django.shortcuts import render, Http404

ARTICLES_DIR = os.path.join(os.path.dirname(__file__), 'articles')

def get_article_by_slug(slug):
    for filename in os.listdir(ARTICLES_DIR):
        if filename.endswith('.md'):
            post = frontmatter.load(os.path.join(ARTICLES_DIR, filename))
            if post.get('slug') == slug:
                return post
    return None

def article_detail(request, slug):
    post = get_article_by_slug(slug)
    if not post:
        raise Http404('Article not found')
    html_content = markdown.markdown(post.content, extensions=['extra', 'codehilite', 'toc', 'fenced_code', 'tables'])
    return render(request, 'blog/article_detail.html', {
        'article': post,
        'content_html': html_content,
    })

def article_list(request):
    articles = []
    for filename in os.listdir(ARTICLES_DIR):
        if filename.endswith('.md'):
            post = frontmatter.load(os.path.join(ARTICLES_DIR, filename))
            articles.append(post)
    # Sort by date, etc.
    articles.sort(key=lambda x: x.get('date'), reverse=True)
    return render(request, 'blog/article_list.html', {'articles': articles})

def blog_home(request):
    """Blog home page with featured content"""
    articles = []
    for filename in os.listdir(ARTICLES_DIR):
        if filename.endswith('.md'):
            post = frontmatter.load(os.path.join(ARTICLES_DIR, filename))
            articles.append(post)
    
    # Sort by date
    articles.sort(key=lambda x: x.get('date'), reverse=True)
    
    context = {
        'featured_articles': articles[:3],
        'recent_articles': articles[3:9],
    }
    return render(request, 'blog/home.html', context)
