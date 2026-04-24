---
name: example-skill
description: An example skill demonstrating the PAOS skill system. Use as a template for creating new skills.
version: 1.0.0
---

# Example Skill

This is a minimal example skill for PAOS. It demonstrates the SKILL.md format and how skills are discovered by the PAOS skill registry.

## What This Skill Does

Provides a hello-world example that can be called via the PAOS skills API.

## When to Use

When you want to test the skill system or use it as a template for building your own skills.

## How to Create Your Own Skill

1. Create a new directory under `skills/` with a hyphenated name
2. Add a `SKILL.md` file with YAML frontmatter (name + description required)
3. Write your instructions in the Markdown body
4. Optionally add `scripts/`, `references/`, or `assets/` subdirectories
5. Restart PAOS or call `POST /api/v1/skills/reload` to discover it
