# Contributing

Bug fixes, documentation improvements and focused feature proposals are welcome.

1. Fork the repository and create a branch from `main`.
2. Install the dependencies with `python -m pip install -r requirements.txt`.
3. Run `python -m unittest discover -s tests -v` before opening a pull request.
4. Describe the user-visible change and how you verified it.

Tests and examples must use synthetic athlete data. Do not commit real activities,
routes, notes, race plans, reports, email addresses or credentials. Keep local data
under `.private/`, and inspect the complete diff before pushing. If a test needs a
provider response, mock the network request and include only the minimum fictional
fields required by the test.

Use [SECURITY.md](SECURITY.md) for vulnerability reporting. Public issues are fine
for ordinary bugs, but never include secrets or personal fitness data in them.
