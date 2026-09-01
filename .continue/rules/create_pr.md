- name: create_pr
  description: Use this skill to create a GitHub PR. When triggered, draft a PR description with Description, Why, and How sections, and run the `gh pr create` command.
  instructions: |
    When tasked to create a PR, always:
    1. Run `git status`, `git diff`, and `git log` (and `git diff <base-branch>...HEAD`) to review
       all staged/unstaged/untracked changes and the full commit history for this branch. If there
       are uncommitted changes, stop and ask the user whether to commit them first — never commit
       on their behalf without confirmation.
    2. Confirm the current branch is not `main`/`master`. If it is, ask the user what branch to use
       before continuing.
    3. Check whether the branch has an upstream and is up to date. If it needs to be pushed,
       confirm with the user before running `git push` — pushing is a visible, hard-to-reverse
       action.
    4. Search the repo for a PR template (`pull_request_template.md` or
       `.github/PULL_REQUEST_TEMPLATE/`) and fold in any required sections, then follow this
       template:
       ## Description
       [Summary of changes]

       ## Why
       [Why the changes were made, e.g., type safety]

       ## How
       [How they were implemented, e.g., using typing.cast]

       Generated with [Continue](https://continue.dev)
       Co-Authored-By: Continue <noreply@continue.dev>
    5. Use `gh pr create --title "<title>" --body "<body>" --head "<current-branch>"` to finalize.
    6. Report the resulting PR URL back to the user.
