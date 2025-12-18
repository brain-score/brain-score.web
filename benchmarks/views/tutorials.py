import os
import re
import unicodedata
import json
from django.shortcuts import render
from django.http import Http404, JsonResponse
from django.conf import settings
import markdown
from html import unescape


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
        html_content = markdown.markdown(
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
        self.content = html_content
        self.description = metadata.get('description', '')
        self.order = int(metadata.get('order', 99))
        self.category = metadata.get('category', 'benchmarks')
        self.next_page = metadata.get('next', '')
        self.prev_page = metadata.get('prev', '')
        
        # Extract searchable content (plain text and headings)
        self.searchable_content = self._extract_searchable_content(content, html_content)
        
    def _extract_searchable_content(self, markdown_content, html_content):
        """Extract searchable text from markdown and HTML for search functionality."""
        # Extract headings from HTML using regex
        headings = []
        heading_pattern = r'<h([1-6])(?:\s+id="([^"]+)")?>([^<]+)</h[1-6]>'
        for match in re.finditer(heading_pattern, html_content):
            level = int(match.group(1))
            heading_id = match.group(2) or ''
            heading_text = unescape(match.group(3)).strip()
            headings.append({
                'level': level,
                'text': heading_text,
                'id': heading_id,
                'slug': heading_id
            })
        
        # Extract code blocks from HTML before removing them (for search)
        code_blocks = []
        
        pre_code_pattern = r'<pre[^>]*>\s*<code[^>]*>([\s\S]*?)</code>\s*</pre>'
        code_block_index = 0
        for match in re.finditer(pre_code_pattern, html_content, re.IGNORECASE | re.DOTALL):
            code_text = match.group(1)
            code_text = re.sub(r'<[^>]+>', '', code_text)
            code_text = unescape(code_text)
            code_text = unescape(code_text)
            code_text_normalized = re.sub(r'\s+', ' ', code_text).strip()
            if code_text_normalized:
                code_blocks.append({
                    'text': code_text_normalized,
                    'index': code_block_index
                })
                code_block_index += 1
        
        html_content = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html_content)
        html_content = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html_content)
        html_for_text = html_content
        html_for_text = re.sub(r'<pre[^>]*>[\s\S]*?</pre>', '', html_for_text)
        html_for_text = re.sub(r'<code[^>]*>[\s\S]*?</code>', '', html_for_text)
        text_content = re.sub(r'<[^>]+>', ' ', html_for_text)
        text_content = unescape(text_content)
        text_content = ' '.join(text_content.split())
        
        markdown_code_blocks = []
        fenced_code_pattern = r'```[\w]*\n([\s\S]*?)```'
        for match in re.finditer(fenced_code_pattern, markdown_content):
            code_text = match.group(1).strip()
            if code_text and len(code_text) > 10:
                markdown_code_blocks.append(code_text)
        
        all_code_blocks = code_blocks.copy()
        current_index = code_block_index
        
        for md_block in markdown_code_blocks:
            md_normalized = re.sub(r'\s+', ' ', md_block.lower().strip())
            is_duplicate = False
            for html_block in code_blocks:
                html_block_text = html_block['text'] if isinstance(html_block, dict) else html_block
                html_normalized = html_block_text.lower().strip()
                if md_normalized in html_normalized or html_normalized in md_normalized:
                    is_duplicate = True
                    break
            if not is_duplicate:
                md_block_normalized = re.sub(r'\s+', ' ', md_block.strip())
                all_code_blocks.append({
                    'text': md_block_normalized,
                    'index': current_index
                })
                current_index += 1
        
        code_text_list = [cb['text'] if isinstance(cb, dict) else cb for cb in all_code_blocks]
        code_text = ' '.join(code_text_list)
        combined_text = f"{text_content} {code_text}".strip()
        
        markdown_text = re.sub(r'```[\s\S]*?```', '', markdown_content)
        markdown_text = re.sub(r'`[^`]+`', '', markdown_text)
        markdown_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', markdown_text)
        markdown_text = re.sub(r'#{1,6}\s+', '', markdown_text)
        markdown_text = ' '.join(markdown_text.split())
        
        # Combine markdown text with code
        markdown_code_text = ' '.join(markdown_code_blocks)
        combined_markdown_text = f"{markdown_text} {markdown_code_text}".strip()
        
        return {
            'text': combined_text,
            'markdown_text': combined_markdown_text,
            'headings': headings,
            'code_blocks': all_code_blocks,
            'full_text': f"{self.title} {self.description} {combined_text}".lower()
        }
        
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
    
    # Prepare search data for all tutorials
    search_data = []
    for t in tutorials:
        search_data.append({
            'slug': t.slug,
            'title': t.title,
            'description': t.description,
            'url': t.get_absolute_url(),
            'searchable': t.searchable_content
        })
    
    context = {
        'tutorials': tutorials,
        'search_data': json.dumps(search_data),  # For search functionality (JSON string)
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
    
    # Prepare search data for all tutorials
    search_data = []
    for t in tutorials:
        search_data.append({
            'slug': t.slug,
            'title': t.title,
            'description': t.description,
            'url': t.get_absolute_url(),
            'searchable': t.searchable_content
        })
    
    context = {
        'tutorial': tutorial,
        'tutorials': tutorials,  # For sidebar navigation
        'prev_tutorial': prev_tutorial,
        'next_tutorial': next_tutorial,
        'search_data': json.dumps(search_data),  # For search functionality (JSON string)
    }
    
    return render(request, 'benchmarks/tutorials/benchmarks/tutorial_detail.html', context)

