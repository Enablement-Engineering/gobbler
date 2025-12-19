#!/usr/bin/env python3
"""
Quick validation script for skills - minimal version
"""

import sys
import os
import re
import yaml
from pathlib import Path

def validate_skill(skill_path):
    """Basic validation of a skill"""
    skill_path = Path(skill_path)

    # Check SKILL.md exists
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return False, "SKILL.md not found"

    # Read and validate frontmatter
    content = skill_md.read_text()
    if not content.startswith('---'):
        return False, "No YAML frontmatter found"

    # Extract frontmatter
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"

    frontmatter_text = match.group(1)

    # Parse YAML frontmatter
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            return False, "Frontmatter must be a YAML dictionary"
    except yaml.YAMLError as e:
        return False, f"Invalid YAML in frontmatter: {e}"

    # Define allowed properties
    ALLOWED_PROPERTIES = {'name', 'description', 'license', 'allowed-tools', 'metadata', 'version', 'dependencies'}

    # Check for unexpected properties (excluding nested keys under metadata)
    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        return False, (
            f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(unexpected_keys))}. "
            f"Allowed properties are: {', '.join(sorted(ALLOWED_PROPERTIES))}"
        )

    # Check required fields
    if 'name' not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if 'description' not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    # Extract name for validation
    name = frontmatter.get('name', '')
    if not isinstance(name, str):
        return False, f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if name:
        # Check naming convention (hyphen-case: lowercase with hyphens)
        if not re.match(r'^[a-z0-9-]+$', name):
            return False, f"Name '{name}' should be hyphen-case (lowercase letters, digits, and hyphens only)"
        if name.startswith('-') or name.endswith('-') or '--' in name:
            return False, f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens"
        # Check name length (max 64 characters per spec)
        if len(name) > 64:
            return False, f"Name is too long ({len(name)} characters). Maximum is 64 characters."

    # Extract and validate description
    description = frontmatter.get('description', '')
    if not isinstance(description, str):
        return False, f"Description must be a string, got {type(description).__name__}"
    description = description.strip()
    if description:
        # Check for angle brackets
        if '<' in description or '>' in description:
            return False, "Description cannot contain angle brackets (< or >)"
        # Check description length (max 1024 characters per spec)
        if len(description) > 1024:
            return False, f"Description is too long ({len(description)} characters). Maximum is 1024 characters."

    # Validate optional version field (if present)
    version = frontmatter.get('version')
    if version is not None:
        if not isinstance(version, str):
            return False, f"Version must be a string, got {type(version).__name__}"
        # Validate semantic versioning format (MAJOR.MINOR.PATCH with optional prerelease)
        version_pattern = r'^(\d+)\.(\d+)\.(\d+)(-[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)*)?$'
        if not re.match(version_pattern, version):
            return False, f"Version '{version}' must follow semantic versioning (e.g., '1.0.0', '2.1.0-beta')"

    # Validate optional dependencies field (if present)
    dependencies = frontmatter.get('dependencies')
    if dependencies is not None:
        if not isinstance(dependencies, dict):
            return False, f"Dependencies must be an object, got {type(dependencies).__name__}"

        allowed_dep_keys = {'skills', 'packages'}
        unexpected_dep_keys = set(dependencies.keys()) - allowed_dep_keys
        if unexpected_dep_keys:
            return False, (
                f"Unexpected key(s) in dependencies: {', '.join(sorted(unexpected_dep_keys))}. "
                f"Allowed keys are: {', '.join(sorted(allowed_dep_keys))}"
            )

        # Validate skills list
        skills_deps = dependencies.get('skills')
        if skills_deps is not None:
            if not isinstance(skills_deps, list):
                return False, f"dependencies.skills must be a list, got {type(skills_deps).__name__}"
            for skill in skills_deps:
                if not isinstance(skill, str):
                    return False, f"Each skill dependency must be a string, got {type(skill).__name__}"

        # Validate packages list
        packages_deps = dependencies.get('packages')
        if packages_deps is not None:
            if not isinstance(packages_deps, list):
                return False, f"dependencies.packages must be a list, got {type(packages_deps).__name__}"
            for pkg in packages_deps:
                if not isinstance(pkg, str):
                    return False, f"Each package dependency must be a string, got {type(pkg).__name__}"

    return True, "Skill is valid!"

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_validate.py <skill_directory>")
        sys.exit(1)
    
    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)