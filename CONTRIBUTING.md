# Contributing to Brainpack

## Adding a pack to the registry

Submitting a pack is simple: open a [Pack Submission issue](../../issues/new?template=pack-submission.yml), paste the sources, add a short description, and submit it. No fork or code required.

If the pack is a good fit, it will be added to the registry.

Maintainers can refer to [REGISTRY-FORMAT.md](REGISTRY-FORMAT.md) for the final pack file structure, versioning, and registry metadata format.

### What makes a good pack

- Focused on a clear topic or creator
- Sources are public and unlikely to disappear
- Description tells users what they'll be able to ask about
- Tags help people discover it

### What to prepare

- A clear pack name
- A short description
- Public source URLs
- A few tags if relevant

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

Packs in this repository contain only source manifests and metadata. Brainpack does not host third-party content, and all retrieval, transcription, indexing, and embedding happen locally on the user's own machine.

### Allowed

- Public YouTube videos and playlists
- Public articles, websites, and RSS feeds
- Metadata such as descriptions, tags, and contributor info

### Not allowed

- Full copied article text or transcripts without permission
- Uploaded audio or video files you do not own
- Paywalled, private, login-protected, or restricted content
- Credentials, tokens, cookies, or session data
- User-built embeddings or vector indexes inside packs

References are fine. Hosted copies of third-party content are not.

### By submitting

- You confirm the sources are public or otherwise permitted to reference
- You are not copying content you do not have permission to share
- The information is accurate to the best of your knowledge

### We may remove packs that

- Spread malware or harmful material
- Impersonate creators or brands
- Use misleading descriptions
- Reference illegal content
- Primarily reproduce or mirror third-party content

### Preferred sources

- publicly accessible sources
- first-party documentation
- open-source content
- Creative Commons or other openly licensed material

### Removal requests

If you are a creator or rights holder and believe a pack references your content in a way that causes harm, contact us. We may review, edit, or remove the pack as appropriate.

Maintainers may reject or remove packs at their discretion.
