---
title: Overhauling the Brain-Score Leaderboard
date: 2025-08-21
author: Brain-Score Team
category: Research, Engineering, New Features
tags: leaderboard, neuroai, ag-grid, platform, benchmarking
excerpt: Transformation of the Brain-Score leaderboard into a dynamic scientific exploration tool for understanding AI and brain alignment.
featured: true
show_on_site: true
---

# Overhauling the Brain-Score Leaderboard

Brain-Score is the benchmarking platform for evaluating how well AI models match biological neural responses and behaviors. At the heart of this scientific endeavor lies the leaderboard - an interface where researchers compare model performance across dozens of behavioral and neural benchmarks spanning vision and language domains.

As the platform expanded to hundreds of models and increasingly complex benchmarks, we recognized that our community needed more than just ranking. Researchers were wondering what is happening under the hood - they wanted tools to investigate why.

Recently, we’ve transformed the leaderboard from a passive display into a powerful exploratory tool, designed to help the community answer these deeper scientific questions with ease.


<div class="comparison-container" style="--comparison-height: 500px;">
  <img src="/static/benchmarks/img/blog/leaderboard_overhaul/leaderboard_after.png" alt="After: New leaderboard design">
  <div class="comparison-before">
    <img src="/static/benchmarks/img/blog/leaderboard_overhaul/leaderboard_before.png" alt="Before: Original leaderboard design">
  </div>
  <div class="comparison-slider"></div>
  <div class="comparison-labels">
    <span class="label">Before</span>
    <span class="label">After</span>
  </div>
</div>

<br>
## Why Change Was Needed

The original leaderboard was a reliable ranking system, but it came with notable limitations:

**1. Static experience -** rankings and scores were locked to a fixed table, making it difficult to explore subsets of interest.

**2. Manual comparisons -** isolating subsets of models or tasks required scraping or exporting the data, and then manually curating metadata.

**3. No filtering -** researchers could not narrow the space by plugin metadata (e.g., by architecture, model size, benchmark task, etc.)

**4. Rigid scoring -** aggregate scores could not be tailored to individual research interests.

**5. Limited interpretability -** the leaderboard showed what works, but offered little help with *why it works* or *where it fails*.

<br>
## What's New

The redesigned leaderboard shares the aesthetic and familiarity of the old leaderboard with an added layer of interactivity and customization that transforms it into a scientific tool:

- **Dynamic filtering and search -** Narrow the search space of models by architecture type, parameter size, training data, or benchmark task directly in the browser. Instantly compare transformers against CNNs on vision tasks.

- **Customizable scoring -** Have a specific research question? Go beyond the default aggregate score by excluding benchmarks and instantly re-weight results.

- **Sharable, persistent views -** Every filter or configuration generates a unique URL, enabling you to:
    - Share a link with your collaborators and see exactly the same filtered view.
    - Bookmark a configuration to revisit later.
    - Embed reproducible views in papers and talks.

- **Public/private view toggle -** Switch seamlessly between viewing only your private models and comparing them against all public models from within your profile leaderboard.

- **Integrated citations -** Instantly export a BibTeX list for all plugins relevant to your current view, that can be pasted directly into your reference manager, simplifying attribution and ensuring contributors receive proper credit.

<br>
## Why It Matters

Science is able to advance rapidly when researchers can ask precise questions and get immediate feedback. The new leaderboard shortens the cycle between idea and insight:

- Instead of spending time writing custom scripts, researchers can conduct exploratory analyses in a few seconds.

- Instead of static scores, results are now tailored to the exact hypotheses being tested.

In practice, this means the leaderboard isn’t just a scoreboard, but a tool for probing the relationship between models and the brain.

<br>
## What Are We Up To Next?

We are actively extending the platform:

- **Benchmark metadata expansion -** Right now, the available metadata is limited. We will be introducing more fields which will allow fine-grained slicing of benchmarks.

- **Streamlined benchmark submissions -** we are working on enabling benchmark submissions directly via the website, alongside metadata extraction. This will lower the barrier for labs to contribute datasets and broaden the benchmark coverage.

<br>
<br>
**Interested In The Technical Blog?** For implementation details keep an eye out on our forthcoming technical blog. Contributions are welcome on [GitHub](https://github.com/brain-score).