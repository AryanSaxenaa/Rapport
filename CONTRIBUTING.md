# Contributing to Rapport

Thanks for your interest in contributing. Rapport is an open-source desktop app for relationship intelligence, and we welcome improvements of all sizes.

## Getting Started

1. Fork the repository
2. Clone your fork:

```bash
git clone https://github.com/YOUR_USERNAME/rapport.git
cd rapport
```

3. Install dependencies:

```bash
npm install
pip install -r python-sidecar/requirements.txt
```

4. Copy `.env.example` to `.env` and fill in your API keys
5. Run in development mode:

```bash
npm run dev
```

## Development Workflow

- **Frontend** lives in `src/` (Electron + React + TypeScript)
- **Backend** lives in `python-sidecar/` (FastAPI + Python)
- Run the sidecar alone with `npm run sidecar`
- Verify builds work with `npm run build`
- Read [ARCHITECTURE.md](docs/ARCHITECTURE.md) for the system design

## Before Submitting

- Make sure `npm run build` succeeds (TypeScript compilation + Vite build)
- Check that your changes work against a running sidecar
- If you add new Python dependencies, update `python-sidecar/requirements.txt`

## Pull Requests

- Keep PRs focused on a single change
- Reference any related issues
- A maintainer will review and merge if everything looks good

## Code Style

- TypeScript files use the project's `tsconfig.json` settings
- Python files in the sidecar follow the project's conventions (no formatter is enforced yet)
- Follow the patterns you see in existing code

## Questions?

Open an issue or start a discussion in the repository.
