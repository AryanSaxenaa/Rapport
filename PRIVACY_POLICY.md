# Privacy Policy

**Effective Date:** May 28, 2026  
**Last Updated:** May 28, 2026

## Overview

Rapport is an open-source desktop application. This privacy policy explains what data Rapport accesses, processes, and stores when you use it.

## Data Rapport Accesses

Rapport may access the following data on your machine:

- **Email content** — When you connect Gmail (via OAuth) or IMAP, Rapport reads your emails to extract relationship signals (contacts, topics, commitments, stance). Email bodies are processed locally and sent to third-party services for AI extraction (see Third-Party Services below).

- **Calendar data** — When you connect Google Calendar, Rapport reads upcoming meeting events to generate pre-call briefs. Calendar event titles, attendee lists, and times are sent to third-party services.

- **Microphone audio** — When you start a live recording, Rapport captures audio from your microphone and sends it to a third-party transcription service (OpenRouter Whisper). Audio is processed in chunks and not stored after transcription.

- **Contact information** — Rapport extracts and stores contact details (name, email, company) from your emails and recordings in a local JSON file and in HydraDB.

## Data Storage

- **Local storage** — Contact data, relationship graphs, and configuration are stored locally on your machine in `rapport_contacts.json` and in the `~/.rapport/` directory.

- **HydraDB** — Relationship memories and extracted signals are stored in your HydraDB tenant. You control your HydraDB API key and tenant.

- **No Rapport servers** — Rapport does not run its own servers. All data processing happens locally or through the third-party services you configure.

## Third-Party Services

When you use Rapport, your data may be sent to:

| Service | What is sent | Purpose |
|---|---|---|
| **OpenRouter** | Text excerpts, audio chunks | LLM extraction and transcription |
| **HydraDB** | Relationship memories, contact metadata | Durable memory storage and recall |
| **Google APIs** | Email headers/bodies, calendar events | Email and calendar ingestion |

Each third-party service has its own privacy policy. You are responsible for reviewing their terms.

## Recording Consent

Rapport captures microphone audio for live transcription. **It is your responsibility to ensure all parties on a call consent to being recorded.** Rapport does not automatically notify other participants. Check your local laws regarding recording consent requirements.

## Data Retention

- Rapport does not automatically delete your data.
- You can delete local contacts and data via the Settings panel (Data Retention section).
- Data stored in HydraDB persists until you delete it through HydraDB.
- IMAP credentials are encrypted at rest on your machine using Fernet encryption.

## Open Source Disclaimer

Rapport is provided as-is under an open-source license. **The developers and contributors of Rapport are not responsible for:**

- Any misuse of the software
- Data loss, unauthorized access, or breaches resulting from your use of Rapport
- Legal consequences arising from recording conversations without consent
- Issues caused by third-party services (OpenRouter, HydraDB, Google)
- Any damages arising from the use or inability to use this software

**This software is provided "AS IS" without warranty of any kind, express or implied.**

## Your Responsibilities

By using Rapport, you agree that:

1. You will comply with all applicable laws regarding recording and data collection
2. You will obtain consent from all parties before recording conversations
3. You will review and accept the privacy policies of third-party services
4. You are solely responsible for the data you choose to ingest and store
5. You will not use Rapport for any illegal purpose

## Changes to This Policy

This privacy policy may be updated at any time. Check the repository for the latest version.

## Contact

For questions about this privacy policy, open an issue at the project's GitHub repository.
