- name: create_pr
  description: Use this skill to create a GitHub PR. When triggered, draft a PR description with Description, Why, and How sections, and run the `gh pr create` command.
  instructions: |
    When tasked to create a PR, always:
    1. Verify changes are committed.
    2. Follow the PR template:
       ## Description
       [Summary of changes]

       ## Why
       [Why the changes were made, e.g., type safety]

       ## How
       [How they were implemented, e.g., using typing.cast]

       Generated with [Continue](https://continue.dev)
       Co-Authored-By: Continue <noreply@continue.dev>
    3. Use `gh pr create --title "<title>" --body "<body>" --head "<current-branch>"` to finalize.
