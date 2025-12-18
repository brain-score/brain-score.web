import os
import re
import unicodedata
from django.shortcuts import render
from django.http import Http404
from django.conf import settings
import markdown


def slugify_heading(value, separator='-'):
    """Convert heading text to a URL-friendly slug."""
    # Normalize unicode characters
    value = unicodedata.normalize('NFKD', str(value))
    value = value.encode('ascii', 'ignore').decode('ascii')
    # Convert to lowercase and replace spaces
    value = value.lower()
    # Remove special characters except alphanumeric and separator
    value = re.sub(r'[^\w\s-]', '', value)
    # Replace whitespace with separator
    value = re.sub(r'[\s_]+', separator, value)
    # Remove leading/trailing separators
    value = value.strip(separator)
    return value


class Tutorial:
    """Represents a single tutorial page loaded from markdown."""
    
    def __init__(self, slug, title, content, metadata, filepath=None):
        self.slug = slug
        self.title = title
        # Convert markdown to HTML with code highlighting
        # Configure codehilite for proper syntax highlighting
        self.content = markdown.markdown(
            content, 
            extensions=[
                'extra',
                'codehilite',
                'fenced_code',
                'tables',
                'toc',
            ],
            extension_configs={
                'codehilite': {
                    'css_class': 'codehilite',
                    'linenums': False,
                    'guess_lang': False,  # Don't guess - prevents ASCII diagrams from being highlighted
                },
                'toc': {
                    'permalink': False,  # We handle permalinks in JS
                    'toc_depth': 4,      # Include h1-h4
                    'slugify': slugify_heading,
                },
            }
        )
        self.description = metadata.get('description', '')
        self.order = int(metadata.get('order', 99))
        self.category = metadata.get('category', 'benchmarks')
        self.next_page = metadata.get('next', '')
        self.prev_page = metadata.get('prev', '')
        
    def get_absolute_url(self):
        return f'/tutorials/benchmarks/{self.slug}/'


def load_benchmark_tutorials():
    """Load all benchmark tutorials from markdown files."""
    tutorial_dir = os.path.join(settings.BASE_DIR, 'tutorial_content', 'benchmarks')
    tutorials = []
    
    if not os.path.exists(tutorial_dir):
        return tutorials
    
    for filename in os.listdir(tutorial_dir):
        if filename.endswith('.md'):
            # Remove .md extension and leading number prefix for slug
            raw_slug = filename[:-3]
            # Remove leading numbers like "01-" for cleaner URLs
            slug = re.sub(r'^\d+-', '', raw_slug)
            filepath = os.path.join(tutorial_dir, filename)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse frontmatter and content
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = parts[1].strip()
                    tutorial_content = parts[2].strip()
                    
                    # Parse frontmatter
                    metadata = {}
                    for line in frontmatter.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            metadata[key.strip()] = value.strip()
                    
                    title = metadata.get('title', slug.replace('-', ' ').title())
                    tutorial = Tutorial(slug, title, tutorial_content, metadata, filepath)
                    tutorials.append(tutorial)
    
    # Sort by order
    tutorials.sort(key=lambda t: t.order)
    return tutorials


def benchmark_tutorial_list(request):
    """Display list of benchmark tutorials (landing page)."""
    tutorials = load_benchmark_tutorials()
    
    context = {
        'tutorials': tutorials,
    }
    
    return render(request, 'benchmarks/tutorials/benchmarks/tutorial_list.html', context)


def benchmark_tutorial_detail(request, slug):
    """Display individual benchmark tutorial page."""
    tutorials = load_benchmark_tutorials()
    tutorial = None
    current_index = -1
    
    for i, t in enumerate(tutorials):
        if t.slug == slug:
            tutorial = t
            current_index = i
            break
    
    if not tutorial:
        raise Http404("Tutorial not found")
    
    # Get previous and next tutorials for navigation
    prev_tutorial = tutorials[current_index - 1] if current_index > 0 else None
    next_tutorial = tutorials[current_index + 1] if current_index < len(tutorials) - 1 else None
    
    context = {
        'tutorial': tutorial,
        'tutorials': tutorials,  # For sidebar navigation
        'prev_tutorial': prev_tutorial,
        'next_tutorial': next_tutorial,
    }
    
    return render(request, 'benchmarks/tutorials/benchmarks/tutorial_detail.html', context)

