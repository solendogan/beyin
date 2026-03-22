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

**What a pack is:** a list of URLs and some metadata. Nothing is stored in the pack itself — Brainpack downloads and processes everything on the user's own machine.

**What's allowed:** links to public YouTube videos, public articles, public websites. That's it.

**What's not allowed:** pasting in full article text, uploading transcripts or audio files, linking to paywalled or private content you copied somewhere.

**We will remove packs that:** spread malware, pretend to be someone they're not, use misleading descriptions, or link to illegal content.

**By submitting:** you're confirming the sources are public and you're not copying content you don't have permission to share.
