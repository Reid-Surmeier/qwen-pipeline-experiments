# Qwen pipeline procedure qualification

This repository is the application-side evidence for one question: can a new agent use the reusable Qwen pipeline correctly without learning hidden rules from old Issues?

## The normal path

1. Read [`qwen-pipeline.json`](qwen-pipeline.json) and its exact [`qwen-pipeline.lock.json`](qwen-pipeline.lock.json).
2. Run the no-cost preflight. It either names the next safe action or explains why the run must stop.
3. For a paid action, write the immutable request and `possibly_spent` event before submitting exactly once through OpenRouter.
4. If authoritative pixels already exist, treat generation as a donor and perform deterministic Assembly before verification.
5. Present a verified candidate to the owner. Only the owner decides whether it looks right.

Start with [`PROCEDURE.md`](PROCEDURE.md). All references, generations, Assembly outputs, checks, and Run Records stay here. The reusable tool repository keeps only generalized rules and neutral tests.

## What the owner should be able to answer

- What is the agent trying to do?
- Which authoritative evidence does it have or still need?
- What happens next, or why did it stop?
- Is money possibly spent?
- What genuine visual decision remains?
Application-side evidence for Qwen Image and Seedance procedure qualification
