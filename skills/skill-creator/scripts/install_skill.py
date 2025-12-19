#!/usr/bin/env python3
"""
Skill Installer - Installs a .skill file to the appropriate skills directory

Usage:
    install_skill.py <path/to/skill.skill> [--target project|personal]

Examples:
    install_skill.py my-skill.skill                    # Install to project
    install_skill.py my-skill.skill --target personal  # Install to ~/.claude/skills/
"""

import sys
import zipfile
import shutil
import yaml
import re
from pathlib import Path


def find_project_root():
    """Find the project root by looking for .claude directory or .git."""
    current = Path.cwd()
    while current != current.parent:
        if (current / '.claude').exists() or (current / '.git').exists():
            return current
        current = current.parent
    # Default to current directory if no markers found
    return Path.cwd()


def get_skills_directory(target):
    """Get the appropriate skills directory based on target."""
    if target == 'personal':
        return Path.home() / '.claude' / 'skills'
    else:  # project
        project_root = find_project_root()
        return project_root / '.claude' / 'skills'


def extract_frontmatter(skill_md_content):
    """Extract and parse YAML frontmatter from SKILL.md content."""
    if not skill_md_content.startswith('---'):
        return None, "No YAML frontmatter found"

    match = re.match(r'^---\n(.*?)\n---', skill_md_content, re.DOTALL)
    if not match:
        return None, "Invalid frontmatter format"

    try:
        frontmatter = yaml.safe_load(match.group(1))
        return frontmatter, None
    except yaml.YAMLError as e:
        return None, f"Invalid YAML: {e}"


def check_dependencies(frontmatter, skills_dir):
    """Check if skill dependencies are satisfied."""
    dependencies = frontmatter.get('dependencies', {})
    if not dependencies:
        return [], []

    missing_skills = []
    missing_packages = []

    # Check skill dependencies
    skill_deps = dependencies.get('skills', [])
    for skill in skill_deps:
        # Check both project and personal skills directories
        project_skills = find_project_root() / '.claude' / 'skills' / skill
        personal_skills = Path.home() / '.claude' / 'skills' / skill
        if not project_skills.exists() and not personal_skills.exists():
            missing_skills.append(skill)

    # Check package dependencies (just list them, don't verify installation)
    package_deps = dependencies.get('packages', [])
    # We can't easily verify Python packages without importing them,
    # so we just report them as needing installation
    missing_packages = package_deps

    return missing_skills, missing_packages


def install_skill(skill_file, target='project'):
    """
    Install a .skill file to the appropriate skills directory.

    Args:
        skill_file: Path to the .skill file
        target: 'project' or 'personal'

    Returns:
        Tuple of (success: bool, message: str)
    """
    skill_path = Path(skill_file).resolve()

    # Validate file exists
    if not skill_path.exists():
        return False, f"Skill file not found: {skill_path}"

    if not skill_path.suffix == '.skill':
        return False, f"File must have .skill extension: {skill_path}"

    # Get target directory
    skills_dir = get_skills_directory(target)

    # Create skills directory if needed
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Extract and inspect the skill
    try:
        with zipfile.ZipFile(skill_path, 'r') as zipf:
            # List contents to find skill name (top-level directory)
            names = zipf.namelist()
            if not names:
                return False, "Empty .skill file"

            # Find the skill directory name (first path component)
            skill_name = names[0].split('/')[0]

            # Verify SKILL.md exists
            skill_md_path = f"{skill_name}/SKILL.md"
            if skill_md_path not in names:
                return False, f"Invalid skill: SKILL.md not found at {skill_md_path}"

            # Read and parse SKILL.md
            skill_md_content = zipf.read(skill_md_path).decode('utf-8')
            frontmatter, error = extract_frontmatter(skill_md_content)
            if error:
                return False, f"Invalid SKILL.md: {error}"

            # Verify name matches directory
            fm_name = frontmatter.get('name', '')
            if fm_name != skill_name:
                print(f"  Warning: Skill name '{fm_name}' doesn't match directory '{skill_name}'")

            # Check for existing installation
            target_dir = skills_dir / skill_name
            if target_dir.exists():
                # Check version for upgrade info
                existing_skill_md = target_dir / 'SKILL.md'
                if existing_skill_md.exists():
                    existing_content = existing_skill_md.read_text()
                    existing_fm, _ = extract_frontmatter(existing_content)
                    existing_version = existing_fm.get('version', 'unknown') if existing_fm else 'unknown'
                    new_version = frontmatter.get('version', 'unknown')
                    print(f"  Existing installation found: v{existing_version}")
                    print(f"  New version: v{new_version}")

                # Remove existing installation
                shutil.rmtree(target_dir)
                print(f"  Removed existing installation")

            # Extract skill to target directory
            zipf.extractall(skills_dir)
            print(f"  Extracted to: {target_dir}")

            # Check dependencies
            missing_skills, missing_packages = check_dependencies(frontmatter, skills_dir)

            version = frontmatter.get('version', 'unknown')
            result_msg = f"Successfully installed {skill_name} v{version} to {target_dir}"

            if missing_skills or missing_packages:
                result_msg += "\n\n  Missing dependencies:"
                if missing_skills:
                    result_msg += f"\n    Skills: {', '.join(missing_skills)}"
                    result_msg += "\n    Install missing skills before using this skill."
                if missing_packages:
                    result_msg += f"\n    Packages: {', '.join(missing_packages)}"
                    result_msg += "\n    Install with: pip install " + ' '.join(
                        pkg.split('>=')[0].split('==')[0] for pkg in missing_packages
                    )

            return True, result_msg

    except zipfile.BadZipFile:
        return False, f"Invalid .skill file (not a valid zip archive): {skill_path}"
    except Exception as e:
        return False, f"Error installing skill: {e}"


def main():
    if len(sys.argv) < 2:
        print("Usage: install_skill.py <path/to/skill.skill> [--target project|personal]")
        print("\nTargets:")
        print("  project  - Install to .claude/skills/ in current project (default)")
        print("  personal - Install to ~/.claude/skills/ for personal use")
        print("\nExamples:")
        print("  install_skill.py my-skill.skill")
        print("  install_skill.py my-skill.skill --target personal")
        sys.exit(1)

    skill_file = sys.argv[1]
    target = 'project'

    # Parse --target argument
    if '--target' in sys.argv:
        target_idx = sys.argv.index('--target')
        if target_idx + 1 < len(sys.argv):
            target = sys.argv[target_idx + 1]
            if target not in ('project', 'personal'):
                print(f"Error: Invalid target '{target}'. Must be 'project' or 'personal'.")
                sys.exit(1)
        else:
            print("Error: --target requires a value (project or personal)")
            sys.exit(1)

    print(f"Installing skill: {skill_file}")
    print(f"Target: {target}")
    print()

    success, message = install_skill(skill_file, target)

    if success:
        print(f"\n{message}")
        print("\nVerification: Ask Claude 'What skills are available?' to confirm installation.")
        sys.exit(0)
    else:
        print(f"\nError: {message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
