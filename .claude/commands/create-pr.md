---
description: Create a GitHub PR with a standardized Description/Why/How template
argument-hint: [title]
---

Create a GitHub pull request for the current branch's changes.

1. Run `git status`, `git diff`, and `git log` (and `git diff <base-branch>...HEAD`) to see all
   staged/unstaged/untracked changes and the full commit history for this branch. If there are
   uncommitted changes, stop and ask the user whether to commit them first — do not commit on
   their behalf without confirmation.
2. Confirm the current branch is not `main`/`master`. If it is, ask the user what branch to use
   before continuing.
3. Check whether the branch has an upstream and is up to date. If it needs to be pushed, confirm
   with the user before running `git push` (push is a visible, hard-to-reverse action).
4. Draft the PR body using this exact template:

   ## Description
   [Summary of the changes]

   ## Why
   [Why the changes were made]

   ## How
   [How they were implemented]

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   Co-Authored-By: Claude <noreply@anthropic.com>

5. Search the repo for a PR template (`pull_request_template.md` or `.github/PULL_REQUEST_TEMPLATE/`)
   and fold in any required sections.
6. Create the PR with:
   `gh pr create --title "<title>" --body "<body>" --head "<current-branch>"`
   Use `$ARGUMENTS` as the title if provided; otherwise infer a concise (<70 char) title from the
   commit history.
7. Report the resulting PR URL back to the user.