import os
import re
from datetime import datetime
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.views.decorators.cache import cache_page
from django.http import Http404
from django.conf import settings
import markdown


class BlogPost:
    def __init__(self, slug, title, content, metadata, filepath=None):
        self.slug = slug
        self.title = title
        # Convert markdown to HTML
        self.content = markdown.markdown(content, extensions=['extra', 'codehilite'])
        self.excerpt = metadata.get('excerpt', '')
        self.created_at = datetime.strptime(metadata.get('date', '2024-01-01'), '%Y-%m-%d')
        self.author_name = metadata.get('author', 'Brain-Score Team')
        self.category = metadata.get('category', '')
        self.tags = metadata.get('tags', '')
        self.featured = metadata.get('featured', 'false').lower() == 'true'
        self.show_on_site = metadata.get('show_on_site', 'false').lower() == 'true'
        
        # Set updated_at from file modification time or use created_at as fallback
        if filepath and os.path.exists(filepath):
            self.updated_at = datetime.fromtimestamp(os.path.getmtime(filepath))
        else:
            self.updated_at = self.created_at
        
    def get_absolute_url(self):
        return f'/blog/{self.slug}/'
    
    def get_tags_list(self):
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []
    
    def get_categories_list(self):
        if self.category:
            return [category.strip() for category in self.category.split(',')]
        return []
    
    @property
    def reading_time(self):
        """Estimate reading time at 200 words per minute."""
        # Strip HTML tags for accurate word count
        text_content = re.sub(r'<[^>]+>', '', self.content)
        word_count = len(text_content.split())
        return max(1, round(word_count / 200))
    
    @property
    def content_text(self):
        """Return plain text version for searching."""
        return re.sub(r'<[^>]+>', '', self.content)


def load_blog_posts():
    """Load blog posts from markdown files"""
    blog_dir = os.path.join(settings.BASE_DIR, 'blog_posts')
    posts = []
    
    if not os.path.exists(blog_dir):
        return posts
    
    for filename in os.listdir(blog_dir):
        if filename.endswith('.md'):
            slug = filename[:-3]  # Remove .md extension
            filepath = os.path.join(blog_dir, filename)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse frontmatter and content
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = parts[1].strip()
                    post_content = parts[2].strip()
                    
                    # Parse frontmatter
                    metadata = {}
                    for line in frontmatter.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            metadata[key.strip()] = value.strip()
                    
                    title = metadata.get('title', slug.replace('-', ' ').title())
                    post = BlogPost(slug, title, post_content, metadata, filepath)
                    # Only include posts that should be shown on site
                    if post.show_on_site:
                        posts.append(post)
    
    # Sort by date, newest first
    posts.sort(key=lambda p: p.created_at, reverse=True)
    return posts


def get_categories():
    """Get unique categories from all posts"""
    posts = load_blog_posts()
    categories = set()
    for post in posts:
        for category in post.get_categories_list():
            categories.add(category)
    return sorted(categories)


def blog_list(request):
    """Display list of blog posts with filtering"""
    posts = load_blog_posts()
    
    # Category filtering
    category = request.GET.get('category')
    if category:
        posts = [p for p in posts if category.lower() in [c.lower() for c in p.get_categories_list()]]
    
    # Tag filtering
    tag = request.GET.get('tag')
    if tag:
        posts = [p for p in posts if tag.lower() in [t.lower() for t in p.get_tags_list()]]
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        search_lower = search_query.lower()
        posts = [p for p in posts if 
                search_lower in p.title.lower() or 
                search_lower in p.content_text.lower() or 
                search_lower in p.excerpt.lower()]
    
    # Pagination
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all categories
    categories = get_categories()
    
    # Get featured posts
    featured_posts = [p for p in load_blog_posts() if p.featured][:3] if not category and not tag and not search_query else None
    
    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'categories': categories,
        'featured_posts': featured_posts,
        'current_category': category,
        'current_tag': tag,
        'search_query': search_query,
        'total_posts': len(posts),
    }
    
    return render(request, 'benchmarks/blog/blog_list.html', context)


def blog_detail(request, slug):
    """Display individual blog post"""
    posts = load_blog_posts()
    post = None
    
    for p in posts:
        if p.slug == slug:
            post = p
            break
    
    if not post:
        raise Http404("Blog post not found")
    
    # Get related posts (posts that share at least one category)
    post_categories = set(post.get_categories_list())
    related_posts = [p for p in posts 
                    if p.slug != slug and 
                    bool(set(p.get_categories_list()) & post_categories)][:3]
    
    context = {
        'post': post,
        'related_posts': related_posts,
        'categories': get_categories(),
    }
    
    return render(request, 'benchmarks/blog/blog_detail.html', context)


def blog_category(request, slug):
    """Display posts from a specific category"""
    posts = load_blog_posts()
    category_posts = [p for p in posts 
                     if slug in [c.lower().replace(' ', '-') for c in p.get_categories_list()]]
    
    if not category_posts:
        raise Http404("Category not found")
    
    # Find the original category name from the first post that matches
    category_name = None
    for post in category_posts:
        for cat in post.get_categories_list():
            if cat.lower().replace(' ', '-') == slug:
                category_name = cat
                break
        if category_name:
            break
    
    # Pagination
    paginator = Paginator(category_posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'categories': get_categories(),
        'current_category': category_name,
        'total_posts': len(category_posts),
    }
    
    return render(request, 'benchmarks/blog/blog_category.html', context)


def blog_tag(request, tag):
    """Display posts with a specific tag"""
    posts = load_blog_posts()
    tag_posts = [p for p in posts if tag.lower() in [t.lower() for t in p.get_tags_list()]]
    
    if not tag_posts:
        raise Http404("No posts found with this tag")
    
    # Pagination
    paginator = Paginator(tag_posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'categories': get_categories(),
        'current_tag': tag,
        'total_posts': len(tag_posts),
    }
    
    return render(request, 'benchmarks/blog/blog_tag.html', context)
