---
name: git-safe-publish
description: Initialize repositories, inspect local changes, update `.gitignore` or `README.md` when needed, stage only the intended files, write clean commit messages, configure remotes, and push safely. Use when Codex needs to handle first-time git setup, routine commits, selective staging, remote binding, or publishing project changes without accidentally including generated or unrelated files.
---

# Git Safe Publish

Use a clean, reviewable git workflow.

Keep the commit scope intentional. Prefer explicit inspection and explicit staging over fast but noisy git operations.

## Workflow

### 1. Inspect before changing git state

- Start with:
  - current directory
  - `git status --short --branch`
  - `git remote -v`
- If the directory is not a git repository, inspect the top-level project structure before running `git init -b main`.
- Identify generated directories, IDE files, cache folders, build outputs, and other content that should not be committed.
- If the change set introduces new entrypoints, scenes, resources, or demos, check whether `README.md` or project config is now stale.

### 2. Curate the commit scope

- Prefer staging explicit paths.
- Use `git add .` only after confirming the ignore rules are correct and the whole worktree belongs in the commit.
- If unrelated user changes are present, leave them unstaged.
- If a project import changes docs or launch/build settings, include those fixes in the same commit when they are part of making the import usable.

### 3. Normalize repository hygiene

- Update `.gitignore` before staging if the repository would otherwise capture generated content.
- For Unity projects, usually commit:
  - `Assets/`
  - `Packages/`
  - `ProjectSettings/`
  - `.gitignore`
  - `README.md`
- For Unity projects, usually ignore:
  - `Library/`
  - `Temp/`
  - `Logs/`
  - `UserSettings/`
  - generated `*.csproj`
  - generated `*.sln`
  - IDE folders such as `.vscode/`, `.idea/`, `.vs/`

### 4. Write commit messages

- Default to Conventional Commit style:
  - `feat:` for a new usable capability
  - `fix:` for a defect correction
  - `chore:` for setup, imports, scaffolding, repo hygiene, or non-user-facing maintenance
  - `docs:` for documentation-only changes
  - `refactor:` for internal restructuring without changing behavior
- Make the subject line describe the outcome, not the command used.
- Add a body when the commit has multiple meaningful parts.
- Use message bodies like:

```text
feat: add UI Toolkit gradient showcase sample

- add Gradient Showcase scene, assets, and runtime scripts
- include sample scene in build settings
- update README for new UI sample resources
```

### 5. Verify before commit

- Check `git status --short`.
- Check `git diff --cached --stat`.
- Verify that no generated directories or unrelated files are staged.
- Verify that changed docs and config files match the shipped content.

### 6. Publish safely

- If no remote exists, add one with `git remote add origin <url>`.
- If a remote already exists and differs from the target, surface that fact before changing it.
- Use `git push -u origin <branch>` for the first push on a branch.
- Use `git push` for later pushes when tracking is already configured.
- Do not force-push, amend published commits, reset local history, or discard user changes unless explicitly requested.

## Command Pattern

Prefer non-interactive git commands.

Common sequence:

```powershell
git status --short --branch
git remote -v
git add <explicit paths>
git diff --cached --stat
git commit -m "<type>: <summary>"
git push
```

Use `git init -b main` when creating a new repository.

## Reporting

- Report the branch, commit hash, remote URL, and push result.
- Mention whether `README.md`, `.gitignore`, or project config files were updated as part of the publish flow.
- If push fails, report the exact blocker instead of hiding it.

## Typical Requests

- "Initialize this project as a git repo, commit it, and push it to a remote"
- "Commit the newly imported assets and push them"
- "Sort the current changes and commit only the relevant files"
- "Check whether README and .gitignore should be updated before the commit"
