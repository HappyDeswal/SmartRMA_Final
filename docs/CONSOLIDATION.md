# SmartRMA consolidation — 29 October 2026

The rebuilt application has been moved into the original workspace and repository, SmartRMA_Final. It is now the single maintained application. Its three-node responsibilities, ports 8010/8011/8012, local-only model allowlists, T1–T4 decisions, no-login local UI, classifier and training tooling are preserved. HAPPY_* environment names and the internal happy_project health identifier remain compatible implementation identifiers.

The active private SQLite database, original photo blobs, audit key and classifier were copied without rewriting their contents. The old JSON case ledger remains read-only reference data in local legacy_data/; it was not converted into fabricated signed events. Recovery ZIPs for both pre-consolidation versions exist locally under output/backups/. They contain private records and are excluded from Git.

Old standalone node scripts and frontend entry files were retired; use run.py and web/ now. The prior new-project repository is retained as historical Git history; future updates target SmartRMA_Final. Original academic materials remain preserved and do not establish current benchmark performance. No model retraining or new accuracy claim is part of this migration.

Recreate the Python environment from requirements.lock and requirements-hardware.txt after unpacking on another machine. The local Ollama weights remain in the normal Ollama model store.
