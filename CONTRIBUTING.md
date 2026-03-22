# Contributing to Brainpack

## Adding a pack to the registry

Open a [Pack Submission issue](../../issues/new?template=pack-submission.yml) and fill in the form. No fork or code required. If accepted, the pack will be added to the registry.

### What makes a good pack

- Focused on a clear topic or creator
- Sources are public and unlikely to disappear
- Description tells users what they'll be able to ask about
- Tags help people discover it

### What a pack must not include

- Full video or audio files you do not own
- Copied article bodies or transcripts
- Paywalled content copied in full
- Private or restricted content

**References are fine. Hosted copies of third-party content are not.**

### Test locally before submitting

```bash
brainpack add ./packs/your-pack-id.yaml
brainpack build your-pack-id
brainpack query your-pack-id "test question"
```

---

## Contributing code

1. Fork the repo
2. Create a branch
3. Make your changes and run tests: `uv run pytest`
4. Open a PR — the template will guide you

For larger changes, open an issue first to discuss the approach.
