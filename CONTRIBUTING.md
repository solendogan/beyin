# Contributing to Brainpack

## Adding a pack to the registry

Open a [Pack Submission issue](../../issues/new?template=pack-submission.yml) and fill in the form. No fork or code required. If accepted, the pack will be added to the registry.

### What makes a good pack

- Focused on a clear topic or creator
- Sources are public and unlikely to disappear
- Description tells users what they'll be able to ask about
- Tags help people discover it

### Test locally before submitting

The easiest way is through an AI agent with Brainpack's MCP server — just say "add this pack, build it, and ask it a test question" and it handles everything.

Or via terminal:

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

---

## Policy

Packs contain source references only — URLs, metadata, tags. All processing happens on the user's machine.

Packs must not include copied article bodies, transcripts, audio or video files, paywalled content, or anything private or restricted. Linking to public content is fine. Hosting copies of it is not.

We will remove packs that contain malware, impersonate creators, use deceptive descriptions, or reference illegal content.

By submitting a pack, you confirm you have the right to reference the included sources and that the information is accurate.
