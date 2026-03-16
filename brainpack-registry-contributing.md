# Contributing to the Brainpack Registry

## How to submit a pack

1. Fork the registry repository
2. Create a new file under `packs/` named `your-pack-id.yaml`
3. Fill in the required fields (see [pack schema](brainpack-registry-pack-rules.md))
4. Open a pull request

That's it. No account needed, no custom tooling — just a YAML file and a PR.

---

## Adding or updating sources

If you want to add sources to an existing pack you maintain, edit the YAML file, bump the version, update the `updated` date, and open a PR.

If you're improving someone else's pack, add yourself to the `contributors` list.

---

## Review process

A maintainer will check:

- Is the `id` unique and lowercase-hyphenated?
- Is the description clear and accurate?
- Are the sources valid, public, and relevant?
- Does the pack avoid hosting third-party content directly?
- Is the version bumped appropriately?
- Are there any broken, spam, or malicious links?

---

## What makes a good pack

- Focused on a clear topic or creator
- Sources are public and unlikely to disappear
- Description tells users what they'll be able to ask about
- Tags help people discover it

---

## Local testing before submitting

Install and build your pack locally before submitting:

```bash
brainpack add ./packs/your-pack-id.yaml
brainpack build your-pack-id
brainpack query your-pack-id "test question"
```
