# Deployment and recovery

Default: three processes bound to loopback: Node 1 gateway/UI on 8010, Node 2 policy/chat on 8011 and Node 3 vision/inference on 8012. `python3 run.py` starts and supervises all three; `python3 run.py --status` checks them. Reserve all three ports and use one worker per service. Keep Ollama listening only on loopback. Set `OLLAMA_NO_CLOUD=1` when launching Ollama to disable its cloud features as additional service-level configuration. Application transport independently refuses remote/cloud inference. Downloading packages or model weights during setup requires network access; inference does not.

Use an unprivileged operating-system account, a local filesystem and an operating-system process supervisor with automatic restart for `run.py`. If an internal node exits, the launcher stops its own cluster so the supervisor can restart it consistently. Normal shutdown stops only the children launched by that invocation; unrelated services and the original project are untouched. Back up regularly using `manage.py backup`, monitor available disk space, failed jobs and integrity verification, and test restore procedures. There is no automatic deletion of customer history/photos; adopt a reviewed retention policy and restrict disk access. The queue is bounded to 20 active jobs; completed records accumulate on disk.

For access from another computer, terminate HTTPS at a reverse proxy, supply `HAPPY_ORIGIN=https://your-real-host` and `HAPPY_SECURE_COOKIE=1`, and keep the application bound to loopback. Proxy to `127.0.0.1:8010` and preserve the original Host. Set the proxy request-body limit to 27 MiB and allow 150 seconds for chat/photo-question responses. Do not expose internal ports 8011/8012, Ollama or the private data directory. The launcher generates a fresh random internal authentication token for each cluster run; it is never placed in the browser or command-line arguments. No wildcard CORS or trusted forwarded headers are enabled. The same configured origin must be used by the browser. Secure cookies will not work through ordinary HTTP.

Environment:

| Variable | Default | Meaning |
|---|---|---|
| `HAPPY_THREE_NODE` | launcher sets `1` | Normal launcher always uses separate node HTTP providers |
| `HAPPY_LOCAL_AUTO_LOGIN` | `1` | Automatically enter as admin only from loopback with a loopback origin; set `0` to require login |
| `HAPPY_DATA_DIR` | package `var/` | Dedicated private local database/key directory |
| `HAPPY_ORIGIN` | `http://127.0.0.1:8010` | Exact externally visible application origin |
| `HAPPY_SECURE_COOKIE` | `0` | Set `1` for HTTPS; required for non-loopback origins |

A custom data directory must be empty or already marked as a Happy Project directory. Do not point it at the original project's working directory. Only one server may own a data directory. Administrator recovery requires stopping the server and running `manage.py reset-admin` as the data owner; it refuses a second server lock and writes a new private credential file without printing its password.

Restore example, with server stopped and a previously created backup:

```sh
export HAPPY_DATA_DIR=/absolute/path/to/the-backup
python3 manage.py verify
python3 run.py
```

Prefer copying the backup into a fresh private working directory first so the backup remains independent. An audit failure is a failure state, not an invitation to regenerate the key or rewrite signatures. Preserve evidence and restore a verified matching database/key pair. File permissions and HMAC detect some changes; they are not encryption at rest.

Policy maintenance: add reviewed PDF or Markdown text documents to `resources/policies`, preserve their provenance and regional scope, run `manage.py rebuild-policies`, inspect the resulting catalog and restart. Image-only PDFs require offline OCR first; the builder refuses partial replacement if any document fails. Retrieval does not independently prove purchase dates, applicable jurisdiction, item identity or electrical failure.

The live smoke scripts deliberately create clearly labelled demo cases and require the bootstrap credential file. They are opt-in diagnostics, not startup hooks. Regression tests use disposable isolated databases and controlled model fixtures. Never use test fixtures to manufacture approval of an actual customer's T4 case.
