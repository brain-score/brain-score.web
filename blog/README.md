# Brain-Score Blog

A simple markdown-based blog system integrated with the Brain-Score website.

## How to Use

### Adding Articles

1. Create a new markdown file in the `articles/` directory
2. Use the following frontmatter format:

```markdown
---
title: "Your Article Title"
slug: "your-article-slug"
author: "Your Name"
date: "2024-01-01"
category: "Category Name"
excerpt: "Brief summary of the article"
tags: ["tag1", "tag2"]
featured_image: ""
has_interactive_elements: false
custom_css: ""
custom_js: ""
---

# Your Article Content

Write your article content in markdown here.

## Interactive Elements

If you want to add interactive elements, set `has_interactive_elements: true` and add your custom CSS/JS in the frontmatter.
```

### URLs

- `/blog/` - Blog home page
- `/blog/articles/` - List of all articles
- `/blog/article/your-slug/` - Individual article page

### Features

- **Markdown Support**: Full markdown rendering with syntax highlighting
- **Interactive Elements**: Support for custom CSS and JavaScript per article
- **Brain-Score Integration**: Uses the same styling and layout as the main site
- **No Database Required**: All content is stored in markdown files

### Dependencies

The blog requires these Python packages (install separately if needed):
- `markdown`
- `python-frontmatter`

Install with: `pip install markdown python-frontmatter` 