# Demo Script

## 90 Second Voiceover

Hi, this is Rapport, an AI relationship memory layer built with HydraDB.

The problem is simple: important relationship context is scattered across emails, meetings, calls, and notes. Before a conversation, we often forget what someone cared about, what concerns they raised, or whether they were a champion, skeptic, or blocker.

Rapport solves this by turning relationship history into persistent, searchable memory.

Here you can see the desktop overlay. It connects to a Python FastAPI sidecar and retrieves real contact memory from HydraDB. The UI immediately shows contacts pulled from stored memory, along with the current data source.

When I select a contact, Rapport shows their profile, stance, company, email, and recent context. The relationship graph visualizes the known contacts and connections, giving a quick map of the relationship network.

The ingest button can pull recent email context, extract useful relationship signals, and write those interactions into HydraDB. That means Rapport keeps improving as more conversations happen.

The live capture mode is designed for calls. While recording, Rapport can listen for commitments, concerns, sentiment shifts, and important people mentioned during the conversation. Those signals are saved back into memory.

The memory button can generate a pre-call brief from HydraDB recall, helping the user prepare with talking points, risks, landmines, and follow-up suggestions.

What makes Rapport different is that it is not just a prompt wrapper. HydraDB acts as the long-term memory system, so context survives across sessions and can be recalled when it is actually useful.

Rapport is built for founders, sales teams, recruiters, community builders, and anyone managing high-context relationships.

In short, Rapport helps you walk into every conversation with memory, context, and confidence.

## 30 Second Version

Rapport is an AI relationship memory overlay built with HydraDB.

It solves a common problem: relationship context is scattered across emails, meetings, and calls. Rapport stores that context as long-term memory and recalls it when you need it.

In the app, real contacts are loaded from HydraDB. Each contact has a stance, profile, and relationship context. The graph shows the relationship network, while email ingest and live capture add new interactions into memory.

Before a call, Rapport can generate a brief with talking points, concerns, risks, and follow-ups.

It is not just a chatbot. It is a memory layer for professional relationships, powered by HydraDB.

## Recording Checklist

1. Run `npm run dev`.
2. Show `Source: hydradb`.
3. Click two or three contact chips.
4. Show the relationship graph.
5. Click `Ingest`.
6. Click `Start`, then `End`.
7. Click `Memory`, type `brief`, and run it.
8. End with: "Rapport helps you walk into every important conversation with context, memory, and confidence."

## Submission Copy

**Tagline:** AI relationship memory that turns emails and calls into live context for better conversations.

**Short description:** Rapport is an AI-powered relationship memory overlay. It uses HydraDB to store and recall context from emails and conversations, then surfaces contacts, relationship graphs, and pre-call briefs in a live desktop UI.

**Thumbnail text:** Rapport - Relationship Memory, Recalled Live.
