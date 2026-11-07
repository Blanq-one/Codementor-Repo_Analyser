# Results

Every number or claim here comes from a command that can be re-run.

### Fix: default embedding provider is hash
- Value: a fresh setup no longer crashes on first index
- Command: `python -m pytest tests/test_config.py`
- Dataset/repo: none (config defaults with env vars unset)
- Date: 2026-10-03
- Commit: e4ba06e
- Notes: Render also sets CODEATLAS_EMBEDDING_PROVIDER=hash explicitly

### Fix: /files/content only returns files inside the indexed repo
- Value: absolute paths, ../ traversal and missing files all return 404; real in-repo files return 200
- Command: `python -m pytest tests/test_safe_join.py`
- Dataset/repo: pytest temp directories, plus a manual check on a small public repo via /docs
- Date: 2026-10-03
- Commit: 219b062
- Notes: symlink test skips on Windows (needs privileges) and runs on Linux CI; project needs Python 3.11+

### Fix: repo cloning has time, size and file-count limits with friendly errors
- Value: invalid URLs get 400, missing/private repos 404, repos over the size or file limit 413, and slow clones 504. Each returns a plain-English `detail` string, and any partial clone is deleted
- Command: `python -m pytest tests/test_git_loader.py`
- Dataset/repo: small local git repos created in pytest temp directories, plus a manual check against a nonexistent public GitHub URL and an unresolvable host
- Date: 2026-10-03
- Commit: c52e941
- Notes: limits default to 60 s / 100 MB / 5000 files (CODEATLAS_CLONE_TIMEOUT_SECONDS, CODEATLAS_MAX_REPO_MB, CODEATLAS_MAX_REPO_FILES). Size is checked from git ls-tree before checkout; the download itself is bounded only by the time limit

### Fix: only github.com, gitlab.com and bitbucket.org repository URLs are accepted
- Value: other hosts, lookalike hosts (github.com.evil.example, evilgithub.com, gist.github.com), localhost, raw IPs and non-default ports get a 400 with a plain-English message before any clone starts
- Command: `python -m pytest tests/test_git_loader.py`
- Dataset/repo: URL strings only (no network)
- Date: 2026-10-03
- Commit: fc26951
- Notes: hostnames must match exactly. GitLab `/-/tree/...` and Bitbucket `/src/...` web URLs are normalized to the clone URL

### Fix: file count is checked before file contents are downloaded, and the clone download is capped
- Value: a repo over the file-count limit is rejected after a partial clone that holds only commits and the file list (cpython at a 1,000-file limit: rejected in 1.0 s with only that partial clone run). A download that grows past the cap is stopped partway and deleted (cpython at a 20 MB cap: stopped after 7.2 s, folder removed)
- Command: `python -m pytest tests/test_git_loader.py` (local repos), plus manual `GitRepositoryLoader(...).load("https://github.com/python/cpython")` runs with low limits
- Dataset/repo: local git repos in pytest temp directories, with and without partial-clone support; public github.com/python/cpython for the manual runs
- Date: 2026-10-03
- Commit: 5956bd6
- Notes: what is limited: file count (before any file contents are downloaded, on hosts that support partial clone), bytes downloaded (CODEATLAS_MAX_DOWNLOAD_MB, default 2x CODEATLAS_MAX_REPO_MB, checked about every 0.2 s), total file size (CODEATLAS_MAX_REPO_MB, checked before anything is written to the working tree), and total time (CODEATLAS_CLONE_TIMEOUT_SECONDS). What is not limited: the size check still needs the contents downloaded first, so a repo under the download cap but over the size limit is downloaded, then deleted. The cap can be overshot by up to 0.2 s of transfer. On hosts without partial clone, the file count is only known after the full download, which is still bounded by the download cap and time limit. The cap counts the whole clone folder, including git's ~20 KB of template files

### Fix: per-client and global request limits on clone and LLM endpoints
- Value: over a limit, /analyze-repo, /ask, /ask/stream, /explain and /generate-code return 429 with a plain-English `detail` ("…Please try again in N seconds.") and a `Retry-After` header that browser code can read through CORS. Browsing endpoints (/repos, /files, /search, …) are not limited
- Command: `python -m pytest tests/test_rate_limit.py`, plus a manual run of `uvicorn codeatlas.app.main:app --no-proxy-headers` with CODEATLAS_LLM_PER_CLIENT_PER_MINUTE=1 (second POST /ask returned 429, `retry-after: 60`, `access-control-expose-headers: Retry-After`)
- Dataset/repo: none (in-process TestClient and a local server)
- Date: 2026-10-03
- Commit: 04ad86f
- Notes: defaults per minute: clones 10 per client / 30 global / 3 at once; LLM 60 per client / 300 global; at most 10,000 clients tracked. The client is the direct connection address unless CODEATLAS_TRUSTED_PROXY_HOPS=N, which takes the entry N from the right of X-Forwarded-For. The startup log states the mode without addresses. Limits live in one process: they reset on restart and multiply with the number of uvicorn workers. The frontend needed no change: chat and indexing errors already show `detail`

### Fix: admin/debug endpoints require an API key; the website's endpoints stay open
- Value: without a valid `X-API-Key`, every admin/debug endpoint returns 401. With no key configured on the server, they return 503 (fail closed). Every endpoint the website calls answers without a key
- Command: `python -m pytest tests/test_auth.py`, plus a manual run of `uvicorn codeatlas.app.main:app` with a throwaway key: anonymous GET /repos and /eval/stats returned 200; anonymous GET /metrics, /docs, /openapi.json and POST /search, /dependencies returned 401; the same GETs with the key returned 200; the CORS preflight for /ask returned 200
- Dataset/repo: none (in-process TestClient and a local server)
- Date: 2026-10-03
- Commit: 144ae11
- Notes: an anonymous visitor **can**: index a repo (POST /analyze-repo), chat (POST /ask, /ask/stream), list repos (GET /repos), browse files and read file contents (POST /files, /files/content), view the overview (POST /repo-overview), view the dependency graph (POST /dependencies/graph), and view the eval page stats (GET /eval/stats). Clone and LLM limits from the previous entry still apply. An anonymous visitor **cannot**: call /explain, /search, /generate-code or POST /dependencies; read /metrics; or open /docs, /docs/oauth2-redirect, /redoc or /openapi.json. The key is read from CODEATLAS_API_KEY and is never sent by the frontend; `codementor-ui` is unchanged, and a test checks that `lib/api.ts` only calls the open endpoints and sends no key. CODEATLAS_AUTH_ENABLED now defaults to true; setting it to false opens everything (local development only). docker-compose.yml and docker-compose.monitoring.yml still set it to false, so Prometheus can scrape /metrics without a key there. The Streamlit tool already has an API key field, so it needs the key for its admin calls

### Fix: landing page says plainly what the app does
- Value: the landing subtitle, page `<title>` and meta description now read "Paste a public GitHub repository and ask questions about its code, with answers that cite the files they came from." The filler lines "Agentic codebase intelligence for master developers" (meta description) and "Professional AI Developer Environment" (footer) are gone
- Command: `python -m pytest`, `ruff check codeatlas tests`, `ruff format --check codeatlas tests`, and in `codementor-ui`: `npm run lint` (0 errors; the same 28 warnings as before the change) and `npm run build`
- Dataset/repo: none (copy change)
- Date: 2026-10-03
- Commit: 5ea7c51
- Notes: the copy claims only what the live chat does today. The website streams answers through /ask/stream, which runs retrieval then the mentor agent, not the full planner/validator pipeline. Citations come from retrieval, so an answer with no matching code has no citations. The workspace welcome modal still describes a planner and "multi-agent AI"; that is outside this change

### Fix: unknown repository ids get a 404 before any language model call
- Value: /ask, /ask/stream, /explain and /generate-code return 404 with "This repository is not indexed on the server. It may have been removed when the server restarted. Go back to the home page and index it again." The model is never called. /ask/stream returns this as a JSON 404 before the stream opens, not as a 200 with an error event. Requests without a repo id (general chat on /ask and /ask/stream) are unchanged
- Command: `python -m pytest tests/test_unknown_repo.py` (fails 5 of 9 without the fix), full `python -m pytest`, `ruff check`, `ruff format --check`, and in `codementor-ui`: `npm run lint` (0 errors, same 28 warnings as before) and `npm run build`. Manual: local `uvicorn` with an empty state folder and fake LLM keys returned 404 for all four endpoints with an unknown id, so no model call was attempted
- Dataset/repo: none (in-process TestClient with stand-ins that record model calls, and a local server)
- Date: 2026-10-03
- Commit: 990ef78
- Notes: "exists" means the repo is in the repo state store, which /analyze-repo fills right after cloning. The LLM client object is still built during dependency setup before the check; building it makes no model call, but on a server with no LLM key configured that setup fails first with a 500, as before this change. The frontend needed no change: the chat already shows a non-200 response's `detail` as "Error: …"

### Feature: "Try an example" button on the landing page
- Value: one click indexes https://github.com/pallets/itsdangerous through the existing POST /analyze-repo flow, then opens the workspace with three suggested questions ("How does Signer create and check a signature?", "What is the difference between Serializer and URLSafeTimedSerializer?", "How does the code detect that a signed value has expired?"). Clicking a suggestion fills the chat input. On a local server the repo indexed in about 3 s: 15 parsed files, 63 dependency edges
- Command: `python -m pytest`, `ruff check codeatlas tests`, `ruff format --check codeatlas tests`, and in `codementor-ui`: `npm run lint` (0 errors, same 28 warnings as before) and `npm run build`. Manual: `curl -X POST localhost:8765/analyze-repo -d '{"repo_url":"https://github.com/pallets/itsdangerous"}'` against a local `uvicorn`, then GET /repos
- Dataset/repo: https://github.com/pallets/itsdangerous (public, BSD-3-Clause, maintained by Pallets)
- Date: 2026-10-03
- Commit: b6b0702
- Notes: no new endpoint. Each click is a normal clone, so it counts against the clone rate limit; /repos returns no URL and repo ids are random, so an earlier copy cannot be reused reliably. Suggestions are saved in localStorage together with the repo id, and the chat shows them only while that repo is the current one and before the first message. The button still uses the current landing flow, which opens the workspace after a fixed animation rather than when indexing finishes (item 4), and the first click after the server sleeps can hit a cold start (item 3). Answer quality for the suggested questions was not checked here because no LLM key is configured locally

### Feature: cold-start message for a sleeping backend; only safe reads are retried
- Value: a request with no answer after 4 s shows "Waking up the server, this can take up to a minute" in a banner at the top of every page, on the landing page's indexing spinner (including the "Try an example" request) and in the chat's thinking spinner. Read-only requests (GET /repos, GET /eval/stats, POST /files, /files/content, /repo-overview, /dependencies/graph) retry network errors and 502/503/504 with backoff (1, 2, 4, then every 8 s) for up to 75 s. POST /analyze-repo, /ask and /ask/stream are sent exactly once and never retried; any HTTP response they get, such as the backend's own 504 for a slow clone, reaches the page unchanged. If the server cannot be reached, the banner and the caller show "Could not reach the server. It may still be starting up. Please wait a minute and try again."
- Command: in `codementor-ui`: `npm test` (8 passed: retry and recovery, gateway retries, deadline, no retry for send-once requests on network and gateway errors, waking state on a slow send-once request, error text, and a check that api.ts sends indexing and chat once), `npm run lint` (0 errors, same 28 warnings as before), `npm run build`; plus `python -m pytest`, `ruff check codeatlas tests`, `ruff format --check codeatlas tests`
- Dataset/repo: none (mocked fetch and timers)
- Date: 2026-10-03
- Commit: 572c561
- Notes: no new dependencies. `npm test` uses Node's built-in test runner with TypeScript type stripping, which needs Node 22.6 or newer; frontend CI pins Node 20 and does not run it. Test files are excluded from the Next.js type check. The POST read endpoints change nothing on the server, so repeating them is safe. Indexing and chat have no client time limit, because the server may need a minute to wake plus up to the clone time limit

### Fix: /analyze-repo answers only when indexing is done; honest progress on the landing page
- Value: POST /analyze-repo now clones, parses, builds the dependency graph and builds the search index before answering, and returns `indexing_status: "ready"`. The repo is saved, and appears in /repos, only after all steps succeed. Indexing has a time limit (CODEATLAS_INDEX_TIMEOUT_SECONDS, default 120), checked between files and between embedding batches of 64. On timeout it returns 504 "Indexing this repository took too long, so it was stopped and nothing was saved. Try a smaller repository."; any other failure returns 500 "Indexing this repository failed, so nothing was saved. Please try again later." In both cases the clone folder and any partial index are deleted. The landing page shows a spinner with "Cloning, parsing and indexing <repo>" instead of the timed progress bar, and opens the workspace only after a success; on failure it stays on the landing page with the error. The "Waking up the server" message now shows only until the server has answered any request in the page session, so normal long indexing shows the indexing text
- Command: `python -m pytest` (130 passed; `tests/test_analyze_indexing.py` covers success and response shape, indexing failure, parse failure, timeout during embedding, timeout after the last batch, no repo visible in the state store or /repos while indexing, FAISS removal, and the config default), `ruff check`, `ruff format --check`, and in `codementor-ui`: `npm test` (10 passed), `npm run lint` (0 errors, same 28 warnings as before), `npm run build`. Manual: local `uvicorn`; https://github.com/pallets/itsdangerous returned 200 `"indexing_status":"ready"` in 2.7 s; https://github.com/pallets/flask with CODEATLAS_INDEX_TIMEOUT_SECONDS=0 returned the 504, and afterwards no clone folder, index files or state for it remained
- Dataset/repo: small Python project written by the test's fake loader; https://github.com/pallets/itsdangerous and https://github.com/pallets/flask for the manual runs
- Date: 2026-10-03
- Commit: e249883
- Notes: the response keeps the same four fields (`repository_id`, `file_count`, `dependency_edges`, `indexing_status`); only the status value changed from "queued" to "ready". The time limit covers the indexing step; cloning has its own limits, and parsing and graph building have none but are bounded by the file-count and size limits. The request holds a clone slot until indexing finishes (measured locally: about 0.1 s of indexing for itsdangerous, 2.5 s for flask, with the default hash embedder). `CodeRetriever` gains an abstract `remove`. "Previously indexed", "Open Coding Workspace" and the welcome popup are unchanged

### Feature: citations open the file preview at the cited lines
- Value: each citation in a chat answer (still inside the "Citations" section) is a button that opens the existing file preview. For a function citation such as `src/itsdangerous/url_safe.py (lines 72-76)`, the preview highlights lines 72-76, scrolls them into view and shows "cited: lines 72-76" in the header. A file citation opens the whole file. Clicking a file in the context panel's retrieved list now also opens at its cited lines (before, the line range was dropped)
- Command: in `codementor-ui`: `npm test` (16 passed, including 6 for the citation parser), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`; plus `python -m pytest`, `ruff check`, `ruff format --check`. Manual: retrieved the citations for two of the example's suggested questions from a local index of pallets/itsdangerous, parsed them with the same rules as `lib/citations.ts`, and posted each path to /files/content on a local `uvicorn`: 10 of 10 returned 200, with every cited range inside the file's line count
- Dataset/repo: https://github.com/pallets/itsdangerous
- Date: 2026-10-03
- Commit: 6aa916f
- Notes: no backend change and no new endpoint; the preview uses POST /files/content, which the website already called. Citation format parsed: "path (lines A-B) | snippet", "path | snippet" or "path". A cited path that is not relative to the repo root (only if the clone folder is outside `.codeatlas/repos`) gets the preview's existing "File not found" error

### Feature: per-stage timing for indexing and chat
- Value: medians in ms on this Windows machine; cold = first request in a fresh process (3 processes), warm = later requests in the same process (6 runs). The model was **not timed**: no GROQ_API_KEY or OPENAI_API_KEY is set here, so the built-in stand-in answered instantly and `llm` below is only LangChain overhead

  | Indexing | clone | parse | graph | read_files | embed | index_write | save_state | total |
  |---|---|---|---|---|---|---|---|---|
  | itsdangerous cold | 1792 | 106 | 23 | 28 | 27 | 7 | 3 | 2013 |
  | itsdangerous warm | 1691 | 97 | 22 | 24 | 25 | 11 | 3 | 1893 |
  | flask cold | 2285 | 809 | 258 | 376 | 263 | 61 | 15 | 4034 |
  | flask warm | 2147 | 820 | 225 | 376 | 260 | 61 | 19 | 3895 |

  | Chat question (model excluded) | embed_query (2 calls) | search (2) | rerank (2) | llm stand-in (3 calls) | first token sent | total |
  |---|---|---|---|---|---|---|
  | itsdangerous cold | 0.4 | 3.5 | 5.7 | 11.0 | 27.0 | 37.0 |
  | itsdangerous warm | 0.3 | 0.4 | 4.7 | 3.1 | 12.2 | 25.5 |
  | flask cold | 0.3 | 4.1 | 7.1 | 7.9 | 24.9 | 34.4 |
  | flask warm | 0.3 | 0.6 | 6.5 | 3.0 | 15.5 | 32.8 |

  Clone is 89% of indexing time for itsdangerous and 55 to 57% for flask. Without the model, a chat question takes under 40 ms. App import and startup took 2.6 to 2.9 s per process
- Command: `python scripts/time_stages.py https://github.com/pallets/itsdangerous --runs 3` and `python scripts/time_stages.py https://github.com/pallets/flask --runs 3`, each run 3 times; plus `python -m pytest` (137 passed; `tests/test_timing.py` covers summing repeated stages, call counts, the no-timer case, thread-pool handoff, every indexing stage in Server-Timing, chat stages in the done event and no question text in logs), `ruff check`, `ruff format --check`, and in `codementor-ui`: `npm test` (16 passed), `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: https://github.com/pallets/itsdangerous (15 files, 63 edges) and https://github.com/pallets/flask (83 files, 432 edges), question "How does Signer create and check a signature?"
- Date: 2026-10-04
- Commit: 64c7ae6
- Notes: /analyze-repo and /ask return a `Server-Timing` header; /ask/stream adds `timings_ms` to its done event; every request logs one `timing <endpoint> stage=ms ...` line with no question, answer or code. `embed` covers the indexing embeddings (hash embedder); `read_files` is reading file contents for them. The streamed chat path calls the model three times per question and none of those calls is streamed from the model: retrieval summarises the snippets, the mentor re-runs retrieval (which summarises again), then the mentor answers. So the time to the first token the user sees is the sum of three full model calls; `first_token_sent` measures that once a key is set, and `first_model_token` is recorded only in general (no-repo) mode, where the model really streams. The answer is then sent 4 words every 8 ms, which adds about 0.8 s for a 400-word answer. Numbers come from an in-process client, so they exclude network time between browser and server, and the clone time depends on this machine's connection to GitHub

### Feature: index cache keyed by repository URL and commit (the only cache built)
- Value: indexing a repository that is already indexed at the same commit takes 687 ms instead of 1,907 ms for itsdangerous (−64%) and 776 ms instead of 4,638 ms for flask (−83%). A repository indexed for the first time pays no extra cost: the lookup is 0.0–0.2 ms and makes no network call. Medians in ms, 3 fresh processes × 3 runs per repo

  | | cache off, warm runs (n=6) | cache on, repeat of an indexed repo (n=6) | cache on, first index (n=3) |
  |---|---|---|---|
  | itsdangerous | 1907 (clone 1706) | 687 (`git ls-remote` 687, lookup 0.2) | 2552 (clone 2324) |
  | flask | 4638 (clone 2347) | 776 (`git ls-remote` 775, lookup 0.2) | 4939 (clone 2475) |

  The cache-on first index is slower than cache-off only because clone times varied between runs (clone 2324 vs 1846 ms cold); it adds no stage beyond the 0.0 ms lookup
- Command: `$env:CODEATLAS_INDEX_CACHE="false"; python scripts/time_stages.py https://github.com/pallets/itsdangerous --runs 3` and the same with `"true"`, each 3 times, and the same for https://github.com/pallets/flask; plus `python -m pytest` (152 passed; `tests/test_index_cache.py` covers a hit, other spellings of the URL, a new commit, a different repo, an unknown remote commit, a missing clone folder or index, the off switch, a restart with the disk kept, an invalid URL, old state files without a commit, no `ls-remote` for a first index, and a real local clone whose recorded commit matches `ls-remote`), `ruff check`, `ruff format --check`, and in `codementor-ui`: `npm test` (16 passed), `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: https://github.com/pallets/itsdangerous and https://github.com/pallets/flask
- Date: 2026-10-04
- Commit: 4e6c097
- Notes: how a hit is decided: same URL after normalising (letter case, trailing `.git`, web paths such as `/tree/main`), the earlier index and clone folder still present, and the commit from `git ls-remote <url> HEAD` equal to the commit checked out when it was indexed. On a hit the response has the same four fields and the earlier `repository_id`, so everyone who indexes the same public repository shares one index; chat history is never stored with it. `ls-remote` takes most of a hit's time; it gets at most 15 s, and any failure falls back to a full index. A hit still counts against the clone rate limit, since it still contacts the host. Two simultaneous first requests for the same repository both index it. CODEATLAS_INDEX_CACHE=false turns the cache off.
  **On a Render restart the cache is lost unless a persistent disk is attached.** The disk must hold CODEATLAS_INDEX_DIR, CODEATLAS_STATE_DIR and the clone folder. Clones always go to `.codeatlas/repos` under the working directory, which is `/app/.codeatlas/repos` in the Docker image. Without such a disk, every entry is missed after a restart and the fallback is a normal full index, which is the old behaviour.
  **Caches skipped:**
  (1) **Query embedding cache**: `embed_query` takes 0.3 ms for 2 calls, about 1% of a 25–37 ms model-free chat question. There is nothing to gain with the hash embedder. It would matter only with `sentence-transformers`, which is not installed.
  (2) **Exact-match answer cache with expiry**: it would skip the model calls, but those could not be timed here because there is no model key. The rest of the question takes 25–37 ms. So the measured gain is about 30 ms, and the rule says skip. Measure the `llm` stage on a server with a key first. If it is built later, it should key on repository id, commit and question, only for a question with no conversation history, and with expiry. It needs no new dependency: an in-process dict is enough, and it is lost on restart.
  (3) **Pre-indexed example repo**: with the index cache, every "Try an example" click after the first already takes about 0.7 s. Indexing at startup would save about 1.9 s on only the first click after each restart. That restart already takes up to a minute to wake on Render. It would cost a clone on every boot, even when nobody visits.
  (4) **Not considered**: a shared cache across server processes or instances, such as Redis, would need a new dependency and an external store.

### Feature: conversation memory for the website chat
- Value: in the streamed chat, the last 4 turns of the same conversation now reach the prompt, capped at about 1,500 tokens (oldest dropped first). A follow-up that leans on earlier turns, such as "what about URLSafeTimedSerializer?", is rewritten into a standalone question for code search. That costs one extra model call; other questions make none. Without the model, the rewrite takes 1.5–1.8 ms (18 follow-ups, 3 fresh processes). The model call itself could not be timed (no key). Its input is the history (at most about 1,500 tokens) plus about 60 tokens of instructions, and its output is one short question. It shows as the `rewrite` stage in `timings_ms` and the log line
- Command: `python scripts/time_stages.py https://github.com/pallets/itsdangerous --runs 3 --follow-up "What about URLSafeTimedSerializer?"` (3 times); `python -m pytest` (181 passed; `tests/test_conversation_memory.py`, 29 tests, covers the turn limit, the token cap and shortening of a single oversized turn, idle expiry, the session-count cap, isolation between sessions, between repositories and between repo and general chat, hashed session keys, when a rewrite happens and when it doesn't, rewrite fallback when the model fails, the rewritten question reaching search while the mentor gets the question as asked plus the history, no memory without a session id, 422 for malformed ids, failed answers not kept, and no conversation text in logs at DEBUG level or in any file written under the test folder); `ruff check`, `ruff format --check`; in `codementor-ui`: `npm test` (19 passed, 3 new for the session id), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`. Manual: local `uvicorn` with no model key: two questions with the same session id. The second one's reasoning steps said "Used 1 earlier turn(s)" and showed the rewrite. A session id `x` returned 422, and a marker word from the questions appeared 0 times in the server log
- Dataset/repo: https://github.com/pallets/itsdangerous; small Python project written by the tests
- Date: 2026-10-04
- Commit: 089a638
- Notes: the chat window makes a random id (`crypto.randomUUID`, or 16 random bytes in hex outside a secure context). It keeps the id in React state for that conversation and sends it as `session_id` on /ask/stream. The id is not stored in localStorage or sessionStorage, so a page reload starts a new chat on screen and a new memory. The server accepts ids matching `^[A-Za-z0-9_-]{16,128}$`. It keys memory by sha256 of id plus repository id, holds it in process memory only, and drops a session after 30 idle minutes or when 1,000 sessions are exceeded (least recently written first). No endpoint returns stored history: a session's turns only go into that session's own prompts. Reading another session's history would require guessing its 122-bit random id. Tokens are estimated as characters ÷ 4 (no tokenizer dependency). The rewrite is used only in repo mode, because only search needs it; general mode passes history as chat messages. Rewriting is decided by a word rule: 3 words or fewer, opening with and/but/so/or/then, starting with "what about"/"how about", or a referring word such as it/that/they/those (but not "this repo"). It errs toward rewriting: a false positive costs one model call, a false negative a weaker search. Failed answers are not kept. Settings: CODEATLAS_CHAT_HISTORY_TURNS, CODEATLAS_CHAT_HISTORY_TOKENS, CODEATLAS_CHAT_SESSION_TTL_SECONDS, CODEATLAS_CHAT_MAX_SESSIONS. **On a Render restart** all memory is lost and the next question starts fresh; there is no fallback store by design. With more than one uvicorn worker, a session's turns stay only in the worker that received them. **Not changed, but conflicts with "no cross-user content":** the existing analytics tracker keeps every question in memory, and the public GET /eval/stats returns the last 20 (first 120 characters) to anyone, so the eval page shows other visitors' questions. /ask (non-streamed, not used by the website) ignores `session_id`. With no model key, the stand-in model's fixed reply becomes the rewritten follow-up, so follow-up citations are poor in that local-only mode

### Fix: public eval stats no longer show other visitors' questions
- Value: GET /eval/stats returns only counts and timings. `recent_queries` entries hold `latency_ms`, `citations` and `timestamp`; question text is gone, and the analytics tracker no longer accepts it at all. The eval page's "Recent Queries" table shows Time, Latency and Citations instead of Question
- Command: `python -m pytest` (183 passed; `tests/test_eval_stats.py` asks marked questions through /ask/stream in repo and general mode and through /ask, then checks the marker is absent from /eval/stats and each recent query has exactly those three fields, and that the tracker takes no question), `ruff check`, `ruff format --check`, and in `codementor-ui`: `npm test` (19 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`. Manual: a local `uvicorn` on port 8000 and `next start` on port 3000. After one marked question, /eval/stats did not contain the marker and returned `{"latency_ms", "citations", "timestamp"}`, and /eval returned 200
- Dataset/repo: none (stand-in model and the tests' small Python project)
- Date: 2026-10-04
- Commit: 574abcf
- Notes: the page fetches the stats in the browser after loading. The 200 for /eval shows the page builds and is served; I did not look at the rendered table in a browser. Existing per-repository stats (name, file and function counts, edges, languages) are unchanged; they describe public repositories, not visitors

### Check: generated folders are ignored by git and nothing generated is staged
- Value: `.gitignore` line 12 (`.codeatlas/`) ignores the clone, index and state folders, including `agent_memory.json`. No file under `.codeatlas` is tracked (0), nothing is staged or untracked, and every file changed on batch-3 since 38662d5 is source, tests, docs or `.env.example`; no `.faiss`, `.pkl` or clone files are tracked. Also ignored: `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`, `codementor-ui/.next/`, `node_modules/`, `next-env.d.ts`, `tsconfig.tsbuildinfo`. No change was needed
- Command: `git check-ignore -v .codeatlas/repos/x .codeatlas/indexes/x.faiss .codeatlas/indexes/x.pkl .codeatlas/state/x.json .codeatlas/state/agent_memory.json`, `git ls-files .codeatlas`, `git status --porcelain`, `git status --short --ignored`, `git diff --name-only 38662d5..HEAD`
- Dataset/repo: this repository's working tree
- Date: 2026-10-04
- Commit: 88855ef (state checked)
- Notes: `scripts/time_stages.py` writes to a temporary folder outside the repo and deletes it afterwards

### Measurement: retrieval baseline on fixed question sets (itsdangerous and flask)
- Value: embedder **hash** (HashEmbeddingService, 384 dims, a hashed bag of words, not a semantic embedding). 40 questions, 20 per repo, split 10 dev / 10 test per repo

  | split | n | hit@1 | hit@3 | hit@5 | P@1 | P@3 | P@5 | MRR@10 |
  |---|---|---|---|---|---|---|---|---|
  | dev | 20 | 0.450 | 0.600 | 0.600 | 0.450 | 0.383 | 0.300 | 0.524 |
  | test (held out) | 20 | 0.400 | 0.550 | 0.700 | 0.400 | 0.400 | 0.400 | 0.496 |
  | all | 40 | 0.425 | 0.575 | 0.650 | 0.425 | 0.392 | 0.350 | 0.510 |

  Per repo, all 20 questions: itsdangerous hit@5 0.700, MRR@10 0.579; flask hit@5 0.600, MRR@10 0.441. A full run of all 40 questions took 4.2–6.1 s on this machine once the two repos were fetched
- Command: `python scripts/eval_retrieval.py --split dev`, the same with `--split test` and `--split all`; plus `python -m pytest` (193 passed; `tests/test_retrieval_eval.py` covers the metric formulas, the question files' pinning and split, rejecting a question with no expected files, fetching a pinned commit once, relative paths and a full run on a small local repo, no question text in the results, and the sorted file walk), `ruff check`, `ruff format --check`, and in `codementor-ui`: `npm test` (19 passed), `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: `eval/questions/itsdangerous.json` (https://github.com/pallets/itsdangerous at 672971d66a2e, 15 files, 159 records indexed) and `eval/questions/flask.json` (https://github.com/pallets/flask at d73fa1cdcbd8, 83 files, 1,705 records indexed)
- Date: 2026-10-05
- Commit: 739a30e (eval added in 7a7a513; 739a30e sorts the parser's file walk and gives the same numbers on Windows)
- Notes: what is scored is `AnswerService.retrieve`, the retrieval step of the chat: embed the question, take the 10 nearest records from FAISS, rerank them by keyword overlap, keep the best. Records are whole files or single functions; each is mapped to its file, and it is relevant if that file is in the question's `expected_files`. hit@k = share of questions with a relevant record in the first k; P@k = relevant records in the first k ÷ k, averaged (two functions from the same right file both count, since both go into the prompt); MRR@10 = mean of 1/rank of the first relevant record in the top 10, 0 if none. "overall" weighs every question the same. I wrote the questions from the source at the pinned commits and fixed the split (alternating, in writing order) before running anything; neither the questions nor the split were changed after seeing results. Expected files are source files only, except one tutorial question in flask. No model key is used. The embedder is whatever the server would use (`CODEATLAS_EMBEDDING_PROVIDER`, default hash); `sentence` was not measured because sentence-transformers is not installed and is not a project dependency. Before 739a30e, reversing the file walk order changed overall P@5 from 0.350 to 0.345 (hit rates and MRR unchanged); the walk is now sorted, so the index no longer depends on the OS. Repos are fetched once into `.codeatlas/eval-repos` (ignored by git)

### Measurement: retrieval tuning experiments (dev set), confirmed on the held-out test set
- Value: of 14 experiments, 6 met the keep rule on dev (E1, E7, E9, E11, E12, E14). Two of those were removals or noise: E7 was later reversed by E14, and E12 is smaller than one question moving one rank. One more (E13) met the rule but was **not adopted** (see Notes). The clear wins are E9 (identifier parts in the hash embedder, dev MRR@10 +0.060) and E11 (stopwords left out of the search question, +0.042), with E1 (search depth 20) adding 3 more dev hits at 5. Final settings on the **held-out test set**: hit@1 0.400 → 0.600, hit@3 0.550 → 0.650, hit@5 0.700 → 0.750, P@3 0.400 → 0.533, MRR@10 0.496 → 0.645. Embedder: hash (HashEmbeddingService, 384 dims), before and after

  Keep rule, fixed before the first run: keep a change only if overall dev MRR@10 goes up and dev hit@5 does not go down. Each experiment changes one setting on top of the best so far. All runs are on commit 07689b1, which added the settings with defaults equal to the old behaviour; flags are added to `python scripts/eval_retrieval.py --split dev`

  | # | change (flag) | on top of | dev hit@1 | hit@5 | MRR@10 | result |
  |---|---|---|---|---|---|---|
  | – | baseline (no flags) | – | 0.450 | 0.600 | 0.524 | |
  | E1 | `--candidates 20` (search depth 10 → 20 before rerank) | baseline | 0.400 | 0.750 | 0.530 | kept |
  | E2 | `--candidates 30` | E1 | 0.400 | 0.700 | 0.521 | rejected |
  | E3 | `--rerank-weight 0.0` (vector order only, no keyword rerank) | E1 | 0.300 | 0.500 | 0.404 | rejected |
  | E4 | `--rerank-weight 0.5` (half keyword overlap, half vector similarity) | E1 | 0.400 | 0.700 | 0.524 | rejected |
  | E5 | `--rerank-weight 0.8` | E1 | 0.400 | 0.750 | 0.530 | rejected (tie) |
  | E6 | `--embed-max-chars 2000` (embed only the first 2,000 chars) | E1 | 0.450 | 0.700 | 0.554 | rejected (hit@5 fell) |
  | E7 | `--embed-max-chars 8000` | E1 | 0.400 | 0.750 | 0.534 | kept, reversed by E14 |
  | E8 | `--hash-lowercase on` | E1+E7 | 0.450 | 0.700 | 0.537 | rejected (hit@5 fell) |
  | E9 | `--hash-subtokens on` (verify_signature also counts verify, signature) | E1+E7 | 0.450 | 0.750 | 0.594 | kept |
  | E10 | `--rerank-subtokens on` (same, in the keyword rerank) | E1+E7+E9 | 0.400 | 0.800 | 0.560 | rejected |
  | E11 | `--drop-stopwords on` | E1+E7+E9 | 0.550 | 0.750 | 0.636 | kept |
  | E12 | `--prefix-metadata on` (file path and function name before the embedded text) | E1+E7+E9+E11 | 0.550 | 0.750 | 0.6375 (vs 0.6363) | kept, noise-sized |
  | E13 | `--skip-tests on` (drop records from test files) | E1+E7+E9+E11+E12 | 0.600 | 0.850 | 0.685 | met the rule, not adopted |
  | E14 | remove E7 again (no text limit) | E1+E9+E11+E12 | 0.600 | 0.750 | 0.6625 | kept |

  Ablations on dev of the final settings, for information: without E12 MRR@10 0.6613 (vs 0.6625); without E1 0.6167 with hit@5 0.700. Final settings, no flags, at 513641c:

  | split | n | hit@1 | hit@3 | hit@5 | P@1 | P@3 | P@5 | MRR@10 |
  |---|---|---|---|---|---|---|---|---|
  | dev | 20 | 0.600 | 0.700 | 0.750 | 0.600 | 0.483 | 0.380 | 0.662 |
  | test (held out) | 20 | 0.600 | 0.650 | 0.750 | 0.600 | 0.533 | 0.420 | 0.645 |
  | all | 40 | 0.600 | 0.675 | 0.750 | 0.600 | 0.508 | 0.400 | 0.654 |

  Per repo on the test set: itsdangerous hit@5 0.800 → 0.900, MRR@10 0.608 → 0.820; flask hit@5 0.600 → 0.600, MRR@10 0.383 → 0.470
- Command: experiments: `python scripts/eval_retrieval.py --split dev <flags in the table>` at 07689b1; held-out check before the defaults changed: `python scripts/eval_retrieval.py --split test --candidates 20 --hash-subtokens on --drop-stopwords on --prefix-metadata on` at 07689b1 (same numbers as the no-flag run at 513641c); final: `python scripts/eval_retrieval.py --split dev`, `--split test`, `--split all` at 513641c; chat timing: `python scripts/time_stages.py https://github.com/pallets/itsdangerous --runs 3`, 3 times; plus `python -m pytest` (206 passed; `tests/test_retrieval_settings.py` covers each setting and the server defaults, `tests/test_index_cache.py` adds two cache-miss tests), `ruff check`, `ruff format --check`, and in `codementor-ui`: `npm test` (19 passed), `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: `eval/questions/itsdangerous.json` and `eval/questions/flask.json` (pinned at 672971d66a2e and d73fa1cdcbd8)
- Date: 2026-10-05
- Commit: 07689b1 (settings, experiments), 513641c (tuned defaults)
- Notes: the test split was run twice: once to confirm the final settings and once with E13 added, for information; nothing was changed after seeing test results. **E13 not adopted:** it raised dev MRR@10 to 0.685 and test MRR@10 to 0.725 (hit@5 0.800), but my labels list source files as the right answer (one tutorial file aside), so part of that gain comes from how I labelled the questions, which the held-out set shares. It would also stop the chat from ever citing a test file, even for "how is X tested?". It is off by default (`skip_tests` in `AppConfig`) for you to decide. **Small samples:** each split has 20 questions, so one question is 0.05 of hit rate; E1's MRR gain (+0.006), E7 (+0.004) and E12 (+0.0012) are within one question moving a rank or two. The greedy order matters: E7 helped when added and hurt in the final combination (E14). **Cost:** with search depth 20 the rerank reads twice as many snippets: a model-free itsdangerous chat question now takes a median 45 ms warm (rerank 19 ms) vs 25.5 ms (rerank 4.7 ms) in the per-stage timing entry above; the model is still not timed. **Index cache:** the embedder change alters vectors, so each repo state now records an index format (`hash:384:lowercase=0:subtokens=1|max_chars=None|prefix=1`) and the cache reuses only an index with the same format; state saved before this has none and is indexed again. An index that is already loaded (not via the cache) keeps its old vectors until the repo is indexed again; on Render without a disk every restart drops them anyway. The `sentence` embedder was not measured; stopword removal and the path prefix apply to it too

### Measurement: chat latency from scripts/benchmark.py (local server, model not timed)
- Value: **the language model is not in these numbers**: no model key is set here, so the server used its stand-in, and the script reported "model: NOT TIMED". Milliseconds, measured by the client over HTTP to `uvicorn` on this Windows machine, POST /ask/stream about pallets/itsdangerous, 5 fresh server processes × 3 questions per benchmark, benchmark run twice (repeat 1 / repeat 2)

  | | n | TTFB p50 | TTFB p95 | first answer token p50 | p95 | total p50 | total p95 |
  |---|---|---|---|---|---|---|---|
  | cold (first question after a server start) | 5 | 35.8 / 32.8 | 52.0 / 51.0 | 89.7 / 96.1 | 121.3 / 148.7 | 95.9 / 102.8 | 130.7 / 164.4 |
  | warm | 10 | 7.9 / 11.0 | 38.9 / 29.7 | 47.5 / 45.4 | 80.1 / 69.1 | 65.6 / 63.2 | 98.3 / 74.9 |

  Server start until /repos answered: p50 2,168 / 2,654 ms. /analyze-repo (full index, fresh server each time): p50 1,756 / 1,940 ms
- Command: `python scripts/benchmark.py http://127.0.0.1:8765 --start-server --runs 5 --count 3`, run twice; plus `python -m pytest` (211 passed; `tests/test_benchmark.py` covers the percentile, timing order and stand-in detection against a local streaming server, a real-looking answer, 429 stopping the run, and refusing to start a server for a remote URL), `ruff check`, `ruff format --check`, and in `codementor-ui`: `npm test` (19 passed), `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: https://github.com/pallets/itsdangerous (current HEAD at run time, not pinned), questions itsd-01, itsd-02, itsd-03 from `eval/questions/itsdangerous.json`
- Date: 2026-10-05
- Commit: af7bb5a
- Notes: TTFB is the first line of the event stream; the server sends a "Retrieving context..." status event before any retrieval, so TTFB says little about the work. The first answer token is the useful number: in repo mode the server finishes retrieval and all three model calls before streaming, then sends 4 words every 8 ms. Percentiles are nearest-rank; with 5 and 10 requests per group, p95 is the slowest request. The server ran with the app's normal rate limits and a 1 s gap between requests (15 questions and 5 clones per benchmark). Not measured: the deployed server, network time to Render, a sleeping Render instance (the script labels the first request "first" against a running server, cold only if it had been asleep), and the model; a run against a server with a key spends 3 model calls per question. The `llm` stage the server reported (p50 7.7 / 6.4 ms) is LangChain overhead around the stand-in

### Measurement: number of routers and API routes
- Value: **11 routers, 18 distinct method+path routes**. 9 routes need the API key: POST /dependencies, /explain, /generate-code, /search, and GET /metrics, /docs, /docs/oauth2-redirect, /redoc, /openapi.json. 9 are open: POST /analyze-repo, /ask, /ask/stream, /dependencies/graph, /files, /files/content, /repo-overview, and GET /repos, /eval/stats. 5 count against a request limit: /analyze-repo (clone), and /ask, /ask/stream, /explain, /generate-code (llm)
- Command: `python scripts/count_endpoints.py`; plus `python -m pytest` (215 passed; `tests/test_count_endpoints.py` checks the script's routes against the open and key-protected sets that `tests/test_auth.py` verifies with real requests, the router count against the controller files, the rate-limited set, and that the patched `include_router` is restored), `ruff check`, `ruff format --check`, and in `codementor-ui`: `npm test` (19 passed), `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: this repository's app, built with `create_app()` (nothing started, no request made)
- Date: 2026-10-05
- Commit: 2a2e905
- Notes: no earlier count is recorded in this repository or its history, so there is nothing to compare against; any older number elsewhere predates the API key (144ae11), which locked 9 of these routes. A router is one APIRouter that `create_app()` includes (one per controller file; `repo_guard.py` has none). Routes include the 4 docs routes defined on the app itself (/docs, /docs/oauth2-redirect, /redoc, /openapi.json). HEAD and OPTIONS that the framework answers on its own are not counted. "Need the API key" holds when CODEATLAS_AUTH_ENABLED is true, the default; with it false every route is open. Counting GET /docs and POST /ask/stream as separate endpoints from /docs/oauth2-redirect and /ask is a choice; without the 4 docs routes there are 14

### Feature: Prometheus stage histograms, error counters, eval hit-rate gauges, and a provisioned Grafana dashboard
- Value: /metrics now has `codeatlas_stage_duration_seconds{endpoint,stage}` (buckets 1 ms to 120 s; indexing stages clone, parse, graph, read_files, embed, index_write, save_state; chat stages embed_query, search, rerank, model; `total` for every timed request), `codeatlas_errors_total{path,kind}` (http_5xx, exception, stream_error), request metrics labelled by route template (unknown URLs share `unmatched`), and `codeatlas_retrieval_hit_rate{split,k}`, `codeatlas_retrieval_mrr{split}` and `codeatlas_retrieval_eval_info{split,commit,embedder}` read at startup from `eval/results/*.json`. `docker-compose.monitoring.yml` runs the app with the API key on; Prometheus sends the key from a Docker secret file, and Grafana loads a data source and a 10-panel dashboard. Checked end to end at this commit with a throwaway key: anonymous GET /metrics 401, with the key 200; Prometheus target `codeatlas` **up** with no scrape error; `codeatlas_retrieval_hit_rate{split="test"}` = 0.6 / 0.65 / 0.75 for k = 1 / 3 / 5 (same as `eval/results/test.json`); 9 indexing stage series after one POST /analyze-repo (200 in 6.8 s inside the container); Grafana listed dashboard "CodeMentor AI" in folder "CodeMentor". In the run just before this commit (same code and config, only `docs/MONITORING.md` changed after), all 10 dashboard queries ran in Prometheus without error
- Command: `docker compose -f docker-compose.monitoring.yml up -d --build` with `CODEATLAS_API_KEY` set to a random value, then `curl` on localhost:8000/metrics (with and without `X-API-Key`), POST /analyze-repo, the Prometheus `/api/v1/targets` and `/api/v1/query` APIs, and the Grafana `/api/search` API; `promtool check config` on `ops/prometheus.yml` in `prom/prometheus:v3.5.0` (SUCCESS); plus `python -m pytest` (224 passed; `tests/test_metrics.py` covers summing the model stages into one observation, stages recorded by a real indexing request, route templates for unknown URLs, an unhandled exception counted as an error and as status 500, an error inside a 200 stream, a 5xx response, gauges from an eval file and a broken file skipped, the committed eval results on /metrics behind the key, every metric the dashboard queries existing, and compose giving Prometheus the secret file it reads), `ruff check`, `ruff format --check`, and in `codementor-ui`: `npm test` (19 passed), `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: https://github.com/pallets/itsdangerous for the compose check; `eval/results/{dev,test,all}.json` written at 0bd92e8 by `python scripts/eval_retrieval.py --split <split> --json eval/results/<split>.json`
- Date: 2026-10-05
- Commit: 858c1d6
- Notes: **/metrics needs the API key**, so compose now needs `CODEATLAS_API_KEY` (in `.env` or the shell) for `up` and also for `down`; without it compose stops with a message. How a deployed Prometheus sends the key is in `docs/MONITORING.md` (`http_headers` with a key file; `promtool` accepted that block on 2.53 and 3.5). The backend reads only `X-API-Key`, not a bearer token. The retrieval gauges come from committed eval files, not live traffic, and change only when the eval is rerun and the files are committed; the Docker image now copies `eval/results`. Both compose files used `CODEATLAS_EMBEDDING_PROVIDER=sentence`, but sentence-transformers is not in the image, so indexing could not work there; both now use `hash`. Not shown: the chat panels stay empty in compose without `OPENAI_API_KEY` (it sets `CODEATLAS_LLM_PROVIDER=openai`; chat returned 500 and was counted as `kind="exception"`), so no chat stage times came from this check. The general (no repository) chat streams straight from the model and records no `model` stage; failed indexing requests record errors but no stages. Counters reset on restart and are per uvicorn worker. Grafana keeps its default admin / admin login locally. **Cleanup mistake:** while removing the files this check created in the shared `.codeatlas` folder, an empty shell variable made the command delete the whole `.codeatlas/repos` folder: five local clones from earlier sessions (flask, itsdangerous twice, a small Next.js project, and one with no index). They were gitignored and not in the state store, and indexing a repository again re-creates its clone

### Feature: CI job that fails if retrieval on itsdangerous drops below the recorded hit rate
- Value: `.github/workflows/retrieval-eval.yml` runs the eval on the 20 itsdangerous questions (pinned commit, no model key) and fails below **hit@5 0.85** or **hit@1 0.70**, the numbers recorded for that set in the tuning entry. The eval itself takes 0.5–0.8 s once the repo is fetched. In a Linux container (Python 3.11, `requirements.txt`, same as CI) it printed hit@1 0.700, hit@5 0.850, MRR@10 0.756 and exited 0; the full 40-question dev, test and all runs in that container gave the same numbers as on Windows. With the pre-tuning settings (`--candidates 10 --hash-subtokens off --drop-stopwords off --prefix-metadata off`) the same gate printed hit@5 0.700 and hit@1 0.500 and exited 1
- Command: `python scripts/eval_retrieval.py --set eval/questions/itsdangerous.json --split all --min-hit-rate 5=0.85 --min-hit-rate 1=0.70`, on Windows and in `docker run ... codementor-ai-codeatlas` (the image built from this repo's Dockerfile), plus the same with the pre-tuning flags; `python scripts/eval_retrieval.py --split dev|test|all` in the container; plus `python -m pytest` (225 passed; a new test runs the script on a small local repo and checks exit codes 0 and 1 for `--min-hit-rate`), `ruff check`, `ruff format --check`, and in `codementor-ui`: `npm test` (19 passed), `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: `eval/questions/itsdangerous.json` (https://github.com/pallets/itsdangerous at 672971d66a2e)
- Date: 2026-10-05
- Commit: 7c51c18
- Notes: **the workflow has not run on GitHub yet**, since nothing was pushed; the Linux container is the stand-in for it, and it fetches the repo from GitHub the same way. It is a separate workflow, not part of Backend CI, and it is not a required check: that is a branch-protection setting, which I did not touch. It runs on pushes and pull requests to main that change `codeatlas/`, `eval/questions/`, `scripts/eval_retrieval.py`, `requirements.txt` or the workflow file. The gate uses the tuned numbers rather than the original baseline (hit@5 0.700), so it catches a return to the old settings. A gate exactly at the recorded value relies on the eval being deterministic, which it was in every run here (Windows and Linux); with 20 questions, one question that drops out of the top 5 fails it (0.85 to 0.80). Only itsdangerous is gated, as the small sample repo; flask (236 files, 2.3 MB at the pinned commit, per `git ls-files` and `du`) could be added: the container's 40-question runs, flask included, took 1.1–2.0 s
### Fix: the validator step is gone from the agent pipeline
- Value: there is no validator agent, so the pipeline no longer pretends to have one. The graph's `validator` node took the finished answer and asked the mentor's model to rewrite it, costing one extra model call on every /ask and letting an already-grounded answer be reworded by a model that had not seen the code. Finishing the plan's steps now ends the run. A plan of one retrieval step makes exactly one agent call (was two: retrieval, then the validating mentor call). `validator` is also gone from the /ask analytics list and from the eval dashboard's agent colours
- Command: `python -m pytest` (187 passed, 1 skipped; `tests/test_agent_pipeline.py`, 4 new tests, checks the compiled graph has no validator node, the orchestrator has no `_validator_node`, a one-step plan ends without a second agent call, and a mentor step is not re-run after the plan finishes); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (19 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: none (fake agents; no model key needed)
- Date: 2026-10-05
- Commit: fb67bd5
- Notes: measured before the change against itsdangerous 672971d with a real model, one /ask took 66.4 s and 5 model calls, of which the validator was the last. The validator was never a separate agent: `_validator_node` called `self._mentor_agent` with a review prompt, so the eval dashboard's "validator" bar was counting mentor calls. The workspace welcome popup is deliberately untouched; it lists five agents and never mentioned a validator. Python 3.12.0 was used for every command here (the `py` launcher lists a 3.11 that is not present on disk)

### Fix: the planner's plan is validated, with a safe default when it is not usable
- Value: 19 planner outputs that a model really produces now all give a runnable plan instead of a crash or a silent empty answer. Four of them used to raise inside the routing function and return 500 for the whole /ask request: `{"steps": "retrieval"}` and `{"steps": [1, 2]}` raised `AttributeError: 'str' object has no attribute 'get'`, `{"steps": {"agent": "retrieval"}}` raised `KeyError: 0`, and a top-level list raised `AttributeError: 'list' object has no attribute 'get'`. A fenced ```` ```json ```` block, which is what a model returns most often when asked for JSON, used to be thrown away and replaced by the fallback; it is now parsed. A step naming an unknown agent used to route to `end` and return "No answer generated."; unknown steps are dropped and the rest kept. A step with no `instruction` used to hand the agent an empty prompt; it now gets the question. Plans are capped at 6 steps, because every step is at least one model call and nothing limited them before
- Command: `python -m pytest` (242 passed, 1 skipped; `tests/test_planner_plan.py`, 55 tests, runs all 19 bad shapes twice — once through `parse_plan` and once through the real orchestrator to prove routing cannot raise — plus fenced/wrapped JSON recovery, agent-name trimming, step dropping, the step cap, a planner model that raises, and a planner with no model at all); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (19 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: none (fake agents and a scripted model; no key needed)
- Date: 2026-10-05
- Commit: b452cbe
- Notes: the default plan is retrieval then mentor, the same two steps the fast path runs. `Plan.note` records anything that was changed and the orchestrator puts it in the answer's reasoning steps, so a bad plan is visible to the user rather than silent. `planner` is deliberately not an agent a plan can ask for, because a plan that re-planned would loop. **Limits:** the cap of 6 steps is a guess, not a measured figure. Validation only checks shape — a plan that is well-formed but a poor decomposition of the question is accepted as-is, and nothing here measures plan quality. A model that returns two JSON objects in one reply has only the outermost `{`...`}` span read, which may merge them into something unparseable and fall back to the default

### Fix: retrieval passes real code snippets, capped, with path and line range
- Value: the retrieval step now hands later steps the code it actually read instead of a prose summary of it. Each snippet carries its display path and the line range it came from. One snippet is clipped at 1,500 characters on a line boundary; the set is clipped at 6,000 characters. Measured on itsdangerous 672971d, the context for three questions is now 3,299 / 2,579 / 5,607 characters (about 824 / 644 / 1,401 tokens); before this change file-scope records were sent whole, and the same pipeline asked Groq for 9,681-10,391 tokens against this account's 8,000 tokens-per-minute limit and was rejected with `413 Payload Too Large` twice in one /ask. Citations are built from the same snippet objects that go into the prompt, so a citation always names code that was read. File-scope citations now carry a line range, where before they had none and showed the first two lines of the file (`from __future__ import annotations`)
- Command: `python -m pytest` (257 passed, 1 skipped; `tests/test_retrieval_snippets.py`, 15 new tests, covers real code in the snippet, a true line range, citations matching the snippets one for one, a 2,000-line file being clipped rather than sent whole, the total cap across snippets, that the model only ever sees capped context, clipping on line boundaries, a single overlong line, whole snippets being dropped rather than cut, the code reaching the next step, and a 413-style model failure still returning the snippets and citations); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (19 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`. The context sizes above come from a throwaway script that indexed itsdangerous through /analyze-repo and called the answer service directly with no model configured
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd; small Python projects written by the tests
- Date: 2026-10-05
- Commit: 2bba4b3
- Notes: the caps are in characters, not tokens, at about 4 characters per token, the same estimate conversation memory already uses; no tokenizer dependency was added. A snippet that does not fit the total budget is dropped whole rather than cut in half, so the model never sees a fragment without its location. When the model call fails the snippets and citations survive and the answer falls back to the list of locations, which is still true. **Limits:** this fixes what reaches the model, not what is found. Retrieval quality is unchanged and still weak — asked "How does Signer create and verify a signature?" against itsdangerous it returns `exc.py`, `timed.py` and `url_safe.py` and not `signer.py`, because the default embedder is the hash embedder, which does no semantic matching. The 1,500 and 6,000 character caps are chosen to sit well under an 8,000 token-per-minute account and are not tuned against answer quality

### Fix: the mentor answers from the snippets it was given and cites only those
- Value: the mentor no longer runs a search of its own, so the code it reads is the code the user is shown as citations. Measured before the change against itsdangerous 672971d with a real model: the answer described `src/itsdangerous/signer.py` while the five citations named `exc.py (22-33)`, `timed.py (185-220)`, `exc.py (36-57)` and `url_safe.py` twice; the retrieval text it was fed said in so many words "the file is not shown in the snippets you posted", and the model then invented the line ranges "lines 1-30" and "lines 31-55" and stated the digest default is sha256 when itsdangerous uses sha1. The mentor's prompt now numbers each snippet with the exact location it must cite, tells it to cite nothing else and never to invent a line number, and to say which part is missing rather than guess. A streamed repo question makes 2 model calls where it made 3, and one search where it made two (`llm_calls` fell from 3 to 2 and the repeated `embed_query` count is gone)
- Command: `python -m pytest` (270 passed, 1 skipped; `tests/test_mentor_grounding.py`, 13 new tests, including an answer service that raises if the mentor searches at all, the code and the exact citable locations being in the prompt, snippets numbered, no model call when there is nothing to answer from, facts marked exact, and two end-to-end checks that the cited files and the files in the mentor's prompt are the same set on the fast path and on a planned mentor step); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (19 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: none for the tests (fake agents and a spy model); the before-numbers come from the diagnosis run against https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd with `openai/gpt-oss-20b`
- Date: 2026-10-05
- Commit: c94ce86
- Notes: two existing tests changed with the behaviour and were updated rather than worked around. `tests/test_timing.py` asserted `llm_calls == 3` for a streamed question and now asserts 2; `tests/test_conversation_memory.py` asserted the old mentor prompt wording `Goal:` and now asserts `Question:`, and its `llm_calls` went from 3 to 2 as well (the follow-up rewrite is counted as its own `rewrite` stage, not as an `llm` call). **Limits:** the prompt instructs the model not to cite anything outside the list, but nothing checks the answer afterwards, so a model that ignores the instruction still produces a bad citation; no test asserts on real model output. The mentor's `run()` still retrieves once for callers outside the graph, such as /generate-code, which is why the answer service is still injected

### Fix: the memory agent uses the website's per-session conversation memory
- Value: the memory agent read its own JSON file on disk (`.codeatlas/state/agent_memory.json`), scoped `repo:<id>` or `global` rather than per visitor, with no expiry and no size cap, so one visitor's saved notes were readable by every other visitor asking about the same repository. Nothing in the pipeline ever read it to answer a question, and its whole command surface was `save: <text>` and `list` — asked "How does Signer work?" it replied "MemoryAgent commands: 'save: <text>' or 'list'". It now reads the same `ConversationStore` the chat writes to, so it inherits that store's rules instead of restating them: in process only, never written to disk, keyed by sha256 of the browser's random session id plus the repository id, the newest turns within a token budget, dropped after idle expiry or when the session cap is exceeded. Only a turn count is logged, never content. `/ask` now passes `session_id`, which it ignored before, so the non-streamed endpoint has conversation memory at all
- Command: `python -m pytest` (284 passed, 1 skipped; `tests/test_memory_agent.py`, 14 new tests, covering reading what the chat wrote, the agent holding the very same store object, no session and empty conversation, another session being unreadable, the same session on another repository being separate, the turn limit, the token cap and idle expiry all being the chat's own, a marker word absent from logs at DEBUG while the count is present, no JSON file written anywhere under a temporary working directory, the three deleted modules no longer being importable, and a planned memory step recalling the session through the graph); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (19 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: none (fake agents and an in-process store)
- Date: 2026-10-05
- Commit: e01698d
- Notes: `codeatlas/services/memory/json_store.py`, `in_memory_store.py`, `interfaces.py` and `codeatlas/models/agent_memory.py` are deleted rather than left unused, because an unused store that writes visitor content to disk is the hazard itself. No test covered them. An `agent_memory.json` written by an earlier run may still sit under `.codeatlas/state/` on a machine that ran the old code; nothing writes or reads it now and `.codeatlas/` is gitignored, so it is not removed automatically. `tests/test_unknown_repo.py`'s orchestrator spy gained `**kwargs` so it accepts the new `session_id` argument. **Limits:** the memory agent can only recall; it cannot be told to remember a fact on purpose, because the conversation store holds whole turns and nothing else. A plan whose memory step runs before any answer exists in that session gets "Nothing earlier in this conversation.". With more than one uvicorn worker a session's turns stay in the worker that received them, which is the conversation store's existing limit, not a new one

### Fix: the agents recorded are the agents that ran
- Value: /ask recorded a list written down in the controller. Measured before the change against itsdangerous 672971d with a real model, one question recorded `['planner', 'retrieval', 'mentor', 'validator']` while the agents that actually ran were `['planner', 'retrieval', 'mentor', 'mentor', 'analyst', 'mentor']` — the analyst ran and was invisible, the mentor's three calls counted as one, and the eval dashboard credited a validator that does not exist. /ask/stream likewise recorded a fixed `['retrieval', 'mentor']`. Each graph node now appends its own name as it executes, so repeats are kept, an agent that did not run is absent, and an agent that raised is still recorded as having run. The list is returned in the /ask response body as `agents_used`, in the stream's `done` event, and as a reasoning step reading "Agents that ran: planner -> retrieval -> analyst."
- Command: `python -m pytest` (295 passed, 1 skipped; `tests/test_agents_used.py`, 11 new tests, covering the recorded list matching a four-step plan, repeats kept rather than collapsed, the analyst recorded when it runs, no validator ever recorded, an unrun agent absent, a bad plan recording the planner plus the default steps, the fast path recording its two agents and no planner, the reasoning step wording, a raising agent still recorded, and two end-to-end checks that the /ask response body and the analytics record agree and that the stream's done event carries the list); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (19 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: none for the tests (fake agents); the before-numbers come from the diagnosis run against https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd with `openai/gpt-oss-20b`
- Date: 2026-10-05
- Commit: 4b22cbb
- Notes: a question asked with no repository is answered by one model call in the controller, not by the agent graph, so it is recorded as `direct` rather than as `mentor`, which would have claimed an agent ran that did not. The eval dashboard has a colour for `direct`; the existing `agent_usage` shape in /eval/stats is unchanged, so the page needed no other change. **Limits:** the per-agent timing on the dashboard is still the request latency divided evenly between the agents that ran, which is not a real per-agent measurement — only the names and counts are now accurate. The follow-up rewrite is a model call made outside any agent and is not recorded as an agent; it shows only as the `rewrite` stage in timings

### Feature: deterministic call graph for Python, and an analyst that answers from it
- Value: the analyst agent could not answer a structural question. It was handed four numbers (file count, function count, edge count, and the five highest-in-degree entries of an import graph whose nodes were module *strings*, not resolved files) and the model produced whatever it produced. `codeatlas/services/analysis/call_graph.py` now reads the syntax tree with Tree-sitter and records every definition, import and call site, resolving a call to a definition inside the repository where imports and lexical scope make it unambiguous, and marking it unresolved otherwise. Six questions are answered with no model call at all: who calls X, what does X call, where is X defined, who imports X, what does X import, and circular imports. Built over itsdangerous 672971d: 15 modules, 135 definitions, 378 call sites, 91 resolved (24.1%), 0 import cycles, in 0.03 s. Over flask d73fa1c: 83 modules, 1,580 definitions, 3,906 call sites, 742 resolved (19.0%), 1 cycle group of 17 modules, in 0.17 s. The 378 call sites for itsdangerous match Python's own `ast` module exactly. Spot checks: `who calls get_signature` returns `Signer.sign` at signer.py:225, `SigningAlgorithm.verify_signature` at :28 and `TimestampSigner.sign` at timed.py:51; `what does Signer.sign call` returns `itsdangerous.encoding.want_bytes` and `Signer.get_signature`
- Command: `python -m pytest` (343 passed, 1 skipped; `tests/test_call_graph.py`, 31 tests on small fixtures, and `tests/test_analyst_agent.py`, 17 tests); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (19 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`. The repository figures above come from `CallGraph.build()` over the two clones under `.codeatlas/eval-repos/`
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd; https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35; small Python packages written by the tests
- Date: 2026-10-05
- Commit: 8336875
- Notes: four bugs were found and fixed while building this, each visible in the numbers. Calls were first recorded once per level of tree depth, giving 1,794 call sites for itsdangerous instead of 378. `child_by_field_name` returns a new wrapper object, so `child is body` was never true and every method body was walked in its class's scope, which attributed `self.get_signature` to the class rather than to `Signer.sign`. Module names were derived by walking up while `__init__.py` exists, which named `src/flask/sansio/app.py` just `app` and collided it with other files; names are now taken from the path relative to the repository root, dropping a leading `src/`. Absolute single-segment imports were matched by suffix, so `import logging` inside flask resolved to flask's own `flask.logging`; a single-segment target is now never matched that way. **Limits, stated in `WHAT_IT_MISSES` in the module and asserted by a test:** dynamic calls (`getattr`, `eval`, dispatch tables), calls through a variable whose type is not obvious, decorators (the undecorated definition is what resolves), base classes that are not plain repo-defined names, `from x import *` (recorded, contributes no names), conditional and function-local imports (recorded but not scoped to their branch, which is why flask's `TYPE_CHECKING` imports count towards its one cycle group), attribute calls on a call's return value, every language other than Python, and a name redefined in a branch keeping its first definition. The resolution rates of 24.1% and 19.0% are not an accuracy figure: most call sites in any repository target the standard library or a dependency, and those are correctly outside the graph. `circular_imports()` returns groups of mutually-importing modules rather than every distinct loop, because flask has 33,796 distinct loops and a list of them tells a reader nothing; `shortest_import_cycle()` gives one concrete example loop per group

### Evaluation: the call graph against Python's own `ast`, on itsdangerous and flask
- Value: 49 structural questions (24 itsdangerous, 25 flask), split development/held-out, answered from the Tree-sitter call graph and independently from Python's `ast` module, compared as sets. **Precision 1.000, recall 0.967, 45 of 49 exact, total wall time 0.40 s.** By split: development n=26 precision 1.000 recall 0.964 exact 23/26; held-out n=23 precision 1.000 recall 0.971 exact 22/23 — the held-out set scores no worse, so the graph was not tuned to the questions it was developed against. By kind: `where_defined` n=23 precision 1.000 recall 1.000 exact 23/23; `who_imports` n=12 precision 1.000 recall 1.000 exact 12/12; `who_calls` n=14 precision 1.000 recall 0.886 exact 10/14. By repository: flask n=25 recall 0.992; itsdangerous n=24 recall 0.942
- Command: `python scripts/structural_eval.py` and `python scripts/structural_eval.py --show-disagreements`; also `--split held-out` and `--repo itsdangerous`. `python -m pytest` (359 passed, 1 skipped; `tests/test_structural_eval.py`, 16 tests covering the ground-truth extraction, the set scoring, and the question set's shape, with no network)
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd; https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35. Both are fetched one commit deep into `.codeatlas/eval-repos/` and reused if already there
- Date: 2026-10-05
- Commit: 2a8ba97
- Notes: **all four disagreements are misses, never false positives**, and two of the four are the ground truth over-counting rather than the graph being wrong. `ast` here matches a call by its trailing name, which is the honest simple rule for an independent check but is not type-aware:
  - `itsdangerous/src/itsdangerous/signer.py:219` is `self.algorithm.get_signature(key, value)`. That is a call on `self.algorithm`, whose type is not known, not a call to `Signer.get_signature`. The graph correctly declines to resolve it; `ast` counts it because the trailing name matches.
  - `flask/src/flask/helpers.py:528` is `werkzeug.utils.send_file(...)`, which is werkzeug's function, not flask's `send_file`. The graph is right to exclude it.
  - `itsdangerous/src/itsdangerous/timed.py:207` is `self.load_payload(base64d)` inside `TimedSerializer`, whose base is written `Serializer[_TSerialized]`. The graph does not follow a subscripted base class, so the method is not found. A genuine miss, already listed in `WHAT_IT_MISSES`.
  - `itsdangerous/src/itsdangerous/url_safe.py:53` is `super().load_payload(...)`. The call target is an attribute of another call's return value, which the graph does not resolve. A genuine miss, already listed.
  - The remaining two sites (`tests/test_signer.py:78` `signer.derive_key()`, `tests/test_signer.py:109`) are calls on a local variable whose type is not obvious — the same documented limit.
  **Limits:** 49 questions on two Python libraries by the same authors is a small, narrow sample, and the subjects were chosen by hand, which is a bias even with a held-out split. Precision of 1.000 is partly structural: the graph only ever claims a target it resolved through imports and scope, so it is built to be quiet rather than to guess, and recall is where it pays for that. The ground truth shares two conventions with the implementation (module naming, and dropping a leading `src/`), so a systematic error in those would be invisible to this comparison; the parsing, scope handling and call resolution are independent. Added to CI as `structural-eval` with `continue-on-error: true`, so it reports but never blocks a merge: the two shallow fetches take about 1 s each and the evaluation itself 0.40 s

### Feature: "Deep analysis" in the chat runs the five-agent pipeline, streamed step by step
- Value: the five agents existed but nothing on the website reached them — the chat always took the fast path, so the planner, analyst and memory agents never ran for a visitor. A "Deep analysis" toggle in the chat header sends `mode: "deep"` on the existing POST /ask/stream. The run is the real LangGraph execution, streamed: one `{"type": "agent", "name", "detail"}` event as each agent finishes, then the answer tokens, then `done`. A deep run of a three-step plan sends agent events for planner, retrieval, analyst and mentor, in that order, all before the first answer token, and reports `agents_used: ["planner", "retrieval", "analyst", "mentor"]`. The chat shows them as a numbered "Agents (4)" list, open by default, above the answer
- Command: `python -m pytest` (378 passed, 1 skipped; `tests/test_deep_mode.py`, 19 new tests, covering one event per agent in graph order, structural details, agent events arriving before the first token, the answer and citations, `first_agent_event` timing, fast being the default and explicitly selectable, an unknown mode rejected with 422, 404 for an unknown repository before any agent runs, the question cap at and over the limit, an empty question rejected, conversation memory kept with a session and not without one, no marker word from the question or answer in logs at DEBUG, no visitor text in any agent detail, and that the route set is unchanged); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (20 passed, 1 new for the default mode and the toggle), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: none (fake agents and the tests' small Python project)
- Date: 2026-10-05
- Commit: 5d129c7
- Notes: deep mode is a field on the existing endpoint rather than a new route, which is the conservative choice: `tests/test_auth.py`'s route classification needed no new entry, and a test in `tests/test_deep_mode.py` asserts the route set is unchanged so a future new route cannot slip past it. The graph blocks on model calls, so it runs in a worker thread that pushes events onto a `queue.Queue` while the endpoint reads them, which is what lets a step reach the browser while the next agent is still working; the thread's stage timings are attached through `run_timed`. **A question cap of 4,000 characters was added**, which did not exist before — deep mode sends the question to several agents, so a very long one multiplies across the pipeline. This is a behaviour change for every /ask and /ask/stream caller: a question over the cap now gets 422 where it was previously accepted. **Limits:** the answer is still not streamed from the model. Deep mode waits for the mentor to finish and then sends the finished answer 4 words at a time, exactly as fast mode does, so `first_agent_event` is the honest measure of when the user first sees progress, not `first_token_sent`. The agent `detail` strings are fixed phrases plus counts, so they say that an agent ran and roughly what it produced, not what it concluded

### Feature: Prometheus metrics for the agent pipeline, and a Grafana dashboard for them
- Value: the only metrics were `codeatlas_request_total` and `codeatlas_request_latency_seconds`, both about HTTP requests, so nothing showed which agents ran, what they cost, or how often the provider refused a call — the 413s and 429s that dominated the diagnosis were invisible. Seven new series: `codeatlas_agent_runs_total{agent}`, `codeatlas_agent_duration_seconds{agent}` (histogram), `codeatlas_agent_model_calls_total{agent}`, `codeatlas_agent_tokens_total{agent,direction}`, `codeatlas_agent_failures_total{agent,reason}`, `codeatlas_planner_routes_total{route}` and `codeatlas_planner_plans_total{source}`. No extra model call is made for any of them. `reason` comes from a closed list of five — `rate_limited` (the provider's 429), `payload_too_large` (413), `model_error`, `agent_error` and `fallback_to_location_list` — so a visitor receiving the degraded location-list answer is counted separately from the provider error that caused it
- Command: `python -m pytest` (396 passed, 1 skipped; `tests/test_agent_metrics.py`, 18 new tests, covering attribution inside and outside an agent's turn, an unknown agent name never becoming a label, runs and durations, a raising agent counted and still raising, model calls and tokens attributed to the running agent, a call outside any agent still counted, the three provider error mappings, a 413 recording both its reason and the degraded answer, planner plans and routes for both a model plan and a fallback, the label sets being closed, that a marker word from a question reaches no label on any agent or planner series, that every observed label value is within its fixed list, that /metrics exposes the series, and that every dashboard panel queries a metric that exists); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (20 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: none (fake agents and a fake model reporting token usage)
- Date: 2026-10-05
- Commit: 694bfdf
- Notes: which agent a model call belongs to is tracked with a `contextvars` variable set around each agent's turn, so a single callback attached to every chat model can attribute calls and tokens without each agent counting for itself. A call made outside any agent is counted under the agent label `none` rather than dropped. **There was no Grafana dashboard to add a panel to** — `docker-compose.monitoring.yml` started a bare Grafana with no provisioning at all — so this adds `ops/grafana/dashboards/codeatlas-agents.json` with seven panels, a provisioned Prometheus datasource, and the two volume mounts that load them, which is the conservative reading of the request. **Limits:** the dashboard JSON and the compose mounts are checked by a test that every panel's query names a metric that exists, and the YAML and JSON parse; **Grafana itself was not started, so no panel has been seen rendering**. `codeatlas_agent_duration_seconds` uses the default Prometheus histogram buckets, which top out at 10 seconds — a deep run that waits through a 29-second provider backoff lands in `+Inf`. Tokens are whatever the provider reports in `usage_metadata`; a provider that reports nothing contributes a call with zero tokens

### Measurement: fast mode against deep mode, with a real model
- Value: three questions against itsdangerous 672971d, each asked in both modes, `openai/gpt-oss-20b` on Groq, 65 s between runs. **Warm runs (2 and 3, the cold first run excluded): fast 2.23 s to the first answer token, 2.25 s total, 2.0 model calls, 3,285 tokens; deep 4.34 s to the first token, 4.36 s total, 3.5 model calls, 6,418 tokens.** Deep mode therefore costs about 1.9× the wall time, 1.75× the model calls and 2.0× the tokens of fast mode for the same question. Per run — fast: 10.32 s / 2.11 s / 2.40 s total, always 2 calls, 2,453–4,117 tokens, 5 citations; deep: 5.70 s / 3.56 s / 5.17 s total, 4 / 3 / 4 calls, 4,962–8,044 tokens, 3–5 citations. The first fast run took 10.32 s because it was the first request in a fresh process; it is excluded from the warm averages and shown here rather than hidden. Deep mode's plan varied by question: `planner -> retrieval -> analyst -> mentor` for two of the three, `planner -> retrieval -> mentor` for the other, which is the planner choosing, not a fixed list. **Zero 413s across all six runs** (the diagnosis run hit two in a single /ask) and one 429 with one retry. The existing retrieval evaluation did not regress: `tests/test_eval.py`, `tests/test_eval_stats.py`, `tests/test_faiss_retriever.py` and `tests/test_answer_service.py` pass (5 tests), and the structural evaluation is unchanged at precision 1.000, recall 0.967, 45/49 exact
- Command: `python scripts/mode_compare.py --questions 3 --pause 65 --out modes.json`; `python -m pytest tests/test_eval.py tests/test_eval_stats.py tests/test_faiss_retriever.py tests/test_answer_service.py`; `python scripts/structural_eval.py`
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd. Questions: "How does Signer create and verify a signature?", "What does URLSafeTimedSerializer do?", "Where is BadSignature raised?"
- Date: 2026-10-05
- Commit: c629764 (script), measured at e0c0962 (deep mode) with the metrics of 694bfdf in place
- Notes: the default mode is unchanged — fast is still what the website sends unless the visitor turns on Deep analysis. The comparison runs against a real uvicorn server on a local port, because FastAPI's `TestClient` buffers a streaming response and hands it over whole, which made the first streamed event appear to arrive at the same moment as the last one in an earlier attempt. **A claim I had to withdraw:** a single-question trial suggested deep mode reaches its first streamed event far sooner than fast mode (0.01 s against 1.19 s). Across the warm runs both are 0.02 s, so that gap was cold start, not mode — both modes send their first status event immediately. The real difference deep mode offers is the per-agent progress events during the wait, not a faster first byte. **Limits:** three questions on one small repository with one model is a very small sample, and each number is a single observation, not a distribution — the 10.32 s cold run is a reminder of the spread. Wall times depend on this machine's connection to Groq and on how busy the provider is. Token counts come from the provider's own `usage_metadata`; the gpt-oss models spend a noticeable share of output tokens on reasoning, so a smaller non-reasoning model would show different totals. The 65 s pause keeps the runs under an 8,000 tokens-per-minute allowance; without it the timings measure the provider's backoff instead of the pipeline

### Check: answer smoke test — **partial run only, stopped before it finished**
- Value: **incomplete.** 9 of the planned 30 runs finished (15 questions × 2 modes) before the run was stopped, so there is no deep-mode figure at all and the fast-mode figure covers 9 questions, not 15. What was measured, with `openai/gpt-oss-20b` on Groq: **fast mode 5 of 9 passed.** Broken down, itsdangerous 4 of 8 and flask 1 of 1. Of the four failures, three were "right fact, wrong file" — the answer contained the hand-written fact but the citations did not include the file it was read from ("What does the base64_encode function do?", "What does TimestampSigner add to a value when it signs it?", "What is the purpose of the want_bytes helper?") — and one failed both tests ("Which class does BadSignature inherit from?"). **Zero 413s and zero 429s across the 9 runs**, against two 413s in a single /ask during the diagnosis. Wall time was about 10 minutes for the 9 runs, almost all of it the deliberate pacing; the runs themselves took 1.3–3.6 s each
- Command: `python scripts/answer_smoke.py --out smoke.json` (stopped partway); `python -m pytest tests/test_answer_smoke.py` (20 passed, no network: the two string tests, the token pacer, and the question set, including a test that reads each expected file in the cached clone and asserts the hand-written fact really appears in it)
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd; https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35; 15 questions in `eval/answer_smoke_questions.json`, each naming the file the answer should come from and one short fact, with a note recording the line the fact was read from
- Date: 2026-10-05
- Commit: 7842c88
- Notes: **why it is partial.** The run was stopped by the tooling because the machine was critically low on memory while the session was idle. That says nothing about the check or the pipeline — no exception was raised, no provider error occurred, and the 9 completed runs are valid. It was not restarted. To finish it: `python scripts/answer_smoke.py --out smoke.json`, which takes roughly 30 minutes because it paces itself to one question a minute under an 8,000 tokens-per-minute allowance. **This is a weak check and must not be read as a quality score.** It is two string tests per answer: does the citation list include the expected file, and does the answer text contain one short word or phrase. There is no judge model and nothing looks at whether the explanation is correct, complete or well-reasoned. An answer can pass while being wrong about everything else, and a good answer fails for using a synonym — "Which class does BadSignature inherit from?" would fail if the model wrote "the base data exception" rather than `BadData`. The three "right fact, wrong file" failures are a retrieval problem, not a model problem, and they match the limit already recorded against the retrieval change: the default embedder is the hash embedder, which does no semantic matching, so the cited files are often not the ones the answer is actually about. Deliberately not added to CI: it costs real tokens, takes half an hour, and its result moves with the model and the provider

### Fix: the committed default model is openai/gpt-oss-20b, with an output budget that fits it
- Value: the committed default was `llama-3.1-8b-instant`, which no longer exists on the Groq account this was developed against — every call returned `404 - The model 'llama-3.1-8b-instant' does not exist or you do not have access to it`, so a fresh checkout could not answer a single question. The default in `codeatlas/utils/config.py` and in `.env.example` is now **openai/gpt-oss-20b**, which is a reasoning model and brings a different failure: it spends part of its output budget thinking before it writes anything the user sees, so too small a budget returns an empty reply. Measured against `openai/gpt-oss-20b` with a short question: budget 64 → 64 completion tokens, 312 characters of reasoning, **0 characters of answer**, `finish_reason=length`; budget 128 → answer present but truncated (`finish_reason=length`); budget 256 → complete (`finish_reason=stop`); budget 2048 on a realistic grounded code question → 878 completion tokens, 3,276 characters, complete, and it cited `signer.py` correctly. The default budget is now **2048**, set explicitly rather than left to the provider's own default, and `CODEATLAS_LLM_MAX_TOKENS` overrides it. `CODEATLAS_LLM_MODEL` still overrides the model. If a reply does come back empty the mentor returns a sentence naming the setting to raise, instead of showing the user nothing
- Command: `python -m pytest` (433 passed, 1 skipped; `tests/test_llm_defaults.py`, 17 new tests with a fake reasoning model that writes only when budget is left over, covering the default model being the one that exists and not the retired one, the env template agreeing with the code default, `CODEATLAS_LLM_MODEL` and `CODEATLAS_LLM_MAX_TOKENS` overriding and not leaking between loads, the default budget producing a non-empty cited answer, a 64-token budget producing the explanation rather than an empty string, the 64/128/256/2048 threshold, the provider passing both model name and budget through for groq and for openai, and the keyless fallback model still answering); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (20 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`. The budget measurements come from direct calls to the Groq API with `max_tokens` varied
- Dataset/repo: none (fake model in the tests); the budget thresholds were measured against the live `openai/gpt-oss-20b`
- Date: 2026-10-05
- Commit: 4abb348
- Notes: model name recorded here as required: **openai/gpt-oss-20b**, provider `groq`, temperature 0.2, output budget 2048. `.env.example` changed on the model line only, plus two comment lines and the new `CODEATLAS_LLM_MAX_TOKENS` line; no key line was added, removed or altered, which a check of the diff confirms (0 added or removed lines matching "key" or "secret"). `llm_max_tokens` was given a default in `AppConfig` and placed among the defaulted fields, so the seven tests that build an `AppConfig` directly did not need changing. **Limits:** 2048 is a judgement, not a tuned figure — large enough for every answer seen here (the longest used 878 tokens) and small enough to keep a request's estimated size well under an 8,000 token-per-minute allowance, but a question needing a very long answer would still be cut off, and the user would see a truncated answer rather than the empty-answer message, which only fires when nothing at all comes back. Model availability is per account: another Groq account may still have `llama-3.1-8b-instant`, and this default may in turn retire

### Fix: the workspace welcome popup describes what the chat actually does
- Value: the popup listed six capability cards, two of which were not true of anything a visitor could reach. **Code Generation** described generating code and refactoring suggestions, but that is `/generate-code`, an admin-only endpoint behind `X-API-Key` that `codementor-ui/lib/api.ts` never calls — the card is removed, leaving five. **Planner Agent** claimed every question is broken into steps and routed to agents; that is only true in Deep analysis mode, and the default chat goes straight from search to answer, so the card now says which is which and which is faster. **Context Memory** is kept and now says what it really holds — the last few turns in this chat window — rather than "your conversation context", which read as if it persisted. The remaining cards (Code Retrieval, Dependency Analysis, Coding Mentor) were already accurate and are untouched
- Command: in `codementor-ui`: `npm test` (20 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`; `python -m pytest` (433 passed, 1 skipped), `ruff check codeatlas/ tests/`
- Dataset/repo: none (copy change)
- Date: 2026-10-05
- Commit: ef7343a
- Notes: this file was deliberately left alone for the whole of batch-6 until this change was asked for, which is why earlier entries say the popup still overstated the pipeline. The diff is 2 insertions and 9 deletions: the three copy changes plus the `Code2` icon import, which the removed card was the only user of and which would have failed lint as an unused import. Nothing else in the file changed — no layout, no behaviour, no dismissal logic. **Limits:** the card text is checked by eye and by the build; no test asserts on the popup's wording, so a future change to what the chat does could make this copy wrong again without anything failing

### Check: answer smoke test, completed run — **fast 8/15, deep 1/15, and the deep figure is not usable**
- Value: the run stopped earlier was resumed and finished; all 30 runs (15 questions × 2 modes) are now recorded. Model: **openai/gpt-oss-20b** on Groq, output budget 2048. **fast: 8 of 15 passed** — the expected file was cited in 9 of 15 and the hand-written fact was present in 13 of 15. **deep: 1 of 15 passed** — expected file cited 7 of 15, fact present 4 of 15. **Failures that had the right fact but cited the wrong file: 5 in fast mode, 3 in deep.** **413 payload-too-large: 0.** **429 rate-limited: 23.** Wall time 1,026 s for the 21 resumed runs, plus about 600 s for the 9 run earlier; nearly all of it is the deliberate pacing, the runs themselves taking 0.3–3.8 s each
- Command: `python scripts/answer_smoke.py --resume --out smoke.json` (completing an earlier `python scripts/answer_smoke.py --out smoke.json`); `python -m pytest tests/test_answer_smoke.py` (28 passed, no network)
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd; https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35; the 15 questions in `eval/answer_smoke_questions.json`
- Date: 2026-10-05
- Commit: eea8df8
- Notes: **this remains a weak check and is not a measure of answer quality.** It is two string tests per answer — does the citation list include the expected file, and does the answer text contain one short word or phrase. There is no judge model, and nothing looks at whether the explanation is correct, complete or well reasoned. An answer can pass while being wrong about everything else, and a good answer fails for using a synonym.
  **The deep figure of 1 of 15 must not be read as deep mode answering badly.** Two separate causes, both found after the run:
  1. **The account's daily token budget ran out partway through.** The 429s are not the per-minute limit the script paces against but `tokens per day (TPD): Limit 200000, Used 199248`. **Six of the fifteen deep runs ran after that point** and got no real model answer at all: the planner fell back to the default plan, retrieval fell back to the location list and the mentor's call was refused, which is why those runs took 0.3–0.9 s instead of about 3 s. One earlier deep run (0.4 s) looks the same. Those runs measure an exhausted quota, not an answer. The pacer guards tokens per minute only; it has no notion of a daily budget.
  2. **When a plan's last step is not the mentor, the user is shown that agent's raw output instead of the answer.** Each graph node overwrites `final_answer`, so the last step wins. Verified with fake agents and no tokens: a plan of retrieval → mentor → analyst returns the analyst's structural output and discards the mentor's answer, while retrieval → analyst → mentor returns the answer. The planner chose a plan ending in the analyst for two of the three questions in the earlier timing measurement, and several deep failures here cited the right file while missing the fact, which is exactly what a structural-facts answer looks like. **This is a real bug, it is not fixed, and it is the most likely reason deep mode scores worse than fast mode on this check.** It was visible in the original diagnosis ("the mentor's work is thrown away") and was only partly addressed: the mentor now reads the right snippets, but which agent's output becomes the answer was never changed.
  A provider quirk also appeared once: `400 - Tool choice is none, but model called a tool`. It affected a single call and is not handled specially.
  The fast-mode failures are the familiar retrieval problem: 5 of the 7 had the right fact but cited the wrong file, because the default embedder is the hash embedder and does no semantic matching. Deliberately not added to CI: it costs real tokens, takes about half an hour, and its result moves with the model, the provider and the remaining daily quota

### Check: full backend and frontend verification, and nothing tracked by mistake
- Value: the whole gauntlet run once more on the final state of batch-6. Backend: **441 passed, 1 skipped** on Python 3.12.0; `ruff check` clean; `ruff format --check` reports 118 files already formatted; the structural evaluation is unchanged at **precision 1.000, recall 0.967, 45 of 49 exact** in 0.47 s. Frontend: **20 tests passed**, `npx tsc --noEmit` clean, `npm run lint` 0 errors and the same 28 pre-existing warnings, `npm run build` succeeds and prerenders all four routes. Repository hygiene: `.env` is **untracked** and ignored by `.gitignore` line 1; the working tree is clean with nothing untracked or staged; **0** files tracked under `.codeatlas/`; **0** tracked files matching `.pyc`, `.faiss`, `.pkl`, `node_modules/`, `.next/`, `__pycache__`, `tsbuildinfo`, `.log`, or the scratch result files; **0** lines changed in `.env.example` that mention a key or secret; and **0** key-shaped strings anywhere in the whole batch-6 diff
- Command: `python -m pytest tests/ -q`; `ruff check codeatlas/ tests/`; `ruff format codeatlas/ tests/ --check`; `python scripts/structural_eval.py`; in `codementor-ui`: `npm test`, `npx tsc --noEmit`, `npm run lint`, `npm run build`; `git ls-files --error-unmatch .env`, `git check-ignore -v .env`, `git status --porcelain`, `git ls-files .codeatlas`, `git diff be8fa71..HEAD -- .env.example`
- Dataset/repo: this repository's working tree, plus the two pinned clones under `.codeatlas/eval-repos/` for the structural evaluation
- Date: 2026-10-05
- Commit: 1a1ef1d (state checked)
- Notes: 27 files were added across batch-6 and all are intentional — 5 source modules, 2 evaluation question sets, 3 Grafana configuration files, 4 scripts and 13 test files. 4 files were deleted, all of them the disk-backed agent memory store. `requirements.txt` and `codementor-ui/package.json` are untouched, so no dependency was added at any point. The branch is local only: it has no counterpart on origin and nothing was pushed. **Limits:** "0 tracked generated files" is a check against a list of known patterns, not proof that nothing generated is tracked; and the frontend build succeeding is not the same as the pages having been opened in a browser, which was not done

### Feature: report the provider's remaining quota before spending any of it
- Value: the completed smoke run was spoiled because the account's daily token budget ran out partway through and nothing noticed until answers started coming back empty. `scripts/token_budget.py` makes one request of a single output token and reads the rate-limit headers before any real work starts. Measured on 2026-10-06 at 16:58 UTC against `openai/gpt-oss-20b`: **tokens per minute 7,927 of 8,000 left; requests today 2 of 1,000 used, 998 left; daily tokens remaining about 199,600 (an estimate)**. The daily window had therefore rolled over since the previous day's exhaustion, and the figure is far above the 60,000 floor required before rerunning the smoke check, so the rerun was allowed to start
- Command: `python scripts/token_budget.py --require-daily 60000` (exit 0); `python -m pytest` (458 passed, 1 skipped; `tests/test_token_budget.py`, 17 new tests with no network, covering reading the daily limit out of a 429 body, not mistaking a per-minute 413 for a daily limit, the estimate being labelled as one, a provider-stated figure not being labelled an estimate, an unknown figure saying so rather than reporting zero, the request counter arithmetic, and the stop threshold at and either side of the boundary); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (20 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: none (one probe request to the live provider; the tests use fixed strings)
- Date: 2026-10-06
- Commit: 92cdd0f
- Notes: **the provider does not expose a tokens-per-day figure.** Every header it sends was checked: `x-ratelimit-limit-tokens` and `x-ratelimit-remaining-tokens` are per minute, `x-ratelimit-limit-requests` and `x-ratelimit-remaining-requests` are per day, and there is no token equivalent of the latter. The daily token number appears only inside the body of a 429 once it has run out, as `tokens per day (TPD): Limit 200000, Used 199248`. So the reported daily figure is an estimate: the share of the daily *request* allowance already used, applied to an assumed 200,000 token limit, and the output says "ESTIMATE" whenever that is what it is. **Limits:** the estimate assumes requests and tokens are consumed at a similar rate, which they are not — a few large requests can exhaust the token budget while barely touching the request count, and that is exactly what happened on 2026-10-05, when about 100 requests used 199,588 tokens. It is therefore a weak upper bound and should not be trusted close to the limit. The reliable guard is the 429 itself, which a long run watches for and stops on

### Fix: a plain message when the demo's AI quota is gone, with the file list beneath it
- Value: a refused provider call reached the visitor in one of two bad ways. The mentor's failure was shown raw — `Error generating answer: Error code: 429 - {'error': {'message': 'Rate limit reached for model ...'}}` — and a refused retrieval call fell back to a bare list of paths under the heading `Top relevant locations:`, which reads as though the list were the answer to the question. Both are now replaced by a short sentence followed by the files that did match, under a heading that says what they are. **The exact messages:**
  - per-minute limit: *"The demo's AI is busy right now — its per-minute quota is used up. Wait a minute and ask again."*
  - daily limit: *"The demo's AI quota for today is used up. Please try again later."*
  - payload too large: *"That question needed more context than the demo's AI accepts at once, so it could not answer."*
  - the heading above the files: *"The search did find these files, which may still help:"*, or *"No matching files were found either."* when there are none.
  A daily limit is recognised **before** the general rate-limit case, because the provider reports both as a 429 and the advice differs. A failure that is not a quota problem is untouched and still reports itself, so a real bug is not disguised as a busy demo
- Command: `python -m pytest` (484 passed, 1 skipped; `tests/test_quota_message.py`, 26 new tests with a fake model, covering each cause being told apart, a daily limit not being mistaken for a plain rate limit, a bare status code being enough, the wording differing between the two limits, no provider codes in visitor copy, the files coming after the message under a heading, `Top relevant locations:` being gone, the empty-file case, the answer service reporting each cause, the fast path and a planned mentor step showing the message rather than the exception, a non-quota failure still reporting itself, and the streamed endpoint delivering the message as the answer); in `codementor-ui`: `npm test` (27 passed, 7 new in `lib/quotaMessage.test.ts`), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`; `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`
- Dataset/repo: none (fake model and the tests' small Python project)
- Date: 2026-10-06
- Commit: 19682c0
- Notes: the frontend tests check that a message split into four-word chunks reassembles intact, that `api.ts` hands `data.content` to `onToken` with no trimming or filtering, that the chat window appends every token into the text it displays, and that the bubble renders the answer directly rather than inside one of its collapsible panels. `lib/api.ts` could not be imported into a test because it imports `./serverRequest` without a file extension, which Node's loader will not resolve, so its behaviour is asserted against its source in the same way the existing tests in that folder already do. Two existing tests asserted the old bare-list behaviour and were updated to the new wording rather than worked around. **Limits:** the wording is duplicated between `codeatlas/services/llm/quota.py` and the frontend test, so the two could drift; the backend is the single source and the frontend test is a copy that would need changing with it. The classification reads the provider's message text, so a provider that reports a daily limit in different words would be treated as a per-minute one and the visitor would be told to wait a minute when waiting will not help. **Nothing here was seen in a browser** — the display is asserted through the source and the build, not by opening the page

### Fix: an answer cut off by the output limit says so
- Value: the provider reports `finish_reason: "length"` when it stopped writing because the output budget ran out. Nothing used to read that, so a truncated answer simply trailed off mid-sentence and looked like the model had finished. The mentor now appends one line when that happens: *"This answer was cut off because it reached the model's output limit."* (rendered in italics, on its own paragraph). A complete answer gets no note, and the note is appended to the answer rather than replacing it, so whatever the model did manage to write is still there. This matters more since the default model became a reasoning model with an explicit 2,048-token budget: the budget is generous but a long answer can still reach it
- Command: `python -m pytest` (484 passed, 1 skipped; the truncation tests are in `tests/test_quota_message.py` — a fake model reporting `finish_reason: "length"` produces the note, one reporting `"stop"` does not, the real answer survives alongside the note, the flag is read from the provider's own field, and the per-generation form of the same field is also recognised); in `codementor-ui`: `npm test` (27 passed, including that the note survives being streamed four words at a time), `npx tsc --noEmit`, `npm run lint`, `npm run build`; `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`
- Dataset/repo: none (fake model)
- Date: 2026-10-06
- Commit: 19682c0
- Notes: **this change shares a commit with the quota message rather than having one of its own, which was my mistake** — the two were written together and committed together before I separated them in the record. The code is `TRUNCATED_NOTE` and `was_truncated` in `codeatlas/services/llm/quota.py` plus three lines in `codeatlas/services/agents/coding_mentor_agent.py`. **Limits:** only the mentor's own call is checked. A truncated answer produced inside the retrieval summary is not annotated, and neither is one from the analyst's phrasing call. The note is appended after the fact, so a sentence still ends mid-word; nothing attempts to continue the answer or re-ask with a larger budget. A provider that truncates without setting `finish_reason` would pass unnoticed

### Check: deep-mode answer smoke test rerun, with the quota damage removed
- Value: the six deep runs that had got no model answer were done again on a fresh daily budget, and all six produced real answers this time (2.5–7.5 s each, against 0.3–0.9 s when they were being refused). The fast runs and the deep runs that had already answered were not repeated. Model: **openai/gpt-oss-20b** on Groq, output budget 2048. Across all 30 recorded runs:

  | mode | passed | expected file cited | fact present | right fact, wrong file | no model answer |
  |------|--------|---------------------|--------------|------------------------|-----------------|
  | fast | **8/15** | 9/15 | 13/15 | 5 | 0 |
  | deep | **4/15** | 8/15 | 8/15 | 4 | 0 |

  **413 payload-too-large: 0. 429 rate-limited: 0.** **Runs that got no model answer: 0**, against 6 in the previous attempt. Wall time for the six reruns: 348 s, nearly all of it pacing. Deep mode rose from 1 of 15 to **4 of 15** once the exhausted-quota runs were replaced, so most of the earlier gap was the quota, not the pipeline
- Command: `python scripts/token_budget.py --require-daily 60000` (about 199,800 estimated, so the rerun was allowed to start), then `python scripts/answer_smoke.py --resume --out smoke.json --daily-start 199800 --min-daily-tokens 40000 --min-free-mb 600`; `python -m pytest` (499 passed, 1 skipped); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (27 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd; https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35; the 15 questions in `eval/answer_smoke_questions.json`
- Date: 2026-10-06
- Commit: f67b5d4
- Notes: **this is still a weak check and is still not a measure of answer quality.** Two string tests per answer — is the expected file among the citations, and does the answer text contain one short hand-written word. No judge model, nothing reading whether the explanation is right. A wrong answer can pass and a good one can fail on a synonym.
  **Deep mode is genuinely worse than fast mode on this check, and the quota is no longer the reason.** The telling number is "fact present": 13 of 15 in fast mode against 8 of 15 in deep. Deep mode loses the *fact* far more often while citing files about as well, which is the signature of the unfixed bug recorded earlier — every graph node overwrites `final_answer`, so when a plan's last step is the analyst the visitor is shown structural facts instead of the mentor's prose answer. Four of the deep failures cite the right file and are missing only the fact ("How does Signer derive its signing key by default?", "Which hash algorithm does Signer use by default?", "What salt does the secure cookie session interface use?", "How does Flask work out the root path for an import name?"), which is exactly what a structural-facts answer looks like. **That bug remains unfixed; it is outside the four items asked for in this batch.**
  The fast-mode failures are unchanged and are the familiar retrieval weakness: 5 of 7 had the right fact but cited the wrong file, because the default embedder is the hash embedder and does no semantic matching.
  Six earlier deep rows were marked as having got no answer on the rule that a deep run finishing in under 1.5 s cannot have made three real model calls. That rule is a judgement, not a flag the provider set; one further run that failed after the daily budget ran out took 3.7 s and was left alone rather than redone, so it may still be measuring an exhausted quota. Still not in CI

### Fix: the answer comes from the mentor, not from whichever agent ran last
- Value: every graph node overwrote `final_answer`, so the last step in a plan won. A plan of retrieval → mentor → analyst showed the analyst's structural facts and discarded the mentor's written answer. The mentor's output is now kept in its own state field that no later step can overwrite, and the result prefers it whenever the plan ran a mentor at all. Behaviour for the four orders asked for: retrieval → mentor → analyst answers with the mentor; retrieval → analyst → mentor answers with the mentor; analyst alone keeps the analyst's output but prefixes it with *"This is a structural result, computed from the code rather than written as an explanation."*; two mentor steps answer with the later one. Nothing is hidden — every agent's output stays in the streamed `agent` events and in the reasoning steps, so the website still shows the whole run, and a reasoning line reads "Answer taken from the mentor step; later steps are shown above." when a step ran after the answer
- Command: `python -m pytest` (516 passed, 1 skipped; `tests/test_final_answer.py`, 17 new tests with fake agents and no model, covering the four plan orders asked for, the rule across four more mentor-containing plans, a mentor-less plan for both the analyst and the memory agent, that a structural result is never passed off as prose, that all three steps of a three-step plan are still in the reasoning, the note when a later step ran, no note when the mentor ran last, the streamed events still carrying every agent, and the fast path being unaffected); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (27 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: none (fake agents)
- Date: 2026-10-06
- Commit: 0b2e564
- Notes: two existing tests asserted the old behaviour and were updated rather than worked around. `tests/test_agent_pipeline.py` expected a retrieval-only plan's answer to be exactly the retrieval output, and `tests/test_memory_agent.py` expected a memory-only plan's answer to be exactly the memory output; both now expect that output inside a labelled structural result. **Limits:** the label says "structural result" for any mentor-less plan, which is accurate for the analyst and loose for a retrieval-only or memory-only plan — a search result is not really a structural one, and the single wording covers all three. The fix changes which output is shown, not whether the plan was sensible: a planner that never includes a mentor step still produces an unwritten answer, just an honestly labelled one. Nothing here measures whether the mentor's answer is any good

### Check: deep-mode smoke test after the mentor-first fix — **the score did not improve**
- Value: all 15 deep runs were done again against the fixed pipeline; the 15 fast runs were not repeated. Model: **openai/gpt-oss-20b** on Groq, output budget 2048. **413: 0. 429: 0.** Runs with no model answer: 0. Wall time 934 s for 15 runs, nearly all of it pacing.

  | | passed | expected file cited | fact present | right fact, wrong file |
  |---|--------|---------------------|--------------|------------------------|
  | deep, before the fix | 4/15 | 8/15 | 8/15 | 4 |
  | **deep, after the fix** | **3/15** | 7/15 | 9/15 | 6 |
  | fast, for comparison (not rerun) | 8/15 | 9/15 | 13/15 | 5 |

  **The fix did not improve this check — the pass count fell from 4 to 3.** Two questions went from fail to pass and three went the other way: *"How does Signer derive its signing key by default?"* and *"Which hash algorithm does Signer use by default?"* now pass, and both are exactly the cases the fix targeted, where the answer had been the analyst's structural facts with the prose fact missing. The three that regressed — *"Which helper serves a file from inside a directory?"*, *"Which function renders a template by name?"*, *"How do I show a one-time message to the user on the next request?"* — all failed on the **cited file**, which this fix does not touch
- Command: `python scripts/token_budget.py --require-daily 60000` (about 196,800 estimated, so the rerun was allowed to start), then `python scripts/answer_smoke.py --resume --out smoke.json --daily-start 196800 --min-daily-tokens 40000 --min-free-mb 600` with all 15 deep rows marked as needing a redo; `python -m pytest` (516 passed, 1 skipped); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (27 passed), `npx tsc --noEmit`, `npm run lint`, `npm run build`
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd; https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35; the 15 questions in `eval/answer_smoke_questions.json`
- Date: 2026-10-06
- Commit: 0b2e564 (the fix); measured at d01ecba
- Notes: **this is still a weak check and still not a measure of answer quality** — two string tests per answer, no judge model, nothing reading whether the explanation is correct.
  **What the numbers do and do not show.** "Fact present" rose from 8 to 9 and "expected file cited" fell from 8 to 7, which is movement of one question each way on a sample of fifteen: noise, not a signal. The fix is right on its own terms and `tests/test_final_answer.py` proves it deterministically with fake agents — a plan of retrieval → mentor → analyst now returns the mentor's answer rather than the analyst's facts — and the two targeted questions flipping to pass is consistent with that. But **the claim that the overwrite bug was the main cause of deep mode's low score is not supported by this rerun**, and the earlier entry that suggested it should be read with this one.
  **Why the file citations move between runs at all:** citations come from retrieval, which the fix does not touch, but the *query* retrieval is given is the planner's instruction text, and the planner is a model call. A different plan means a different search, so the cited files vary between runs even with the same question and temperature 0.2. That is the likeliest source of the three regressions, and it means a 15-question comparison cannot separate a real change from run-to-run variation.
  Deep mode remains worse than fast mode on this check (3/15 against 8/15), and the reason is now less clear than it appeared: deep still cites the expected file less often (7/15 against 9/15) despite retrieval being identical code, which points back at the planner's instructions rather than at the answer-selection bug that has now been fixed. Not in CI

### Fix: deep mode searches with the visitor's question, not the planner's wording
- Value: retrieval in a planned run searched with the planner's `instruction` text for the step, not with what the visitor typed. The planner is a model call, so the same question produced differently worded instructions between runs, a different search, and different cited files. That is the likeliest explanation for three smoke questions flipping from pass to fail across the previous rerun on a change that touched nothing in retrieval. Retrieval now searches with the visitor's own question, or with its standalone rewrite when the question is a follow-up — deep mode now performs that rewrite the same way the fast path already did, so "why does it do that?" is no longer sent to the index verbatim. The planner still chooses which agents run and in what order; it no longer chooses the query
- Command: `python -m pytest` (525 passed, 1 skipped; `tests/test_final_answer.py` gained 6 tests, including the one asked for: two fake planners wording the same step as "Locate the Signer class and its key derivation" and "find where signing keys come from in this repo" produce an identical search query, plus the planner's wording never reaching the search, an empty instruction changing nothing, two retrieval steps both searching the question, a rewritten follow-up being what search sees, and the planner still deciding which agents run); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (27 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: none (fake agents, no model)
- Date: 2026-10-06
- Commit: e5347a2
- Notes: one existing test asserted the old behaviour and was updated: `tests/test_agent_pipeline.py` expected retrieval to be called with the planner's `"find x"` and now expects the question `"q"`, which is the change itself rather than a workaround. The rewrite in deep mode costs one extra model call, and only for a question the word rule judges to be a follow-up, exactly as in fast mode. **Limits:** this removes one source of run-to-run variation; it does not make a planned run deterministic, because the planner still varies which agents run and the mentor's wording still varies. Whether it improves the smoke score is measured separately and should not be assumed from the reasoning here

### Fix: a stand-in answer is labelled for what it is, not called structural regardless
- Value: when a plan had no mentor step, whatever agent ran last supplied the answer prefixed with "This is a structural result, computed from the code rather than written as an explanation." That was accurate only for the analyst. A retrieval-only plan told the visitor a file search was a structural result, and a memory-only plan said the same of a recalled conversation turn. The label now follows the agent that actually produced the output:
  - analyst → *"This is a structural result, computed from the code rather than written as an explanation."*
  - retrieval → *"This is a search result, not a written answer."*
  - memory → *"This is recalled context from this conversation, not a written answer."*
  The matching reasoning step changed the same way, from one wording to "showing the structural result" / "showing the search result" / "showing the recalled context". An agent with no label of its own has its output shown plainly rather than mislabelled. A plan containing a mentor is unaffected: the mentor's answer is returned with no prefix at all
- Command: `python -m pytest` (525 passed, 1 skipped; `tests/test_final_answer.py` covers all three labels through the graph, that the three differ from one another, and that only the analyst is called structural — a retrieval-only and a memory-only plan are asserted not to carry the structural prefix); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (27 passed), `npx tsc --noEmit`, `npm run lint`, `npm run build`
- Dataset/repo: none (fake agents, no model)
- Date: 2026-10-06
- Commit: e5347a2
- Notes: **this change shares a commit with the deep-mode search fix instead of having one of its own, which was my mistake** — both edited `orchestration.py` and I staged the file whole. It is the second time in this batch that two changes landed in one commit; the truncation note did the same earlier. The code for this one is the three prefixes, the `STAND_IN_PREFIXES`/`STAND_IN_NOTES` maps and the `final_agent` state field in `codeatlas/services/agents/orchestration.py`. Two existing tests asserted the single old label and were updated: `tests/test_agent_pipeline.py` for a retrieval-only plan and the parametrised label test in `tests/test_final_answer.py`, which now covers all three agents. **Limits:** the labels are fixed strings chosen by hand and nothing checks they read well to a visitor; and a plan with no mentor step is still a poor plan, which this only makes honest rather than prevents

### Check: third deep smoke pass — **incomplete, stopped at the daily limit; and the budget probe was wrong**
- Value: the 15 deep runs were started again against the fixed search. **The run stopped cleanly after 8 of them**, on the provider's own statement `tokens per day (TPD): Limit 200000, Used 199400` — 600 tokens left. The 7 questions not reached are all flask ones. Model: **openai/gpt-oss-20b**, output budget 2048. **413: 0. 429: 3.** Runs that got no model answer: 1 (the one caught mid-refusal). Wall time 462 s.

  | | passed | expected file cited | fact present | right fact, wrong file |
  |---|--------|---------------------|--------------|------------------------|
  | deep pass 2, planner's wording as the query | 3/15 | 7/15 | 9/15 | 6 |
  | **deep pass 3, visitor's question as the query** | **4/8** (7 answered, 4 passed) | 4/8 | 6/8 | 2 |
  | fast, for comparison (not rerun) | 8/15 | 9/15 | 13/15 | 5 |

  **Cited files changed between the two deep passes for 7 of the 8 questions both passes covered.** One stayed the same.
- Command: `python scripts/token_budget.py --require-daily 60000` (reported about 199,200 estimated and exited 0, **which was wrong — see below**), then `python scripts/answer_smoke.py --resume --out smoke.json --daily-start 199200 --min-daily-tokens 40000 --min-free-mb 600` with all 15 deep rows marked as needing a redo; `python -m pytest` (525 passed, 1 skipped); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (27 passed), `npx tsc --noEmit`, `npm run lint`, `npm run build`
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd; https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35; the 15 questions in `eval/answer_smoke_questions.json`
- Date: 2026-10-06
- Commit: e5347a2 (the search fix); measured at 32a9aba
- Notes: **15 questions cannot separate a small improvement from run-to-run variation, and 8 questions certainly cannot.** Pass 3 covers 8 of the 15 and only itsdangerous, so 4/8 is not comparable with pass 2's 3/15. Nothing here shows the search fix helped or hurt. This remains a weak check — two string tests per answer, no judge model, nothing reading whether the explanation is right.
  **The "7 of 8 cited files changed" figure does not measure stability.** Pass 2 searched with the planner's instruction text and pass 3 searched with the visitor's question, so the query itself differed and a change in the cited files is exactly what should happen. Measuring whether the fix makes citations *stable* needs two passes that both use the new search, and that was not run. What the figure does show is how much the cited files move when the query changes, which is the mechanism the fix was aimed at.
  **The budget probe gave a badly wrong number and the daily floor could not be honoured.** `scripts/token_budget.py` estimated about 199,200 daily tokens remaining; the provider then reported 199,400 of 200,000 already used. The estimate is derived from `x-ratelimit-remaining-requests`, which was showing 996 of 1000 — but that counter's own `x-ratelimit-reset-requests` header reads under three minutes, so it is not a daily counter at all and refills continuously. Treating it as daily was my error, and the entry for that script should be read with this one. The `--min-daily-tokens 40000` floor was therefore never applied: the true figure is only knowable from a 429, by which time the budget is already spent, so the run stopped at 600 tokens left rather than 40,000. The stop itself worked exactly as intended — it caught the provider's own words, stopped cleanly, and kept every completed result on disk — but it is a backstop, not a floor

### Fix: the daily token figure is counted locally, not inferred from a request counter
- Value: `scripts/token_budget.py` estimated daily tokens remaining from `x-ratelimit-remaining-requests`, treating it as a daily counter. It is not: its own `x-ratelimit-reset-requests` header reads one to three minutes, so it refills continuously. The consequence was measured on 2026-10-06 — the probe reported **about 199,200 daily tokens left** while the provider had in fact used **199,400 of 200,000**, and a run started on that basis was refused minutes later. The inference is removed. The probe now prints only what the provider really sends, and says the daily figure is unknown unless the provider has stated it:
  ```
  model                     : openai/gpt-oss-20b
  tokens per minute         : 7,927 of 8,000 left (resets in 547ms)
  requests                  : 999 of 1,000 left (resets in 1m26.4s; not a daily counter)
  daily tokens              : unknown unless the provider states it
  spent today, this machine : 0 tokens over 0 call(s)  [.codeatlas\token-spend.json]
  WARNING                   : nothing recorded today on this machine; the account may still have been used elsewhere
  ```
  In its place the spend is counted on this machine. Every model call adds its usage to `.codeatlas/token-spend.json` — per model, with a call count, reset when the date changes — and `scripts/answer_smoke.py` stops cleanly once today's total passes `--max-daily-tokens`, default **150,000**, leaving room under a 200,000 allowance for live testing. A figure the provider does state, inside a 429, is still used and is shown as its own rather than as an estimate
- Command: `python scripts/token_budget.py` (output above; one request of a single output token, no model answer requested); `python -m pytest` (548 passed, 1 skipped; `tests/test_token_ledger.py`, 25 new tests with a fake provider, and `tests/test_token_budget.py` rewritten to 14 tests for what remains true); `ruff check codeatlas/ tests/ scripts/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (27 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`
- Dataset/repo: none (a fake provider reports usage; the single probe request went to the live provider and asked for one output token)
- Date: 2026-10-06
- Commit: 0926959
- Notes: the ledger file sits under `.codeatlas/`, which `.gitignore` line 12 already ignores; `git check-ignore` confirms it. Recording is wrapped so a failure to write leaves the call uncounted rather than failing the request, which a test covers by pointing the path at a directory. The tests covered the counting through the real `AgentUsageCallback`, and in doing so revealed that **the suite had been writing invented tokens into the developer's real ledger** — 36 tokens under the model name "unknown" after one run. `tests/conftest.py` now points the ledger at a temporary file for every test, and the suite was confirmed to leave no file behind. **Limits:** the count is of what *this machine* spent. Another machine, another checkout with a different working directory, or use through the provider's web console are not in it, so it is a lower bound on the account's real usage and the probe warns when it has recorded nothing today. The probe's own one-token request goes through the raw SDK rather than the app, so it is not counted either. 150,000 is a default, not a measured safe figure, and a provider that reports no usage metadata contributes a call with zero tokens

### Fix: an unknown embedding provider name is rejected, not guessed at
- Value: `get_embedder()` read `CODEATLAS_EMBEDDING_PROVIDER` as "hash, or else sentence-transformers". Any other value — a typo such as `sentance`, or a provider that was never wired up — fell through to sentence-transformers, so the app either crashed later with an install message naming a package the operator never asked for, or, once that package was present, indexed with vectors nobody chose. The known names now live in one tuple (`EMBEDDING_PROVIDERS` in `codeatlas/utils/config.py`); `load_config()` rejects anything else at startup with `Unknown embedding provider 'sentance'. Set CODEATLAS_EMBEDDING_PROVIDER to one of: hash, sentence. 'hash' is the default and needs no extra install.`, and `build_embedder()` repeats the check for an `AppConfig` built directly rather than from the environment. Names are matched after stripping and lowercasing, so `HASH` and ` hash` work
- Command: `python -m pytest tests/test_config.py` (9 tests: the typo rejected with both valid names in the message, every listed provider accepted and buildable, three spellings of `hash` normalized, and `build_embedder` rejecting a name it was handed directly); `python -m pytest` (597 passed, 1 skipped); `ruff check codeatlas/ tests/ scripts/`, `ruff format codeatlas/ tests/ --check`
- Dataset/repo: none (config values only; constructing an embedder loads no model)
- Date: 2026-10-06
- Commit: feb180c
- Notes: this is a startup failure, by choice — an app told to use a provider that does not exist stops rather than serving results built from vectors the operator did not pick. `hash` stays the default and nothing changes for a setup that does not set the variable. **Limits:** the check is on the *name*, not on whether the provider will work. `sentence` is still accepted on a machine with no `sentence-transformers` installed; that failure still happens at the first index, with the install message it always had. Normalizing case and spaces is a convenience that hides a sloppy value rather than reporting it

### Change: fastembed is available as an opt-in embedding provider; hash stays the default
- Value: `CODEATLAS_EMBEDDING_PROVIDER=fastembed` selects `FastEmbedEmbeddingService` (`BAAI/bge-small-en-v1.5`, 384 dims, ONNX on CPU, no PyTorch), which produces real semantic vectors instead of the default hash embedder's hashed bag of words. Nothing about the default path changes: `hash` is still the default, `requirements.txt` is untouched, and the default Docker image contains neither the package nor a model. Opting in has four parts, and each applies **only** when that provider is selected:
  - install from `requirements-fastembed.txt`, a separate file (`fastembed==0.8.1`)
  - **batch size 1** — one document per `embed()` call, so a CPU transformer does not hold a large batch in memory and the indexer's time check is not deferred by a whole batch
  - **3,000-character clipping** of each file or function before embedding (`CODEATLAS_FASTEMBED_MAX_CHARS`)
  - **a longer index timeout, 900 s** against the 120 s the other providers use (`CODEATLAS_FASTEMBED_INDEX_TIMEOUT_SECONDS`), applied by `index_options()` only for this provider
  The model download is an opt-in build argument: `docker build --build-arg INSTALL_FASTEMBED=1 .` installs the package and bakes the model into the image; without it the `RUN` copies one small file and does nothing, so the default image is unchanged. The embedder's `signature()` is `fastembed:<model>`, so an index built with it is never reused by `hash` or by a different fastembed model
- Command: `python -m pytest tests/test_fastembed_provider.py` (15 tests: hash still the default, the provider selected by name without loading a model, batch size 1 at both the embedder and the index service, the 3,000-character clip, the longer timeout applying to fastembed and not to `hash` or `sentence`, the fastembed-only settings being invisible to other providers, the signature differing from hash and naming the model, batch size deliberately *not* in the signature, the missing-install message naming `requirements-fastembed.txt`, and two that load the real model — 384-dim unit-length vectors, and a signature question scoring closer to `verify_signature` than to `render_template`); `python -m pytest` (613 passed, 1 skipped); `ruff check codeatlas/ tests/ scripts/`, `ruff format codeatlas/ tests/ --check`
- Dataset/repo: none here (the two model-loading tests embed four short hand-written strings). Retrieval quality is measured separately in the entry below
- Date: 2026-10-06
- Commit: f755f47
- Notes: `fastembed` was installed into the project environment from the optional file so the two model-loading tests could run; they call `pytest.importorskip("fastembed")` and skip where it is absent, which is the default for this project, so CI is unaffected. **Limits:** the Docker build argument was **not** exercised — no image was built in this batch, so the `--build-arg INSTALL_FASTEMBED=1` path is written and reviewed but unverified, and `FASTEMBED_MODEL` must be set to the same model as `CODEATLAS_FASTEMBED_MODEL` by hand or the image bakes in a model the app will not ask for. 900 s and 3,000 characters are judgement calls, not measured figures: 3,000 characters is roughly the 512-token window the model truncates to anyway, so the clip mostly saves tokenizer work rather than changing vectors. `sentence` is still accepted as a name and still has no install of its own

### Fix: an index is only searched by the embedder that built it
- Value: the index cache already compared `CodeIndexService.index_format` (which contains the embedder's signature) against the copy saved in the state store, so `/analyze-repo` missed and re-indexed when the embedder changed. The **index itself** recorded nothing about who built it, which left two paths unguarded: `has_index()` said yes to any stored index, and a question asked against a `repo_id` held from before a provider change searched the old index with the new embedder's query vector. Nothing makes that visible at search time — the hash embedder and `bge-small` are **both 384 wide**, so FAISS returns confidently ranked nonsense rather than an error. `FaissCodeRetriever` now stores the embedder's signature beside the records and exposes it as `stored_embedder(repo_id)`; `has_index()` refuses a recorded mismatch, and `AnswerService.retrieve` returns no records and logs `Index for repo r was built by embedder 'fake-a', not 'fake-b'; refusing to search it. Analyze it again.`
- Command: `python -m pytest tests/test_embedder_identity.py` (18 tests, all with fake embedders and no real provider: the signature written with the index and surviving a restart, the real hash embedder's full signature recorded, two fake embedders that return **identical vectors** still refused each other's index, an embedder that does not override `signature()` still separated by its class name, `has_index` false across embedders, the analyze cache missing and then reusing the new embedder's index, switching back reusing the first one, a question returning nothing across embedders, the warning naming both embedders, and an unknown `repo_id` not mistaken for a mismatch); `python -m pytest` (631 passed, 1 skipped); `ruff check codeatlas/ tests/ scripts/`, `ruff format codeatlas/ tests/ --check`
- Dataset/repo: none (fake embedders over a one-file repo in a pytest temp directory)
- Date: 2026-10-06
- Commit: cdd285a
- Notes: **which of these tests the new code is actually responsible for was checked, not assumed.** With `embedder_mismatch` forced to return `False`, 6 of the 18 fail and 12 still pass. The 12 include both end-to-end `/analyze-repo` tests, because the pre-existing state-store comparison already covered that path; they are kept as regression cover but they do **not** demonstrate this change. The 6 that do are the two `embedder_mismatch` cases, the identical-vectors case, the default-signature case, `has_index`, and the two question-path cases.
  **Limits, and a deliberate hole.** An index with no recorded embedder — every index written before this commit — is still searched and still reused. Absence of a record is not evidence of a different embedder, and refusing them all would blank out existing deployments until every repository was analyzed again; the trade is that an index from before this commit gets no protection at all. `stored_embedder` returns `None` by default on `CodeRetriever`, so a retriever that does not track it is treated the same way. The guard is on the embedder's *name for itself*: an embedder that changes how it produces vectors without changing its `signature()` would pass, which is why the fastembed signature carries its model name. The on-disk `.pkl` now holds a dict rather than a bare record list, and a file in the old shape is still read

### Check: retrieval eval, hash against fastembed, on the dev split and the held-out split
- Value: both providers were run over the same 40 questions at the same pinned commits, with no setting tuned on either split. **fastembed is better on both splits, and the gain on the held-out split is the larger of the two.**

  **dev split (20 questions)**

  | repo | n | embedder | hit@1 | hit@3 | hit@5 | P@1 | P@3 | P@5 | MRR@10 |
  |------|---|----------|-------|-------|-------|-----|-----|-----|--------|
  | itsdangerous | 10 | hash | 0.600 | 0.700 | 0.800 | 0.600 | 0.500 | 0.400 | 0.692 |
  | itsdangerous | 10 | **fastembed** | 0.600 | **0.800** | **0.900** | 0.600 | **0.567** | **0.520** | **0.708** |
  | flask | 10 | hash | 0.600 | 0.700 | 0.700 | 0.600 | 0.467 | 0.360 | 0.633 |
  | flask | 10 | **fastembed** | **0.700** | **1.000** | **1.000** | **0.700** | **0.633** | **0.480** | **0.850** |
  | overall | 20 | hash | 0.600 | 0.700 | 0.750 | 0.600 | 0.483 | 0.380 | 0.662 |
  | overall | 20 | **fastembed** | **0.650** | **0.900** | **0.950** | **0.650** | **0.600** | **0.500** | **0.779** |

  **test split, held out (20 questions)**

  | repo | n | embedder | hit@1 | hit@3 | hit@5 | P@1 | P@3 | P@5 | MRR@10 |
  |------|---|----------|-------|-------|-------|-----|-----|-----|--------|
  | itsdangerous | 10 | hash | 0.800 | 0.800 | 0.900 | 0.800 | 0.700 | 0.560 | 0.820 |
  | itsdangerous | 10 | **fastembed** | 0.800 | **0.900** | 0.900 | 0.800 | **0.767** | **0.720** | **0.867** |
  | flask | 10 | hash | 0.400 | 0.500 | 0.600 | 0.400 | 0.367 | 0.280 | 0.470 |
  | flask | 10 | **fastembed** | **0.800** | **0.900** | **0.900** | **0.800** | **0.667** | **0.520** | **0.861** |
  | overall | 20 | hash | 0.600 | 0.650 | 0.750 | 0.600 | 0.533 | 0.420 | 0.645 |
  | overall | 20 | **fastembed** | **0.800** | **0.900** | **0.900** | **0.800** | **0.717** | **0.620** | **0.864** |

  Held-out overall: **hit@1 +0.200, hit@3 +0.250, hit@5 +0.150, MRR@10 +0.219.** Per question on the held-out split, **5 questions gained a hit@5 and 2 lost one** (net +3 of 20); by reciprocal rank, 7 improved, 2 got worse, 11 were unchanged. On dev, 4 gained and **0 lost**. Nearly all of the held-out gain is flask, where hash was weakest: `flask-10`, `flask-12`, `flask-14` and `flask-20` went from no relevant file in the top 10 to the right file at rank 1. The two regressions are `flask-16` (rank 1 → rank 9) and `itsd-12` (rank 5 → rank 6).

  **Cost: hash indexed and scored a split in 4–5 s; fastembed took 256 s (dev) and 341 s (test)**, about 60x, for the same 1,864 records — which is why that provider gets batch size 1, a 3,000-character clip and a 900 s index timeout
- Command: `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/eval_retrieval.py --split dev --json eval/results/dev.json` and the same for `--split test` and `--split all`; `CODEATLAS_EMBEDDING_PROVIDER=fastembed python scripts/eval_retrieval.py --split dev --json eval/results/fastembed/dev.json` and the same for `--split test`. No model key is used; retrieval only
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd (15 files, 159 records); https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35 (83 files, 1705 records); the 40 questions in `eval/questions/*.json`, split as fixed before any of this was run
- Date: 2026-10-06
- Commit: f2a55dd (the results); measured at 97242ac
- Notes: **nothing was tuned on the held-out split, and nothing was tuned at all.** Both providers ran on the settings already in `config.py`; no tuning flag was passed, and the test split was run once per provider after the dev run, not used to choose anything. The gain on held-out was not small or negative — it is larger than the gain on dev, which is the opposite of the usual worry and is itself a reason for caution: 20 questions per split is small, so a 0.200 difference in hit@1 is 4 questions.
  **This is not a controlled embedder-only swap, and should not be read as one.** The fastembed run also clipped each document to 3,000 characters and embedded at batch size 1, because those are that provider's settings; hash embedded the full text. So what is compared is *the server running hash* against *the server running fastembed*, which is the decision actually on the table, not the embedder in isolation. The clip plausibly helps on flask's long files, and separating the two was not measured.
  **The reranker limits how much the embedder can matter.** `rerank_weight` is 1.0, so the final order is keyword overlap with vector similarity only breaking ties; the embedder chooses the 20 candidates, not their order. A fair reading of these numbers is that fastembed puts the right file in the candidate pool far more often on flask, where hash's bag of words misses questions phrased in plain English.
  **hash remains the default** and nothing in this entry changes that: fastembed is 60x slower to index, needs an extra install and a model download, and the deployment it would run on has not been sized for it. The retrieval gauges on `/metrics` still read the three hash files in `eval/results`; the fastembed results are in a subfolder the gauge loader does not glob, verified by loading them (3 files read, all labelled `hash`).
  Four of the five eval runs report the commit as `97242ac-dirty`. The only modified files were the eval result JSON files the runs themselves had just written; no code differed between the five runs. `eval/results/all.json` was refreshed for hash at the same commit, for consistency within the folder; `all` is dev and test together and is not a third measurement

### Check: what the Cloudflare Workers AI embeddings endpoint actually does, where the docs are silent
- Value: nine calls answered the four questions that decide how the provider has to be written. **An array of 101 texts was accepted, so the widely repeated 100-item cap is not current. An 8,000-character text is accepted and silently truncated. `pooling: "cls"` is accepted over REST and is a genuinely different vector space. A bad token is an HTTP 401 with error code 10000.**

  | call | texts | chars | result |
  |------|-------|-------|--------|
  | baseline | 1 | 56 | HTTP 200, success=True, shape=[1, 384], pooling=mean |
  | array-50 | 50 | 2840 | HTTP 200, success=True, shape=[50, 384], pooling=mean |
  | array-100 | 100 | 5690 | HTTP 200, success=True, shape=[100, 384], pooling=mean |
  | array-101 | 101 | 5748 | HTTP 200, success=True, shape=[101, 384], pooling=mean |
  | long-8000 | 1 | 8000 | HTTP 200, success=True, shape=[1, 384], pooling=mean |
  | head-2400 | 1 | 2400 | HTTP 200, success=True, shape=[1, 384], pooling=mean |
  | tail-2400 | 1 | 2400 | HTTP 200, success=True, shape=[1, 384], pooling=mean |
  | pooling-cls | 1 | 56 | HTTP 200, success=True, shape=[1, 384], pooling=cls |
  | invalid-token | 1 | 56 | HTTP 401, success=False, errors=[{"code": 10000, "message": "Authentication error"}] |

  **Batch size: 101 works, and the real ceiling was not looked for.** The "maximum 100" that circulates comes from a LlamaIndex integration page marked as seen 2024-03-31 and from cloudflare-docs issue #11316, a user report from 2023. Neither matches the endpoint today. Finding the true edge would mean a binary search of calls against a free allowance to learn a number the provider does not need, so the probe stopped at 101 and the provider will batch at 50 - comfortably inside whatever the limit is, and small enough that one failed batch re-sends little.

  **Over-length text is truncated, not refused, and the cut is at or before 2,400 characters.** The 8,000-character input was 2,400 characters on one subject followed by 5,600 on an unrelated one. Its vector against the first subject embedded alone: **cos = 1.0000**. Against the second subject alone: **cos = 0.5888**. Identical to the head to four decimal places means the tail contributed nothing at all. Since 2,400 characters is already about 600 tokens, this is consistent with the documented 512-token window and tells us the model's own cut sits below 2,400 characters. The planned 2,000-character clip is therefore a cost control that we choose, not a limit we are up against - but it also means **a document longer than roughly 2,000 characters is only ever embedded by its opening**, whatever we set, which is a retrieval limitation to carry into the evaluation rather than a bug to fix.

  **cls and mean are different spaces, and not different enough to be safe.** The same text embedded both ways gives **cos = 0.9466**. That is the dangerous case: not orthogonal nonsense that any sanity check would catch, but a near-miss that would quietly degrade ranking if an index built under one pooling were searched under the other. It is the concrete reason pooling belongs in the embedder signature alongside the model name, where the existing `embedder_mismatch` guard will refuse the mismatch.

  **A refusal is HTTP 401 with `success: false` and `errors: [{"code": 10000, "message": "Authentication error"}]`.** The body is JSON and carries no echo of the request. **What a spent-budget refusal looks like is still unknown** and cannot be learned without spending the day's allowance, so the fallback to hash will trigger on any non-2xx status and any transport failure, never on a particular code.
- Command: `python scripts/cloudflare_probe.py --dry-run` then `python scripts/cloudflare_probe.py`
- Dataset/repo: none. Every input is an invented string defined in the script - short filler sentences, and two unrelated paragraphs for the truncation test. No repository content, no question, and no credential is printed: the output is statuses, shapes, pooling and error codes only
- Date: 2026-10-09
- Commit: 83fff8c
- Notes: **cost: 6,344 estimated input tokens, 11.68 estimated neurons** of the 10,000-per-day free allowance (0.12%), by the estimator the provider will use - `ceil(chars / 3)` per text, capped at 512 per text. The invalid-token call is excluded from the estimate because it never reached the model. This is an estimate from character counts, not a figure Cloudflare reported: the response carries no token or neuron count, so the only authoritative number is the account dashboard.
  **The probe is capped at 10 calls in code** (`MAX_CALLS`), and `--dry-run` prints the plan and the estimate without sending anything, which is also how the tests exercise it - `tests/test_cloudflare_probe.py` asserts the plan stays inside the cap, that every input is small, that the whole run costs under 1% of the daily allowance, and that nothing printed contains an input text.
  **Three things this run did not establish.** The true maximum array length (above 101, not looked for). Whether Cloudflare bills the truncated tail of an over-length text or only the 512 tokens it read - our estimator assumes the latter, which is the optimistic reading, so a dashboard figure above the estimate would mean documents must be clipped before sending rather than relying on the model's own cut. And the status and body of a budget-exhausted refusal

### Check: the neuron estimator against the account dashboard, after the probe
- Value: **the dashboard read 8.41 neurons for the probe run; the estimator said 11.68.** The estimator over-counts by **1.39x**, which is the direction it was built to err in, and the gap is explained entirely by its deliberately pessimistic 3 characters per token.

  | | input tokens | neurons |
  |---|---|---|
  | `estimated_neurons`, `ceil(chars / 3)` capped at 512 per text | 6,344 | 11.68 |
  | implied by the dashboard, at 1,841 neurons per million input tokens | 4,568 | **8.41** |

  **Where the 1.39x comes from, and a second thing it tells us.** The probe billed 27,190 characters across eight successful calls, 8,000 of them in the single over-length text. Solving for the real characters-per-token under each assumption about how that long text was billed:

  | assumption about the 8,000-character text | characters per token the rest implies |
  |---|---|
  | billed the 512 tokens it actually read | **4.73** |
  | billed its full length, about 1,700 tokens | 6.69 |
  | billed more still | 10.09 |

  Only 4.73 is a real number for English prose; 6.69 and 10.09 are not figures any tokenizer produces. So **the truncated tail was not billed** - Cloudflare charged for the 512 tokens the model read, not the 8,000 characters sent. That answers one of the three questions the probe left open, and it means the per-document clip is a bandwidth and latency choice rather than a cost one. The clip stays at 2,000 characters anyway: it is below the model's own cut, so it changes nothing about what is embedded, and sending less is still better.
- Value (kept deliberately): the estimator stays `ceil(chars / 3)` capped at 512 tokens per document. Against real code, which tokenizes worse than prose, the margin will be smaller than 1.39x, and an estimate that stops early is the one that protects a free allowance. **The ledger is therefore a ceiling on spend, never a measurement of it.**
- Command: `python scripts/cloudflare_probe.py` (the run recorded in the entry above), then the account dashboard read by hand
- Dataset/repo: none; the probe's own invented inputs
- Date: 2026-10-09
- Commit: 83b2284 (the probe results this calibrates)
- Notes: **the 8.41 figure is user-supplied, read from the Cloudflare dashboard by the account holder, not obtained by this project.** Nothing in the codebase can read it: the embeddings response carries no token or neuron count, which is the whole reason the ledger exists. It is also rounded to two decimals at an unknown precision, and may include overheads this arithmetic cannot see, so the 4.73 characters per token derived from it is an inference from one data point and not a constant to build on.
  The comparison to repeat after the first real evaluation build is this same one at a scale where code, not prose, is being embedded

### Feature: an opt-in Cloudflare Workers AI embedding provider, off by default
- Value: `CODEATLAS_EMBEDDING_PROVIDER=cloudflare` embeds through @cf/baai/bge-small-en-v1.5 over REST, with **no new dependency** - the call is the stdlib client added with the probe. **hash is still the default**, and `test_the_cloudflare_settings_are_ignored_by_other_providers` pins that no cloudflare setting can move a hash index or its signature.

  **Three failure paths, all of which end at the hash index.** This provider spends a free allowance that resets once a day and cannot be topped up, so it is built to stop rather than to try harder:

  | reason | when | what the visitor reads |
  |---|---|---|
  | `budget` | today's estimated spend would pass `CODEATLAS_CLOUDFLARE_DAILY_NEURONS` (8,000 of the 10,000 free) | "Today's semantic search allowance is used up, so this answer used keyword search." |
  | `api` | any transport error, any non-2xx, any malformed body | "Semantic search did not respond, so this answer used keyword search." |
  | `circuit` | three consecutive failures, for the next five minutes | "Semantic search is briefly unavailable, so this answer used keyword search." |
  | `cap` | repository over `CODEATLAS_CLOUDFLARE_MAX_DOCUMENTS` (600) | "This repository is too large for semantic search, so this answer used keyword search." |

  **Failures are deliberately not told apart.** A spent allowance is reported by a status Cloudflare has not documented - the probe could not learn it without spending the day's budget - so matching on an error code would be guessing at the one case that matters most. "It did not work, use the hash index" is the only reading that cannot be wrong, and it is what the caller needs in every case anyway.

  **The budget is checked before the call, never after.** Each batch's estimate is compared against a gitignored per-UTC-day ledger in `.codeatlas/cloudflare-neurons.json` and refused if it would pass the budget. UTC because that is when Cloudflare's allowance resets; local time would hand back the allowance at the wrong hour. `test_the_budget_stops_part_way_through_a_long_repository` pins that the refusal happens at the batch boundary, so a repository indexes as far as the budget reaches rather than all-or-nothing.

  **Settings in the signature, and settings deliberately not in it.** The signature is `cloudflare:<model>:pooling=<p>:max_chars=<n>:prefix=<0|1>:subtokens=<0|1>:stopwords=<0|1>`. Pooling is in it because the probe measured **cos 0.9466** between the same text under `cls` and under `mean`: close enough to look like it is working, far enough to rank worse, and nothing downstream would catch it. Batch size, timeout, retries, the budget and the document cap are **out** of it, because none of them changes a vector and putting them in would throw away an index that had been paid for every time a budget was raised.
- Command: `python -m pytest tests/test_cloudflare_provider.py tests/test_neuron_ledger.py -q` (76 and 11 tests), then the full suite: `python -m pytest tests/ -q` -> 750 passed, 1 skipped
- Dataset/repo: none. **No test in this change reaches the network**: the provider is driven end to end by a fake client that records what it was asked to send
- Date: 2026-10-09
- Commit: 009d69f
- Notes: **what is never written down, and how that is checked.** No document, question, URL, account id or token appears in a log, an error message, an exception repr or the ledger. `test_no_document_text_question_or_credential_is_logged` drives four real failures with `caplog` at DEBUG, asserts something was logged (so the test cannot pass vacuously) and then that none of it is the text being embedded, the credentials, or even the hostname. The ledger holds three fields per day - estimated neurons, documents, calls - and `test_the_ledger_holds_counts_and_nothing_about_what_was_embedded` pins that list exactly.
  **A real cost worth knowing about: `rerank_subtokens` is in the signature although it does not change any vector.** It was included because an index should only be searched under the retrieval configuration it was measured with. The price is that flipping that one rerank setting invalidates every Cloudflare index and makes the repositories pay to be embedded again, for vectors that would have been identical. The eval's vector cache is keyed on the text rather than the signature, so experiments do not pay it; a deployment that flips the setting would. Dropping it from the signature is a one-line change if that trade turns out to be the wrong way round.
  **Spend is counted only after a call that worked.** A refused call is not billed, and a call that vanished in transit cannot be counted without inventing the number - so a timeout that Cloudflare did in fact process goes uncounted, and the ledger reads low by that much. The 2,000-neuron cushion between the 8,000 budget and the 10,000 allowance is what covers that.
  **The index time limit is the shared `CODEATLAS_INDEX_TIMEOUT_SECONDS`**, not a new one. A repository at the 600-document cap is twelve calls of fifty, so the 120 s default has room; raising the cap means raising the limit too, and a timeout throws the index away while the neurons stay spent

### Feature: every semantic repository also gets a hash index, and questions fall back to it with a note
- Value: with `CODEATLAS_EMBEDDING_PROVIDER=cloudflare` a repository is indexed twice from the same records. **The hash index is built first and always**, so a repository is never left holding only the index that might not be there when a question arrives. 30 tests in `tests/test_dual_index.py` cover it; 781 pass overall.

  **Where each index lives, and why that is not a detail.** The hash index stays in `CODEATLAS_INDEX_DIR`, exactly where existing hash indexes already are - nothing was moved or rebuilt. The semantic index gets `CODEATLAS_CLOUDFLARE_INDEX_DIR` (`.codeatlas/indexes-cloudflare`). Two embedders' vectors are not comparable and a FAISS index cannot tell you so: both are 384 wide, so a mismatched query returns confident nonsense. Separate folders are the cheapest way to be certain they never meet, and the embedder signature check is the second line, not the first.

  **Two kinds of failure, so the routing happens in two stages.**

  | stage | what is known | what happens |
  |---|---|---|
  | before calling anything | what is on disk: whether a usable semantic index exists for this repository | an over-cap repository, or one whose semantic index was built by a different embedder, goes straight to hash with the `unindexed` note |
  | while calling | whether the embedder actually works | `EmbeddingUnavailableError` from `embed_query` is caught, the same question is asked again against the hash index, and the note is the reason's |

  The second stage is the one that matters: a visitor is already waiting when it happens. `test_a_failure_at_question_time_falls_back_and_tells_the_visitor` indexes with an embedder that works and then asks with one that does not, because that is the real sequence and a test that fails at index time would prove something else entirely.

  **The visitor is told, above the answer.** One sentence, in a small bordered line over the answer text rather than inside the "Reasoning" dropdown: an answer built from the weaker search should say so where the answer is, not where someone would have to go looking. The note travels `GroundedAnswer.note` -> `AnswerResult.note` -> `AskResponse.retrieval_note` and the `done` event -> `MessageBubble`. In the agent graph a later successful retrieval does **not** erase an earlier fallback, so if any search behind an answer used the hash index the visitor hears about it.

  | reason | sentence |
  |---|---|
  | `budget` | Today's semantic search allowance is used up, so this answer used keyword search. |
  | `circuit` | Semantic search is briefly unavailable, so this answer used keyword search. |
  | `api` | Semantic search did not respond, so this answer used keyword search. |
  | `unindexed`, `cap` | Semantic search is not available for this repository, so this answer used keyword search. |

- Command: `python -m pytest tests/test_dual_index.py -q` (30 tests), `python -m pytest tests/ -q` -> 781 passed, 1 skipped; `npm run lint`, `npm run test`, `npm run build` in `codementor-ui`
- Dataset/repo: none. Repositories are built in pytest temp directories and the failing provider is a fake that raises the real exception type; nothing reaches the network
- Date: 2026-10-09
- Commit: c7f51cd
- Notes: **a correction to the previous entry's wording.** That entry listed the `cap` note as "This repository is too large for semantic search". It now reads "Semantic search is not available for this repository", because at question time an over-cap repository and one whose semantic index was built by a different embedder are indistinguishable from the index on disk, and telling a visitor their repository is too large when in fact the index is stale would be worse than saying less. The `cap` key is still what indexing logs when it skips a repository for size.
  **The error lives on the embedding interface, not on the provider.** `EmbeddingUnavailableError` is defined in `embedding.py` and `CloudflareUnavailableError` subclasses it, so `AnswerService` catches the general case and the question path contains no mention of Cloudflare. A later provider that can fail the same way gets the fallback without the question path being touched.
  **For hash, the default, none of this exists.** `get_fallback_retriever()` and `get_fallback_embedder()` return `None` for every provider but cloudflare, `get_index_service()` returns the single `CodeIndexService` it always did, and `test_without_a_fallback_nothing_changes` pins that a mismatched index still returns nothing rather than quietly falling back to something.
  **A fix that came with this, not asked for but needed:** `/search` used to read `CODEATLAS_INDEX_DIR` whatever the provider was, so with a semantic provider selected it would have embedded the query with one embedder and searched the other embedder's index - the exact failure the signature guard exists to prevent, on the one endpoint that bypasses the guard. It now reads the selected provider's own index. Its behaviour is otherwise untouched.
  **What is not covered.** The two indexes are written in sequence with no transaction: a crash between them leaves a hash index and no semantic one, which is the safe direction but means `indexes` in the repository state can be optimistic if the process dies mid-write. An index built before this change records `indexes: ()`, which means "not recorded" and must not be read as "has no indexes"

### Feature: the seven retrieval settings are configurable by environment variable, with the measured defaults
- Value: `candidates`, `rerank_weight`, `rerank_subtokens`, `drop_stopwords`, `skip_tests`, `embed_max_chars` and `embed_prefix_metadata` now read from the environment. **Every default is unchanged** and `test_every_default_is_the_one_that_was_measured` checks all seven against the figures the earlier entries in this file measured.

  | variable | default | what it does |
  |---|---|---|
  | `CODEATLAS_RETRIEVAL_CANDIDATES` | 20 | records taken from vector search before reranking |
  | `CODEATLAS_RERANK_WEIGHT` | 1.0 | 1.0 keyword overlap only, 0.0 vector order only |
  | `CODEATLAS_RERANK_SUBTOKENS` | false | match the parts of identifiers too |
  | `CODEATLAS_DROP_STOPWORDS` | true | leave common English words out of the question |
  | `CODEATLAS_SKIP_TESTS` | false | drop records from test files |
  | `CODEATLAS_EMBED_MAX_CHARS` | 0 (no limit) | embed only the first N characters of a document |
  | `CODEATLAS_EMBED_PREFIX_METADATA` | true | start each document with its path and name |

  **A wrong value stops the app rather than becoming a setting.** `CODEATLAS_RETRIEVAL_CANDIDATES=twenty`, `CODEATLAS_RERANK_WEIGHT=1.5` and `CODEATLAS_DROP_STOPWORDS=flase` are all startup failures naming the variable. This is **stricter than the older flags in the same file**, which read `== "true"` and so take a typo as off, and it is stricter deliberately: the failure being guarded against is not a crash, it is an app that starts, answers differently, and tells nobody - after which a number in this file would describe a configuration that was never running. An empty variable is the single exception and means the default, because that is how a deployment unsets a value.
- Command: `python -m pytest tests/test_retrieval_settings_from_env.py -q` (31 tests), then `python -m pytest tests/ -q` -> 812 passed, 1 skipped
- Dataset/repo: none; environment variables and config defaults
- Date: 2026-10-09
- Commit: 68d0ae9
- Notes: **provider-specific defaults still win where a provider has one.** `CODEATLAS_EMBED_MAX_CHARS` is the shared setting; the cloudflare provider clips at `CODEATLAS_CLOUDFLARE_MAX_CHARS` (2,000) whatever the shared one says, and fastembed at its own 3,000, exactly as before. `test_a_provider_may_still_have_its_own_defaults` pins that.
  **`POST /search` does not go through any of this, and now says so** in `.env.example` and in its own module docstring. It embeds the query and returns what the index gives back: no reranking, no stopword dropping, no test filtering, no fallback to hash. Its results are therefore not what a visitor would see for the same words, and it is not the endpoint to measure retrieval with - `scripts/eval_retrieval.py` goes through `AnswerService`, which is the pipeline. Its behaviour is unchanged by this batch apart from following the selected provider's index.
  **The two indexing settings are not free to change.** `embed_max_chars` and `embed_prefix_metadata` are part of `index_format`, so changing either means the index cache stops reusing existing indexes and every repository is indexed again - which for the cloudflare provider costs neurons

### Check: recall@20 added to the retrieval eval, and the existing numbers are unchanged
- Value: **hash on the held-out split still prints hit@5 0.750 and MRR@10 0.645**, the figures recorded before this change, and now also prints recall@20.

  | split | repo | n | hit@1 | hit@3 | hit@5 | P@1 | P@3 | P@5 | MRR@10 | **recall@20** |
  |---|---|---|---|---|---|---|---|---|---|---|
  | dev | itsdangerous | 10 | 0.600 | 0.700 | 0.800 | 0.600 | 0.500 | 0.400 | 0.692 | **0.900** |
  | dev | flask | 10 | 0.600 | 0.700 | 0.700 | 0.600 | 0.467 | 0.360 | 0.633 | **0.800** |
  | dev | overall | 20 | 0.600 | 0.700 | 0.750 | 0.600 | 0.483 | 0.380 | 0.662 | **0.850** |
  | test | itsdangerous | 10 | 0.800 | 0.800 | 0.900 | 0.800 | 0.700 | 0.560 | 0.820 | **1.000** |
  | test | flask | 10 | 0.400 | 0.500 | 0.600 | 0.400 | 0.367 | 0.280 | 0.470 | **0.600** |
  | test | overall | 20 | 0.600 | 0.650 | 0.750 | 0.600 | 0.533 | 0.420 | 0.645 | **0.800** |

  **What recall@20 is for.** It is the share of questions whose expected file is anywhere in the 20 candidates the reranker chooses from - the embedder's own score, with the reranker's opinion removed. `rerank_weight` is 1.0, so the final order is keyword overlap; the embedder decides *which* 20 records are available and nothing else. A question whose file never reaches the pool cannot be answered well however the ordering is tuned, so this is the number that moves when the embedder changes.

  **It already says something about hash.** On held-out flask, hash has recall@20 **0.600** against hit@5 0.600 - every question whose file is in the pool is already ranked into the top five, so **reranking is not what is losing those four questions; the bag-of-words embedding never found the file at all.** On itsdangerous, recall@20 is 1.000 while hit@5 is 0.900: there, one question is in the pool and mis-ranked, which is the kind of loss an ordering change could recover. The two repositories therefore have different problems, and only one of them is an ordering problem.

  **How the old numbers were kept old.** Retrieval runs once to the pool depth and is read twice: the ranked answer is still its first ten, and recall is computed over the full pool through a separate `candidates` argument to `ranking_metrics`. Deepening the list the existing metrics see would have raised MRR@10 for every question with a hit at rank 11 to 20 and silently invalidated every earlier entry in this file.
- Value (also added): under each repository's line, how many file records and function records are longer than the per-document clip, and what share of their characters survives it. For hash there is no clip, so both read 0.0% over the clip and 100.0% of characters kept
- Command: `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/eval_retrieval.py --split dev` and `--split test`; `python -m pytest tests/ -q` -> 817 passed, 1 skipped
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd (15 files, 159 records); https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35 (83 files, 1705 records); the same 40 questions in `eval/questions/*.json`, split as fixed before any of this
- Date: 2026-10-09
- Commit: fa0db11
- Notes: **no neurons were spent on this**: hash runs entirely locally, and both splits took about three seconds each.
  The commit reports as `9256a77-dirty` in the run output because the eval was run before the commit that contains it; no code differed between the two runs other than being uncommitted.
  **recall@20 is capped by the pool, not by the index.** A file at rank 21 counts as not recalled, which is correct for this pipeline - the reranker would never see it - but means the figure describes retrieval as configured, not the embedding in the abstract. Raising `CODEATLAS_RETRIEVAL_CANDIDATES` would change it

### Check: what the Cloudflare evaluation will cost, before any of it is spent
- Value: the three dev configurations together are **1,485.90 estimated neurons**, 18.6% of the 8,000 budget and 14.9% of the 10,000 daily allowance. Nothing was sent to produce this figure.

  ```
  split: dev
  configurations: cls-2000, mean-1500, mean-2000
  ledger: 0.00 estimated neurons spent today (UTC 2026-10-09)
  budget: 8000, remaining 8000.00
    cls-2000      1864 documents   1884 not yet cached    495.47 estimated neurons
    mean-1500     1864 documents   1884 not yet cached    494.96 estimated neurons
    mean-2000     1864 documents   1884 not yet cached    495.47 estimated neurons
    total                              1485.90 estimated neurons
  ```

  **Far cheaper than the worst case, and the reason is the corpus.** A pessimistic estimate - every one of the 1,864 records filling the 2,000-character clip - would be about 1,757 neurons per configuration and over 5,200 for the three. The real figure is 495 per configuration, because most records are single functions of a few hundred characters and only a handful reach the clip at all. **The 600-document cap would have been the binding constraint, not the budget**, which is exactly why the evaluation does not apply it: capping the corpus at 600 of 1,864 records would have measured a third of flask and called it flask.

  **1,884 texts, not 1,864**: the twenty dev questions are embedded too, and are cached the same way. A question costs neurons like any other text.

  **The held-out runs are nearly free.** Both splits ask questions of the same repositories, so after the dev runs every document vector is already cached; a held-out run pays only for its own twenty questions, a fraction of a neuron. The same is true of a rerun. This is the whole reason the cache exists, and it is what makes "run held-out once for the default and once for the dev winner" cost almost nothing on top of the figure above.
- Command: `python scripts/eval_cloudflare.py --split dev --plan-only`
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd and https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35, 1,864 records between them; the 20 dev questions from `eval/questions/*.json`
- Date: 2026-10-09
- Commit: 7ed7016
- Notes: **this is the estimate, not a measurement**, by the same `ceil(chars / 3)` capped at 512 that over-counted the probe by 1.39x against the dashboard. If that ratio holds, the real cost of the three configurations is nearer 1,070 neurons - but code tokenizes worse than the prose the ratio was measured on, so the true figure should sit somewhere between the two, and the estimate remains the one to plan against.
  **The run was stopped here deliberately**, before a single call, so the dashboard can be read before and after and the ledger compared against it at a scale where code rather than prose is being embedded. 838 tests pass, including 21 covering the cache and the orderings

### Note: a record longer than the clip is embedded by its opening only
- Value: **more than half of every file record in both evaluation repositories is longer than the 2,000-character clip, and flask's file records keep only 18.6% of their characters.** The probe established that the model ignores text past about 512 tokens, so this is not only a bandwidth choice - a longer document is represented by its opening however the clip is set.

  | repo | clip | scope | records | over the clip | share | characters kept |
  |---|---|---|---|---|---|---|
  | itsdangerous | 2000 | file | 15 | 8 | 53.3% | 37.8% |
  | itsdangerous | 2000 | function | 144 | 8 | 5.6% | 70.1% |
  | itsdangerous | 1500 | file | 15 | 9 | 60.0% | 30.3% |
  | itsdangerous | 1500 | function | 144 | 11 | 7.6% | 65.2% |
  | flask | 2000 | file | 83 | 45 | 54.2% | 18.6% |
  | flask | 2000 | function | 1622 | 52 | 3.2% | 72.8% |
  | flask | 1500 | file | 83 | 47 | 56.6% | 14.6% |
  | flask | 1500 | function | 1622 | 81 | 5.0% | 68.9% |

  **The two scopes have completely different problems.** Function records are mostly intact: 3.2% of flask's 1,622 functions are clipped at all, and 72.8% of their characters survive. File records are not: **a flask file record is, on average, its first fifth**, and for the 54% that are clipped it is whatever the imports and the first definition happen to be. A question answered by matching a file record is therefore matching a header, not a file.

  This is a limit on what the semantic numbers in the following entries can mean. Whatever recall@20 turns out to be, it was achieved with file records that are mostly openings, and the headroom above it is not all reranking.
- Value (not built, deliberately): two candidates for a later batch, listed here so the reasoning is not lost and **neither is implemented in this one**:
  1. **Header-style file records.** Instead of a file's first 2,000 characters, an assembled summary: the path, the imports, and the names and signatures of what it defines. That is what a file record is being used for - "which file is this question about" - and it would fit the window with room to spare rather than being a truncated prefix pretending to be a file.
  2. **Windowed long functions.** Split a function longer than the clip into overlapping windows, embed each, and keep the best-scoring window for the record. This matters far less than the first: it would touch the 3-8% of functions that are clipped at all.

  Both change what is in an index, so both mean re-embedding every repository, which for this provider costs neurons. Neither should be built on this evidence alone - the right order is to find out what the semantic numbers are first, and only then decide whether file records are worth rebuilding
- Command: `CodeIndexService.clipped_counts` over both pinned checkouts at clips of 2,000 and 1,500; the same figures print under each repository in `python scripts/eval_retrieval.py` and `python scripts/eval_cloudflare.py`
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd (15 files, 159 records); https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35 (83 files, 1705 records)
- Date: 2026-10-09
- Commit: 3c53c66
- Notes: measured on the source text, before the path prefix is added, because that is the part the clip is deciding about. **No neurons were spent**: this counts characters and calls nothing.
  **The hash provider has no clip at all** (`embed_max_chars` is unset), so it reads every record in full. That is one more way in which the hash and cloudflare comparisons in this file are not a controlled embedder-only swap, and it cuts against the semantic provider rather than for it

### Fix: the Cloudflare embedder signature holds only what decides a vector
- Value: `rerank_subtokens` is out of the signature. It splits identifiers **while reranking**, long after the vectors exist, so an index built with it off and searched with it on would have returned exactly the same vectors - but the guard would have refused the index, and for this provider refusing an index means paying to embed every document again.

  | | before | after |
  |---|---|---|
  | signature | `cloudflare:<model>:pooling=mean:max_chars=2000:prefix=1:subtokens=0:stopwords=1` | `cloudflare:<model>:pooling=mean:max_chars=2000:prefix=1:stopwords=1` |

  **What is in it, and why each one earns its place.** The model and the pooling decide the vector outright - the probe measured cos 0.9466 between the same text under `cls` and under `mean`, close enough to look like it is working and far enough to rank worse. The clip decides how much of a document is seen. `prefix` decides the text of every document; `stopwords` decides the text of every question before it is embedded. Those five, and nothing else.

  **What is out, and why that is not laxity.** The rerank weight, reranker identifier splitting, the candidate count and test-file filtering all reorder records that have already been embedded. A signature that included them would be a guard against a mismatch that cannot happen, paid for in re-embedded documents.

  **The cost of getting this wrong was asymmetric, which is why it was worth fixing first.** Too little in the signature means confident nonsense from mismatched vectors. Too much means an unnecessary bill. But no Cloudflare index exists yet, so correcting it now costs nothing at all, while correcting it after the evaluation had built three indexes would have meant either re-embedding them or carrying the wrong signature forward.
- Command: `python -m pytest tests/test_cloudflare_provider.py -q` (82 tests), then `python -m pytest tests/ -q` -> 842 passed, 1 skipped
- Dataset/repo: none; the signature is a pure function of settings
- Date: 2026-10-09
- Commit: 60f5cf4
- Notes: tested in both directions. `test_flipping_a_ranking_only_setting_leaves_the_signature_alone` flips each of `CODEATLAS_RERANK_SUBTOKENS`, `CODEATLAS_RERANK_WEIGHT`, `CODEATLAS_RETRIEVAL_CANDIDATES` and `CODEATLAS_SKIP_TESTS` and asserts the signature is byte-identical; `test_every_setting_that_changes_the_embedded_text_changes_the_signature` asserts the five that remain each change it. A third test reads the signature as a **list of field names** rather than as a string, so a setting appended later fails a test and has to be argued for.
  This supersedes the "a real cost worth knowing about" paragraph in the provider's entry above, which recorded the trade as accepted. It was not worth accepting

### Check: three Cloudflare configurations on the dev split, three orderings each
- Value: **recall@20 is 1.000 for every configuration and every ordering** - all three put the expected file in the candidate pool for all 20 dev questions, against **0.850 for hash**. No ordering change passed the keep rule in any configuration, and no configuration beat the default, so **the dev winner is the default: mean pooling, clip 2,000, keyword ordering.**

  **Starting point: the account dashboard read 8.41 neurons before this run** (user-supplied, the probe's spend).

  | config | ordering | n | hit@1 | hit@3 | hit@5 | MRR@10 | recall@20 |
  |---|---|---|---|---|---|---|---|
  | mean-2000 (default) | vector | 20 | 0.650 | 0.750 | 0.900 | 0.732 | 1.000 |
  | mean-2000 (default) | **keyword** | 20 | 0.650 | 0.950 | **1.000** | **0.804** | 1.000 |
  | mean-2000 (default) | rrf | 20 | 0.600 | 0.850 | 1.000 | 0.743 | 1.000 |
  | mean-1500 | vector | 20 | 0.650 | 0.750 | 0.900 | 0.740 | 1.000 |
  | mean-1500 | keyword | 20 | 0.600 | 0.950 | 1.000 | 0.771 | 1.000 |
  | mean-1500 | rrf | 20 | 0.650 | 0.800 | 1.000 | 0.764 | 1.000 |
  | cls-2000 | vector | 20 | 0.600 | 0.700 | 0.850 | 0.677 | 1.000 |
  | cls-2000 | keyword | 20 | 0.650 | 0.900 | 0.950 | 0.779 | 1.000 |
  | cls-2000 | rrf | 20 | 0.650 | 0.750 | 0.850 | 0.726 | 1.000 |

  **The keep rule, applied, and every experiment it rejected.** Keep a change only if dev MRR rises and dev hit@5 does not fall. The baseline is the default configuration under the ordering the server uses today, mean-2000 / keyword: MRR 0.804, hit@5 1.000.

  | experiment | MRR@10 | vs 0.804 | hit@5 | verdict |
  |---|---|---|---|---|
  | vector ordering (mean-2000) | 0.732 | -0.072 | 0.900 | **rejected**, MRR falls and hit@5 falls |
  | rrf ordering (mean-2000) | 0.743 | -0.061 | 1.000 | **rejected**, MRR falls |
  | clip 1,500 (keyword) | 0.771 | -0.033 | 1.000 | **rejected**, MRR falls |
  | clip 1,500 + vector | 0.740 | -0.064 | 0.900 | **rejected** |
  | clip 1,500 + rrf | 0.764 | -0.040 | 1.000 | **rejected** |
  | cls pooling (keyword) | 0.779 | -0.025 | 0.950 | **rejected**, MRR falls and hit@5 falls |
  | cls + vector | 0.677 | -0.127 | 0.850 | **rejected** |
  | cls + rrf | 0.726 | -0.078 | 0.850 | **rejected** |

  **Eight experiments, none kept.** That is the honest outcome: the settings chosen before any of them were run are the best of what was tried.

  **Keyword ordering beats the embedder's own order, and fusion does not rescue it.** Under every configuration, ordering by keyword overlap beats ordering by vector similarity on MRR - by 0.072 at the default, 0.102 under cls. Reciprocal rank fusion lands between the two every single time (0.743, 0.764, 0.726 against keyword's 0.804, 0.771, 0.779), which is what fusion does when one input is simply worse than the other: it dilutes the better ranking rather than combining strengths. **No BM25 was tried, and that is not what these numbers argue against** - they argue against fusing *this* vector order into *this* keyword order.

  **cls is worse than mean here, against Cloudflare's own advice.** Their documentation recommends cls "for better accuracy on larger inputs". On these 20 questions it was worse on both metrics (MRR 0.779 against 0.804, hit@5 0.950 against 1.000). The probe had already measured cos 0.9466 between the two spaces, so they were never going to be far apart; what this adds is that the difference, such as it is, runs the other way for code.

  **A tighter clip is not free.** 1,500 characters loses 0.033 of MRR against 2,000 and raises the share of clipped flask file records from 54.2% to 56.6%, keeping 14.6% of their characters instead of 18.6%. There was no cost argument for it either: the full run came in at 18% of the budget.

  **What dev cannot tell us.** recall@20 saturated at 1.000 for all three configurations, so **the dev split cannot discriminate between them on recall at all** - every difference above is a ranking difference over 20 questions, where one question is 0.05 of hit@5. The configuration choice rests on differences of 0.025 to 0.033 in MRR, which is two or three questions moving a rank or two. That is thin, and it is the reason the held-out run matters.
- Command: `python scripts/eval_cloudflare.py --split dev --json eval/results/cloudflare/dev.json`
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd (15 files, 159 records); https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35 (83 files, 1705 records); the 20 dev questions from `eval/questions/*.json`. **The held-out split was not run and not looked at**
- Date: 2026-10-09
- Commit: 149dac1
- Notes: **cost: 1,464.37 estimated neurons over 177 calls, against a plan of 1,485.90**; 5,355 documents counted, 1,785 texts embedded per configuration. The small shortfall against the plan is duplicate texts, which the cache embeds once and the plan counted twice. Today's ledger stands at 1,464.37 of the 8,000 budget, 6,535.63 remaining. **The dashboard read 8.41 before this run**; the figure after it is the comparison worth making, since this is code being embedded rather than the probe's prose.
  **Re-running the whole dev evaluation afterwards cost nothing**: 1,944 cache hits, 0 texts embedded, the ledger unmoved. That is the vector cache doing what it was built for, and it is why the held-out runs will be nearly free.
  **The clipping limit from the note above applies to every number here.** These results were achieved with more than half of each repository's file records represented by their opening only, and for flask by 18.6% of their characters. The headroom above these figures is not all reranking.
  **This is not a controlled embedder-only comparison with hash.** hash reads every record in full and has no clip at all; the Cloudflare configurations clip at 2,000 or 1,500 characters. What is being compared is the server running one provider against the server running the other, which is the decision actually on the table

### Fix: the neuron estimate was three times under, because a batch is billed by its longest text
- Value: **the dev run was estimated at 1,464.37 neurons and the dashboard billed about 4,400.** The estimator now prices every text in a call at the longest text in that call, which predicts 4,767 for the same run - 9% high rather than 3x low.

  **The dashboard figures, as supplied.** bge-small read 8.41 neurons before the dev run and about 4.41k over the following 24 hours, so the run itself cost roughly **4,392** real neurons. (The "used today" figure came through as the letter `N` and is not recorded here; the arithmetic below uses the 24-hour reading.)

  | | tokens | neurons | vs billed |
  |---|---|---|---|
  | old estimate: each text's own tokens | 807,111 | 1,485.90 planned / **1,464.37 recorded** | **0.33x** |
  | billed, from the dashboard | ~2,385,000 | **~4,392** | 1.00x |
  | new estimate: every text at its batch's longest | 2,589,429 | **4,767.1** | 1.09x |
  | ceiling: every text at the full 512-token window | 2,893,824 | 5,327.5 | 1.21x |

  **Why padding explains it and nothing else does.** The average prepared document is 455 characters in flask and 587 in itsdangerous - about 141 and 177 estimated tokens. Billed, the run works out at roughly 445 tokens per text, close to the 512-token window. That is not a tokenizer being three times worse than guessed; it is fifty texts in one call all being charged at the length of the longest one. About one record in twenty is long enough to reach the clip, so with batches of fifty **nearly every batch contained one and paid the long rate for all fifty.**

  **The spend reconciles exactly, and nothing was wasted.** 177 calls were recorded. Reconstructed from the corpus: 3 configurations x (39 document batches + 20 query calls) = **177**. So **no index was built more than once and no call was retried** - a retry would have raised the count and would also have logged a warning, and none did. 5,355 texts were sent, 1,785 per configuration, which is the 1,864 documents plus 20 questions less 99 duplicates that the cache embedded once.

  **What to assume going forward: about 3.0 real neurons per *old* estimated neuron, and about 0.92 per *new* one.** The new estimate is deliberately the high side of the truth, so the honest instruction is to treat it as the figure to plan against and expect to be billed a little less.

  **This closed a hole, not a rounding error.** Under the old estimate the 8,000-neuron budget stop would have allowed roughly **24,000 real neurons, nearly two and a half times the 10,000 daily free allowance**. The stop would not have fired; the day's allowance would simply have run out and every question would have fallen back to hash. The only reason that did not happen is that the evaluation was run once.
- Value (what a repository actually costs now): **a 600-document index of a flask-sized repository costs 562 neurons** at the current batch size of 50 - about **14 analyses inside the 8,000 budget**, 17 inside the free allowance.

  | | batch 50 | batch 10 | batch 5 | batch 50, length-sorted |
  |---|---|---|---|---|
  | 600 documents, clip 2000 | **561.9** | 483.4 | 423.0 | **276.1** |
  | 600 documents, clip 1500 | 561.8 | 482.7 | 422.2 | 275.4 |
  | 600 documents, clip 1000 | 385.6 | 350.4 | 318.9 | 225.6 |
  | all 1,705 flask documents, clip 2000 | 1,442.1 | - | - | 463.9 |

  **A tighter clip is not a cost lever, and that is the most useful thing in this table.** Clip 1,500 costs 561.8 against clip 2,000's 561.9 - a saving of 0.1 neurons in 562, because padding is set by the longest text in each batch and at either clip that text is at the ceiling. The dev run already showed clip 1,500 losing 0.033 of MRR. **It costs retrieval quality and saves nothing.**

  **The lever is batching.** Sorting a repository's documents by length before batching halves the cost - 276 against 562 - for **byte-identical vectors**, because batches then contain texts of similar length and pay for almost no padding. It changes nothing about the index, nothing about the signature, and nothing a visitor sees.
- Proposed, and **not applied without approval**:
  1. **Sort documents by length before batching, then restore their order** (embed in length order, write records back in the original order). Halves the cost of every index. The only argument against is the code it adds.
  2. **Leave the clip at 2,000.** Lowering it demonstrably costs MRR and saves nothing under padding.
  3. **Leave the document cap at 600 if (1) is taken** - it would then cost 276 neurons per repository, about 29 analyses inside the budget. **Without (1), lower the cap to 300**, which costs about 280 and restores the same headroom, at the price of more repositories falling back to hash.
  4. **Leave the batch size at 50 if (1) is taken.** Without it, 10 would save 14% and 5 would save 25%, but both multiply the number of calls and the time an index takes, and the index time limit is 120 s.
- Command: `python -m pytest tests/test_neuron_ledger.py tests/test_cloudflare_provider.py -q`, then `python -m pytest tests/ -q` -> 852 passed, 1 skipped. The cost tables are `CodeIndexService.documents` over the pinned flask checkout, priced by the new estimator; no call was made to produce them
- Dataset/repo: the dev run recorded above (`eval/results/cloudflare/dev.json`), and https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35 for the cost tables
- Date: 2026-10-10
- Commit: 686413f
- Notes: **the dashboard figures are user-supplied** and read by hand: 8.41 before, about 4.41k over 24 hours after. The embeddings response carries no usage at all, which is why the ledger exists and why it had to be calibrated against a figure this project cannot read. Both readings are rounded, so "about 4,392" carries real uncertainty - but not enough to explain a factor of three.
  **The probe script keeps its own old estimator** and its recorded numbers are left alone. It is a record of a run that happened, not a tool to be re-run, and its inputs were nine calls of one or two texts where padding barely applies.
  **No default was changed by this commit.** The budget stays 8,000, the cap 600, the clip 2,000, the batch size 50. What changed is that the stop now fires where it was meant to - and at the new prices it will fire about three times sooner than it used to

### Check: the held-out split, run once, for the default configuration
- Value: **held-out overall MRR@10 0.854 against hash's 0.645, and recall@20 1.000 against 0.800.** Run once, for mean pooling at clip 2,000 with keyword ordering - the default, and also the dev winner, so there was one run to make. No other configuration and no other ordering was scored on this split.

  | repo | embedder | hit@1 | hit@3 | hit@5 | P@3 | MRR@10 | R@20 |
  |---|---|---|---|---|---|---|---|
  | itsdangerous | hash | 0.800 | 0.800 | 0.900 | 0.700 | 0.820 | 1.000 |
  | itsdangerous | **cloudflare** | 0.800 | **0.900** | 0.900 | **0.767** | **0.864** | 1.000 |
  | flask | hash | 0.400 | 0.500 | 0.600 | 0.367 | 0.470 | 0.600 |
  | flask | **cloudflare** | **0.800** | **0.900** | **0.900** | **0.667** | **0.843** | **1.000** |
  | overall | hash | 0.600 | 0.650 | 0.750 | 0.533 | 0.645 | 0.800 |
  | overall | **cloudflare** | **0.800** | **0.900** | **0.900** | **0.717** | **0.854** | **1.000** |

  **Overall gain: hit@1 +0.200, hit@3 +0.250, hit@5 +0.150, P@3 +0.184, MRR@10 +0.209, recall@20 +0.200.** The gain on held-out is larger than on dev, which is the opposite of the usual worry and is itself a reason for caution: 20 questions per split is small, and 0.200 of hit@1 is four questions.

  **Nearly all of it is flask, and recall@20 says why.** On itsdangerous both embedders already had recall@20 1.000 - the right file was always in the pool - so the only available gain was in ordering, and it came to +0.044 of MRR. On flask hash had recall@20 0.600: **four of ten questions never had their file in the pool at all**, and no reranking could have recovered them. Cloudflare takes that to 1.000, and the ranking metrics follow: hit@1 0.400 to 0.800, MRR 0.470 to 0.843. This is the clearest statement yet of what the semantic embedder buys - not better ordering, but finding the file in the first place.

  **A consistency check that was not planned and is worth keeping.** The fastembed entry earlier in this file measured held-out overall hit@1 0.800, hit@3 0.900, hit@5 0.900, P@3 0.717, MRR@10 0.864. This run: 0.800, 0.900, 0.900, 0.717, **0.854**. Those are two independent implementations of the same model - bge-small-en-v1.5 under ONNX locally, and the same model behind Cloudflare's API - agreeing to **0.010 of MRR and exactly on everything else**, despite different clips (3,000 against 2,000) and different batch sizes. Neither number is validating the other by construction, so the agreement is real evidence that both are measuring the model rather than their own plumbing.
- Command: `python scripts/eval_cloudflare.py --split test --config mean-2000 --ordering keyword --json eval/results/cloudflare/test.json`; the hash column is the `--split test` run recorded earlier in this file
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd (15 files, 159 records); https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35 (83 files, 1705 records); the 20 held-out questions from `eval/questions/*.json`, split as fixed before any of this work began
- Date: 2026-10-10
- Commit: b1bbfd4
- Notes: **cost: 1.25 estimated neurons planned, 0.55 recorded across 20 calls** - the twenty held-out questions and nothing else. All 1,864 document vectors were already in the cache from the dev run, which is exactly what the cache was built for: 1,874 hits and 10 texts embedded on the run that completed.
  **The first attempt crashed after embedding ten of the questions**, on a reference left pointing at every ordering rather than the chosen ones. It cost 0.24 estimated neurons and no numbers were produced or looked at; the retry paid only for the remaining ten. Both halves are in today's ledger.
  **Nothing was tuned on this split.** The configuration and the ordering were both chosen on dev before this was run, and `--ordering keyword` was passed so that the alternatives were not even computed - they would have cost nothing, which is precisely why not computing them had to be deliberate.
  **The clipping limit still stands over these numbers.** 54.2% of flask's file records are over the clip and keep 18.6% of their characters, so this result was achieved with most file records represented by their opening alone

### Check: length-sorted batching halves the cost of an index, and changes no vector
- Value: **600 flask documents cost 276.06 estimated neurons sorted against 561.87 in file order** - a 50.9% saving, confirmed by the ledger, for **identical** vectors.

  | | estimated neurons |
  |---|---|
  | 600 documents, file order, batch 50 | 561.87 |
  | 600 documents, **length order**, batch 50 | **276.06** |
  | ledger delta for the real sorted index | **276.06** |

  **The safety check came first, and it is the only reason this was applied.** The same 50 flask documents were embedded twice through the real API, once in file order and once in length order, and the smallest cosine between the two vectors of the same document was measured:

  ```
  documents: 50, clip 2000, batch size 50
  estimate for both calls: 94.26 estimated neurons
  minimum cosine between the two vectors of the same document: 1.000000
  required: 0.9999
  PASS: batching order does not change a vector
  ```

  **1.000000, not 0.9999-something.** Had it come back lower, an index would have depended on the order its files happened to be read in - two analyses of the same repository giving different vectors - and no saving would have been worth that. The check cost 94.26 estimated neurons and is reproducible: `python scripts/index_cost_check.py --check-order`.

  **Why it works.** A call is billed at the length of its longest text. In file order a batch of fifty holds whatever fifty records came next, and about one record in twenty is long enough to reach the clip, so nearly every batch paid the long rate for all fifty. In length order the long records are together in their own few batches and the short ones pay short-record prices.

  **What this is worth in practice.** A 600-document repository falls from 562 to 276 neurons, so the 8,000 budget covers about **29 analyses a day instead of 14**, and the 10,000 free allowance about 36 instead of 17 - without touching the clip, the cap, the batch size or anything a visitor sees.
- Command: `python scripts/index_cost_check.py --check-order` then `python scripts/index_cost_check.py --index 600`; `python -m pytest tests/test_index_batching.py -q` (11 tests), full suite 863 passed, 1 skipped
- Dataset/repo: https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35, its first 600 prepared documents at clip 2,000
- Date: 2026-10-10
- Commit: b91833f
- Notes: **spend for this entry: 94.26 for the order check plus 276.06 for the validation index = 370.32 estimated neurons**, on top of the 0.55 the held-out run cost. Today's ledger reads 370.87 over 34 calls. Both figures were printed before each run, as a dashboard reading on either side was wanted.
  **Nothing in the index changed.** `test_sorting_changes_neither_the_signature_nor_the_index_format` pins both strings, because if either had moved, every existing index would have been invalidated by what is purely a billing optimisation. The vectors are returned in the order their documents arrived, so a record keeps its own vector, and `test_an_indexed_repository_is_the_same_either_way` checks that end to end by indexing a repository both ways and comparing every record and vector.
  **It is on for every provider, not only Cloudflare.** For hash it provably cannot matter - the vector is a pure function of the text - and for fastembed the batch size is 1, so there is nothing to sort. The check that justifies it was made against Cloudflare's bge-small; a future provider whose vectors did depend on batch composition would need checking again before trusting this.
  **Two existing tests were changed**, from asserting which text the embedder saw *first* to asserting which texts it saw. The order is now a billing detail, not a contract, and a test that pins it would fail the next time the batching is tuned

### Proposal: Render settings for the semantic provider, and what happens when the allowance runs out
- Value: a complete deployment configuration, **proposed and not applied**. Nothing in this entry has been set anywhere; no default was changed.

  | variable | proposed | why |
  |---|---|---|
  | `CODEATLAS_EMBEDDING_PROVIDER` | `cloudflare` | held-out MRR@10 0.854 against hash's 0.645, recall@20 1.000 against 0.800 |
  | `CODEATLAS_CLOUDFLARE_MODEL` | `@cf/baai/bge-small-en-v1.5` | the measured model; 384 dims, free tier |
  | `CODEATLAS_CLOUDFLARE_POOLING` | `mean` | cls was worse on dev (MRR 0.779 against 0.804) and the two are not interchangeable |
  | `CODEATLAS_CLOUDFLARE_MAX_CHARS` | `2000` | 1,500 lost MRR and saved 0.1 neurons in 562 |
  | `CODEATLAS_CLOUDFLARE_MAX_DOCUMENTS` | `600` | 276 neurons per repository with length-sorted batching |
  | `CODEATLAS_CLOUDFLARE_DAILY_NEURONS` | **`2500`**, not 8000 | see the ledger problem below |
  | `CODEATLAS_CLOUDFLARE_BATCH_SIZE` | `50` | unchanged |
  | `CODEATLAS_NEURON_LEDGER` | `/var/data/cloudflare-neurons.json` | only if a disk is mounted; otherwise leave unset |
  | `CODEATLAS_INDEX_DIR` | `/var/data/indexes` | the hash index, which every question can fall back to |
  | `CODEATLAS_CLOUDFLARE_INDEX_DIR` | `/var/data/indexes-cloudflare` | the semantic index, which must never share a folder |
  | `CLOUDFLARE_ACCOUNT_ID` | the account id | **as an environment variable in the Render dashboard**, never in the repository |
  | `CLOUDFLARE_API_TOKEN` | the API token | the same, and marked secret |

  **What a visitor sees when the allowance is gone.** They get an answer. The question is embedded, the call is refused, the hash index answers instead, and one sentence appears above the answer: *"Today's semantic search allowance is used up, so this answer used keyword search."* Citations, snippets and the rest are unchanged - the answer is built from the same pipeline, searched with a weaker embedder. Analysing a new repository also still works: the hash index is built first and always, so an analysis never fails for want of neurons; only the semantic half is skipped, and the next question on that repository says *"Semantic search is not available for this repository"*.

  **The ledger problem, which is the real reason for the lower budget.** The ledger lives in `.codeatlas/cloudflare-neurons.json`, under the gitignored working directory. **On Render's free plan there is no persistent disk, so every restart wipes it** - and a free service spins down when idle and restarts on the next request, which for a demo may be several times a day. After each restart the budget guard believes nothing has been spent today and will allow a further full budget.

  So with the budget at 8,000, four restarts in one UTC day could authorise 32,000 neurons against a 10,000 allowance. **2,500 is proposed instead: four restart-cycles still fit inside the free allowance**, and 2,500 is nine capped repository analyses, which is a reasonable day for a demo. If a disk is ever mounted, `CODEATLAS_NEURON_LEDGER` should point at it and the budget can go back up.

  **The honest framing: the budget guard is a courtesy, not the protection.** It exists to stop *this project* spending more than it meant to. The protection against actually exceeding the allowance is that **Cloudflare refuses the call and every refusal falls back to hash with a note** - which is tested, and which works whether or not the ledger survived the restart. A wiped ledger means the day's allowance may really run out; it does not mean anything breaks.

  **A larger cost driver than the ledger, and the reason to mount a disk if anything is paid for.** Without a persistent disk the *indexes* are wiped too. Every restart means every repository is analysed again, and under the cloudflare provider each re-analysis is a real 276 neurons. The index cache and the repository state are both under `.codeatlas` by default for the same reason. On a free plan with no disk, the practical ceiling is not the budget but how often the service restarts.
- Command: none; nothing was run and nothing was applied. The figures come from the entries above
- Dataset/repo: none
- Date: 2026-10-10
- Commit: b157fe5 (the state this proposal describes)
- Notes: **approval required before any of this is set.** The defaults in the repository are unchanged: provider `hash`, budget 8,000, cap 600, clip 2,000, batch size 50.
  **The credentials belong only in Render's own environment settings.** They are read straight from the environment into an object with a redacting repr and are never part of the app config, so no config dump or log line can print them; `.env.example` carries the names with empty values and `.env` is gitignored.
  **One thing this proposal cannot answer:** whether a free Render instance's latency to `api.cloudflare.com` keeps a 600-document index inside `CODEATLAS_INDEX_TIMEOUT_SECONDS` (120 s). Length-sorted batching makes it twelve calls, which should be ample, but it has not been measured from Render and a timeout throws the index away while the neurons stay spent

### Change: the default daily neuron budget is 2,500
- Value: `CODEATLAS_CLOUDFLARE_DAILY_NEURONS` now defaults to **2,500** instead of 8,000, as approved from the Render proposal above.

  **The allowance is not what sets this figure; the ledger is.** The running total lives in `.codeatlas/cloudflare-neurons.json`, on local disk. A host without a persistent disk wipes it on every restart, and a free service restarts whenever it has been idle. After each restart the guard reads zero spent today and will authorise a further full budget.

  | budget | restart-cycles that fit inside 10,000 | capped repositories per cycle |
  |---|---|---|
  | 8,000 | 1 (four cycles would authorise 32,000) | ~29 |
  | **2,500** | **4** | ~9 |

  Nine capped repositories per cycle is a reasonable day for a demo, and four wipes in one UTC day is a pessimistic restart rate for one. If `CODEATLAS_NEURON_LEDGER` is ever pointed at a persistent disk, this can go back up.
- Command: `python -m pytest tests/ -q` -> 863 passed, 1 skipped
- Dataset/repo: none; a configuration default
- Date: 2026-10-11
- Commit: 61d5412
- Notes: **the budget stop is a courtesy, not a hard limit**, and `.env.example` now says so in as many words. Its estimate has run from about 8% high to about 1.5% low against the dashboard, so a budget of 2,500 might stop at 2,300 real or 2,540 real. What actually protects the allowance is that Cloudflare refuses the call and the refusal falls back to the hash index with a note - which works whether or not the ledger survived the restart.
  Only the default moved. The clip stays 2,000, the document cap 600, the batch size 50, and the provider stays off unless `CODEATLAS_EMBEDDING_PROVIDER=cloudflare` is set

### Change: the semantic index has its own time limit, and running out of it is survivable
- Value: `CODEATLAS_CLOUDFLARE_INDEX_TIMEOUT_SECONDS` defaults to **180** and applies only when that provider is selected. Missing it **no longer fails the analysis**.

  | provider | index time limit | missing it |
  |---|---|---|
  | hash, sentence | `CODEATLAS_INDEX_TIMEOUT_SECONDS`, 120 s | 504, nothing saved |
  | fastembed | `CODEATLAS_FASTEMBED_INDEX_TIMEOUT_SECONDS`, 900 s | 504, nothing saved |
  | **cloudflare** | **`CODEATLAS_CLOUDFLARE_INDEX_TIMEOUT_SECONDS`, 180 s** | **hash index kept, analysis succeeds** |

  **Why 180.** A repository at the 600-document cap is twelve calls of fifty under length-sorted batching, so 180 s allows about fifteen seconds a call - room for a slow free host and a retry inside each - without leaving a visitor waiting three minutes on an API that is not answering. It is separate from the shared limit because this is the only provider whose indexing crosses a network, and the only one for which running late is survivable.

  **Why missing it is survivable here and nowhere else.** By the time the semantic index is being built the hash index is already on disk - it is built first, always. Throwing a completed analysis away and telling a visitor their repository could not be read, when the repository is in fact perfectly usable, would be a worse outcome than a repository that is merely harder to search. So a timeout now ends exactly as a refused call does: the half-built semantic index is discarded, the repository keeps its hash index, and the next question carries the note *"Semantic search is not available for this repository, so this answer used keyword search."*

  **A timeout on the only index there is remains fatal**, and `test_a_timeout_on_the_only_index_is_still_fatal` pins that. Nothing here softens the single-index case, where running out of time really does mean no index at all.

  **Outcomes, which are not what a visitor sees.** An attempt at a semantic index now ends in one of six named outcomes - `ok`, `budget`, `failure`, `breaker`, `timeout`, `cap` - mapped from the reasons a single call can fail. They exist for a log line and a metric. What a visitor is told is a shorter list, decided at question time from what turned out to be on disk, because at that point an over-capped repository, a timed-out one and one with a stale index are indistinguishable and should be.
- Command: `python -m pytest tests/test_dual_index.py tests/test_config.py -q` (47 tests), full suite 869 passed, 1 skipped
- Dataset/repo: none. The slow provider is a fake embedder driving a fake clock past the limit; **no call was made to Cloudflare in this task**
- Date: 2026-10-11
- Commit: afb686f
- Notes: **the limit is validated at startup** like the other numeric settings, so `CODEATLAS_CLOUDFLARE_INDEX_TIMEOUT_SECONDS=0` stops the app rather than producing an index that times out instantly.
  **Neurons already spent are not refunded by a timeout.** The documents embedded before the limit was reached were paid for and their vectors are discarded with the half-built index, so a repository that times out repeatedly would cost repeatedly. The circuit breaker does not help here either, since a timeout is not a failed call. **The real protection is the document cap**, which is unchanged at 600 pending a latency measurement from Render

### Check: what a full 1,705-document flask index would cost, with the cap left at 600
- Value: **463.86 estimated neurons in 35 calls**, length-sorted. The cap stays at 600 until Render's latency has been measured; this is what lifting it would buy and cost.

  | flask at the pinned commit, clip 2,000, batch 50 | estimated neurons | calls | per document |
  |---|---|---|---|
  | all 1,705 documents, file order | 1,442.08 | 35 | 0.846 |
  | **all 1,705 documents, length-sorted** | **463.86** | **35** | **0.272** |
  | capped at 600, length-sorted | 276.06 | 12 | 0.460 |

  **Lifting the cap would cost 68% more for 2.8 times the documents.** 463.86 against 276.06 is +187.80 neurons, and the per-document price falls from 0.460 to 0.272 - a capped index is *worse* value per document, because the 600 it keeps are the first 600 in file order and include a disproportionate share of the long, expensive file records.

  | | full index | capped at 600 |
  |---|---|---|
  | inside the 2,500 budget | 5.4 repositories | 9.1 |
  | inside the 10,000 allowance | 21.6 | 36.2 |

  **The number that decides it is 35 calls against 12, not the neurons.** At the 180 s index limit, 35 calls allow about five seconds each; 12 allow fifteen. Whether a free Render instance can finish 35 round trips to `api.cloudflare.com` inside 180 s is exactly the unmeasured thing, and a timeout now costs the neurons already spent and keeps nothing. **That, not the budget, is why the cap stays at 600.**
- Command: `CodeIndexService.documents` over the pinned flask checkout, priced by `neuron_ledger.estimated_neurons(..., batch_size=50)`
- Dataset/repo: https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35, 83 files and 1,622 functions, 1,705 prepared documents at clip 2,000
- Date: 2026-10-11
- Commit: 6933310
- Notes: **no neurons were spent on this and no call was made** - it counts characters and prices them with the committed estimator. The estimator itself has run between about 8% high and about 1.5% low against the dashboard, so read 463.86 as roughly 430 to 470 real.
  **A caveat on "capped at 600".** The cap keeps the first 600 documents in the order they are collected - every file record first, then functions - so a capped flask index is all 83 file records plus the first 517 functions. That is not a random sample, and the retrieval numbers in this file were all measured on the **uncapped** corpus. What a capped index would score has not been measured

### Change: one log line and three metrics per semantic analysis, and exactly what a visitor reads
- Value: every attempt at a semantic index now logs one line and increments one counter, and every question answered from the fallback index is counted by reason.

  ```
  Semantic index for repo <id>: outcome=ok documents=1705 calls=35 api_seconds=31.5 estimated_neurons=463.86
  ```

  | field | what it is |
  |---|---|
  | `outcome` | one of `ok`, `budget`, `failure`, `breaker`, `timeout`, `cap` |
  | `documents` | records offered to the embedder, before the cap is applied |
  | `calls` | API calls made, **including attempts that failed and were retried** |
  | `api_seconds` | time spent waiting on those calls, successful or not |
  | `estimated_neurons` | this analysis's share of the ledger estimate |

  | metric | labels |
  |---|---|
  | `codeatlas_semantic_index_total` | `outcome` |
  | `codeatlas_semantic_index_estimated_neurons_total` | none |
  | `codeatlas_retrieval_fallback_total` | `reason` |

  **Every label is a word from a closed list** - the six outcomes above, and `budget`, `circuit`, `api`, `unindexed`, `cap` for a question. No label can hold a path, a question or a provider's error text, so cardinality is fixed and nothing a visitor typed can reach `/metrics`.

  **Usage is taken twice per analysis**, once before the attempt and once after, so spend left over from an earlier analysis cannot be reported as this one's. `test_one_analysis_is_not_charged_for_the_one_before_it` pins that by handing the reporter a leftover and checking it never reaches the line.
- Value (what the visitor actually sees): the note is shown **above** the answer, in a small bordered line with an information icon, not inside the collapsed "Reasoning" section - an answer built from the weaker search should say so where the answer is.

  | reason | when | the sentence, in full |
  |---|---|---|
  | `budget` | today's estimated spend would pass the budget | *Today's semantic search allowance is used up, so this answer used keyword search.* |
  | `circuit` | three consecutive failures, during the five-minute cooldown | *Semantic search is briefly unavailable, so this answer used keyword search.* |
  | `api` | transport error, non-2xx, or a malformed body | *Semantic search did not respond, so this answer used keyword search.* |
  | `unindexed` | no usable semantic index: over the cap, timed out, or built by a different embedder | *Semantic search is not available for this repository, so this answer used keyword search.* |
  | `cap` | same sentence; the key is kept for the index-time log | *Semantic search is not available for this repository, so this answer used keyword search.* |
  | anything unrecognised | a reason added later and not given a sentence | falls back to the `api` sentence |

  **No, the note never appears when the semantic index was used normally.** The note is the empty string on every path where the first-choice index answered, and it is only non-empty where a reason was set - which happens in exactly two places, both of which switch to the fallback index first. `test_the_semantic_index_answers_when_it_can_and_says_nothing` and `test_an_ordinary_answer_carries_no_note` pin it, and with the hash provider there is no fallback pair at all, so the note cannot be produced.

  **No reason names Cloudflare, a neuron, a status code or a provider.** A visitor is told what happened to their answer, not what happened to our budget.
- Command: `python -m pytest tests/test_semantic_observability.py -q` (25 tests), full suite 894 passed, 1 skipped
- Dataset/repo: none. Fake embedders and a fake usage reporter; **no Cloudflare call was made in this task**
- Date: 2026-10-11
- Commit: 0621511
- Notes: **failed attempts are counted as calls.** A batch that is retried twice and then gives up reports three calls and all the seconds they took. That is deliberate: a line reading `outcome=failure calls=36 api_seconds=140.0` says something a line reading `calls=0` would hide.
  **`estimated_neurons` on the line is an estimate like every other figure in this file**, and the ledger it comes from has run between about 8% high and about 1.5% low against the dashboard.
  **An over-cap repository logs a line too**, with `calls=0`, although no analysis was attempted. A line saying a repository was skipped and why is more use than silence

### Check: the second dashboard reconciliation, and the range the estimator has actually shown
- Value: **the dashboard read 376.56 neurons against the ledger's 370.87 estimated - 1.5% low.** This is the first reconciliation of the padding-aware estimator against real spend, and it is close.

  **The dashboard figures, as supplied.** The 24-hour view read **376.56 neurons** for bge-small, in a single bar at **Oct 10 17:15 (UTC-4)**. "Used today" read **0**, because the UTC day had rolled over since. The dev run's roughly 4,400 is outside that 24-hour window and does not appear in it.

  | run | estimated | real | estimator |
  |---|---|---|---|
  | dev evaluation, 3 configurations | 4,767.10 | ~4,392 | **8.5% high** |
  | held-out + order check + validation index | **370.87** | **376.56** | **1.51% low** |

  The 370.87 is three pieces of work in one UTC day: 0.55 for the held-out questions, 94.26 for the sorted-versus-unsorted order check, and 276.06 for the 600-document validation index. The single bar at 17:15 is all three; they ran within about an hour of each other.

  **So the estimator's error has run from about 8% high to about 1.5% low.** It is not a bound in either direction, and the 1.5% low matters more than the 8.5% high: an estimate that can come in *under* real spend means **the budget stop is a courtesy and not a hard limit**. A budget of 2,500 might stop after 2,540 real neurons rather than 2,500.

  **What that does and does not mean.** It does not mean the allowance can be blown through: when the real allowance is gone Cloudflare refuses the call, the refusal falls back to the hash index, and the visitor is told - which is tested and works whether or not the estimate was accurate, and whether or not the ledger survived a restart. The budget stop exists to keep this project inside what it meant to spend, and a few per cent either way is within what it was built for. It should not be described, in this file or anywhere else, as a guarantee.

  **Why the two errors run in opposite directions is not established.** The padding model prices every text in a call at its longest member, which was 8.5% generous on the dev run's 177 calls of mostly long batches, and 1.5% mean on this day's 34 calls - which were dominated by one length-sorted index where padding is almost absent by construction. A plausible reading is that sorted batching removes the slack the model was over-counting, leaving a small genuine under-count from the 3-characters-per-token figure. **Two data points cannot distinguish that from coincidence**, and no further calls were made to find out.
- Command: the account dashboard, read by hand; `cat .codeatlas/cloudflare-neurons.json` for the ledger. **No call was made to Cloudflare in this task**
- Dataset/repo: none
- Date: 2026-10-11
- Commit: f5e55e0
- Notes: **both dashboard figures in this file are user-supplied.** The embeddings response carries no usage at all, which is why the ledger exists and why it can only ever be calibrated against a number read by a person from a web page. Both readings are rounded at an unknown precision.
  **"Used today" reading 0 is the UTC rollover working as intended**, not a lost record: the ledger keeps a dated history and still holds both days

### Fix: a DI test built a real model client, and only a developer's .env was hiding it
- Value: **`tests/test_dual_index.py::test_the_answer_service_is_given_the_fallback_only_when_there_is_one` passed locally and failed in GitHub CI** with `pydantic ValidationError: ChatOpenAI did not find openai_api_key`. It now passes in both, and the whole suite passes with no credentials anywhere: **894 passed, 1 skipped**.

  **What it was doing.** The test builds the answer service through the real `get_answer_service()` factory, so the real `LlmProvider` has to build *something*. The LLM provider was left at its default of `groq`, so it constructed a `ChatOpenAI` - which needs a key to exist at construction time, before any call is made.

  **Why it passed locally and not in CI.** Two separate routes put `.env` into the process environment on a developer's machine, and neither exists in CI:

  | route | when |
  |---|---|
  | `codeatlas/app/main.py` calls `load_dotenv()` at import | any test that builds the FastAPI app, which several do |
  | `load_cloudflare_credentials()` calls `load_dotenv()` | any test that touches the Cloudflare credentials helper |

  Either one loads the **whole** file, so `GROQ_API_KEY` lands in `os.environ` for the rest of the session no matter which test pulled it in. Test order then decides whether a test that needs a key happens to find one - locally it always did, and in CI there was nothing to find. **The test was never isolated; it was sharing state with whatever ran before it.**

  **The fix is `CODEATLAS_LLM_PROVIDER=none`**, which makes the factory return the app's own `FallbackChatModel`: no key, no client, no network, and the same path the server takes when nothing is configured. That exercises real code rather than a fake, and it is a far better fix than **putting a dummy key in the workflow**, which would have left the test free to build a real client and merely stopped CI from mentioning it.

  The test now also asserts *which* model it was given, so the next time something makes this path build a real client it fails with that sentence rather than with a missing key.
- Command: `python -m pytest tests/ -q` locally (894 passed, 1 skipped); the same suite with dotenv disabled and every provider credential cleared from the environment, which is how CI runs it (894 passed, 1 skipped)
- Dataset/repo: none
- Date: 2026-10-11
- Commit: 33d5f0a
- Notes: **reproduced before it was fixed**, with a pytest plugin that makes `dotenv.load_dotenv` a no-op and deletes every `CLOUDFLARE_*`, `OPENAI_API_KEY` and `GROQ_API_KEY` from the environment before any project module is imported. It reproduced the CI failure exactly - the same one test, 893 others passing. **The `.env` file was never read, moved or renamed to do this.**
  **One other place builds a real client, deliberately.** `tests/test_llm_defaults.py` constructs `ChatOpenAI` three times to check that the model name and token budget are passed through, and sets an obviously fake key itself to do so. That is a legitimate use - it is testing the construction - and it depends on nothing ambient, which is why it passed in CI too. The guard added in the next entry makes that intent explicit rather than incidental.
  **No test reaches a real provider.** Nothing in the suite calls a model, and nothing calls Cloudflare: every Cloudflare test passes a fake client into the provider

### Guard: no test may reach a real provider, or depend on one being configured
- Value: an autouse fixture now clears the provider credentials and disables `.env` loading for **every** test, and building a provider client fails with a message saying what to do instead. The suite reports **903 passed, 1 skipped locally and 903 passed, 1 skipped with no credentials at all** - the two runs are now identical, which is the whole point.

  | what | how it is blocked | why that way |
  |---|---|---|
  | `ChatOpenAI` (both the openai and groq paths) | construction raises | construction is what needs the key; by the time the object exists the mistake has been made |
  | `ChatGroq` | construction raises, if the package is ever added | same |
  | Cloudflare | the **call** raises, not the construction | several tests build a provider only to read its signature and never embed anything; one built without a fake client is given one that refuses |
  | credentials in the environment | deleted per test | a test that finds one passes where one is configured and fails where it is not |
  | `.env` | `load_dotenv` patched out in both places the app calls it | otherwise the first test to touch either puts the whole file back for every test after it |

  **The opt-out is a marker, not an exception list.** Three tests in `test_llm_defaults.py` construct `ChatOpenAI` deliberately, to check that the model name and token budget reach it, and set their own plainly fake key. They carry `@pytest.mark.builds_model_client`. That turns what was an incidental fact - they happened to pass in CI because they supplied a key - into a stated one.

  **Two mistakes made while writing this, both kept as comments in the code.**

  1. **The guard reloaded the file it had just cleared.** `monkeypatch.setattr("codeatlas.app.main.load_dotenv", ...)` *imports* that module to patch it, and importing it runs `load_dotenv()` at module level. Clearing the environment first and patching second put every credential straight back. The patching now happens first, and the main module is only patched if it is already imported.
  2. **A failing assertion printed a live token.** The obvious way to check the environment is clean is `assert name not in os.environ`; when it fails, pytest renders the entire environment into the report - which put a real `CLOUDFLARE_API_TOKEN` into a terminal. The test now builds a list of **names** and asserts on that, so the worst it can print is a list of variable names. **The token exposed this way was reported for rotation.**
- Command: `python -m pytest tests/ -q` (903 passed, 1 skipped), and the same suite with `.env` disabled and every provider credential cleared, which is how CI runs it (903 passed, 1 skipped)
- Dataset/repo: none
- Date: 2026-10-11
- Commit: 3143178
- Notes: **the skip counts differ between the two machines for three reasons, and none of them hides a problem.** Locally: 1 skip, the symlink test in `test_safe_join.py`, which needs privileges Windows does not give. In CI: 4 skips - the two `test_fastembed_provider.py` tests that need the optional `fastembed` package, which CI does not install and this machine has, and the two `test_answer_smoke.py` tests that need cached eval clones under `.codeatlas/eval-repos`, which this machine has from the retrieval evaluation and CI starts without. The symlink test runs on Linux, so it is not among CI's four. 1 + 2 + 2 = the difference exactly, and **they were left alone**: each skip states its condition and would run if the condition were met.
  **What the guard does not cover.** It does not stop a test making an HTTP request by some other route - `urllib` is not patched, because `tests/test_json_client.py` exercises the stdlib client directly with a fake `urlopen` and blocking it would break a legitimate test. Nothing in the suite does make one; this is a gap in the guard, not a known problem
### Change: the structural eval can write a result file, and that file is committed
- Value: `scripts/structural_eval.py --json <path>` writes the figures it already prints as JSON: overall, by split, by repository and by question kind, plus every disagreement with `ast` in both directions. `eval/results/structural/all.json` is that file at the pinned commits, and it repeats the entry recorded at 2a8ba97 exactly — **precision 1.000, recall 0.9673, 45 of 49 exact**; development n=26 recall 0.9641 exact 23, held-out n=23 recall 0.9710 exact 22; `where_defined` 23/23, `who_imports` 12/12, `who_calls` 10/14 recall 0.8857; flask n=25 recall 0.9920, itsdangerous n=24 recall 0.9417. All four disagreements are misses — `graph_found_ast_did_not` is empty for every one of them. Nothing else about the script changed: the printed report, the exit code and the scoring are untouched
- Command: `python scripts/structural_eval.py --json eval/results/structural/all.json` (0.49 s after the two clones were already cached) and `python scripts/structural_eval.py --show-disagreements`; `python -m pytest tests/ -q` -> 907 passed, 1 skipped (`tests/test_structural_eval.py` gains 4: the grouping by split, repository and kind including an empty group, both directions of a disagreement, the pinned repository commits, and the committed file against the figures recorded at 2a8ba97); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd; https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35; the 49 questions in `eval/structural_questions.json`
- Date: 2026-10-11
- Commit: 28fb0e2
- Notes: **why a committed file rather than running the script.** The script needs both repositories cloned under `.codeatlas/eval-repos/`, which is ignored by git. The benchmarks summary and the test that regenerates it must work from a clean checkout with no network, so they read this file instead. Re-running the command above is the only thing that changes it.
  It sits in a subfolder, like the fastembed and cloudflare results, because `load_eval_results` globs `*.json` in `eval/results` itself and labels each gauge by the file's `split`; this file has no single split and would be skipped with a warning. The glob is not recursive, so nothing else reads it. `eval/results/structural/README.md` says the same in place.
  **The recorded commit reads `bf5f6d5-dirty`**, which is the commit before this one plus the uncommitted `--json` flag that this commit contains. The same thing happened to the retrieval result files at 97242ac and it is recorded there too; the alternative is a second commit whose only purpose is to make a string look tidier.
  **What the file does not contain:** no account id, no key, no budget or neuron figure, and no visitor text. The subjects in it are Python identifiers from the two public repositories, which the question set already names, and the `note` on each is my own one-line description of why that question is interesting
### Change: the committed hash retrieval results carry recall@20
- Value: `eval/results/{dev,test,all}.json` were written at 97242ac, before recall@20 was added to the eval at fa0db11, so the only record of hash's recall@20 was the table in this file. The three files were regenerated and **every figure already in them is byte-identical**; the runs added recall@20 per question, per repository and overall, and the per-repository clipping block (0 clipped, 100.0% of characters kept — hash has no clip)

  | split | repo | n | hit@1 | hit@3 | hit@5 | P@1 | P@3 | P@5 | MRR@10 | recall@20 |
  |---|---|---|---|---|---|---|---|---|---|---|
  | dev | itsdangerous | 10 | 0.600 | 0.700 | 0.800 | 0.600 | 0.500 | 0.400 | 0.692 | 0.900 |
  | dev | flask | 10 | 0.600 | 0.700 | 0.700 | 0.600 | 0.467 | 0.360 | 0.633 | 0.800 |
  | dev | overall | 20 | 0.600 | 0.700 | 0.750 | 0.600 | 0.483 | 0.380 | 0.662 | 0.850 |
  | test (held out) | itsdangerous | 10 | 0.800 | 0.800 | 0.900 | 0.800 | 0.700 | 0.560 | 0.820 | 1.000 |
  | test (held out) | flask | 10 | 0.400 | 0.500 | 0.600 | 0.400 | 0.367 | 0.280 | 0.470 | 0.600 |
  | test (held out) | overall | 20 | 0.600 | 0.650 | 0.750 | 0.600 | 0.533 | 0.420 | 0.645 | 0.800 |
  | all | overall | 40 | 0.600 | 0.675 | 0.750 | 0.600 | 0.508 | 0.400 | 0.654 | 0.825 |

  The dev and held-out recall@20 figures are the ones recorded at fa0db11, reproduced four days later on the same machine. `all` is dev and test together and is not a third measurement; its recall@20 of 0.825 appears here for the first time. Runs took 3.3 s, 3.7 s and 6.2 s
- Command: `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/eval_retrieval.py --split dev --json eval/results/dev.json`, the same for `--split test` and `--split all`; `python -m pytest tests/test_metrics.py tests/test_retrieval_eval.py tests/test_eval_stats.py -q` -> 27 passed. No model key is set and no API is called; hash runs entirely locally
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd (15 files, 159 records); https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35 (83 files, 1,705 records); the 40 questions in `eval/questions/*.json`
- Date: 2026-10-11
- Commit: c05e439
- Notes: **nothing was re-measured and nothing moved.** The check was mechanical: both files were loaded, `seconds`, `codementor_commit`, the new `recall@20` keys and the new `clipped` block were removed from each, and the remainder compared as parsed JSON. All three compared equal. Had any hit rate, precision or MRR differed, this entry would be reporting that instead.
  The files now record commit `016c655` rather than `97242ac`, and none of them says `-dirty`: each split was written into a scratch folder first and copied in afterwards, so the working tree was clean for all three runs. The retrieval gauges on `/metrics` read these three files and are unaffected — `load_eval_results` reads only `split`, `overall.hit_rate`, `overall.mrr@10`, the commit and the embedder.
  **Why this was worth a commit of its own.** The benchmarks summary is built from committed result files and is checked by regenerating it; a figure that lives only in the prose of this file cannot be part of that. recall@20 is also the most informative number hash has — on held-out flask it is 0.600 against hit@5 0.600, which says the losses there are the embedder never finding the file, not the reranker mis-ordering it
### Feature: a read-only GET /eval/benchmarks that serves recorded results
- Value: a new open route reads one committed file, `eval/benchmarks.json` (`CODEATLAS_BENCHMARKS_FILE`), and returns it with a heading note and two live facts. **Nothing is measured at request time.** The response is `{"available": true, "heading_note", "live": {"embedding_provider", "semantic_document_cap"}, "summary": <the file>}`. **A missing or unreadable file gives 200 with `available: false`** and a note saying the recorded results are not in this build — the heading note and the live block are still there, so the page shows its empty panels and an explanation rather than an error. The file is read per request, not at startup, so a build without it boots normally. The route count went from **18 to 19** and open routes from 9 to 10; routers stay at 11 and 9 routes still need the key
- Command: `python scripts/count_endpoints.py` (11 routers, 19 routes, 9 need the key, 10 open, 5 rate limited); `python -m pytest tests/ -q` -> 917 passed, 1 skipped (`tests/test_benchmarks_route.py`, 9 new tests: the file served unchanged, the heading note, a missing file answered rather than refused, a file that is not JSON treated as missing, the live block for a cloudflare server, nothing secret or private in the body, no key needed with auth on, the file re-read per request so deleting it changes the answer, and the default path; `tests/test_auth.py` classifies the route as user-facing, which `tests/test_count_endpoints.py` checks against the script); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (27 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before)
- Dataset/repo: none (the app built with `create_app()`, and small files under tmp_path)
- Date: 2026-10-11
- Commit: 7831330
- Notes: **it is classified, not just added.** `tests/test_auth.py` holds the two sets every route must fall into and `tests/test_count_endpoints.py` compares the script's own answer against them, so an unclassified route fails the suite. The route is open because `/eval/stats` beside it is open and the website calls both without a key; `tests/test_auth.py` also asserts the website sends no key and calls nothing outside the open set, which is why `fetchBenchmarks` was added to `codementor-ui/lib/api.ts` in this commit rather than with the page.
  **What it must never carry**, asserted by a test on the response text: `api_key`, `api-key`, `account_id`, `token`, `neuron`, `budget`, `question_text`. The two live values are the provider name and an integer ceiling, both already public in `.env.example`.
  **Limits:** `semantic_document_cap` is reported whatever the provider is, because it is a configured number rather than a live one — on a `hash` server it is the cap that *would* apply if the semantic provider were switched on, and the page has to say so. The route does not validate the summary's shape: a file written by hand with the wrong keys would be served as-is, and what stops that is the regeneration test on the summary, not this route.
  The Dockerfile does not copy `eval/benchmarks.json` yet — the file does not exist at this commit. That goes with the commit that creates it
### Feature: one committed summary of recorded results, which cannot be hand-edited or go stale
- Value: `scripts/build_benchmarks.py` writes `eval/benchmarks.json` (18.7 KB), the single file the website's Benchmarks section reads. **No model and no API is called to produce it.** Three kinds of source, and every block carries the embedder or script, the question count, the commit and the date it was recorded:

  | block | where the numbers come from | recorded |
  |---|---|---|
  | retrieval, hash | `eval/results/{dev,test}.json` | 016c655, 2026-10-11 |
  | retrieval, cloudflare | `eval/results/cloudflare/{dev,test}.json`, config mean-2000, keyword ordering | 149dac1 2026-10-09 (dev), b1bbfd4 2026-10-10 (held-out) |
  | structural | `eval/results/structural/all.json` | 28fb0e2, 2026-10-11 |
  | routers and routes | `scripts/count_endpoints.py`, recomputed on every build | 7831330, 2026-10-11 |
  | call-graph coverage | quoted from `docs/RESULTS.md` | 8336875, 2026-10-05 |
  | model-free chat timing | quoted from `docs/RESULTS.md` | 64c7ae6 2026-10-04 (stages), 513641c 2026-10-05 (shipped settings) |
  | answer smoke check | quoted from `docs/RESULTS.md` | f67b5d4 2026-10-06 (fast), d01ecba 2026-10-06 (deep) |
  | document cap | `DEFAULT_CLOUDFLARE_MAX_DOCUMENTS` in the code, with the entry that argued for it | 6933310, 2026-10-11 |

  Retrieval carries hit@1, hit@3, hit@5, P@3, MRR@10 and recall@20 per repository and overall, for both splits and both embedders — hash overall held-out 0.600 / 0.650 / 0.750 / 0.533 / 0.645 / 0.800 against cloudflare 0.800 / 0.900 / 0.900 / 0.717 / 0.854 / 1.000. **A metric a run did not compute is `null`, never 0** — the Cloudflare development run reported no P@3, and a 0.000 there would be a lie about the embedder.

  **The staleness guard.** The summary has no timestamp and no run id, so a build is a pure function of its inputs. `tests/test_build_benchmarks.py` rebuilds the whole file and compares it with the committed copy **byte for byte**: a figure typed in by hand, a result file that was regenerated, or a route added without rebuilding all fail it. `python scripts/build_benchmarks.py --check` does the same from the command line
- Command: `python scripts/build_benchmarks.py` then `python scripts/build_benchmarks.py --check` (up to date); `python -m pytest tests/ -q` -> 935 passed, 1 skipped (`tests/test_build_benchmarks.py`, 18 new tests: the committed file against a fresh build, a hand edit caught, the build being pure, `--check` passing and failing, the retrieval rows against the result files, the cloudflare rows against the default configuration and ordering, an uncomputed metric being null rather than zero, the structural block against its file, the endpoint counts against the app as it is now, every block having a date and a commit, every quoted entry still being in `docs/RESULTS.md`, the heading note, end-to-end latency absent, nothing secret in the file, no question text from any set, and the Dockerfile copying it); `docker build -t codementor-benchmarks-check .`, then inside the image `ls /app/eval` and a `TestClient` GET of the route; `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`
- Dataset/repo: the committed result files listed above; this repository's own app for the route count
- Date: 2026-10-11
- Commit: 3c8b35f
- Notes: **what the image ships, checked rather than assumed.** `COPY eval/benchmarks.json ./eval/benchmarks.json` was added and the image rebuilt: `/app/eval/benchmarks.json` is 18,711 bytes, the route answers 200 with `available: true`, `routes` reads 19 and `live` reads `{"embedding_provider": "hash", "semantic_document_cap": 600}`. **With the file missing** (`CODEATLAS_BENCHMARKS_FILE` pointed at a path that is not there) the same image answers 200 with `available: false`, the explanatory note, the heading note and the live block, and no `summary` key — one `WARNING` line naming the path, and the server starts and serves everything else normally.
  **Three figures are quoted from prose rather than read from a file**, because prose is their only record: the model-free chat timings, the call-graph coverage, and the answer smoke results. Each names the `docs/RESULTS.md` entry it came from and a test asserts that heading still exists, matched by prefix so a heading can be quoted without its bolded tail. That is a weaker guarantee than the file-sourced blocks: if someone edits a number inside one of those entries, the summary will not notice. Moving them into result files would need a script run that costs tokens (the smoke check) or that measures a machine (the timings), which is a different piece of work.
  **The timing block carries two measurements on purpose.** The per-stage breakdown was taken at 64c7ae6, *before* search depth rose from 10 to 20, so its totals are lower than the shipped settings give; the figure for the settings that actually ship is the 45 ms warm total at 513641c. Showing only the first would have been stale and showing only the second loses the breakdown, so both are there and labelled.
  **Limits.** The structural block repeats the four disagreements, which name Python identifiers and file:line positions from two public repositories — that is the point of listing a disagreement, and no question text of any kind is in the file (a test checks all 55 questions from the three sets that have text). The build reads `DEFAULT_CLOUDFLARE_MAX_DOCUMENTS` from the code, so changing that default makes the test fail until the summary is rebuilt, which is the intended behaviour rather than an inconvenience
### Feature: a Benchmarks section on the evaluation page, showing recorded results
- Value: a new section under the live session telemetry, fed by `GET /eval/benchmarks`. Under the heading it says **"Recorded results on small fixed question sets, not live accuracy."** Five panels:

  | panel | what it shows | where the numbers come from |
  |---|---|---|
  | Retrieval | hit@1, hit@3, hit@5, P@3, MRR@10, recall@20 per repository and overall, for both splits. hash is the panel that opens; cloudflare is a second button marked opt-in. Beside every table: the embedder, the question count, the commit and the date | `eval/results/{dev,test}.json` and `eval/results/cloudflare/{dev,test}.json`, through the summary |
  | Structural analysis against Python's `ast` | precision, recall and exact matches by split, by repository and by question kind, then the four disagreements with the file:line each one turns on | `eval/results/structural/all.json` |
  | System facts | routers, routes, open, need a key, rate limited; the embedding provider this server is actually running and the document cap; call-graph coverage per repository | `scripts/count_endpoints.py` for the routes, the running server's config for the two live facts, `docs/RESULTS.md` for the call graph |
  | Model-free chat timing | the per-stage breakdown and the figure for the settings that ship, under a badge reading **"excludes the language model"** | `docs/RESULTS.md`, `scripts/time_stages.py` |
  | Limitations and weak checks | **collapsed by default**: the answer smoke check with what it actually tests, the three sample sizes, the two repositories at their pinned commits, and the document cap | `docs/RESULTS.md` and the summary |

  **No end-to-end latency is shown anywhere**, and the timing panel ends with the line that it depends on the model provider and is not benchmarked here. **A metric a run did not compute renders as an em dash in a dimmed cell**, not as 0.000 — which is what the four Cloudflare development P@3 cells do.

  **When the data is missing** the section still renders: the heading, the heading note, and one panel saying the recorded results are not in this build. That is also what a reader sees for the moment before the fetch returns, and it is what a server without the file shows permanently. The two fetches are independent, so a failing `/eval/stats` does not hide the recorded results and a failing `/eval/benchmarks` does not hide the session stats
- Command: in `codementor-ui`: `npm test` (51 passed, 24 new in `lib/benchmarks.test.ts`), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build` (compiled, /eval prerendered); `python -m pytest tests/ -q` -> 935 passed, 1 skipped. Served locally: `uvicorn` on 8123 with no provider key and `next dev` on 3123 against it — `GET /eval/benchmarks` answered 200 with `available: true`, and the rendered `/eval` page carries "Benchmarks", the heading note and the empty-state wording
- Dataset/repo: `eval/benchmarks.json` as committed; the tests read that same file rather than a fixture
- Date: 2026-10-11
- Commit: cee4f45
- Notes: **the tests are on the view model, not on a rendered DOM.** This project's frontend suite is `node --test lib/*.test.ts`; there is no DOM testing library and adding one was not part of this work. So `lib/benchmarks.ts` turns the response into the exact rows, cells and labels the section draws, the component maps over them and invents no number and no wording of its own, and the 24 tests cover the rows per split, the held-out hash cells as strings, which provider opens first, every split carrying a commit and a date, a dash for an uncomputed metric, the structural groupings and disagreements, the live facts falling back to a dash with their hints intact, the timing badge and the absence of any end-to-end figure, the collapsed limitations panel, a response with no summary, a response that is `null`, and a summary missing two blocks. **What that does not cover is the markup**: a panel could be laid out wrongly and these tests would pass.
  **The phone layout was not checked in a browser.** No browser tooling was available in this session. What was done: every table is wrapped in a horizontally scrolling container with a minimum width, so a narrow screen scrolls a table sideways rather than crushing it; panels use a 2-column fact grid that widens to 3 and 5; long strings (embedder names, URLs, file:line lists) are set to break. `npm run build` compiles the page. A visual check at phone width is still outstanding.
  **One wording choice worth stating.** The document cap is shown in System facts as a live configuration value whatever the provider is, with the hint "applies when the semantic provider is on", because on a `hash` server it is the cap that *would* apply rather than one in force. The alternative - hiding it unless the semantic provider is running - would leave the panel silent about a limit the Limitations panel then discusses.
  **Limits.** The section shows what the summary holds and nothing more: it cannot tell a stale summary from a fresh one, which is `tests/test_build_benchmarks.py`'s job, not the page's
### Change: holdout2, a second held-out question set, written and committed unscored
- Value: `eval/questions/holdout2/{itsdangerous,flask}.json` — **20 questions, 10 per repository**, at the same pinned commits as the first sets (672971d66a2e and d73fa1cdcbd8). They exist because the original "held-out" split has now been scored in at least five entries in this file and is no longer a clean test of anything. **Nothing has been scored on holdout2 and no result from it has been looked at.**

  Each question is about a fact none of the existing forty asks about. For itsdangerous: constant-time signature comparison, `validate()` as a boolean instead of an exception, why `hashlib.sha1` is looked up lazily, the default salts, how text-vs-binary serializers are told apart, `dump`/`load` to a file object, overriding the serializer for one `load_payload` call, what `BadHeader` carries, why `SignatureExpired` stops the remaining signers, and the top-level re-exports. For flask: `after_this_request`, the "working outside of application context" message, the signal namespace, a blueprint's own static folder, `jsonify`, `g` as per-request storage, `.env`/`.flaskenv` loading, `FlaskCliRunner`, `before_request`/`after_request`/`teardown_request` registration, and the tutorial's per-request SQLite connection.

  **Six of the ten flask questions point at files no earlier question expects** — `ctx.py`, `globals.py`, `signals.py`, `blueprints.py`, `json/__init__.py`, `examples/tutorial/flaskr/db.py`. For itsdangerous, which has only eight source files, one question reaches `__init__.py`, which no earlier question does. Every `expected_files` path was checked to exist in the pinned checkout
- Command: `python -m pytest tests/ -q` -> 944 passed, 1 skipped (`tests/test_retrieval_eval.py` gains 9: ten questions per file at the same commit and repository URL as the first set, unique ids, every question in the `holdout2` split, no question or id repeated from the first set, a word-overlap check under 50% against every existing question, the new split selecting only under its own name and under "all", and an unknown split still rejected); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (51 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before)
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2ef9f85151e53283113f33d642dabd; https://github.com/pallets/flask at d73fa1cdcbd8b1465c151db8924ba58b1dd14e35
- Date: 2026-10-11
- Commit: 73783d3
- Notes: **the loader change is the only code in this commit.** `QUESTION_SPLITS` is now `("dev", "test", "holdout2")` and the error message lists them; `SPLITS` adds "all" on top, as before. Nothing selects or scores the new split yet, and the default question files are untouched, so every recorded number is unaffected.
  **How "not a paraphrase" is enforced, and what that enforcement is worth.** A test rejects any holdout2 question sharing more than half its words (over two letters) with any existing question. That catches the real failure mode — writing a "new" set by reshuffling the old wording — but it cannot prove two differently worded questions ask different things. The guarantee that they do is that each was written from a specific piece of source after reading the twenty existing questions, and the list above names the fact behind each one.
  **Limits.** Twenty questions is small; one question is 0.1 of a per-repository hit rate. They are mine, written by hand from the source, which is the same bias the first set has — a held-out split narrows it, it does not remove it. itsdangerous is 1,176 lines across eight files and the first twenty questions already cover it closely, so the ten new ones there are necessarily about smaller details than the flask ten. And a question written by the same person who will read the results is not an independent test of anything; what it is, is a set of questions whose answers were not known to the retriever when the settings were chosen
### Feature: BM25 as a second retriever, fused into the vector candidates, off by default
- Value: `codeatlas/services/retrieval/bm25.py` is Okapi BM25 in plain Python — a postings dictionary, `Counter`, and arithmetic. **No new dependency.** It scores every record in the repository, not a neighbourhood, which is the point: the existing pipeline has one way of *finding* records (the embedder) and one way of *ordering* them (the keyword rerank), and no amount of reordering recovers a file the embedder never found. On held-out flask, hash scores recall@20 0.600 against hit@5 0.600 — every file that reached the pool was already ranked into the top five, so the losses there are findings, not orderings.

      score(q,d) = Σ idf(t) · f(t,d)·(k1+1) / (f(t,d) + k1·(1 − b + b·|d|/avgdl))
      idf(t)     = ln(1 + (N − n(t) + 0.5) / (n(t) + 0.5))

  The idf form is the one that stays positive for a term present in every document; the alternative lets a record win by *not* containing a query word, which for a term like `self` would decide a lot of rankings. Tokenisation is the one retrieval already uses — identifiers split into their parts (`verify_signature` → `verify`, `signature`) and the same English stopword list — so BM25 and the embedder read the same words. It reads each record **uncapped**: the per-document clip is a cost control for a paid API, and nothing here is paid for.

  Its ranking is fused into the vector candidates by reciprocal rank fusion before the rerank runs, and **the fused pool is cut back to the same depth**, so nothing downstream sees a longer list — what changes is which records are in it. The fusion moved to `codeatlas/services/retrieval/fusion.py`; `services/eval/orderings.py` now calls that instead of keeping its own copy, so an ordering measured in an experiment is the same arithmetic the server would run.

  | setting | default | rejected unless |
  |---|---|---|
  | `CODEATLAS_BM25` | **off** | a recognised on/off word |
  | `CODEATLAS_BM25_K1` | 1.2 | a number greater than 0 |
  | `CODEATLAS_BM25_B` | 0.75 | a number between 0 and 1 |
  | `CODEATLAS_BM25_RRF_K` | 60 | a whole number of at least 1 |
  | `CODEATLAS_BM25_DEPTH` | 0 (= the vector pool's depth) | a whole number of at least 0 |

  **With it off not one line of the BM25 path runs**: `python scripts/eval_retrieval.py --split test` still prints itsdangerous hit@5 0.900 / MRR@10 0.820, flask 0.600 / 0.470, and **overall hit@5 0.750, MRR@10 0.645** — the figures recorded at 016c655
- Command: `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/eval_retrieval.py --split test` (unchanged, 6.1 s); `python -m pytest tests/ -q` -> 996 passed, 1 skipped (`tests/test_bm25.py`, 26 new: identifier parts and stopwords in the tokeniser, frequency kept as a list, a term in every record unable to decide the order, a rarer term worth more, saturation strictly between linear and constant, length penalised, `b=0` switching that off, the full formula written out against one hand-computed document, an empty corpus and empty records not dividing by zero, mismatched records and texts rejected, ties breaking by document order on a rerun, `top_k` honoured, the three fusion properties, and six through `AnswerService`: off by default, a lexically matching record pulled into a pool of two it was not in, the pool not growing, the index built once, rebuilt on reindex, and a retriever that cannot list its records still answering; `tests/test_retrieval_settings_from_env.py` gains 26 covering the five defaults, 11 valid values and 13 invalid ones, and the settings reaching the pipeline); `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (51 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before)
- Dataset/repo: small corpora written by the tests; the held-out check is `eval/questions/*.json` at the pinned commits
- Date: 2026-10-11
- Commit: 34632e0
- Notes: **nothing is measured here.** This entry adds a mechanism and shows the defaults did not move; whether fusing BM25 helps is the next entry's question, and the defaults in the table are the literature's values, not anything this repository chose.
  **Why the index is built lazily and cached by the record list's identity.** The lexical index needs every record's text, which the vector index does not keep, so `CodeRetriever` gained a `records(repo_id)` with an empty default — a retriever that cannot enumerate its records makes BM25 find nothing rather than making the search fail, and a test covers that. Reindexing replaces the record list, so caching on `id(records)` rebuilds exactly when the code changed. Building it costs one read of every record: the same reads the reranker already does, but all of them at once, on the first question after an index.
  **Limits.** The fusion is symmetric and unweighted — there is no setting that says "trust the vectors more than the words", because reciprocal rank fusion has no such parameter and adding one would be a different method. `bm25_depth` reads deeper into BM25's list than the vector list, which can only add candidates that the cut back to pool depth may then drop; it is there for the experiments. And BM25's corpus statistics are per repository, which is correct but means a one-file repository gives every term the same idf
### Check: five retrieval arrangements on the dev split, for hash and for cloudflare
- Value: the keep rule, fixed before the runs: **keep a change only if overall dev MRR@10 rises and dev hit@5 does not fall.** Baseline is `current`, the pipeline the server runs today. **No API call was made for any of this**: hash is local arithmetic, and the cloudflare half reads the evaluation vector cache through an embedder that refuses to call the provider.

  **hash (the default), dev, 20 questions**

  | arrangement | hit@1 | hit@3 | hit@5 | MRR@10 | recall@20 | verdict |
  |---|---|---|---|---|---|---|
  | current — vector pool, keyword rerank | 0.600 | 0.700 | 0.750 | 0.662 | 0.850 | baseline |
  | **bm25** — BM25 over every record | **0.750** | **0.800** | **0.850** | **0.782** | **0.950** | **meets the rule** |
  | vector — vector similarity alone | 0.350 | 0.550 | 0.550 | 0.479 | 0.850 | rejected, MRR falls |
  | rrf — fusion of vector and BM25 | 0.550 | 0.750 | 0.800 | 0.651 | 0.950 | rejected, MRR falls by 0.011 |
  | **rrf+keyword** — fused pool, keyword rerank | 0.600 | **0.800** | **0.900** | **0.717** | **0.950** | **meets the rule** |

  **cloudflare (opt-in), dev, 20 questions, mean pooling, clip 2,000**

  | arrangement | hit@1 | hit@3 | hit@5 | MRR@10 | recall@20 | verdict |
  |---|---|---|---|---|---|---|
  | current | 0.650 | 0.950 | 1.000 | **0.804** | 1.000 | baseline |
  | bm25 | 0.750 | 0.800 | 0.850 | 0.782 | 0.950 | rejected, MRR falls |
  | vector | 0.650 | 0.750 | 0.900 | 0.732 | 1.000 | rejected, MRR falls |
  | rrf | 0.650 | 0.750 | 0.950 | 0.742 | 1.000 | rejected, MRR falls |
  | rrf+keyword | 0.600 | 0.850 | 0.950 | 0.725 | 1.000 | rejected, MRR falls |

  **Nothing beats the current pipeline for cloudflare. Two things beat it for hash, and the bigger win is BM25 on its own.**

  Per repository, and this is where the result actually lives:

  | | hash current | hash bm25 | cloudflare current | cloudflare bm25 |
  |---|---|---|---|---|
  | itsdangerous MRR@10 | 0.692 | 0.663 | 0.758 | 0.663 |
  | flask MRR@10 | 0.633 | **0.900** | 0.850 | 0.900 |
  | flask recall@20 | 0.800 | **1.000** | 1.000 | 1.000 |

  **The whole of hash's gain is flask, and BM25 is slightly worse than hash on itsdangerous.** That is the shape the earlier recall@20 work predicted: hash's losses on flask were records it never found, not records it mis-ordered, and a real lexical retriever finds them. On itsdangerous, where hash already had recall@20 0.900, there was nothing for BM25 to recover and its different ranking costs a little.

  **recall@20 and recall at the candidate pool depth are the same number in every row**, because the pool depth is 20 — the default `CODEATLAS_RETRIEVAL_CANDIDATES`. Both are printed so that a run at a different depth cannot quietly relabel one as the other
- Command: `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/experiment_retrieval.py --embedder hash --split dev --json eval/results/experiments/arrangements-dev-hash.json --expect-current mrr@10=0.6625 --expect-current hit@5=0.75` (3.6 s) and `python scripts/experiment_retrieval.py --embedder cloudflare --split dev --json eval/results/experiments/arrangements-dev-cloudflare.json` (3.0 s); `python -m pytest tests/ -q` -> 1010 passed, 1 skipped (`tests/test_arrangements.py`, 14 new: all five described, every arrangement returning records with no duplicate, an unknown name rejected, `current` being the server's own settings rather than a reimplementation, `vector` and `rrf+keyword` carrying the settings they claim, BM25 alone finding a file the vectors rank last, the fused list holding both pools' first choices, depth honoured, the arrangements not all collapsing to one list, and four on the offline cache: a cached text served, a miss stopping the run with a count and no text, the signature, and `known`); `ruff check codeatlas/ tests/ scripts/experiment_retrieval.py`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (51 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before). Defaults unchanged: `python scripts/eval_retrieval.py --split test` still prints overall hit@5 0.750, MRR@10 0.645
- Dataset/repo: `eval/questions/*.json`, the 20 dev questions, at 672971d66a2e and d73fa1cdcbd8
- Date: 2026-10-11
- Commit: 9a7a94d
- Notes: **cost: zero neurons and zero tokens.** The cloudflare numbers come from `.codeatlas/eval-vectors/98332e737349d50a.json`, 1,805 vectors paid for at 149dac1 and b1bbfd4. Before running, all 1,864 document texts and all 40 dev and held-out questions were confirmed present in that file by hashing them against it; the run then served 1,864 + 20 lookups with **0 embedded**. `OfflineVectorCache` has no inner embedder to fall through to, so a miss raises instead of spending, and the run was made with every provider variable removed from the environment.
  **Two independent consistency checks passed, and they are what make the rest of the table believable.** `current` for hash printed MRR@10 0.6625 and hit@5 0.750 — the committed dev figures, asserted by `--expect-current`. `current` for cloudflare printed hit@1 0.650, hit@3 0.950, hit@5 1.000, MRR@10 0.8042, recall@20 1.000, which is `eval/results/cloudflare/dev.json` for mean-2000/keyword exactly; `vector` printed 0.732, also exactly. So the offline cache reproduces the paid run, and `current` is the server's pipeline rather than a lookalike.
  **The rejections are close, and one is very close.** `rrf` for hash is MRR 0.651 against 0.662 — 0.011, which on 20 questions is one question moving a couple of ranks. It is rejected because the rule says so, and the rule was fixed first; it is not evidence that fusion hurts.
  **What this cannot say.** Twenty questions, two repositories, and the two arrangements that meet the rule do so on the strength of ten flask questions. BM25's advantage over hash is not a surprising finding - hash is a bag of words with no semantics, so a properly weighted lexical retriever ought to beat it - and the honest reading is that **this measures how weak the hash embedder is**, not that BM25 is a good retriever in general. The cloudflare column is the one that tests BM25 against something competent, and there it loses on every arrangement.
  Nothing has been decided here and nothing held out has been scored. The choice is the next entry
### Feature: a "structured" record format — file headers and overlapping function windows
- Value: `CODEATLAS_RECORD_FORMAT` chooses what a record *is*. **`whole` is the default and is exactly today's behaviour**; `structured` changes two things that `docs/RESULTS.md` already showed were costing retrieval:

  | | `whole` (today) | `structured` |
  |---|---|---|
  | file record | the entire file, clipped from the start | path, module docstring, imports, and every class and function signature, capped at the window |
  | function record | the entire function, clipped from the start | one record if it fits; otherwise overlapping windows of the window size, each with its own line range |
  | records per function | 1 | 1 or more, shown as one result |

  The problem each half addresses is recorded: 54.2% of flask's file records are over the 2,000-character clip and keep 18.6% of their characters, so a clipped `app.py` is embedded as its licence header and imports; and 52 of flask's function records are over the clip, so a long function is embedded by its opening whatever its body says.

  **Windows are cut on line boundaries, never mid-line.** A record's line range is what the citation prints and what the file preview opens, so a window whose range is off by one points a reader at the wrong code while looking right. A single line longer than the whole window becomes its own window rather than being split. The walk always advances, even with an overlap larger than the window.

  **Ranking keeps one result per function** (`AnswerService._dedupe_windows`), so a visitor is never shown three slices of the same function. Records written under `whole` carry no `function_id`, so for them the step returns the list unchanged — asserted, not assumed.

  **The format is part of the mismatch guard.** `with_record_format` wraps the embedder so its signature becomes `hash:384:lowercase=0:subtokens=1|records=structured`, which puts the format into `CodeIndexService.index_format` and into `embedder_mismatch`. An index built under one format is refused by a server running the other rather than searched and answered wrongly. **Under `whole` the embedder is returned unwrapped and the signature is the string it has always been**, so no stored index is invalidated and the index cache still hits
- Command: `python -m pytest tests/ -q` -> 1056 passed, 1 skipped (`tests/test_record_format.py`, 32 new; `tests/test_retrieval_settings_from_env.py` gains 14). Windows: text that fits coming back as one unchanged window, a long text cut into several, every line covered with no gap, consecutive windows overlapping rather than abutting, no window starting or ending mid-line (checked against the file's own lines), ranges absolute in the file rather than relative to the function, an over-long line kept whole, the walk advancing under an absurd overlap, empty text, and a zero window size rejected. Headers: path, docstring, imports and signatures present, bodies absent, the cap applied, the path surviving the cap, a file with neither docstring nor imports, a one-line docstring, and a licence comment not hiding the docstring. Indexing: `whole` making exactly one record per function with no `function_id`, `structured` splitting a long one and numbering the windows, a short function keeping its plain id, and every window record pointing at lines that are really in the file. Signature: the default leaving it untouched, the non-default naming the format, the guard refusing each direction, vectors passing through unchanged, and an unknown format rejected by name. Deduplication: only the best window surviving, ranking order kept, records with no `function_id` returned identical, and the empty list. End to end: a structured index, a question naming one line deep inside a long function, and the citation opening a window that really holds that line; `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.750**, MRR@10 **0.645**, unchanged; `ruff check codeatlas/ tests/ scripts/experiment_retrieval.py`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (51 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before)
- Dataset/repo: files written by the tests; the held-out check is `eval/questions/*.json` at the pinned commits
- Date: 2026-10-11
- Commit: fce9e2a
- Notes: **nothing is measured here either.** Whether `structured` retrieves better is the next entry; this one adds the format and shows the default did not move.
  **The window size follows the clip.** `CODEATLAS_RECORD_WINDOW_CHARS` defaults to 2,000, but a provider with a per-document clip uses that clip instead, because a window larger than the clip would be embedded by its opening alone and the windowing would achieve nothing. Overlap defaults to 200 characters.
  **A known inconsistency, stated rather than fixed.** Under `structured` the embedder sees a file's *header*, but the keyword rerank and BM25 still read the file's *whole text* from disk, because `_record_text` is shared with the `whole` format. So a file record can be found by the embedder on its header and then ranked on its body. That is arguably the right trade - the rerank is local and free, and reading only the header would throw away the words a question actually matches - but it does mean "the file record is a header" is true of the vector and not of the ordering. Changing it would alter the `whole` format too, which this batch is not allowed to do.
  **Limits.** The header extraction is regex-based rather than parsed: the docstring rule looks for a leading triple-quoted string after comments and blank lines, and the import rule matches a line beginning with `import`, `from`, `#include`, `using`, `require`, `package`, `use` or `extern crate`. That covers the two Python repositories this is evaluated on and will be partly wrong elsewhere — a language whose imports are written differently simply contributes none. Signatures come from the Tree-sitter parse, which is already language-aware, so those are as good as the parser is
### Check: the structured record format on the dev split, for hash and for cloudflare
- Value: the same keep rule as before — **keep a change only if overall dev MRR@10 rises and dev hit@5 does not fall** — against the same baseline, `whole` records with the current pipeline.

  **Every configuration measured on dev, 20 questions.** The four rows in bold are the ones the server could actually be set to; the others are arrangements the experiment scores but the server has no mode for.

  | records | arrangement | hash MRR@10 | hash hit@5 | cloudflare MRR@10 | cloudflare hit@5 |
  |---|---|---|---|---|---|
  | **whole** | **current** (baseline) | **0.662** | **0.750** | **0.804** | **1.000** |
  | **whole** | **rrf+keyword** | **0.717** | **0.900** | **0.725** | **0.950** |
  | **structured** | **current** | **0.690** | **0.750** | **0.825** | **1.000** |
  | **structured** | **rrf+keyword** | **0.743** | **0.900** | **0.794** | **0.950** |
  | whole | bm25 alone | 0.782 | 0.850 | 0.782 | 0.850 |
  | whole | vector alone | 0.479 | 0.550 | 0.732 | 0.900 |
  | whole | rrf, no rerank | 0.651 | 0.800 | 0.742 | 0.950 |
  | structured | bm25 alone | 0.763 | 0.850 | 0.763 | 0.850 |
  | structured | vector alone | 0.488 | 0.600 | 0.733 | 0.900 |
  | structured | rrf, no rerank | 0.649 | 0.800 | 0.721 | 0.950 |

  **For hash, `structured` helps on its own** (0.662 → 0.690, hit@5 unchanged) **and helps more on top of BM25 fusion** (0.717 → 0.743, hit@5 0.900). **For cloudflare, `structured` helps and BM25 fusion does not**: 0.804 → 0.825 with the current pipeline, while every arrangement involving BM25 falls below the baseline.

  Per repository, where the result actually lives:

  | | hash whole | hash structured | cloudflare whole | cloudflare structured |
  |---|---|---|---|---|
  | itsdangerous MRR@10 (current) | 0.692 | **0.746** | 0.758 | **0.817** |
  | flask MRR@10 (current) | 0.633 | 0.635 | 0.850 | 0.833 |
  | flask recall@20 (rrf+keyword) | 0.900 | **1.000** | 1.000 | 1.000 |

  **The structured gain is itsdangerous, not flask** — the opposite of BM25's, whose whole gain was flask. itsdangerous is eight small files where a file record under `whole` is already short enough not to be clipped, so the gain there is the *header*: a record that is the path, the docstring and the signatures rather than the whole module. On flask the current-pipeline figure moves by 0.002 and 0.017 in opposite directions, which is noise
- Command: `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/experiment_retrieval.py --embedder hash --split dev --record-format structured --json eval/results/experiments/structured-dev-hash.json` (3.2 s); `python scripts/experiment_retrieval.py --embedder cloudflare --split dev --record-format structured --plan-only`, then the same with `--allow-spend --json eval/results/experiments/structured-dev-cloudflare.json` (19.0 s); `python -m pytest tests/ -q` -> 1056 passed, 1 skipped; `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.750**, MRR@10 **0.645**, unchanged; `ruff check codeatlas/ tests/ scripts/experiment_retrieval.py`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (51 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before)
- Dataset/repo: `eval/questions/*.json`, the 20 dev questions, at 672971d66a2e and d73fa1cdcbd8
- Date: 2026-10-11
- Commit: c92cb5b
- Notes: **cost, in full.** hash: nothing. cloudflare `whole`: nothing — every vector was already in the cache. cloudflare `structured`: a record format changes every document, so its vectors cannot be cached in advance. **Planned 313.88 estimated neurons over 333 uncached texts of 2,039; actually recorded 249.92 over 26 calls.** The ledger read **0.00 spent today** before the run and **249.92 of the 2,500 budget** after, leaving 2,250.08. The shortfall against the plan is duplicate texts, which the cache embeds once and the plan counted twice — the same effect recorded at 149dac1. A rerun of the structured evaluation would cost nothing.
  **How the spending was gated.** `--allow-spend` is the only way this script pays for anything, and before it sends a byte it prints the plan and the ledger, then refuses to start if the estimate would take the day past the budget. `--plan-only` prints the same and sends nothing; that is the run that produced the 313.88 figure above, and it was read before `--allow-spend` was used.
  **A consistency check worth keeping.** `structured` adds 175 documents (1,864 → 2,039) but only 333 of them are new *texts*. Most windows of a short function are byte-identical to the whole function, so the cache already had them — which is a check that windowing leaves a short function alone, arrived at from the billing side rather than from a test.
  **Two things this does not show.** First, 20 questions: a 0.021 difference in cloudflare MRR is about one question moving two ranks, and the `structured`-vs-`whole` gap for hash on flask is noise in both directions. Second, **the arrangements in the unbolded rows are not settings** — `bm25` alone scores highest of anything for hash (0.782) and there is no way to configure the server to do it, because BM25 was built as a second retriever fused with the first, which is what the four bold rows measure. Adding a BM25-only mode would be a different change and it is not in this batch
### Decision: the configuration chosen for each embedder, from the dev results alone
- Value: **chosen before anything held out was scored, and recorded here first so that the order cannot be argued about afterwards.** The choice is made only from the two dev entries above, and only from among configurations the server can actually be set to.

  | embedder | chosen | settings | dev MRR@10 | dev hit@5 | against the baseline |
  |---|---|---|---|---|---|
  | **hash** (default) | `structured` records **and** BM25 fusion on | `CODEATLAS_RECORD_FORMAT=structured`, `CODEATLAS_BM25=on` | **0.743** | **0.900** | 0.662 → 0.743 (+0.081), hit@5 0.750 → 0.900 |
  | **cloudflare** (opt-in) | `structured` records, BM25 fusion **off** | `CODEATLAS_RECORD_FORMAT=structured`, `CODEATLAS_BM25=off` | **0.825** | **1.000** | 0.804 → 0.825 (+0.021), hit@5 unchanged at 1.000 |

  Both meet the keep rule, which was fixed before any of these runs: dev MRR@10 rises and dev hit@5 does not fall.

  **Why the two differ on BM25.** For hash, fusing a real lexical retriever into the pool is worth +0.026 of MRR on top of `structured` (0.717 → 0.743 reading down the BM25 column, or 0.690 → 0.743 reading across from `structured` alone). For cloudflare it costs 0.031 (0.825 → 0.794). That is consistent with what BM25 is for: it rescues records a weak embedder never found, and a semantic embedder that already has recall@20 1.000 on this split has nothing to rescue — so fusion can only disturb an ordering that was already better than BM25's.

  **What was considered and not chosen.** `bm25` alone scores higher than either choice for hash (MRR 0.782, hit@5 0.850). It is **not adopted**, for a reason that is not about the numbers: the server has no BM25-only mode. BM25 was built as a second retriever fused with the first, so "BM25 alone" is an arrangement the experiment can score and the application cannot be configured to do. Adopting it would mean designing and testing a third retrieval mode, which is a different change from the one this batch made. It is recorded here so that the figure is not lost, and it is the obvious thing to try next for the default embedder.

  `whole` + BM25 fusion (hash MRR 0.717) and `structured` alone (hash 0.690, cloudflare 0.825) also meet the rule; each is beaten by the chosen configuration for its embedder, except that for cloudflare `structured` alone **is** the chosen configuration
- Command: no run. This entry reads `eval/results/experiments/{arrangements,structured}-dev-{hash,cloudflare}.json`, all four committed above, and decides from them
- Dataset/repo: the 20 dev questions in `eval/questions/*.json`. **The held-out split and holdout2 have not been scored under any of these configurations and no result from either has been looked at**
- Date: 2026-10-11
- Commit: recorded at this entry's own commit; the four result files it reads are at 9a7a94d and c92cb5b
- Notes: **this entry exists to fix the order of events.** Choosing a configuration after seeing how it does on held-out data is not a held-out measurement at all, and the only defence against doing it accidentally is to write the choice down first. What follows this entry is two scoring runs and no further tuning.
  **Neither default is being changed by this entry.** `CODEATLAS_RECORD_FORMAT` stays `whole` and `CODEATLAS_BM25` stays off in the committed configuration; the table above is what the held-out runs will be *passed*, not what the server ships. Changing a default is a separate decision that should be made after the held-out numbers, not before them, and `hash` held-out must still print hit@5 0.750 and MRR@10 0.645 until it is.
  **The margins are small and the sample is small.** +0.021 for cloudflare is about one question moving two ranks on 20 questions. +0.081 for hash is larger but rests on ten flask questions. Both are reasons to read the held-out runs as a check rather than a confirmation, and the original held-out split has been scored repeatedly in this file already, which is why a second set was written
### Check: the chosen configurations on the original held-out split and on holdout2, scored once
- Value: six runs, each made once, with no tuning after any of them. The configurations are the ones recorded in the decision entry above, which was committed before any of this was run.

  **The original held-out split (20 questions). This is a weak confirmation and should be read as one** — it has been scored in at least six entries in this file since it was written, so it has informed choices before, and a configuration that does well on it is not being tested on code the process has never seen.

  | embedder | configuration | hit@1 | hit@3 | hit@5 | MRR@10 | recall@20 |
  |---|---|---|---|---|---|---|
  | hash | default: `whole`, no BM25 | 0.600 | 0.650 | 0.750 | 0.645 | 0.800 |
  | hash | **chosen: `structured` + BM25 fusion** | **0.700** | **0.850** | **0.850** | **0.778** | **1.000** |
  | cloudflare | default: `whole`, no BM25 | 0.800 | 0.900 | 0.900 | 0.854 | **1.000** |
  | cloudflare | **chosen: `structured`, no BM25** | **0.850** | 0.900 | 0.900 | **0.873** | 0.950 |

  **holdout2 (20 questions, written for this batch, scored once, never used to choose anything).**

  | embedder | configuration | hit@1 | hit@3 | hit@5 | MRR@10 | recall@20 |
  |---|---|---|---|---|---|---|
  | hash | default: `whole`, no BM25 | 0.300 | 0.450 | 0.500 | 0.396 | 0.750 |
  | hash | **chosen: `structured` + BM25 fusion** | **0.500** | **0.550** | **0.750** | **0.576** | **0.850** |
  | cloudflare | default: `whole`, no BM25 | 0.450 | 0.700 | 0.800 | 0.587 | **0.950** |
  | cloudflare | **chosen: `structured`, no BM25** | **0.550** | 0.700 | **0.850** | **0.641** | 0.900 |

  Per repository on holdout2:

  | | hash default | hash chosen | cloudflare default | cloudflare chosen |
  |---|---|---|---|---|
  | itsdangerous MRR@10 | 0.488 | **0.650** | 0.733 | **0.900** |
  | flask MRR@10 | 0.303 | **0.502** | 0.440 | **0.382** |
  | flask recall@20 | 0.700 | **0.900** | 0.900 | 0.800 |

  **Three things these numbers say, and the first is the largest finding in this batch.**

  **1. A genuinely fresh question set scores far worse than the sets that have been used before.** hash's default falls from MRR 0.645 on the original held-out split to **0.396** on holdout2; cloudflare's falls from 0.854 to **0.587**. Same code, same repositories, same commits, same person writing the questions, same method — twenty questions that had never been looked at. The gap is roughly 0.25 of MRR for both embedders. **The earlier splits flatter this system**, and every retrieval figure recorded in this file before today should be read with that in mind.

  **2. Both chosen configurations are better than today's defaults on both held-out sets.** hash gains +0.133 of MRR on the original split and **+0.180 on holdout2**, with hit@5 +0.100 and +0.250; cloudflare gains +0.019 and +0.054. The improvements are larger on the fresh set than on the stale one, which is the opposite of what overfitting to dev would produce.

  **3. `structured` costs cloudflare recall, on both held-out sets.** recall@20 goes 1.000 → 0.950 on the original split and 0.950 → 0.900 on holdout2, and on holdout2's flask it is 0.900 → 0.800 with MRR falling 0.440 → 0.382. A file record that is a header is a worse net for a question whose words appear in a body the header does not quote. The overall figures still improve because the ranking gains more than the pool loses, but **this is a real cost, it is in the direction a reader should worry about, and it only shows up outside dev** — on dev, cloudflare's recall@20 was 1.000 under both formats and could not have revealed it
- Command: `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/experiment_retrieval.py --embedder hash --split test --record-format structured --arrangement rrf+keyword --json eval/results/experiments/chosen-heldout-hash.json`; `python scripts/experiment_retrieval.py --embedder cloudflare --split test --record-format structured --arrangement current --json eval/results/experiments/chosen-heldout-cloudflare.json`; then for holdout2, `--questions holdout2 --split holdout2` with `--record-format whole --arrangement current` and with each embedder's chosen pair, writing `eval/results/experiments/holdout2-{default,chosen}-{hash,cloudflare}.json`; the two cloudflare holdout2 runs added `--allow-spend`. `python -m pytest tests/ -q` -> 1056 passed, 1 skipped; `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; `ruff check codeatlas/ tests/ scripts/experiment_retrieval.py`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (51 passed), `npm run lint` (0 errors, same 28 warnings as before)
- Dataset/repo: `eval/questions/*.json` held-out split, and `eval/questions/holdout2/*.json`, all at 672971d66a2e and d73fa1cdcbd8
- Date: 2026-10-11
- Commit: 5edf06e
- Notes: **cost: 0.67 estimated neurons.** The cloudflare held-out run under `structured` needed nothing — the dev run had already paid for every document vector, and the twenty held-out questions were paid for at b1bbfd4 — so it was made through the offline cache with **0 texts embedded**. The two holdout2 runs needed only the twenty new question vectors: planned 0.88, recorded 0.67, over 20 calls. **Today's ledger: 250.59 estimated neurons of the 2,500 budget, 46 calls, 2,249.41 remaining.**
  **What "scored once" means here, precisely.** Each of the six runs was made one time and its numbers are the ones above. `--arrangement` was passed on every held-out run so that the arrangements *not* chosen were never computed on held-out data — they would have cost nothing, which is exactly why not computing them had to be deliberate. No configuration was changed after any run, and this entry is the first time any holdout2 number appears anywhere.
  **No default has been changed.** `CODEATLAS_RECORD_FORMAT` is still `whole` and `CODEATLAS_BM25` is still off in the committed configuration. Changing them is a decision for after this entry, not part of it, and `scripts/eval_retrieval.py --split test` still prints the recorded 0.750 / 0.645.
  **Limits.** Twenty questions per set: one question is 0.05 of a hit rate, so hash's +0.250 of hit@5 on holdout2 is five questions and cloudflare's +0.050 is one. holdout2's questions are mine, written from the same two repositories by the same method as the others, so "fresh" means unseen by the tuning process, not independent of me. And the per-repository split is uncomfortable: on holdout2 the chosen cloudflare configuration is much better on itsdangerous (0.733 → 0.900) and worse on flask (0.440 → 0.382), so the overall gain of 0.054 is an average over two repositories that disagree
### Feature: a grounded chat mode — one search, one model call, the model's own tokens streamed
- Value: `CODEATLAS_CHAT_MODE` is `legacy` or `grounded`, **default `legacy`**, which is the agent pipeline every recorded measurement describes. Grounded answers a repository question differently:

  | | legacy (fast path) | grounded |
  |---|---|---|
  | retrievals | 2 (retrieval agent, then the mentor searches again) | **1** |
  | model calls | 3 | **1** |
  | what is streamed | the finished answer, retyped 4 words every 8 ms | **the model's own tokens, as they arrive** |
  | citations | the mentor's snippets | **exactly the snippets in the prompt** |
  | agents recorded | `retrieval`, `mentor` | `grounded` — no agent graph runs, so naming one would be a lie |

  The prompt holds the capped snippets, each introduced by its path and line range, the session history as real turns, and the question. **Citations and prompt come from one list of snippets, built once** by `grounded_context`, and the cap is applied *before* the citations are made — so a snippet dropped for size cannot be cited, and the model cannot be blamed for a file it was never shown.

  **Everything the legacy path guarantees still holds**, and each has a test: the unknown-repo 404 happens before the stream opens and no model call is made; the 4,000-character question cap and the empty-question rejection are the request schema's and still 422; the rate limits are the router's and unchanged; the session history goes into the prompt and the answer goes back into it; a provider refusal becomes the same plain sentence as before, with the files beneath it and no `429` in sight; a reply cut off by the output limit still carries the truncation note; and the semantic-fallback note still reaches the `done` event.

  **Two provider behaviours are handled rather than left to surprise a reader.** A reasoning model emits chunks with no visible content first, so the first thing a visitor sees can be seconds after the call started: those chunks are skipped, they do not count as the first token, and the timer's `first_model_token` fires when something readable actually arrives. A model that finishes having said nothing produces a plain sentence and the file list, not an empty bubble
- Command: `python -m pytest tests/ -q` -> 1090 passed, 1 skipped (`tests/test_grounded_chat.py`, 26 new, every model a fake that yields chunks from a list: the mode setting and its rejection; the prompt holding each snippet's path and line range; citations equal to the prompt's snippets; a snippet dropped for size not cited; history in the prompt; a no-match question still producing a prompt; tokens forwarded one at a time in order; a reasoning model's empty chunks skipped; the first-token mark firing once; an empty reply explained; truncation; a daily refusal told apart from a per-minute one with no provider text leaking; a mid-stream failure keeping what was already said; and through the endpoint: status before tokens before done, citations in the done event present in the prompt, the question cap, the empty question, the 404 with no model call, the answer entering the session history, a refused answer **not** entering it, legacy mode not taking the grounded path, deep mode unaffected, exactly one model call, and no question text in the timings or the reasoning. `tests/test_retrieval_settings_from_env.py` gains 8 for the setting); in `codementor-ui`: `npm test` (57 passed, 6 new in `lib/streaming.test.ts`: one visible frame per token, a frame never shorter than the one before it, a single-token answer, no frame before a late first token, whitespace preserved, and nothing on the token path buffering, trimming or delaying), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`; `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; `ruff check codeatlas/ tests/`, `ruff format codeatlas/ tests/ --check`
- Dataset/repo: none — fake streaming models and a small index built by the tests. **No provider was called**
- Date: 2026-10-11
- Commit: ae7abcf
- Notes: **grounded mode retrieves through a service with no model attached.** `get_retrieval_service()` is `get_answer_service()` without the chat client, because grounded mode streams the model itself and has no use for the one the answer service would build. That matters beyond tidiness: a dependency on the full service would have meant every `/ask/stream` request — including one for a repository that does not exist — constructed a provider client before it could be refused, which is the failure recorded at 3143178.
  **Deep mode is untouched by the setting.** A `mode: "deep"` request runs the planned five-agent pipeline whichever chat mode is configured; grounded replaces the fast path only. That is deliberate — deep mode's value is the visible agent steps, which one model call cannot produce.
  **What is not measured here.** Whether grounded answers *better* is the next entry's question, and this one claims nothing about it. The number this design is aimed at is the one recorded at 64c7ae6 — "the time to the first token the user sees is the sum of three full model calls" — and even that is not measured yet.
  **Limits.** The system prompt tells the model to answer only from the snippets and to say so when they do not contain the answer; nothing enforces either, and a model that ignores the instruction will be cited as though it had not. A failure part way through the stream leaves the visitor with a partial answer followed by an explanation, which is better than an exception but is still two voices in one bubble. And the retrieval is a single search with no follow-up: if the first search misses, grounded mode has no second chance, where the legacy pipeline's second retrieval occasionally rescued one
### Check: legacy against grounded on the fifteen smoke questions, with a real model
- Value: both chat modes answered the same fifteen questions about the same two indexed repositories, warm, **one run each, thirty runs in all, none repeated**. Model: **openai/gpt-oss-20b on Groq**, the committed default, at the committed retrieval settings (`whole` records, BM25 off). **The deterministic check is the weak one** — two string tests per answer, no judge model, nothing that reads whether the explanation is right.

  | | legacy | grounded |
  |---|---|---|
  | passed | **12/15** | **12/15** |
  | expected file cited | 12/15 | 12/15 |
  | fact present | 14/15 | 14/15 |
  | runs with no model answer | 0 | 0 |
  | **time to the first streamed token, median** | 1.53 s | **0.61 s** |
  | total time, median | 1.56 s | **0.90 s** |
  | model calls | **30** (2 per question) | **15** (1 per question) |
  | tokens | **52,084** | **24,495** (−53%) |
  | cited files that were in the prompt | 45/45 | 45/45 |

  **The two modes score identically on the check and grounded costs half as much.** Same passes, same files cited, same facts found, with one model call instead of two and 27,589 fewer tokens over fifteen questions. The median first token arrives in 0.61 s against 1.53 s.

  **Every cited file was in the prompt, in both modes — 45 of 45.** For grounded that is true by construction and this measures the claim rather than discovering it. For legacy it was an open question, because the citations come from one retrieval and the answer from a later one, and the answer is that on these fifteen questions they never disagreed.

  **The medians hide a wide spread, and the spread is the model, not the pipeline.** Legacy's first token ranged 1.04 s to 15.15 s and grounded's 0.37 s to 14.71 s. The slow runs are a reasoning model spending ten to fifteen seconds on tokens nobody sees before it writes anything; when it does not, both modes answer in about a second. So the 2.5× median gap is real but it is the gap on the *fast* runs — on a run where the model thinks for fourteen seconds, neither shape helps
- Command: `python scripts/chat_mode_compare.py --max-session-tokens 140000 --out eval/results/experiments/chat-modes.json` (912.6 s, nearly all of it the pacer); `python -m pytest tests/ -q` -> 1096 passed, 1 skipped; `ruff check codeatlas/ tests/ scripts/`, `ruff format codeatlas/ tests/ --check`; in `codementor-ui`: `npm test` (68 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`; `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged
- Dataset/repo: the 15 questions in `eval/answer_smoke_questions.json`; https://github.com/pallets/itsdangerous and https://github.com/pallets/flask, indexed once and shared by both modes
- Date: 2026-10-11
- Commit: dcdb314
- Notes: **the default mode is unchanged.** `CODEATLAS_CHAT_MODE` is still `legacy`. This entry measures; it does not switch anything on.
  **Two accounting bugs were found by running this, and both are fixed.** A streamed call reported no usage at all, so every token it spent was missing from the metrics and from the on-disk ledger — which is the ledger a long run checks before deciding it still has budget, so the guard was guarding nothing. `stream_usage=True` on both providers fixes it, and it also means the website's general (no-repository) chat, which has always streamed, has never been counted until now. Separately, the comparison script works in a temporary directory and the ledger path is relative by default, so the day's spend was being written there and thrown away. **Both were discovered because the first trial reported 0 tokens for runs that had plainly cost some**, and that is the only reason the spend below is knowable at all.
  **Tokens: 100,196 spent today** (73,161 in, 27,035 out, 57 calls) against the 140,000 cap approved for this session, which includes about 17,500 from the two instrumentation trials before the accounting worked, and an unmeasured amount from the first trial, which recorded nothing. The run completed all thirty; nothing stopped it early, and no daily-limit 429 was seen. The per-minute limit was hit repeatedly and handled by the pacer and the client's own retry.
  **A result that should temper every smoke number in this file.** The legacy mode here is the committed fast path at the committed settings, and it scored **12/15** — against the **8/15** recorded for the same check, the same fifteen questions and the same model at f67b5d4. Nothing in the retrieval path changed between those runs. Four questions of fifteen moved on run-to-run variation alone, which is a 0.27 swing in a pass rate, and it is the clearest evidence yet that **this check cannot distinguish a change worth making from a different afternoon.** It is also why the identical 12/15 above is reported as "the two modes are not distinguishable on this check" rather than as "they are equally good".
  **Limits.** One machine, one provider, one day, one model. The timings are the client's own over a local socket, so they exclude the network between a browser and a deployed server and say nothing about one. Fifteen questions and a two-string check. Grounded's single retrieval has no second chance if the first search misses, which these questions did not test for; and the "cited files in the prompt" figure is 45/45 for both, so it did not discriminate either
### Feature: an Experiments table on the Benchmarks page, built from the experiment result files
- Value: `scripts/build_benchmarks.py` now reads `eval/results/experiments/` and the page gains an **Experiments** panel under the model-free timing one. **Twenty rows — every retrieval arrangement this batch scored, kept and rejected** — each with the change, the number of questions, the dev result, the held-out and fresh-split results where they were scored, the verdict, the embedder, the commit and the date.

  | column | what it holds |
  |---|---|
  | embedder | `hash` or `cloudflare` |
  | change | the record format and the arrangement, e.g. `structured / rrf+keyword` |
  | n | questions scored (20 for every split) |
  | dev hit@5, MRR@10, recall@20 | the development result, which is what the choice was made from |
  | held out | MRR@10 on the original held-out split — **only where it was actually scored** |
  | fresh | MRR@10 on holdout2 — likewise |
  | verdict | `baseline`, `chosen`, `met the rule; not chosen`, `met the rule; the server has no mode for it`, or `rejected` |

  **The verdict is computed, not copied.** The builder applies the keep rule — dev MRR@10 rises and dev hit@5 does not fall — to each row's own numbers, and a test in `tests/test_build_benchmarks.py` recomputes every verdict independently from the committed figures. A row whose numbers moved would change its own label rather than keeping a stale one.

  **A score is shown only where it was measured.** Non-chosen rows carry `null` for held out and fresh, and render as a dimmed dash; a test asserts that no row claims a held-out number it never earned. By default the panel shows the baselines, the chosen rows and the ones that met the rule; one button reveals all twenty including the rejections.

  The chat-mode comparison sits in the same panel under a badge reading **"one local run, one model, one question set - not a benchmark"**, with the model named, the question count shown, the weak-check wording repeated, and the first-token and total times beside the model calls and tokens. **No end-to-end latency claim appears anywhere in the panel**, asserted by a test on both sides that greps the rendered block for `ttfb`, `end_to_end`, `p95` and `latency`
- Command: `python scripts/build_benchmarks.py` then `python scripts/build_benchmarks.py --check`; `python -m pytest tests/ -q` -> 1096 passed, 1 skipped (`tests/test_build_benchmarks.py` gains 6: every dev run reaching the summary, the keep rule recomputed from the numbers for every row, exactly one chosen configuration per embedder, held-out numbers claimed only where scored, the chat-mode block saying what it is, and no end-to-end claim); in `codementor-ui`: `npm test` (68 passed, `lib/benchmarks.test.ts` gains 10 for the new panel), `npx tsc --noEmit`, `npm run lint` (0 errors, same 28 warnings as before), `npm run build`; `CODEATLAS_EMBEDDING_PROVIDER=hash python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; `ruff check codeatlas/ tests/ scripts/`, `ruff format codeatlas/ tests/ --check`
- Dataset/repo: the ten result files in `eval/results/experiments/`, written at 9a7a94d, c92cb5b, 5edf06e and dcdb314
- Date: 2026-10-11
- Commit: 33cf1e8
- Notes: **the regeneration guard still holds.** `eval/benchmarks.json` is still a pure function of its inputs with no timestamp, and the test that rebuilds it and compares byte for byte passes — which now also means an experiment result file cannot be edited by hand or quietly replaced without the summary failing to rebuild.
  **One figure in the table is worth a reader's attention more than the rest.** The two baseline rows carry a fresh-split score far below their dev score, and a frontend test asserts that relationship rather than the numbers, so the table cannot stop showing it: a question set that has never been used scores much worse than the ones that have.
  **Limits.** The held-out and fresh columns show MRR@10 only; the full set of metrics for those splits is in the result files and in the entries above, not on the page, because a table with three metrics across three splits does not fit a phone. The rows are generated from four dev runs of five arrangements, so an arrangement added later appears automatically but a *new kind* of experiment — a different question set, say — would need a new source entry in the builder. And the panel reports what the files say; it cannot tell a result file that is six weeks old from one written this morning, which is what the commit and date beside each row are for
### Check: the chosen hash configuration, run through the server's own retrieval path
- Value: `scripts/adoption_check.py` takes the embedder from `di.get_embedder()`, the index options from `di.index_options()`, the retrieval settings from `di.get_retrieval_settings()` and the search from `AnswerService.retrieve` — the four calls `get_retrieval_service()` makes — and is told nothing else. With two environment variables set, **it reproduces every number the experiment recorded, on all three splits and in both repositories, to four decimal places**.

  | split | scope | n | hit@1 | hit@3 | hit@5 | MRR@10 | recall@20 |
  |---|---|---|---|---|---|---|---|
  | dev | itsdangerous | 10 | 0.600 | 0.700 | 0.800 | 0.685 | 1.000 |
  | dev | flask | 10 | 0.600 | 1.000 | 1.000 | 0.800 | 1.000 |
  | dev | **overall** | 20 | **0.600** | **0.850** | **0.900** | **0.7425** | **1.000** |
  | held out | itsdangerous | 10 | 0.800 | 0.800 | 0.800 | 0.828 | 1.000 |
  | held out | flask | 10 | 0.600 | 0.900 | 0.900 | 0.729 | 1.000 |
  | held out | **overall** | 20 | **0.700** | **0.850** | **0.850** | **0.7785** | **1.000** |
  | holdout2 | itsdangerous | 10 | 0.600 | 0.600 | 0.800 | 0.650 | 0.800 |
  | holdout2 | flask | 10 | 0.400 | 0.500 | 0.700 | 0.503 | 0.900 |
  | holdout2 | **overall** | 20 | **0.500** | **0.550** | **0.750** | **0.5763** | **0.850** |

  Each row is compared against the committed experiment file metric by metric and the script exits 1 on any difference. Every row read `same`.

  **The two environment variables, and nothing else.** `CODEATLAS_RECORD_FORMAT=structured` and `CODEATLAS_BM25=true`. The other twelve settings the check reports came from their defaults and are printed with their source: `CODEATLAS_EMBEDDING_PROVIDER=hash`, window 2000 / overlap 200, candidates 20, rerank weight 1.0, BM25 k1 1.2 / b 0.75 / rrf_k 60 / depth 0, stopwords dropped, metadata prefixed, no per-document clip. So "`structured` + `rrf+keyword`" is two switches on the server, not a mode it lacks.

  **What `structured` costs, measured both ways on the same parse.**

  | repo | format | source files | records | file | function | index on disk | indexing |
  |---|---|---|---|---|---|---|---|
  | itsdangerous | whole | 15 | 159 | 15 | 144 | 810.1 KB | 0.23 s |
  | itsdangerous | **structured** | 15 | **177** (+11.3%) | 15 | 162 | **904.3 KB** (+11.6%) | 0.22 s |
  | flask | whole | 83 | 1,705 | 83 | 1,622 | 8,681.0 KB | 2.74 s |
  | flask | **structured** | 83 | **1,862** (+9.2%) | 83 | 1,779 | **9,516.4 KB** (+9.6%) | 2.24 s |

  The file record count is unchanged by construction — a file is still one record, it is just a header instead of the whole text. Every extra record is a window of a function longer than 2,000 characters: 18 more in itsdangerous, 157 more in flask. Index size tracks the record count almost exactly, because a record costs one 384-wide vector plus its metadata whatever its text says.

  **The index guard, driven in both directions.** An index is built under each format and then searched by a service configured for each, four combinations:

  | index built as | server configured as | records returned | index cache reuses it |
  |---|---|---|---|
  | whole | whole | 5 | yes |
  | whole | **structured** | **0 — refused** | no |
  | structured | **whole** | **0 — refused** | no |
  | structured | structured | 5 | yes |

  A mixed pair returns nothing and logs which signature it expected against which it found. `CodeIndexService.has_index` says no for the same pairs, so the index cache rebuilds rather than handing back an index of the wrong shape
- Command: `$env:CODEATLAS_EMBEDDING_PROVIDER = "hash"`; `$env:CODEATLAS_RECORD_FORMAT = "structured"`; `$env:CODEATLAS_BM25 = "true"`; `python scripts/adoption_check.py --json eval/results/experiments/adoption-hash.json` -> exit 0, 20.4 s. Then with both of the last two removed from the environment: `python -m pytest tests/ -q` -> 1096 passed, 1 skipped; `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (184 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; in `codementor-ui`: `npm test` (68 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: `eval/questions/*.json` (dev and held-out) and `eval/questions/holdout2/*.json`, at https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8. **No provider was called and no network beyond the two cached checkouts**
- Date: 2026-10-11
- Commit: ce05005
- Notes: **no default changed.** `CODEATLAS_RECORD_FORMAT` is still `whole` in the committed configuration and `CODEATLAS_BM25` is still off; this entry says the configuration is reachable and correct, not that it is on. The held-out guard still prints 0.750 / 0.645.
  **One trap found by writing this, and it is the reason the check could not be a flag on the existing script.** `scripts/eval_retrieval.py` reads `CODEATLAS_BM25` but **not** `CODEATLAS_RECORD_FORMAT`: its `IndexSettings` is built from three values and the record format falls back to `whole`, while the embedder it uses is `get_embedder()`, which *is* wrapped and signs itself `|records=structured`. Set both variables and run it and you get `settings: ... "record_format":"whole"` printed beside a structured signature, and overall MRR@10 0.799 on the held-out split — a real number for whole records fused with BM25, and **not** the 0.7785 this configuration actually scores. Nothing is corrupted, because the eval index lives and dies in one process, but a reader would be measuring something other than what they set. It is left as it is here on purpose: changing it is a behaviour change and belongs in its own commit.
  **What this does not show.** It is the retrieval step only — no model, no prompt, no citation. It says the same records come back, not that the answers are better; the only comparison of answers in this file is the fifteen-question smoke check, whose own entry records a 12/15-against-8/15 swing on run-to-run variation alone. The index-size figures are a FAISS flat index plus a pickled record list on this machine's filesystem, and the indexing seconds are one run each, warm, with the repositories already parsed — they are the right order of magnitude and nothing finer. And the guard check proves refusal for the record format specifically; the signature carries the provider, the dimensions and two hash options besides, and only the format was exercised here
### Change: holdout3, a third held-out question set, written and left unscored
- Value: ten new questions per repository, twenty in all, in `eval/questions/holdout3/`. Same two repositories at the same two pinned commits as every other set, so the code they ask about is the code every number in this file describes. **No number on them exists.** They were not scored, no result file mentions them, and nothing in this entry says how the system does on them.

  | | dev | held out (test) | holdout2 | **holdout3** |
  |---|---|---|---|---|
  | questions | 20 | 20 | 20 | **20** |
  | written | before any tuning | before any tuning | 2026-10-11, after both had been used | **2026-10-11, after holdout2 was scored** |
  | times scored | many | at least six | once | **none** |

  **What "new" is checked to mean.** Six tests, parametrised over both repositories. No question text and no id repeats one of the sixty earlier questions. No question overlaps an earlier one by half its words or more — the same cheap reworded-question check holdout2 got, run here against all thirty earlier questions per repository rather than the first twenty. Every expected path is a real file in the checkout at the pinned commit. Each set is ten questions, all carrying the `holdout3` split, each with at least one expected file.

  **And one test whose whole job is to keep it unscored:** neither `scripts/eval_retrieval.py` nor `scripts/experiment_retrieval.py` may contain the string `holdout3`. Both scripts name the question files they read, so a plain run of either cannot reach this set by accident; scoring it has to be a deliberate act, written down.

  The questions reach parts of each repository the earlier sets did not ask about: the text encoding used before signing, an unrecognised key-derivation name, a signed value with no separator, whether the timestamp is inside what gets signed, a valid signature with no time part, why a date conversion catches `OSError` and `OverflowError`, serializer keyword options, the base exception class, non-ASCII characters in the compact payload, and what a replacement serializer must implement; and for flask, a reused class-based view instance, writing to the session with no secret key, the cookie being rewritten when nothing changed, dictionary key order in a JSON response, the command that lists routes, running a command line callback inside an application context, rendering a template as a stream, reading settings from a TOML file, an invalid JSON request body, and the tutorial app's status for editing someone else's post
- Command: `python -m pytest tests/test_retrieval_eval.py -q` -> 36 passed (11 new); `python -m pytest tests/ -q` -> 1107 passed, 1 skipped; `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (184 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; in `codementor-ui`: `npm test` (68 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: https://github.com/pallets/itsdangerous at 672971d66a2e and https://github.com/pallets/flask at d73fa1cdcbd8, read from the two checkouts already in `.codeatlas/eval-repos`. **No provider was called and nothing was scored**
- Date: 2026-10-11
- Commit: 3ace1de
- Notes: **why a third set exists.** The entry at 5edf06e records that hash's default fell from MRR 0.645 on the original held-out split to 0.396 on holdout2, and concluded that the earlier splits flatter this system. holdout2 has now been scored — six times in one entry, and again in the adoption check above — so the same erosion has started on it. A set that has never been looked at is the only kind that can answer "is this better" honestly, and it stops being one the moment it is used. This one is being banked, not spent.
  **Limits, and they are the same ones holdout2 has.** Twenty questions: one question is 0.05 of a hit rate. Two Python libraries by the same authors, at one commit each. The questions are mine, written by reading the source with the earlier sets in front of me to avoid repeating them — so "fresh" means unseen by the tuning process, not independent of the person who wrote the other sixty. And the overlap test is word counting: it catches a shuffled rewording and cannot catch two differently worded questions that happen to want the same passage
### Change: the Benchmarks page says which held-out set to believe, and shows both
- Value: the page carried one clause about holdout2 being "fresh" and left a reader to work out what that meant for the other column. It now says it three times, where the numbers are.

  **In the Experiments panel**, above the table: the original held-out split was reused — scored in at least six recorded entries since it was written, so it has informed choices before and is a weak confirmation rather than a clean one; holdout2 was written after those runs and scored once, so it is the fresher estimate, and it is the lower one; where they disagree, **holdout2 is the one to believe**. The two column headings come from the summary and now read *held out — reused, scored many times before* and *fresh — written later, scored once*.

  **In the retrieval tables**, the held-out split carries a `reused` badge and the same sentence underneath it; the development split carries neither, and a test asserts both halves of that.

  **And a new side-by-side block**, four rows — each embedder's default and its chosen configuration — with dev, the reused held-out figure, the fresh one and the gap:

  | embedder | configuration | dev | held out (reused) | fresh (holdout2) | difference |
  |---|---|---|---|---|---|
  | hash | today's default | 0.663 | 0.645 | **0.396** | **−0.249** |
  | hash | chosen | 0.743 | 0.779 | **0.576** | **−0.202** |
  | cloudflare | today's default | 0.804 | 0.854 | **0.587** | **−0.267** |
  | cloudflare | chosen | 0.825 | 0.873 | **0.641** | **−0.232** |

  **Every configuration is 0.20 to 0.27 of MRR worse on the set that had never been used**, and that is now one glance rather than four files. A baseline's held-out figure is not in the experiment files — it is the recorded retrieval run in the panel above — so each row names the file each of its two numbers came from rather than having one quietly filled in. Two tests assert the *relationship* (fresh is lower, the difference is negative) rather than the values, so the table cannot stop showing it; a third reads every fresh number back out of the file its row names.

  **The two-question trial can no longer be mistaken for the thirty-run comparison.** `chat-modes-trial.json` was a fallback source: with `chat-modes.json` absent it would have been drawn under the same heading, the same "not a benchmark" badge and the same column names, and the only thing distinguishing a four-run block from a thirty-run one would have been a number a reader had to notice. It is now not a source at all, the builder refuses any file that is not 15 questions and 30 runs, and the block prints its own size — *15 questions, 30 runs* — beside the model. The trial file is kept where it is as the record of that run
- Command: `python scripts/build_benchmarks.py` then `python scripts/build_benchmarks.py --check` -> up to date; `python -m pytest tests/ -q` -> 1114 passed, 1 skipped (`tests/test_build_benchmarks.py` gains 7: the reuse wording in both panels, the four side-by-side rows with their sources, every row worse on the fresh split, each fresh number read back from the file its row names, the trial not being a source, the block stating its scale, and the builder returning nothing when pointed at the trial); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (184 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; in `codementor-ui`: `npm test` (74 passed, 6 new in `lib/benchmarks.test.ts`), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before), `npm run build`
- Dataset/repo: the committed result files in `eval/results/` and `eval/results/experiments/`; nothing was re-scored and no number changed
- Date: 2026-10-11
- Commit: 7045a97 (the summary and its builder), e6598b9 (the page)
- Notes: **the regeneration guard still holds.** `eval/benchmarks.json` is still a pure function of its inputs with no timestamp, and the byte-for-byte rebuild test passes.
  **No measurement is in this entry.** Every figure above was already recorded — at 5edf06e for holdout2, at 016c655 and b1bbfd4 for the two held-out retrieval runs. What changed is which of them sit next to each other and what the page says about them.
  **What this does not fix.** The side-by-side table is MRR@10 only, because four metrics across three splits does not fit a phone; the rest is in the result files and in the entries above. The reuse count — "at least six" — is a statement about this file written by hand, not something the builder counts, so it will go stale if the split is scored again without the sentence being updated. And saying holdout2 is the fresher estimate is already slightly untrue of today: it has now been scored seven times in all, including in the adoption check above, which is why holdout3 was written and left alone
### Fix: the eval script builds its index with the server's record settings, and refuses a mismatched pair
- Value: the trap recorded in the note at ce05005 is closed. `scripts/eval_retrieval.py` took three of its index settings from `di.index_options` and let the record format fall back to `whole`, while the embedder it scored with was `di.get_embedder()` — which under `CODEATLAS_RECORD_FORMAT=structured` **is** wrapped and signs itself `|records=structured`. The run printed `"record_format":"whole"` beside a structured signature and scored a pair the server refuses to put together.

  **The same two environment variables, before and after.** `CODEATLAS_RECORD_FORMAT=structured` and `CODEATLAS_BM25=true`, held-out split, overall:

  | | MRR@10 | hit@5 | recall@20 | what it was really measuring |
  |---|---|---|---|---|
  | before (recorded at ce05005) | 0.799 | — | — | **whole** records fused with BM25, under a structured signature |
  | after | **0.778** | **0.850** | **1.000** | structured records fused with BM25 |

  The second row is the configuration those variables name, and it is **the same to four decimal places as `scripts/adoption_check.py` and `eval/results/experiments/chosen-heldout-hash.json`**: itsdangerous MRR@10 0.828, flask 0.729, overall hit@1 0.700, hit@3 0.850, hit@5 0.850, MRR@10 0.7785, recall@20 1.000. Three different paths through the same settings now print one number instead of two.

  **Three changes, and the first is the whole fix.**

  1. `record_format`, `window_chars` and `window_overlap` come from `di.index_options` with the rest of the index settings, so the eval indexes what the server would index.
  2. **The effective record format is printed before the run** — `record format: structured (window 2000, overlap 200)` — rather than only inside the settings JSON, where it was previously the dataclass default rather than anything that had been read.
  3. **A signature that disagrees with the settings stops the run with status 1** and names both sides. It is a backstop, not a flag: with the fix in place no command line can produce a disagreement, because the one path that rebuilt the embedder (`--hash-lowercase`, `--hash-subtokens`) now wraps the rebuilt one in the same format again. It is driven in both directions by tests instead.

  `describe_embedder` also looks inside the wrapper, so a structured run reports `hash (HashEmbeddingService, 384 dims, subtokens, …), records structured` instead of `RecordFormatEmbedder`, which named no provider at all
- Command: `python scripts/eval_retrieval.py --split test` -> `record format: whole (window 2000, overlap 200)`, overall hit@5 **0.750**, MRR@10 **0.645**, unchanged; `$env:CODEATLAS_RECORD_FORMAT = "structured"` then the same command -> `record format: structured`, overall hit@5 0.750, MRR@10 **0.688**; with `$env:CODEATLAS_BM25 = "true"` as well -> overall hit@5 0.850, MRR@10 **0.778**, recall@20 1.000; both variables then removed from the environment. `python -m pytest tests/ -q` -> **1127 passed**, 1 skipped (13 new: `tests/test_eval_retrieval_script.py` 12, `tests/test_retrieval_eval.py` 1); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (185 files); in `codementor-ui`: `npm test` (74 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: `eval/questions/*.json` held-out split, at https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8, from the checkouts already in `.codeatlas/eval-repos`. **No provider was called and no API key was read**
- Date: 2026-10-12
- Commit: 04a0295
- Notes: **no default moved.** With nothing set the format is `whole`, the window settings are 2000/200, and the held-out guard still prints 0.750 / 0.645 — the two numbers every entry in this file has checked since the format existed.
  **What the tests cover.** Every index setting compared field by field against `di.index_options` under both formats; the format and both window settings read from the environment; a rebuilt hash embedder keeping the format in its signature; an unwrapped signature reading as `whole`; the message naming both sides and the variable to look at; the guard driven in each direction; and `main` returning 1 **and never calling `run`** on a mismatched pair, so a disagreement cannot produce a number at all.
  **What this does not fix.** The structured figure of 0.688 above is a new number on the *reused* held-out split, which this file already says is a weak confirmation; it is here as evidence that the script now measures what it is told to, not as a result. And the inconsistency recorded at fce9e2a is untouched: under `structured` the embedder sees a file's header while the keyword rerank and BM25 still read the file's whole text
### Decision: the rule holdout3 will be read by, written before holdout3 was scored
- Value: **no number on holdout3 exists when this entry is committed**, and that is the point of it. holdout3 was written at 3ace1de and banked unscored; it is about to be spent, and the rule it is spent under is fixed here first so that the order cannot be argued about afterwards.

  **The candidates. Four are eligible, one is scored for information only.**

  | # | embedder | candidate | settings | eligible |
  |---|---|---|---|---|
  | 1 | hash | **today's default** — whole records, no BM25 | none set | the incumbent |
  | 2 | hash | **structured records + BM25 fusion** — the dev choice at 9a7a94d | `CODEATLAS_RECORD_FORMAT=structured`, `CODEATLAS_BM25=on` | **yes** |
  | 3 | cloudflare | **today's default** — whole records | `CODEATLAS_EMBEDDING_PROVIDER=cloudflare` | the incumbent |
  | 4 | cloudflare | **structured records**, BM25 off — the dev choice | + `CODEATLAS_RECORD_FORMAT=structured` | **yes** |
  | 5 | hash | whole records + BM25 fusion | `CODEATLAS_BM25=on` | **no — information only** |

  **The rule, metric by metric.**

  * **The hash candidate (2) replaces the default (1) only if its holdout3 MRR@10 is higher *and* its holdout3 hit@5 is not lower.** Both conditions, on holdout3, overall.
  * **cloudflare structured (4) replaces cloudflare whole (3) only if its holdout3 MRR@10 is higher *and* its holdout3 recall@20 is not lower.** Both conditions, on holdout3, overall.
  * **Row 5 is not eligible for selection whatever it scores.** It is scored because it separates the two halves of candidate 2 — whether a gain is the record format or the fusion — and a reader who sees only the chosen pair cannot tell. A number that is not allowed to decide anything is still worth having, and saying so in advance is the only thing that keeps it that way.

  **Why the two guards are different metrics, and it is not an arbitrary choice.** Each embedder is guarded on the metric this file has already recorded the candidate *costing* it. For hash the risk is ranking: the entry at 5edf06e records hit@5 moving 0.500 → 0.750 on holdout2, so hit@5 is what must not go backwards. For cloudflare the recorded cost of `structured` is **recall** — 1.000 → 0.950 on the original held-out split and 0.950 → 0.900 on holdout2, because a file record that is a header is a worse net for a question whose words are in a body the header does not quote. recall@20 is the pool the reranker chooses from, so a candidate that ranks better out of a smaller pool is buying the gain with coverage, and the guard refuses that trade.

  **What is reported, for every candidate:** hit@1, hit@3, hit@5, MRR@10 and recall@20, per repository and overall.

  **holdout3 is scored once and never retuned.** One run per candidate, the numbers that come back are the numbers, and no setting is changed afterwards and re-scored on it. If a candidate fails the rule it is not adjusted and tried again — that would make holdout3 a development set, which is exactly what happened to the original held-out split and then to holdout2. Any further tuning needs a fourth question set, written after these numbers are read
- Command: no run. This entry decides nothing from data; it fixes the rule the next entry's data will be read by
- Dataset/repo: `eval/questions/holdout3/*.json`, 20 questions at https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8. **Not yet scored under anything.** No result file names holdout3 and no number on it appears anywhere in this file above this line
- Date: 2026-10-12
- Commit: decided at 56a9c35 and committed on top of it; no code changed by this entry
- Notes: **what passing the rule does and does not do.** It makes a default change *proposable*, not applied. Changing `CODEATLAS_RECORD_FORMAT` or `CODEATLAS_BM25` in the committed configuration would rebuild every existing index (the format is in the embedder signature and therefore in the index-format guard) and would move the two numbers the held-out guard asserts, so it is its own change with its own entry, and this batch does not make it.
  **The sample is twenty questions.** One question is 0.05 of a hit rate and about 0.05 of MRR, so a rule written on "higher" and "not lower" can turn on a single question moving two ranks. That is a known weakness of deciding from twenty questions and it is why the rule is two conditions rather than one, and why the per-repository table is reported beside the overall one: two repositories that disagree are worth seeing even when the average passes.
  **What could still go wrong even if everything passes.** holdout3's questions are mine, written from the same two Python libraries at the same two commits by the same method as the other sixty, so "fresh" means unseen by the tuning process, not independent of the person who wrote it. And retrieval is not answers: nothing in this rule says a visitor's answer gets better
### Change: the experiment script can score a question set named on the command line
- Value: an enabler for the entry below, committed separately because it changes a script and that should be reviewable on its own. `scripts/experiment_retrieval.py` carried exactly two question lists, `original` and `holdout2`, and named their files in its source. A set written later cannot be added to that source: `test_holdout3_is_not_wired_into_any_default_question_list` asserts that neither eval script contains the string, which is what stops a default run reaching an unscored set by accident. The consequence was that such a set could not be scored **at all** by this script — and the Cloudflare half of any scoring run has to go through it, because it is the only path with the offline vector cache, the spend plan and the neuron ledger.

  `--set` names a question file, is repeatable, and **replaces** the list `--questions` names rather than adding to it. The result file is then labelled by the folder those files live in — computed from the paths, so the script still carries no list of sets that will exist later.

  | run | files scored | `"questions"` in the result file |
  |---|---|---|
  | no flag | `eval/questions/*.json` | `original` |
  | `--questions holdout2` | `eval/questions/holdout2/*.json` | `holdout2` |
  | `--set a/x.json --set a/y.json` | exactly those two | `a` |
  | files from two folders | exactly those | `mixed` |

  Nothing about a run without `--set` changes, and the guard test still passes unchanged: scoring a later set is a deliberate act with the paths written out in the command line and in this file
- Command: `python -m pytest tests/ -q` -> **1133 passed**, 1 skipped (6 new in `tests/test_experiment_retrieval_script.py`: the two built-in lists, a run with no flag keeping them, a named set replacing the list entirely under either `--questions`, the folder label, the `mixed` label for files from two folders, and a relative path labelled like an absolute one); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (186 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; in `codementor-ui`: `npm test` (74 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: none for the tests (paths only, nothing is read or scored). The guard eval is `eval/questions/*.json` at the two pinned commits. **No provider was called**
- Date: 2026-10-12
- Commit: fac69a4
- Notes: **no measurement is in this entry** and nothing was scored by it.
  **Why not a `--questions holdout3` choice instead.** That is the one thing that cannot be done: the string would be in the script's source and the guard test exists precisely to forbid it. Naming the files on the command line keeps the set reachable only from a command somebody wrote down
### Check: holdout3, scored once for each candidate, and the rule applied
- Value: five runs, each made one time, under the rule committed at 16464d2 before any of them existed. **No setting was changed after any run and nothing was re-scored.**

  **Overall, 20 questions.** The verdict column is the rule, not a judgement.

  | # | embedder | candidate | hit@1 | hit@3 | hit@5 | MRR@10 | recall@20 | verdict |
  |---|---|---|---|---|---|---|---|---|
  | 1 | hash | today's default — whole, no BM25 | 0.500 | 0.600 | 0.650 | 0.5517 | 0.700 | the incumbent |
  | 2 | hash | **structured + BM25 fusion** | **0.600** | **0.750** | **0.800** | **0.6900** | **0.850** | **passes: MRR +0.1383, hit@5 +0.150** |
  | 5 | hash | whole + BM25 fusion | 0.550 | 0.750 | 0.800 | 0.6571 | **0.950** | not eligible — information only |
  | 3 | cloudflare | today's default — whole | 0.700 | **0.900** | **0.950** | 0.8042 | 0.950 | the incumbent |
  | 4 | cloudflare | **structured, no BM25** | **0.750** | 0.850 | 0.900 | **0.8113** | 0.950 | **passes: MRR +0.0071, recall@20 equal** |

  Per repository, which is where both verdicts get uncomfortable:

  | | hash default | hash chosen | hash whole+BM25 | cloudflare default | cloudflare chosen |
  |---|---|---|---|---|---|
  | itsdangerous MRR@10 | 0.683 | **0.780** | 0.760 | **0.900** | 0.883 |
  | itsdangerous recall@20 | 0.900 | **1.000** | **1.000** | **1.000** | **1.000** |
  | flask MRR@10 | 0.420 | **0.600** | 0.554 | 0.708 | **0.739** |
  | flask recall@20 | 0.500 | 0.700 | **0.900** | 0.900 | 0.900 |

  **Both candidates pass the rule. Four things a reader should see anyway.**

  **1. The hash result is large and consistent.** +0.138 of MRR and +0.150 of hit@5 overall, better on both repositories, and flask — where the default is weakest on this set (MRR 0.420, recall@20 0.500) — gains most. This is the third held-out set in a row where the chosen hash configuration beats the default, after +0.133 on the original split and +0.180 on holdout2.

  **2. The cloudflare result is one question wide.** +0.0071 of MRR is a single question moving a rank or two. It passes because the rule is MRR and recall, and on both it does; but **hit@3 falls 0.900 → 0.850 and hit@5 falls 0.950 → 0.900**, and on itsdangerous MRR falls 0.900 → 0.883. The whole of the overall gain is flask (0.708 → 0.739). A rule written on two metrics was always going to be able to pass while a third fell — that is what choosing the metrics in advance costs, and the alternative, picking the metric after seeing the numbers, is worse.

  **3. The information-only row says where hash's gain comes from, and it is mostly not the record format.** Whole records fused with BM25 — row 5, which the rule forbade from being selected — scores MRR 0.657 against the default's 0.552. So **fusion is worth about +0.105 of the +0.138, and the structured format about +0.033 on top of it.** And row 5 has the **best recall@20 of any hash run, 0.950 against the chosen configuration's 0.850**: `structured` costs hash recall here exactly as it was recorded costing cloudflare recall at 5edf06e. The chosen configuration ranks better out of a smaller pool. Had the hash rule been written on recall rather than hit@5 the chosen candidate would have failed and row 5, which is not eligible, would have been the only candidate that passed.

  **4. holdout3 does not repeat holdout2's collapse, so "a fresh set scores worse" is not what the earlier finding showed.** MRR@10 for the same configuration across all four sets:

  | configuration | dev | held out (reused) | holdout2 (fresh) | **holdout3 (never used)** |
  |---|---|---|---|---|
  | hash default | 0.662 | 0.645 | 0.396 | **0.552** |
  | hash chosen | 0.743 | 0.779 | 0.576 | **0.690** |
  | cloudflare default | 0.804 | 0.854 | 0.587 | **0.804** |
  | cloudflare chosen | 0.825 | 0.873 | 0.641 | **0.811** |

  The entry at 5edf06e read holdout2's gap as the reused splits flattering the system. holdout3 is a *different* never-looked-at set by the same author from the same two repositories, and it lands between holdout2 and the reused splits — cloudflare's default lands exactly on its dev figure. **The honest reading is that a twenty-question set varies by this much**: the two fresh sets differ from each other by 0.114 (hash chosen) to 0.217 (cloudflare default) of MRR. That is a statement about the size of these question sets, not about which set is virtuous, and it should temper every single-set comparison in this file, including the ones above it
- Command: for each candidate, `python scripts/experiment_retrieval.py --split holdout3 --set eval/questions/holdout3/itsdangerous.json --set eval/questions/holdout3/flask.json --json eval/results/experiments/holdout3-<name>.json` with: `--embedder hash --record-format whole --arrangement current` (default-hash, 4.4 s); `--embedder hash --record-format structured --arrangement rrf+keyword` (chosen-hash, 5.6 s); `--embedder hash --record-format whole --arrangement rrf+keyword` (whole-bm25-hash, 5.1 s); `--embedder cloudflare --record-format whole --arrangement current --allow-spend` (default-cloudflare, 27.0 s); `--embedder cloudflare --record-format structured --arrangement current` (chosen-cloudflare, 3.1 s, no `--allow-spend` and no API call). Each cloudflare run was preceded by the same command with `--plan-only`. Then `python -m pytest tests/ -q` -> 1133 passed, 1 skipped; `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (186 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; in `codementor-ui`: `npm test` (74 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: `eval/questions/holdout3/*.json`, 20 questions, at https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8, from the checkouts already in `.codeatlas/eval-repos`
- Date: 2026-10-12
- Commit: ecf3744 (the five result files); the runs were made at ef754c6 with a clean tree, which is the commit recorded inside each file
- Notes: **cost, in full. 0.71 estimated neurons.** The plan for the whole-records cloudflare run was 1,864 documents of which **20 were not yet cached** — exactly the twenty holdout3 question vectors — for a planned 0.96; recorded 0.7069 over 20 calls. The structured run then planned **2,039 documents, 0 uncached, 0.00 neurons** and was served entirely from the offline cache with **no API call**, because its documents were paid for at c92cb5b and its questions had just been paid for by the run before it. **Today's ledger: 0.71 estimated neurons of the 2,500 budget, 20 calls, 2,499.29 remaining.** Both plans were printed and read before anything was sent.
  **What "scored once" means here, precisely.** Five runs, one each. `--arrangement` was passed on every one, so the four arrangements not under consideration were never computed on holdout3 — they would have cost nothing, which is exactly why not computing them had to be deliberate. The two `--plan-only` runs computed no score. This entry is the first time any holdout3 number appears anywhere, and holdout3 is now spent: it has been scored, and the next time a setting needs choosing it will need a fourth set.
  **No default is changed by this entry.** `CODEATLAS_RECORD_FORMAT` is still `whole` and `CODEATLAS_BM25` is still off in the committed configuration. What the rule supports is proposed in a later entry and applied in neither.
  **Limits.** Twenty questions per set: one question is 0.05 of a hit rate, so cloudflare's +0.0071 of MRR is well inside the noise a single question makes, and point 4 above is a measurement of that noise rather than an aside. The questions are mine, written from the same two Python libraries at the same two commits as the other sixty. And this is retrieval only — no model, no prompt, no citation, and nothing here says a visitor's answer is better
### Change: holdout3 on the Benchmarks page, with the rule it was scored under
- Value: the summary and the page carried two held-out sets. They now carry three, and the newest one is drawn with the rule that was fixed before it was spent rather than with a sentence written afterwards.

  **A block of its own, above the older tables.** Five rows — each embedder's incumbent and candidate, plus the one configuration the rule barred from selection — with all five metrics, the question count, and the file each number came from:

  | embedder | configuration | hit@1 | hit@3 | hit@5 | MRR@10 | recall@20 | verdict |
  |---|---|---|---|---|---|---|---|
  | hash | today's default | 0.500 | 0.600 | 0.650 | 0.552 | 0.700 | the incumbent |
  | hash | candidate | 0.600 | 0.750 | 0.800 | 0.690 | 0.850 | **passes: MRR@10 higher, hit@5 not lower** |
  | hash | information only | 0.550 | 0.750 | 0.800 | 0.657 | 0.950 | not eligible — barred before it was scored |
  | cloudflare | today's default | 0.700 | 0.900 | 0.950 | 0.804 | 0.950 | the incumbent |
  | cloudflare | candidate | 0.750 | 0.850 | 0.900 | 0.811 | 0.950 | **passes: MRR@10 higher, recall@20 not lower** |

  **Every verdict in that table is computed by the builder** from the committed result files, against the two guard metrics as data (`hash` → hit@5, `cloudflare` → recall@20). None of them is a sentence typed beside a number, so a result file that changed would change the verdict rather than leave a stale claim next to a new figure. A test recomputes all five from the numbers, and another reads every metric back out of the file its row names.

  **The ineligible row is drawn, and says so.** Whole records with BM25 fusion has the best recall@20 of any hash run on holdout3 (0.950) and was forbidden from being selected before it was scored. Leaving it off the page would hide where the hash gain comes from; drawing it like a candidate would let a reader think it was one. It is drawn, greyed, and labelled *not eligible*.

  **holdout3 also gets a column** in the experiments table — filled only for the rows actually scored on it, dashed everywhere else — and in the side-by-side block, which is now **three** held-out sets. The `difference` column is unchanged and its heading now names which two sets it compares.

  **And the page stops telling a reader which fresh set to believe.** It said *"where they disagree, holdout2 is the one to believe"*, which was fair when holdout2 was the only never-used set. It now says that holdout2 and holdout3 are both fresh, that they **do not agree with one another — by up to 0.217 of MRR@10 on the same code** — and that no single set of twenty questions settles a comparison on its own. Two tests assert that wording, and the ones asserting that the reused split is flagged and that holdout2 is the lower of the first two still pass unchanged
- Command: `python scripts/build_benchmarks.py` then `python scripts/build_benchmarks.py --check` -> up to date; `python -m pytest tests/ -q` -> **1139 passed**, 1 skipped (`tests/test_build_benchmarks.py` gains 6: the block and its label, the rule recomputed with both guard metrics, the ineligible row, every number read back from the file its row names, the column in both tables with a number claimed only where it was scored, and the wording about the two fresh sets); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (186 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; in `codementor-ui`: `npm test` (**79 passed**, 5 new in `lib/benchmarks.test.ts`), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before), `npm run build`
- Dataset/repo: the committed result files in `eval/results/` and `eval/results/experiments/`. **Nothing was re-scored and no number changed**; the five holdout3 files are the ones committed at ecf3744
- Date: 2026-10-12
- Commit: d056989
- Notes: **the regeneration guard still holds.** `eval/benchmarks.json` is still a pure function of its inputs with no timestamp, and the byte-for-byte rebuild test passes.
  **No measurement is in this entry.** Every figure above was recorded at ecf3744. What changed is which numbers sit beside each other and what the page says about them.
  **What this does not fix.** The per-row `recorded` label in the experiments table still names one entry (5edf06e) for a row that now carries dev, held-out, holdout2 **and** holdout3 numbers recorded in different entries; the holdout3 block carries its own correct provenance, and splitting the row-level label per column is a larger change than this one. The side-by-side block is still MRR@10 only, because five metrics across four splits does not fit a phone. And the "at least six" reuse count is still a sentence written by hand rather than something the builder counts
### Proposal: the default changes holdout3 supports, and everything each one would move
- Value: **proposed and not applied. No default is changed by this entry, no file outside `docs/RESULTS.md` is touched by it, and nothing here has been set anywhere.** Both candidates passed the rule fixed at 16464d2, which makes exactly this proposable and nothing more.

  | variable | today | proposed | what passed the rule |
  |---|---|---|---|
  | `CODEATLAS_RECORD_FORMAT` | `whole` | **`structured`** | hash: MRR@10 0.552 → 0.690 with hit@5 0.650 → 0.800. cloudflare: 0.804 → 0.811 with recall@20 unchanged at 0.950 |
  | `CODEATLAS_BM25` | `off` | **`on`** — only while the provider is `hash` | the hash candidate is the pair; the format alone is not what was scored |

  **The two candidates share one variable and disagree about the other.** `CODEATLAS_RECORD_FORMAT` is global, and both candidates want `structured`, so that one is a clean proposal. `CODEATLAS_BM25` is global too, and BM25 **on** is the hash candidate while BM25 **off** is the cloudflare one — fusion cost cloudflare 0.031 of dev MRR at c92cb5b, because an embedder with recall@20 1.000 has nothing for a lexical retriever to rescue. Render runs `CODEATLAS_EMBEDDING_PROVIDER=hash`, so `on` is right there today; **switching that service to cloudflare would have to turn BM25 off in the same change**, and nothing in the code enforces that pairing. A provider-aware default would be a different change, and it is not proposed here.

  **1. The index format guard, and what it refuses.** Under `structured` the embedder is wrapped and signs itself `hash:384:lowercase=0:subtokens=1|records=structured`. That string is `CodeIndexService.index_format` and the value `embedder_mismatch` compares, so **every index already on disk is refused rather than searched** — `has_index` says no, the index cache misses, and the repository is reindexed on its next analysis. That is the designed behaviour (driven in both directions at ce05005) and it is also the whole operational cost: nothing silently answers from the old vectors.

  **2. Existing indexes rebuilt — cheap here, expensive on the other provider.** For `hash` a rebuild is local arithmetic: 0.22 s for itsdangerous and 2.24 s for flask under `structured`, with the index on disk growing 11.6% and 9.6% (measured at ce05005). On the free Render plan there is **no persistent disk**, so indexes are already wiped on every restart and the practical cost is zero; if the disk proposed at b157fe5 is ever mounted, each repository is rebuilt once, on its next analysis, and then stays. **Under `cloudflare` the same flip is not cheap**: a record format changes every document, so every vector would have to be paid for again — about 276 estimated neurons per capped repository.

  **3. The hash held-out guard numbers, and this is the part with a real casualty.**

  | what asserts it | today | under the proposal |
  |---|---|---|
  | `.github/workflows/retrieval-eval.yml`, itsdangerous, 20 questions, `MIN_HIT_AT_5=0.85` | hit@5 **0.850** — passes with **zero margin** | hit@5 **0.800** — **the workflow fails** |
  | the same workflow, `MIN_HIT_AT_1=0.70` | hit@1 **0.700** — passes with zero margin | hit@1 **0.700** — still passes, still with zero margin |
  | the same run's other metrics | MRR@10 0.756, recall@20 0.950 | MRR@10 **0.756** (identical), recall@20 **1.000** |
  | `eval/results/test.json`, which `/metrics` and the Benchmarks retrieval panel read | hit@5 0.750, MRR@10 0.645 | hit@5 **0.850**, MRR@10 **0.7785** once regenerated; stale and wrong until it is |
  | `eval/results/dev.json`, the same | hit@5 0.750, MRR@10 0.6625 | hit@5 **0.900**, MRR@10 **0.7425** once regenerated |
  | the line every entry in this file carries — *"`--split test` -> 0.750 / 0.645, unchanged"* | the guard | **no longer the guard**; a new pair would have to be adopted deliberately, in the entry that changes the default |

  **The CI workflow is the thing to look at before anything else.** The proposed configuration retrieves *better* overall on every held-out set and **worse on the one 20-question slice that CI happens to assert**: itsdangerous keeps its MRR exactly (0.756) and trades a hit@5 for a recall@20 — the file moves out of the top five and into the pool. Applying the default change therefore means editing a guard downwards in the same commit, which is the one move this file should never make quietly. It is also worth recording that **both thresholds pass today by exactly 0.000**, so that workflow has been one question away from red since it was written.

  **4. What else moves, all of it downstream of the files above.** Regenerating `eval/results/{dev,test}.json` moves the `codeatlas_retrieval_hit_rate` and `codeatlas_retrieval_mrr` gauges (`split="test"`: 0.750 → 0.850 and 0.645 → 0.7785), the hash rows of the Benchmarks retrieval panel, and the hash baseline row of the side-by-side block (held-out 0.645 → 0.7785, its difference −0.2494 → −0.2022). The Benchmarks builder would also need changing rather than just rebuilding: `BASELINE = ("whole", "current")` is labelled *"today's default"* in two panels, and after the flip the chosen configuration **is** the default, so the baseline and the candidate would be the same row. `tests/test_build_benchmarks.py` compares the summary byte for byte, so it fails until the summary is rebuilt; `tests/test_metrics.py` reads the result file rather than a literal, so it follows quietly — which is exactly why the result files have to be regenerated deliberately rather than left behind.

  **5. One cost that is not a number anywhere yet.** With BM25 on, `AnswerService` builds a lexical index **in process, on the first question about a repository, and keeps it** until that repository is reindexed — the full text of every record, 1,862 of them for flask under `structured`, in a dictionary keyed by repository that nothing evicts. On a free Render instance that is memory which grows with the number of repositories a visitor has analysed. **It has not been measured**, and it should be before this is applied
- Command: the two runs this entry adds are `python scripts/eval_retrieval.py --set eval/questions/itsdangerous.json --split all --min-hit-rate 5=0.85 --min-hit-rate 1=0.70` — which is the CI workflow's own command — first with nothing set (`ok: 0.8500 >= 0.8500`, `ok: 0.7000 >= 0.7000`), then with `$env:CODEATLAS_RECORD_FORMAT = "structured"` and `$env:CODEATLAS_BM25 = "true"` (`FAIL: overall hit@5 0.8000 is below the minimum 0.8500`, exit status 1), both variables then removed from the environment. Everything else here is read from entries above. `python -m pytest tests/ -q` -> 1139 passed, 1 skipped; `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (186 files); `python scripts/build_benchmarks.py --check` -> up to date; `python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; in `codementor-ui`: `npm test` (79 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: `eval/questions/itsdangerous.json`, all 20 questions, at https://github.com/pallets/itsdangerous 672971d66a2e. **No provider was called; the holdout3 figures quoted are the ones recorded at ecf3744 and nothing was re-scored**
- Date: 2026-10-12
- Commit: d056989 (the state this proposal describes)
- Notes: **approval required before any of this is set**, and applying it is at least four things in one change: the two variables, a regeneration of the two hash result files and the summary, an edit to the Benchmarks builder's notion of a baseline, and a decision about `MIN_HIT_AT_5` in CI. That is why it is a proposal and not a commit.
  **What the rule did not say, and this entry will not say either.** Passing on holdout3 is one twenty-question set. The same entry that recorded the pass also recorded that two freshly written sets disagree with each other by up to 0.217 of MRR@10, that cloudflare's margin is +0.0071 with hit@3 and hit@5 both falling, and that most of hash's gain is the BM25 fusion rather than the record format. A reader who wants to apply only the half with the large, consistent effect could turn **BM25 on and leave the record format alone**: that is the ineligible row on holdout3 (MRR 0.657 against the default's 0.552, hit@5 0.800, **recall@20 0.950, the best of any hash run**), and the rule deliberately forbade *selecting* it. Proposing it would need its own decision entry and its own fresh question set, because choosing it now would be choosing from numbers that have already been looked at.
  **Nothing here is about answers.** Every figure is retrieval: which files come back and in what order. No model, no prompt, no citation, and the inconsistency recorded at fce9e2a still stands — under `structured` the embedder sees a file's header while the keyword rerank and BM25 read the file's whole text
### Feature: the record format and BM25 are set per index kind, not once for the whole server
- Value: the proposal at d056989 ended on a pairing nothing enforced. `CODEATLAS_BM25` was global, BM25 **on** was the hash candidate and BM25 **off** was the cloudflare one, and *"switching that service to cloudflare would have to turn BM25 off in the same change, and nothing in the code enforces that pairing."* It is enforced now, by making the setting per index kind rather than per server.

  **The case is not hypothetical, because one server already holds two indexes.** Under `CODEATLAS_EMBEDDING_PROVIDER=cloudflare` a repository gets a cloudflare index *and* a hash fallback index, built from the same records in the same analysis (`DualIndexService`), and the fallback is what answers when the API is spent, slow or unreachable. Everything recorded in this file says those two want different things: fusion is worth about **+0.105 of MRR@10** to hash on holdout3 and **cost cloudflare 0.031 of dev MRR** at c92cb5b, because an embedder already at recall@20 1.000 has nothing for a lexical retriever to rescue. A single global variable had to be wrong for one of them.

  **Four new variables, each unset by default:**

  | variable | falls back to | what it decides |
  |---|---|---|
  | `CODEATLAS_HASH_RECORD_FORMAT` | `CODEATLAS_RECORD_FORMAT` | what a record is in the hash index — including the fallback index in the dual-index path |
  | `CODEATLAS_CLOUDFLARE_RECORD_FORMAT` | `CODEATLAS_RECORD_FORMAT` | the same, for the cloudflare index |
  | `CODEATLAS_HASH_BM25` | `CODEATLAS_BM25` | whether a question against the hash index is fused with BM25 |
  | `CODEATLAS_CLOUDFLARE_BM25` | `CODEATLAS_BM25` | the same, for the cloudflare index |

  **No default changed in this entry.** With none of the four set, `config.record_format_for(kind)` is `whole` and `config.bm25_enabled_for(kind)` is `False` for both kinds, which is what the server already did; a test asserts exactly that, and `--split test` is unmoved at hit@5 0.750, MRR@10 0.645.

  **Three things that had to be got right rather than merely wired up.**

  **1. Unset and off are different, and `or` cannot tell them apart.** `None` means "this kind said nothing, use the global"; `False` means "this kind said off". `bm25_enabled_for` therefore tests for `None` explicitly — an `or` would have made `CODEATLAS_BM25=true` with `CODEATLAS_CLOUDFLARE_BM25=false` silently turn fusion **on** for cloudflare, which is the exact mistake this entry exists to prevent. A **set but unreadable** value still stops the app, for the reason `_flag` already gives: a retrieval setting that quietly reverts makes a measurement describe something other than what was configured. The error message now names the variable that carried the value, because always naming the global one would send a reader to a variable they had not set.

  **2. Only two settings are per kind, and the service enforces it.** The BM25 parameters (k1, b, rrf_k, depth) and the two window settings stay global: nothing has measured them differing per index, and a setting with no evidence behind it is not worth a second way to be wrong. `AnswerService` takes **only** the fields in `PER_INDEX_FIELDS` from the fallback's settings and keeps everything else from the primary's — `drop_stopwords` is applied to the question *before* the index is chosen, and it also signs the cloudflare embedder, so the two indexes could not differ on it even if the code let them. A test asserts that a caller asking for a different `drop_stopwords` on the fallback gets the primary's.

  **3. The BM25 cache was keyed by repository alone, and one repository now has two record lists.** Keyed by `repo_id` only, the hash fallback's lexical index and the cloudflare index's would have collided under one key and thrashed — each question rebuilding the other's. The key is now `(id(retriever), repo_id)`. A test asserts that a fallback question builds the index against the *fallback* retriever and not against the semantic one

  **The guard still refuses a mixed index, now once per kind.** The record format reaches `embedder_mismatch` through the embedder's signature, so `CODEATLAS_HASH_RECORD_FORMAT=structured` signs the hash embedder `hash:384:lowercase=0:subtokens=1|records=structured` and an index on disk under the other format is refused rather than searched. This is tested for **both kinds and both directions** (four cases), plus the case that matters now that the settings are separate: moving the *other* kind's variable must refuse nothing
- Command: `python -m pytest tests/ -q` -> **1165 passed**, 1 skipped (`tests/test_per_index_settings.py` is new and adds 26: what the settings resolve to with nothing set, with the globals set and with a per-kind override; a per-kind `false` under a global `true`; a provider that is not an index kind; four invalid values that stop the app; an empty value reading as unset; the settings reaching `index_options`, the embedder signature and `retrieval_settings_for`; a dual index holding two formats at once and its `index_format` naming both; the guard refusing a mixed index for each kind in both directions; the other kind's variable refusing nothing; a fallback question answered in the hash index's own format and fused only if the hash index says so; and a window record's line range checked against the file on disk). `tests/test_bm25.py` has two assertions updated for the new cache key. `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (187 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; in `codementor-ui`: `npm test` (79 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: no question set was scored and no provider was called. The tests build their own one-file repository in a temporary directory; the `--split test` run is the committed guard on https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8 from the checkouts in `.codeatlas/eval-repos`
- Date: 2026-10-12
- Commit: dec0764
- Notes: **what this does not do.** It does not change a default, propose one, or make the pairing the proposal described *automatic* — a server that sets `CODEATLAS_BM25=true` globally and then switches to cloudflare still fuses the cloudflare index. What it does is make the right configuration **expressible**: `CODEATLAS_HASH_BM25=true` with `CODEATLAS_CLOUDFLARE_BM25=false` survives a provider switch, where the global variable did not. Choosing which of those a deployment sets is step 5's decision, not this one's.
  **The window and BM25 parameters are deliberately still global**, so a reader looking for `CODEATLAS_HASH_BM25_K1` will not find one. Adding it would be two more ways for a measurement to describe something other than what was configured, for a difference nothing in this file has measured.
  **`scripts/adoption_check.py` now reports both layers**, the global variable and the effective hash value, so its environment table cannot say `whole` while the index it builds is structured. Its `--record-format` equivalent goes through `every_index_kind_on`, which clears the per-kind overrides rather than setting only the global one — without that, the index-cost and guard sections would have measured the override instead of the format they were asked for
### Check: what the in-process BM25 cache weighs, and a cap on it with least-recently-used eviction
- Value: point 5 of the proposal at d056989 was *"one cost that is not a number anywhere yet"* — with BM25 on, `AnswerService` builds a lexical index on the first question about a repository and keeps it, in a dictionary **nothing evicted**. It has a number now, and a ceiling.

  **The index itself, walked with `sys.getsizeof` and deduplicated by object id.** This is the deterministic measurement: it does not move with the allocator or with what else the process is holding.

  | record format | repo | records | terms | postings | lengths | **the cache's own** | shared with the retriever |
  |---|---|---|---|---|---|---|---|
  | whole | itsdangerous | 159 | 877 | 519.7 KB | 3.7 KB | **0.51 MB** | 0.01 MB |
  | whole | flask | 1,705 | 4,121 | 4,077.8 KB | 21.5 KB | **4.02 MB** | 0.08 MB |
  | whole | **both** | | | | | **4.53 MB** | |
  | structured | itsdangerous | 177 | 877 | 569.4 KB | 4.3 KB | **0.56 MB** | 0.01 MB |
  | structured | flask | 1,862 | 4,121 | 4,538.7 KB | 23.2 KB | **4.47 MB** | 0.09 MB |
  | structured | **both** | | | | | **5.03 MB** | |

  **Two columns, because one of them is not a cost.** A `Bm25Index` holds a list of the retriever's `EmbeddingRecord` objects; the list is new, the objects are not. Evicting the index frees the postings and the lengths and **does not** free the records, so the records are reported separately — and that column is the objects' own weight, not their text, which is read from disk per question and never held. The term count does not move with the record format, because `structured` re-cuts the same text rather than adding any new words to it.

  **The process, read from the operating system.** Working set via `GetProcessMemoryInfo`, which is how `scripts/answer_smoke.py` already reads memory: `ctypes` into the Win32 API with a `/proc` fallback and no new dependency. Three separate processes, one per arm, because a process that has held one arm's indexes does not give the next arm's number back.

  | arm | after imports | after both repos indexed | after one question each | **total** |
  |---|---|---|---|---|
  | **today's defaults** — whole, BM25 off | 134.6 MB | 172.5 MB (+37.9) | 172.9 MB (+0.4) | **172.9 MB** |
  | whole records, BM25 **on** | 134.6 MB | 173.0 MB (+38.4) | 178.4 MB (+5.4) | **178.4 MB** |
  | **the proposed defaults** — structured, BM25 on | 134.9 MB | 175.1 MB (+40.2) | 181.9 MB (+6.8) | **181.9 MB** |

  **The whole of the difference is +9.0 MB**, and it splits the way the deterministic measurement predicts: about **+5.5 MB** is the two lexical indexes (5.03 MB of structures, the rest allocator overhead) and about **+2.6 MB** is `structured` adding 157 more records to flask's index and 18 to itsdangerous's. Both repositories at once, which is the worst case this evaluation has.

  **The cap.** `CODEATLAS_BM25_MAX_INDEXES`, **default 4**, caps how many lexical indexes are held at once across every repository and every retriever. The cache is an `OrderedDict` in least-recently-used order: a cache *hit* moves its entry to the newest end, so what is dropped is what has gone unused longest rather than what was built first — a repository asked about every minute is not evicted for having been the first one analysed. An evicted index is **rebuilt on the next question** about that repository, from records already in memory, so the cost of setting the cap too low is time and never a different answer; a test asserts the rebuilt index returns the same ranking as the one it replaced.

  **Why 4, and what it bounds.** flask is the larger of the two repositories at 4.47 MB, so four of the largest repository this evaluation has is about **18 MB**, reached only by a visitor who has asked questions about four such repositories without the service restarting. The cap is **one number for one cache**, deliberately not a per-index setting: under the dual-index path a single repository can hold a lexical index per index kind, and a test asserts both are counted against the cap
- Command: three runs of `python scripts/bm25_memory.py --json eval/results/experiments/bm25-memory-<arm>.json`, each in its own process at 87d8f57 with a clean tree: nothing set (old-defaults, 3.2 s); `$env:CODEATLAS_HASH_BM25 = "true"` (whole-records, 3.5 s); `$env:CODEATLAS_HASH_RECORD_FORMAT = "structured"` with `$env:CODEATLAS_HASH_BM25 = "true"` (new-defaults, 3.8 s). Both variables were removed from the environment after each run. Then `python -m pytest tests/ -q` -> **1174 passed**, 1 skipped (`tests/test_bm25.py` gains 9: the default cap existing at all, the cache stopping at the cap, the least recently *used* entry being the one evicted rather than the oldest, an evicted index rebuilt on demand returning the same ranking, a cap of 1 still keeping 1, an eviction logged with the repository and no question text, two retrievers holding one repository counting as two, the cap read from the environment and refused at 0 or at a word, and the cap not being a per-index field); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (188 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; in `codementor-ui`: `npm test` (79 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8, from the checkouts in `.codeatlas/eval-repos`. **No provider was called and no question set was scored** — the first question of each set is asked once per arm to force the lexical index to be built, and its answer is discarded
- Date: 2026-10-12
- Commit: 9293366 (the three result files); the runs were made at 87d8f57, which is the commit recorded inside each file
- Notes: **the host's memory limit is unverified.** Every figure above is this Windows machine's working set under Python 3.12.15. Nothing here has read the memory limit of any deployment, no Render plan's limit has been looked up or confirmed, and no claim is made that 181.9 MB fits anywhere. What the measurement supports is the **difference** — +9.0 MB for both evaluation repositories at once, and a bound of about 18 MB on what the cache can hold under the default cap — not an absolute verdict about any host.
  **What a working set is and is not.** It is noisy: an allocator does not return freed pages promptly, imports and FAISS dominate the 134 MB baseline, and a rehearsal of the same arm before these files were committed differed by 0.3 MB. That is why the deterministic `getsizeof` walk is reported beside it rather than instead of it, and why the three arms were run in separate processes.
  **No default changed in this entry** beyond the cap itself, which had no previous value because nothing was capped. `CODEATLAS_RECORD_FORMAT` is still `whole`, `CODEATLAS_BM25` is still off, and `--split test` is unmoved at hit@5 0.750, MRR@10 0.645.
  **Limits.** Two repositories, both Python, both small to medium; flask at 1,862 structured records is the largest thing measured and a repository at the 600-document cloudflare cap or beyond is not. The cap counts *indexes*, not bytes — four small repositories and four flask-sized ones are the same to it, which is the cheap approximation and is worth knowing before the number 4 is read as a memory limit. Nothing here measures the vector index, the record objects, or the conversation store, all of which also grow with the number of repositories
### Change: the retrieval-eval workflow gates on MRR@10 and recall@20, per repository
- Value: the proposal at d056989 said the CI workflow was *"the thing to look at before anything else"* — the candidate retrieves better on every held-out set and worse on the one 20-question slice CI happened to assert. The gate is re-baselined rather than edited downwards, on the two metrics the holdout3 decision was actually made on.

  **The old gate and the new one.**

  | | old | new |
  |---|---|---|
  | question sets | `itsdangerous.json` only | `itsdangerous.json` **and** `flask.json` |
  | split | `all` (20 questions) | `all` (20 + 20 = **40 questions**) |
  | thresholds | `MIN_HIT_AT_5=0.85`, `MIN_HIT_AT_1=0.70`, both on **overall** | `MIN_MRR_ITSDANGEROUS=0.7564`, `MIN_RECALL_ITSDANGEROUS=1.0`, `MIN_MRR_FLASK=0.7646`, `MIN_RECALL_FLASK=1.0`, each on **one repository** |
  | recorded for | hash on whole records, BM25 off, at 513641c | hash on structured records, BM25 fusion on |
  | margin | 0.000 on both, since the day they were written | **0.000 on all four, deliberately** |

  **Three reasons, in order of how much they matter.**

  **1. hit@5 is the metric the candidate trades away, and it is the only one the gate watched.** On this split the candidate keeps itsdangerous's MRR almost exactly (0.7558 → 0.7564) and moves one expected file out of the top five and into the pool: hit@5 0.850 → 0.800, recall@20 0.950 → **1.000**. A gate on hit@5 alone reads that as a regression. The holdout3 rule, fixed at 16464d2 *before* anything was scored, was written on MRR@10 with a guard metric; gating on MRR@10 and recall@20 is that rule, applied to the thing that runs on every push.

  **2. Overall is an average of two repositories that do not move together.** Under the old default, on this split, itsdangerous scored MRR@10 0.7558 and flask 0.5517 — a gap of 0.20. The degraded run below makes the point concretely: clipping every document to 200 characters drops **itsdangerous from 0.7564 to 0.6667** while **flask rises from 0.7646 to 0.8396**, and overall moves only 0.7605 → 0.7530. An overall gate at the recorded value does still catch that, by 0.0075; the per-repository gate catches it by **0.0897**, twelve times the margin, and names which repository broke.

  **3. No hidden slack, and that is a choice rather than an oversight.** Each threshold is the recorded value to four decimal places. A gate set below what was measured passes the regression it was put there to catch, and any margin would be a number nobody had measured anything about. The cost is real and is accepted: `recall@20 = 1.0` on both repositories means a single expected file leaving a 20-candidate pool turns the check red. A deliberate improvement is expected to move these lines up in the same commit that earns them.

  **The gate was run three ways, locally, with the exact command the workflow uses.**

  | configuration | itsdangerous MRR@10 / recall@20 | flask MRR@10 / recall@20 | exit |
  |---|---|---|---|
  | **the new hash default** (structured + BM25) | 0.7564 / 1.0000 — ok, ok | 0.7646 / 1.0000 — ok, ok | **0** |
  | the old default (whole, BM25 off) | 0.7558 / 0.9500 — **FAIL**, **FAIL** | 0.5517 / 0.7000 — **FAIL**, **FAIL** | **1** |
  | the new default, **deliberately degraded** (`CODEATLAS_EMBED_MAX_CHARS=200`) | 0.6667 / 1.0000 — **FAIL**, ok | 0.8396 / 1.0000 — ok, ok | **1** |

  The degraded run is the one worth reading twice. Clipping every embedded document to its first 200 characters is a real setting a server can be given, it genuinely hurts retrieval on itsdangerous, and **one repository improving did not hide it**. Recall survived on both, so a gate on recall alone would have passed this; MRR on one repository is what caught it.

  **`--min-mrr` and `--min-recall` take a repository name or `overall`.** A scope the run did not score is a **failure**, not a skip — otherwise a renamed question set silently disarms the gate that named it, and the workflow goes green while asserting nothing. Every threshold is still reported after one of them fails, because a gate that stops at the first says nothing about how close the others were.

  **The old baseline is kept reproducible, not merely remembered.** `eval/results/legacy/{dev,test}.json` hold the previous configuration's runs, regenerated under `CODEATLAS_HASH_RECORD_FORMAT=whole` and `CODEATLAS_HASH_BM25=false` and **byte-identical** to the figures recorded at 016c655: held out hit@5 **0.750**, MRR@10 **0.645**, recall@20 0.800; dev hit@5 0.750, MRR@10 0.6625. `eval/results/{dev,test}.json` follow whatever the default is and will be regenerated when it changes; these two do not move, so the hundreds of lines in this file ending *"--split test -> overall hit@5 0.750, MRR@10 0.645, unchanged"* keep something to point at. Unlike the files recorded at 016c655, these name the configuration inside themselves — `record_format: whole`, `bm25_enabled: false` — which the older ones could not, because neither setting existed yet
- Command: `python scripts/eval_retrieval.py --set eval/questions/itsdangerous.json --set eval/questions/flask.json --split all --min-mrr itsdangerous=0.7564 --min-recall itsdangerous=1.0 --min-mrr flask=0.7646 --min-recall flask=1.0` — which is the workflow's own command — run three times: with `$env:CODEATLAS_HASH_RECORD_FORMAT = "structured"` and `$env:CODEATLAS_HASH_BM25 = "true"` (exit 0); with nothing set (exit 1, all four below); and with the same two plus `$env:CODEATLAS_EMBED_MAX_CHARS = "200"` (exit 1, itsdangerous MRR below). Every variable was removed from the environment afterwards. The legacy files are `python scripts/eval_retrieval.py --split {test,dev} --json eval/results/legacy/{test,dev}.json` under `$env:CODEATLAS_HASH_RECORD_FORMAT = "whole"` and `$env:CODEATLAS_HASH_BM25 = "false"`. Then `python -m pytest tests/ -q` -> **1190 passed**, 1 skipped (`tests/test_retrieval_eval.py` gains 6 for the new flags: a per-repository threshold on each metric, a repository below its own threshold failing, `overall` still available, a scope that was not scored failing with the scored names printed, a spec that is not `SCOPE=VALUE` failing, and every threshold still reported after one fails; `tests/test_legacy_baseline.py` is new and adds 9); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (190 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 0.750, MRR@10 0.645, unchanged; in `codementor-ui`: `npm test` (79 passed), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: `eval/questions/itsdangerous.json` and `eval/questions/flask.json`, all 20 questions of each, at https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8, from the checkouts in `.codeatlas/eval-repos`. **No provider was called**: every run is the hash embedder
- Date: 2026-10-12
- Commit: 5312156 (the per-scope thresholds), 16cb414 (the workflow and the legacy baseline)
- Notes: **this gate is red until the default changes, and that is deliberate.** The thresholds describe a configuration the committed server does not yet run — the middle row of the table above is this branch's own state. The workflow runs on pushes to `main` and on pull requests to it, so what CI sees is the branch head, where the default change lands. The two must not be separated: a `main` that has this workflow and not the default is a `main` that cannot go green.
  **What is still not gated.** flask's 20 questions are now in the gate and the three held-out sets are not; holdout2 and holdout3 are deliberately kept out of anything that runs automatically, because a set that runs on every push is a set that is being tuned against, which is the whole reason three of them exist. hit@1, hit@3 and hit@5 are still computed and printed on every run — they are simply no longer thresholds.
  **The CI job is slower.** It indexes flask as well as itsdangerous: 6.1 s locally against 3.1 s, inside a 10-minute timeout that has not changed.
  **Limits.** Forty questions over two Python libraries at two pinned commits, scored on file-level retrieval only. Nothing here says an answer is better, and a gate at zero margin will eventually go red for a change that is an improvement — at which point the right move is to record the new numbers in this file and raise the lines, not to widen them
### Change: the hash default is structured records with BM25 fusion
- Value: the proposal at d056989 is applied, for **hash only**. Steps 2 to 4 of this batch were the conditions on it: the setting had to be expressible per index kind, the memory cost had to have a number, and the CI gate had to be re-baselined on the metrics the decision was made on. All three are done, so the default moves.

  | variable | before | now | who it applies to |
  |---|---|---|---|
  | `CODEATLAS_RECORD_FORMAT` | `whole` | **`structured`** | hash, and any provider without a default of its own |
  | `CODEATLAS_BM25` | off | **on** | the same |
  | `CODEATLAS_CLOUDFLARE_RECORD_FORMAT` | *(did not exist)* | **`whole`**, pinned | cloudflare |
  | `CODEATLAS_CLOUDFLARE_BM25` | *(did not exist)* | **off**, pinned | cloudflare |

  **The hash numbers, every split, before and after.** Nothing here is new evidence: these are the configuration's own runs, regenerated so the committed files describe what the server does.

  | split | questions | hit@5 | MRR@10 | recall@20 |
  |---|---|---|---|---|
  | dev | 20 | 0.750 → **0.900** | 0.6625 → **0.7425** | 0.850 → **1.000** |
  | held out (reused) | 20 | 0.750 → **0.850** | 0.645 → **0.7785** | 0.800 → **1.000** |
  | holdout2 (fresh) | 20 | 0.650 → **0.750** | 0.3956 → **0.5763** | 0.750 → **0.850** |
  | holdout3 (never used) | 20 | 0.650 → **0.800** | 0.5517 → **0.6900** | 0.700 → **0.850** |
  | all 40, per repo — itsdangerous | 20 | 0.850 → 0.800 | 0.7558 → **0.7564** | 0.950 → **1.000** |
  | all 40, per repo — flask | 20 | 0.650 → **0.950** | 0.5517 → **0.7646** | 0.700 → **1.000** |

  **Two things in that table a reader should not skip.** itsdangerous's hit@5 **falls**, 0.850 → 0.800, which is the trade the proposal named and the reason the CI gate had to be re-baselined rather than left alone: the file moves out of the top five and into the pool, and recall@20 goes to 1.000 in exchange. And on the dev split itsdangerous's MRR **falls slightly**, 0.6917 → 0.6850, while flask's rises 0.6333 → 0.8000. The gain is real, it is consistent across four question sets, and it is not uniform — it is mostly flask, which is the repository the old default was weakest on.

  **What the adoption check says, run with nothing set.** `scripts/adoption_check.py` builds an index and answers questions through the server's own path — `di.get_embedder`, `di.index_options`, `di.get_retrieval_settings`, `AnswerService.retrieve` — and compares the result against the committed experiment files. It now reports **MATCH on all three splits with no environment variable set at all**, where before this change it only matched with two variables exported. Every one of the fourteen settings it prints reads `default`. That is the whole of what "adopted" means here: the recorded numbers are what a server does when nobody configures it.

  **The CI gate now passes, having been red on this branch since 16cb414.** The workflow's own command exits 0: itsdangerous MRR@10 0.7564 ≥ 0.7564 and recall@20 1.0000 ≥ 1.0000, flask 0.7646 ≥ 0.7646 and 1.0000 ≥ 1.0000. Those four thresholds were recorded in the commit that wrote them, from this configuration, and are unchanged by this one.

  **What it costs.** Measured at 9293366: **+9.0 MB** of process working set with both evaluation repositories indexed and asked about — about +5.5 MB of lexical index and +2.6 MB of extra records — against a cache now capped at four indexes. On disk the index grows **11.6%** for itsdangerous (810.1 → 904.3 KB, 159 → 177 records) and **9.6%** for flask (8,681.0 → 9,516.4 KB, 1,705 → 1,862 records); indexing is not slower, and measured marginally faster both times (itsdangerous 0.30 → 0.27 s, flask 3.26 → 2.82 s), which is noise rather than a finding.

  **Every index already on disk is refused, by design.** The hash embedder now signs itself `hash:384:lowercase=0:subtokens=1|records=structured`. `embedder_mismatch` compares that against what an index stored, so `has_index` says no, the index cache misses, and a repository is reindexed on its next analysis rather than answered from vectors that mean something else. The adoption check drives the guard in both directions and both refuse. On the free Render plan there is no persistent disk, so indexes are wiped on every restart anyway and the practical cost is zero.

  **Why cloudflare structured was not adopted, although it passed the same rule.** The rule fixed at 16464d2 said cloudflare structured replaces cloudflare whole if its holdout3 MRR@10 is higher and its recall@20 is not lower. It was: 0.8042 → **0.8113**, recall@20 unchanged at 0.950. It passes, and it is not adopted. Four reasons, in order:

  1. **The margin is one question wide.** +0.0071 of MRR@10 on a twenty-question set is a single question moving a rank or two. The same entry that recorded it also recorded that two freshly written sets disagree with each other by up to 0.217 of MRR@10 on the same code. The hash margin is +0.1383; this one is twenty times smaller than the noise its own evidence measured.
  2. **Two metrics the rule did not name went backwards.** hit@3 fell 0.900 → 0.850 and hit@5 fell 0.950 → 0.900, and on itsdangerous MRR fell 0.900 → 0.883. The whole of the overall gain is flask. A rule written on two metrics was always able to pass while a third fell; that is what choosing metrics in advance costs, and the alternative — picking the metric after seeing the numbers — is worse. It is a reason to decline a 0.0071 gain, not a reason to rewrite the rule.
  3. **A record format changes every document, and cloudflare's documents are paid for.** Flipping it means re-embedding every repository at about 276 estimated neurons per capped repository, against a 2,500-a-day budget. Hash pays for the same flip in local arithmetic.
  4. **Nothing is running on it.** Render runs `CODEATLAS_EMBEDDING_PROVIDER=hash`. Adopting cloudflare structured would spend a budget and invalidate a paid index, for a margin inside the noise, on a provider no deployment currently selects.

  So cloudflare is **pinned** to whole records with BM25 off rather than merely left at a global default: `CODEATLAS_RECORD_FORMAT` and `CODEATLAS_BM25` no longer move it, because a configuration resting on a 0.0071 margin must not change because someone set a variable meant for the index the server is actually running. `CODEATLAS_CLOUDFLARE_RECORD_FORMAT` and `CODEATLAS_CLOUDFLARE_BM25` move it, and nothing else does.

  **The Benchmarks page, relabelled.** The hash panel now names its configuration — *structured records, BM25 fusion on* — and draws **four** tables instead of two: development and held-out for the default, and *development (legacy)* and *held-out (legacy)* for whole records with BM25 off, each carrying the configuration it was measured under, read out of the result file rather than typed beside it. The legacy tables say in so many words that they are *"the configuration the server ran before the default change"* and *"not the server's current numbers"*; the legacy held-out row still shows hit@5 0.750 and MRR@10 0.645, the pair this file quotes in entry after entry. In the side-by-side block the hash rows are now **the previous default** and **the default**, and the cloudflare rows are **the default** and **candidate, not adopted** — all four computed from `DEFAULT` rather than typed, with one row per embedder marked `is_default` and a test that asserts exactly one is. The holdout3 block keeps its rows exactly as they were scored, because they record a decision that was made, and gains an `adopted` map and a note saying that both candidates passed and only the hash one was taken
- Command: `python scripts/eval_retrieval.py --split {dev,test,all} --json eval/results/{dev,test,all}.json` with nothing set; `python scripts/adoption_check.py --json eval/results/experiments/adoption-hash.json` -> **MATCH**, 30.6 s, every reported setting `default`; `python scripts/build_benchmarks.py` then `--check` -> up to date; the workflow's own gate command (see the entry above) -> exit 0, all four thresholds ok. Then `python -m pytest tests/ -q` -> **1198 passed**, 1 skipped (`tests/test_build_benchmarks.py` gains 8 and changes 1: the hash panel naming its configuration, each table saying what it was measured under and where it came from, the legacy tables saying they are not current, the legacy held-out pair 0.750/0.645 still drawn, the default having moved for hash and not for cloudflare, exactly one default row per embedder in both blocks, the legacy baseline row reading the legacy file, and passing the rule being recorded separately from being adopted; nine tests across `test_cloudflare_provider.py`, `test_fastembed_provider.py`, `test_dual_index.py`, `test_eval_retrieval_script.py`, `test_retrieval_settings.py`, `test_retrieval_settings_from_env.py` and `test_per_index_settings.py` now pin the new default instead of the old one); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (190 files); in `codementor-ui`: `npm test` (**81 passed**, 2 new and 2 changed in `lib/benchmarks.test.ts`), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before), `npm run build`
- Dataset/repo: `eval/questions/*.json`, all 80 questions across four sets, at https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8, from the checkouts in `.codeatlas/eval-repos`. **No provider was called by anything in this entry** — every run is the hash embedder, and the cloudflare figures quoted are the ones recorded at ecf3744 and earlier. **Nothing was re-scored on holdout2 or holdout3**; those rows are the committed experiment files
- Date: 2026-10-12
- Commit: a1c9a35
- Notes: **what the held-out line at the end of every entry means from here on.** It was *"--split test -> overall hit@5 0.750, MRR@10 0.645, unchanged"*. The guard for the default is now **hit@5 0.850, MRR@10 0.7785**, and the old pair is kept, reproducible and drawn, in `eval/results/legacy/`. Setting `CODEATLAS_RECORD_FORMAT=whole` and `CODEATLAS_BM25=false` gets it back exactly; `tests/test_legacy_baseline.py` asserts both the numbers and that those variables really produce that configuration.
  **The `/metrics` gauges moved with the files.** `codeatlas_retrieval_hit_rate{split="test",k="5"}` is 0.750 → 0.850 and `codeatlas_retrieval_mrr{split="test"}` is 0.645 → 0.7785, because `load_eval_results` reads `eval/results/*.json` at startup. It globs the top level only, so the legacy pair in the subfolder does not reach the gauges and cannot be mistaken for a second split.
  **What was deliberately left alone.** `eval/results/fastembed/` and `eval/results/cloudflare/` are untouched: they record provider comparisons made under whole records with BM25 off, and that is what they still say they are. The `sentence` and `fastembed` providers now inherit structured records and BM25, because they follow the global settings and have no measurement of their own either way — stated here rather than hidden, and anyone who wants the old behaviour from them sets the two global variables.
  **Limits, and they are the same ones as before.** Four twenty-question sets, two Python libraries, two pinned commits, file-level retrieval only. No model, no prompt, no citation, and nothing in this entry says a visitor's answer is better — only that the file they need is found more often and ranked higher. The inconsistency recorded at fce9e2a still stands: under `structured` the embedder sees a file's header while the keyword rerank and BM25 read the file's whole text. And the gate's four thresholds have zero margin, so the first change that moves retrieval at all will turn CI red and will have to record new numbers here
### Change: every setting the config reads is documented, and a test keeps it that way
- Value: fifteen of the sixty-eight environment variables `codeatlas/utils/config.py` reads had no line in `.env.example`, so the only way to discover them was to read the loader. All fifteen are now documented with their defaults and a line each. They are, in the order they appear in the file: `CODEATLAS_BM25`, `CODEATLAS_BM25_K1`, `CODEATLAS_BM25_B`, `CODEATLAS_BM25_RRF_K`, `CODEATLAS_BM25_DEPTH`, `CODEATLAS_BM25_MAX_INDEXES`, `CODEATLAS_RECORD_FORMAT`, `CODEATLAS_RECORD_WINDOW_CHARS`, `CODEATLAS_RECORD_WINDOW_OVERLAP`, `CODEATLAS_HASH_RECORD_FORMAT`, `CODEATLAS_HASH_BM25`, `CODEATLAS_CLOUDFLARE_RECORD_FORMAT`, `CODEATLAS_CLOUDFLARE_BM25`, `CODEATLAS_CHAT_MODE` and `CODEATLAS_BENCHMARKS_FILE`.

  **Every one of them is a setting this repository added in the last two batches**, which is the shape of the drift: a variable is added to the loader with a careful comment beside it, and nothing makes the example file follow.

  **The four per-index-kind overrides get the longest note**, because they are the ones a reader is most likely to set wrongly. The hash pair is written empty, which the loader reads as "use the global setting" and which is what a server configured before they existed already does; the comment beneath gives the two lines — `CODEATLAS_HASH_RECORD_FORMAT=whole` and `CODEATLAS_HASH_BM25=false` — that reproduce the legacy baseline. The cloudflare pair is written at its pinned values with the 0.0071-of-MRR@10 margin that is the reason it does not fall back to the globals.

  **The test compares behaviour, not text.** `tests/test_env_example.py` stands in for `os.getenv` while `load_config()` and `load_cloudflare_credentials()` run, collects every name they ask for, and asserts each one appears as a `NAME=` line in `.env.example` — commented or not, because several lines there are examples to set rather than defaults to keep. A regex over the source would have passed on a name built by string concatenation and failed on a docstring that happened to mention one; recording the reads does neither. Two further tests keep the guard honest: one asserts the recorder really sees settings that are read (including one reached through a helper and one credential), and one asserts an undocumented name is reported rather than passed over
- Command: `python -m pytest tests/ -q` -> **1202 passed**, 1 skipped (`tests/test_env_example.py` is new and adds 3); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (191 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; the same command under `$env:CODEATLAS_HASH_RECORD_FORMAT = "whole"` and `$env:CODEATLAS_HASH_BM25 = "false"` -> overall hit@5 **0.750**, MRR@10 **0.645**, the legacy pair, unchanged; in `codementor-ui`: `npm test` (81 passed), `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: none — nothing here is a measurement. The two retrieval runs quoted are the guard, re-run to show the defaults did not move; both are the hash embedder on `eval/questions/{itsdangerous,flask}.json` at the pinned commits. **No provider was called**
- Date: 2026-10-14
- Commit: 81d6c30
- Notes: **no behaviour changed.** `.env.example` is read by nothing at runtime; `load_dotenv()` reads `.env`, which is gitignored. Writing `CODEATLAS_HASH_RECORD_FORMAT=` with an empty value is exactly equivalent to not setting it, because `_optional_record_format` and `_optional_flag` both treat an empty or whitespace string as unset — which is why the hash pair can be shown in the file at its real default rather than only in a comment.
  **What the test does not cover.** Variables read outside `codeatlas/utils/config.py` are not in its scope: `CODEATLAS_ALLOWED_ORIGINS` (read in `app/main.py`), `CODEATLAS_TOKEN_LEDGER` and `CODEATLAS_NEURON_LEDGER` (read by the two ledgers), and `NEXT_PUBLIC_API_URL` (the frontend's). Three of those four are mentioned somewhere — `CODEATLAS_ALLOWED_ORIGINS` has its own line in `.env.example`, `CODEATLAS_NEURON_LEDGER` is named in the cloudflare comment there, and `NEXT_PUBLIC_API_URL` is in the frontend README — but nothing asserts it, and `CODEATLAS_TOKEN_LEDGER` is documented nowhere at all. It is deliberately left that way here: it is a test and script setting, not a deployment one, and inventing a line for it in a file about deploying the server would be the wrong fix. Widening the test to the whole package would mean importing every module and guessing which reads are configuration, which is a different and much less reliable check.
  **It also does not check that a documented default matches the code's.** The file says `CODEATLAS_BM25_K1=1.2` and `bm25.py` says `DEFAULT_K1 = 1.2`, and if one moved the test would still pass. That is a real gap and a harder one to close, because several of these lines are deliberately not the default (`CODEATLAS_API_KEY=` is empty, `CODEATLAS_ALLOWED_ORIGINS` names localhost). Presence is the weaker claim and the one that is actually made
### Feature: CODEATLAS_REASONING_EFFORT, sent only to the two Groq models that document it
- Value: `low`, `medium`, `high`, or unset. **Unset is the default and is not a fourth level**: the parameter is not sent at all, so the request body is exactly the one this app has always built and every figure in this file still describes it. An unrecognised value stops the app starting, for the reason every other retrieval setting does and one more — a typo would otherwise reach the provider inside the request body, and a 400 there reads on the site as every answer being an error.

  **The mechanism, since the question is reasonable.** The Groq client here is `ChatOpenAI` pointed at Groq's OpenAI-compatible endpoint, and the installed langchain-openai is **0.1.22**, which predates the parameter and has no `reasoning_effort` field (`ChatOpenAI.__fields__` does not contain one). The parameter therefore travels in **`model_kwargs`**, that class's own mechanism for a body parameter it does not model: its contents are merged into the request body alongside `model`, `temperature` and `max_tokens`. `reasoning_effort_kwargs` returns a **dict**, not a field assignment, so `**{}` adds nothing at all to the constructor call and "unset" means the key is absent rather than present and empty.

  **Two models, one provider.** Groq documents `reasoning_effort` as supported by `openai/gpt-oss-20b` and `openai/gpt-oss-120b` only, so the model name is checked rather than trusted, and so is the provider: the OpenAI branch builds the same class against OpenAI's own API, where those two names do not exist. **The output token budget is untouched** — `max_tokens` is passed exactly as before, at every level and at none.

  **What the four arms measured.** Eight questions were planned, each under the current chat mode and grounded mode, each with the effort unset and with `low`, one run per arm. Five completed under all four arms before the token cap stopped the run; a sixth (`flask-10`) got one arm and is left out of the summary, because an arm carrying an extra question nobody else answered has a median taken from a different sample.

  | arm | runs | pass | first token, median | first token, range | total, median | calls | tokens | no answer |
  |---|---|---|---|---|---|---|---|---|
  | legacy, unset *(the default)* | 5 | 5/5 | 2.38s | 1.33 – **30.65s** | 2.39s | 10 | 17,492 | 0 |
  | legacy, low | 5 | 5/5 | **1.31s** | 1.21 – 1.79s | 1.33s | 10 | 15,506 | 0 |
  | grounded, unset | 5 | 5/5 | 0.72s | 0.37 – 1.73s | 1.06s | 5 | 8,597 | 0 |
  | grounded, low | 5 | 5/5 | **0.35s** | 0.22 – 0.56s | 0.68s | 5 | 7,632 | 0 |

  **The 30.65s is one run, and it is the first recorded one** — `itsdangerous-1` under legacy with the effort unset, after that arm had already been warmed. Every other legacy-unset run in the set is between 1.33s and 2.52s. It is reported rather than dropped, because dropping the one number that does not fit is how a measurement stops being one, but nothing should be read into the legacy-unset *range* beyond "one run took half a minute and nobody knows why". The medians are what the arms differ on.

  **What the numbers do and do not support.** `low` was faster to the first token in both modes, on every question in the set but one (`itsdangerous-2` under legacy, 1.80s against 1.33s), and spent fewer tokens in both — 11% fewer in legacy, 11% fewer in grounded. That is the direction a lower reasoning effort should move both, and it is five questions. **The pass check saw nothing at all**: 5/5 under all four arms, which is what a weak check does on five easy questions and is not evidence that quality survived. **The check is weak and runs vary a lot** — two string tests per answer, no judge model, nothing that reads whether the explanation is correct; the same legacy path scored 8/15 on one day and 12/15 on another. Five questions at 5/5 cannot distinguish any of the four arms from any other.

  **The default does not move.** Nothing here is a large enough sample to move it, and the point of `unset` sending nothing is that the configuration every recorded measurement describes stays reachable by doing nothing
- Command: `python scripts/reasoning_effort_compare.py --limit 4 --max-session-tokens 60000 --out eval/results/experiments/reasoning-effort.json`. Then `python -m pytest tests/ -q` -> **1250 passed**, 1 skipped (`tests/test_reasoning_effort.py` is new and adds 39; `tests/test_reasoning_effort_compare.py` is new and adds 9); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (194 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (81 passed), `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: the first four questions of each repository in `eval/answer_smoke_questions.json` — `itsdangerous-1..4` and `flask-9..12` — against https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8, indexed once with the hash default. Five of the eight completed under all four arms
- Model: groq / **openai/gpt-oss-20b**, `CODEATLAS_LLM_MAX_TOKENS=2048` unchanged
- Date: 2026-10-14
- Commit: 250f734 (the setting), 2dff8e6 (the measurement)
- Notes: **the token cap was overshot, by me, and the script is fixed so it cannot happen again.** The cap is 60,000 for the session; **65,202 tokens went out**. The four warm-up calls ran *before* the script read the ledger position the cap is measured from, so about 12,000 tokens were spent outside the only thing that stops the run, and the run was stopped by hand once the day's ledger passed 60,000. The script now reads the ledger **before** the warm-ups. No daily-limit 429 was seen at any point; the provider never stated a daily position, so the stop was the local cap and nothing else.
  **The per-arm answer files are missing, and that is the second half of the same mistake.** The script wrote the result file after every run and the answers only at the end, so stopping the run by hand kept all 21 rows and lost every answer text. It now writes both after every run. Reproducing the answers means running the arms again at roughly **53,000 more tokens**, which is over the cap for this session, so it was not done — the command above writes them to `.codeatlas/reasoning-effort-answers/` (gitignored) on any later run.
  **What the comparison is not.** Five questions, one run per arm, one machine, one model, one afternoon. No repeats, so nothing here separates an arm from the variance between two runs of the same arm — and the 30.65s outlier is a direct demonstration that the variance is large. The timings are wall clock against a local server, so they include this machine's load. Both token figures are the ledger's own count of input plus output, which is a lower bound on what the account was billed.
  **What the setting does not do.** It is ignored for every model except the two Groq names above, and on the OpenAI provider, silently rather than by failing — a server that sets it with another model gets the behaviour it had before, not an error. Nothing warns about that, which is a deliberate choice (the alternative is a warning on every boot of a perfectly normal configuration) and a real sharp edge
### Feature: the chat stream names the files it found before the model has said anything
- Value: the wait a visitor sits through on a repository question is mostly the model. Until now the only thing on screen during it was `"Retrieving context..."` — a sentence written **before** the search started, still showing while the search was long finished and the model was thinking. The stream now sends a status event the moment retrieval ends and before the model is asked anything:

  ```
  {"type": "status", "stage": "retrieved", "content": "Found 2 files", "count": 2,
   "files": [{"path": "src/itsdangerous/signer.py", "start_line": 10, "end_line": 42},
             {"path": "src/itsdangerous/timed.py",  "start_line": 1,  "end_line": 30}]}
  ```

  The page draws *Found 2 files*, the file names, and a spinner, and keeps them until the first answer token lands; from then on it renders exactly as it did before.

  **The early list is sent only where it is guaranteed to equal the final one, and that is one mode of three.**

  | path | what it sends early | why |
  |---|---|---|
  | **grounded** | stage, count and every location | `grounded_context` builds the snippets **once**; the event, the prompt and the `done` citations are all read from that one list. A test asserts the early files equal the `done` citations and appear in the prompt, rather than trusting the sentence above |
  | legacy (the default) | the stage name alone | retrieval happens **inside** the agent graph, behind model calls of its own, so at the point this event would go out the citations do not exist yet |
  | deep | the stage name alone | the same, plus a planner ahead of it |
  | general (no repository) | the stage name alone | there is no retrieval to report |

  **So on the shipped default the browser gets a stage name and no file list.** That is the rule working, not a gap in it: a file list the answer then contradicts is worse than a spinner, and the spec this was built to says as much. What it would take to change is in the notes below.

  **Every status event now carries a stable `stage`** — `thinking`, `planning`, `retrieving`, `retrieved`, `answering` — beside its sentence, so the browser keys off a name and the prose stays free to be reworded. An older server that sends no stage still renders its sentence; a test covers that.

  **`count` is distinct files, not locations.** The structured record format can put two windows of one module into the same answer, and counting locations would quietly turn one file into two under a heading that says *files*. The tooltip still carries every line range
- Command: `python -m pytest tests/ -q` -> **1270 passed**, 1 skipped (`tests/test_early_status_event.py` is new and adds 20); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (195 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (**91 passed**, `lib/streamStatus.test.ts` is new and adds 10), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: none — nothing here is a measurement. Every test uses a fake model over a real two-file index built in a temporary directory. **No provider was called**
- Date: 2026-10-14
- Commit: 36ae774
- Notes: **no question text goes into the event, and a test enforces it.** A status event is written into a response body, which is something a proxy or an access log may keep, and the question is the visitor's. A marker planted in the question is asserted to reach no status event, and `retrieved_event` is asserted to emit nothing per file but `path`, `start_line` and `end_line`. Nothing in the logging changed, because nothing in it ever carried the question: the only two lines that mention one say *"Answering question for repo %s"* and name the exception type.
  **What still works, tested after the early event has already gone out.** The quota refusal (both kinds), the truncation note, the empty-reply sentence and the semantic-fallback note all behave exactly as before; the fallback note is the same retrieval call the event is built from. The unknown-repository **404 still happens before the stream opens**, so it comes before any event at all — asserted as "the response carries no events", because the failure to guard against is a 200 with a status event and an error inside it.
  **What it would take to give the default path its file list.** Legacy's citations come from `AnswerService.answer` inside `_retrieve`, and that call summarises the snippets through the model, so there is no point in that path that is both after retrieval and before a model call. Two ways out, neither taken here: hand the controller's model-free `AnswerService` the search first and pass the result into the orchestrator, which removes a model call from the default path and so changes `agents_used`, the token spend and the metrics; or search twice, once for the event and once in the graph, which is honest only while nothing can change the index between the two. Both are behaviour changes to the default and belong in their own entry with their own measurement.
  **One thing found while reading that path and deliberately left alone.** In fast mode `handle_question_fast` uses `retrieved.snippets`, `retrieved.citations` and `retrieved.note` and **never reads `retrieved.answer`** — which is the text the retrieval agent spent a model call producing. On the fifteen-question comparison recorded at 2a66017 legacy made 30 model calls to grounded's 15, and this is one of the two. Removing it would cut roughly a third of the default path's tokens, and it would change the default, the metrics and `agents_used`, so it is recorded here rather than done
### Fix: Prometheus is out of its own graphs, two axes read the right scale, semantic search is drawn
- Value: three fixes to `ops/grafana/dashboards/`. **Grafana was not started**; the JSON was edited and the tests read it, which is also all the earlier dashboard work ever did.

  **1. `/metrics` is out of the three panels it dominated.** Prometheus scrapes this app every 15 s whether anyone is using it or not — `scrape_interval: 15s` in `ops/prometheus.yml` — and the request middleware counts that scrape like any other request, under `path="/metrics"`. That is **0.067 req/s of requests nobody made**, running all day.

  | panel | was | now |
  |---|---|---|
  | Requests per second by route | `sum by (path) (rate(codeatlas_request_total[5m]))` | the same with `{path!="/metrics"}` |
  | Response start latency p95 by route | `histogram_quantile(0.95, sum by (le, path) (rate(codeatlas_request_latency_seconds_bucket[5m])))` | the same with `{path!="/metrics"}` |
  | Responses by status | `sum by (status) (rate(codeatlas_request_total[5m]))` | the same with `{path!="/metrics"}` |

  On a site with no visitors the first was a flat line at 0.067 labelled `/metrics` and nothing else, the third was *every* 200 on the dashboard, and the second drew a latency line for the one route whose behaviour tells a reader nothing. **The errors panel is deliberately not filtered**: a 5xx on `/metrics` is a real failure, and there is a test saying so, so that nobody tidies it later.

  The filter is a **negative match**, not a list of the routes that count. A list would silently drop every route added after it was written, and a test asserts the expression names no route positively.

  **2. Two panels read 60 times too small.** `rate()` is per second. *Agent runs per minute* and *Model calls per minute, by agent* computed a per-second rate, titled themselves *per minute*, and set the axis unit to `reqps`, which Grafana renders as **req/s**. So a reader saw `0.05 req/s` under a heading promising per-minute and had no way to know which of the three to believe. Both now multiply by 60 and use `cpm` (counts/min), so the title, the query and the axis agree. `reqps` was wrong twice over on these: an agent run is not a request.

  **The other two panels on that dashboard with the same defect are untouched** — *Agent failures per minute, by reason* and *Planner routes per minute* both compute a per-second rate under a per-minute title with a `reqps` axis. They were not in the scope of this change and are recorded here rather than quietly fixed or quietly left; they are a one-line change each when someone wants them.

  **3. A "Semantic search" row, from metrics that were already being recorded.** Three counters have been written by the app since the cloudflare provider landed and have never appeared on a dashboard: `codeatlas_semantic_index_total` (attempts by outcome), `codeatlas_semantic_index_estimated_neurons_total` (the running estimate the budget guard reads), and `codeatlas_retrieval_fallback_total` (questions the hash index answered instead, by reason). **No new metric was added**, and a test asserts each panel's metric is one the app defines.

  All three are per minute with a `cpm` axis, matching fix 2 rather than repeating the mistake. **On a server running the hash default all three are empty**, which is not a bug: it is the answer to "is semantic search on here", and each panel's description says so
- Command: `python -m pytest tests/ -q` -> **1282 passed**, 1 skipped (`tests/test_metrics.py` gains 11 and rewrites 1, `tests/test_agent_metrics.py` gains 1); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (195 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (91 passed), `npm run lint` (0 errors, 28 warnings, the same ones as before). Both files were re-parsed as JSON after editing
- Dataset/repo: none. The 0.067 req/s is `1 / 15 s` from `ops/prometheus.yml`; the `path="/metrics"` label was confirmed by scraping a test client and reading the sample back, not assumed
- Date: 2026-10-14
- Commit: 76246ed
- Notes: **nothing here was seen rendered.** Grafana was not started, which was the instruction, so every claim about how a panel *looks* is read off the JSON and off Grafana's unit names rather than off a screen. `cpm` is Grafana's "counts/min" and `reqps` its "requests/sec"; if a Grafana version renders either differently the panels will be wrong in a way no test here can catch.
  **The dashboards are provisioned read-only** (`"editable": false` on `codementor.json`), so these files are the dashboard rather than a starting point someone has since edited in the browser — which is what makes a test over the JSON worth anything.
  **The existing test now walks nested panels.** It read `dashboard["panels"]` flat, which was correct while there were no rows; a panel inside a collapsed row would have been skipped and its query never checked. `_panels` descends one level, which is as deep as Grafana nests.
  **What is still not checked.** Nothing validates the PromQL — a query that names real metrics and is nonsense passes every test here. Nothing checks that a panel's `datasource` uid matches the provisioned one. And nothing asserts a panel is *reachable*: the semantic row is `"collapsed": false`, and if someone collapses it the panels keep their queries and simply stop being visible
### Change: the evaluation page opens with five numbers, and everything else is behind one closed panel
- Value: the Benchmarks section opened with the full retrieval tables for two providers across four splits, then the structural tables, then the system facts, then the stage timings, then a **twenty-row** Experiments table with three held-out comparisons and a chat-mode block inside it, then the limitations. Every number on it was true, carried its provenance, and nobody was ever going to read it.

  **What is now at the top**, in a block called *At a glance*:

  | | holdout2 (20 q) | | holdout3 (20 q) | |
  |---|---|---|---|---|
  | | **MRR@10** | **hit@5** | **MRR@10** | **hit@5** |
  | **hash — the default** — structured records, BM25 fusion on | 0.576 | 0.750 | 0.690 | 0.800 |
  | **cloudflare — opt-in** — whole records, no fusion | 0.587 | 0.800 | 0.804 | 0.950 |

  plus **precision 1.000 / recall 0.967** over 49 questions against Python's `ast`, the model-free chat timing — **45 ms** warm on itsdangerous, 19 ms of it the rerank — labelled *"excludes the language model"*, and one line: *"Recorded results on small fixed question sets, not live accuracy."*

  **Three choices in that block worth stating.**

  1. **holdout2 and holdout3, not the original held-out split.** Those two were written after the configurations were chosen and scored once each; the first was reused run after run and flatters everything on it. It is still on the page, in the tables below, where the panel that draws it says what it is.
  2. **Only the configuration each embedder actually runs.** The experiments table has twenty rows, four of them scored and rejected. A rejected row beside an adopted one with no verdict between them is how a summary misleads, so the block takes the row the builder marked `is_default` — which is *chosen* for hash and *baseline* for cloudflare, because cloudflare's candidate passed its rule and was not adopted.
  3. **The wording matches the defaults as they are now**: hash *structured records, BM25 fusion on*; cloudflare *whole records, no fusion*. Both strings are in the builder beside the `DEFAULT` map they describe.

  **Everything else is inside one `Details` disclosure, closed by default** — the retrieval tables, the structural tables, the system facts, the stage timings, the Experiments table with its held-out comparisons and chat-mode block, and the limitations. It is a **native `<details>` element**, not React state: it is closed on first paint with no hydration step, the browser's own find-in-page opens it to reach a number inside, and it needs no JavaScript at all. A test asserts there is no `open` attribute and no `useState` in it, because both would quietly undo all three.

  **The headline cannot disagree with the tables it summarises.** `build()` builds the structural, timing and experiments blocks once and hands them to `headline()`, which reads no result file of its own. A test asserts that by reading the function's source for `_read(` and for each builder's name; six more compare every headline figure against the block of the same build it came from.

  **The session telemetry above the section is untouched** — queries, latency, citations, agent utilisation, indexed repositories and recent queries are exactly as they were
- Command: `python scripts/build_benchmarks.py` then `--check` -> up to date; `python -m pytest tests/ -q` -> **1290 passed**, 1 skipped (`tests/test_build_benchmarks.py` gains 8); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (195 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (**106 passed**, `lib/benchmarks.test.ts` gains 15), `npx tsc --noEmit`, `npm run lint` (0 errors, 28 warnings, the same ones as before), `npm run build`
- Dataset/repo: no new measurement. Every figure is the committed `eval/benchmarks.json`, which is built from `eval/results/`; the holdout2 and holdout3 numbers are the ones scored once at ecf3744 and 16464d2 and re-drawn here, not re-run. **No provider was called**
- Date: 2026-10-14
- Commit: a1167bd
- Notes: **the page was not opened in a browser.** `npm run build` succeeds and `npx tsc --noEmit` is clean, and the tests cover the view model and read the component's source, but nothing here has seen it rendered — so every claim about how it *looks*, including that it reads well on a phone, rests on the markup rather than on a screenshot. What is actually asserted about the phone case is structural: the block is a grid of figures rather than a table, so it has no `min-w-[640px]` and nothing to scroll sideways, and every long string is `break-words`. The tables inside `Details` keep their horizontal scrollers, which is what they had before.
  **The headline duplicates numbers that are also in the tables below it**, by design, and the tests are what keep the two the same. If someone adds a figure to the headline by hand rather than deriving it, nothing in `test_build_benchmarks.py` will catch it — the guard is that `headline()` has no way to read a file, not that every field is cross-checked.
  **One thing a reader of the headline can still get wrong.** Cloudflare's numbers are higher than hash's on both sets, and the block says cloudflare is *opt-in* without saying why it was not adopted. That reasoning — a 0.0071 margin on a twenty-question set, two metrics the rule did not name going backwards, and a paid re-index — is in the holdout3 block inside `Details`, which is closed. The headline names the default and marks it; it does not argue for it
### Change: the chat timing line says what the question cost, not only how long it took
- Value: chat latency rises as one session asks more questions, and the timing line could not say why. It carried stage durations and nothing else, so four different causes — the prompt growing with history, the follow-up rewrite making an extra model call, the provider making the request wait, and the model simply thinking for longer — all looked identical from outside: a larger `llm` number.

  **Five fields, one per candidate.**

  | field | what it is | which candidate it separates |
  |---|---|---|
  | `history_turns` | earlier turns put into the prompt | the prompt growing with history |
  | `rewrite_ran` | 0 or 1: did the follow-up rewrite call the model | the extra model call |
  | `in_tokens`, `in_tokens_each` | input tokens the provider reported, totalled and per call | a prompt that is growing, seen growing |
  | `llm_each` | how long **each** model call took, not their sum | which of two calls was the slow one |
  | `retry_wait` | the provider client's own 429 backoff, as a stage | a wait the provider imposed |

  `out_tokens` is recorded as well. It comes out of the same already-parsed usage object as `in_tokens` at no extra cost, and without it a call that was slow cannot be told from a call that wrote a long answer — which is the one distinction the other five fields cannot make.

  **`retry_wait` is the field that did not exist anywhere.** The OpenAI-compatible client retries a 429 itself and `time.sleep`s inside the call, so from the application's side the wait is invisible: it only makes the model call look slow. The client logs `Retrying request to %s in %f seconds` at INFO immediately before each sleep, and a `logging.Handler` on the `openai` logger reads the number of seconds out of that line and adds it to whichever request's timer is current. **Only the number**: not the URL logged beside it, not the request being retried. It is recorded as a stage, so it also reaches the existing `codeatlas_stage_duration_seconds` histogram with no new metric defined. It is *inside* the model call, so `llm` already contains it — both are reported and a reader subtracts.

  **No metric was added and none changed.** `observe_stages` is still fed from the stage totals alone, so counts and facts cannot reach Prometheus as if they were seconds.

  **`as_dict()` is no longer all durations**, which forced one correction: `server_timing()` now builds from a new `durations()` method rather than from `as_dict()`. A Server-Timing header's `dur` is milliseconds by definition, so `in_tokens;dur=1800` would have been read by the browser as 1.8 seconds.

  **Grounded mode gained the `llm` stage it never had.** Its one model call is pulled on a worker thread, which had no timer in its context, so a grounded question's line had an embed, a search and a rerank and no model call at all. The stream is now pulled under `run_timed` — which is also what lets the usage callback and the retry handler find a timer — and the call is timed around the loop. Side effect, stated rather than hidden: the grounded path now always makes one executor hop for `_search_question` instead of only when a rewrite is needed. That function is a regular-expression test over the question when no rewrite is due.

  **The rewrite decision moved into one function.** `needs_rewrite` plus `rewrite_question` appeared in three places — grounded, deep and the legacy fast path. `rewrite_ran` would have had to be recorded in all three, so instead `_search_question` does both and all three call it. The fact is written on **both** branches: a line with no `rewrite_ran` at all would be indistinguishable from a line written before the field existed

  **Nothing new can carry text.** Every field added is a duration, a token count the provider reported, or a count of turns. The existing assertions that no question text reaches the timings or the log line are untouched and still pass
- Command: `python -m pytest tests/ -q` -> **1296 passed**, 1 skipped (was 1290; `tests/test_timing.py` gains 5, `tests/test_grounded_chat.py` gains 1); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (195 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (106 passed), `npx tsc --noEmit` (clean), `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: none. **No provider was called** — the retry handler is tested by logging the client's own line, args and all, through `openai._base_client` and reading the stage back
- Date: 2026-10-14
- Commit: 924b90e
- Notes: **the retry handler depends on a log line in someone else's library.** `openai==1.109.1` logs that sentence at two places in `_base_client.py`; a future version that reworded it, logged it below INFO or moved it off a logger under `openai` would make `retry_wait` silently always absent, and no test here would fail — the test logs the line itself rather than provoking a real retry. Absence of the field is therefore weak evidence that no retry happened.
  **`retry_wait` is attributed to whichever request's timer is current on the sleeping thread**, which is the right one for a chat question because the model call happens under `run_timed`. A provider call made outside any request would have its backoff counted nowhere, which is the intended behaviour and not a loss.
  **`in_tokens` is absent, not zero, when the provider reports nothing.** The two are kept distinguishable deliberately, but it means the number of entries in `in_tokens_each` need not equal `llm_calls`.
  **Nothing here measures anything yet.** This change only makes the measurement possible; what the fields actually say about a real session is the next entry
### Fix: the last two per-minute panels on the agents dashboard count per minute
- Value: `rate()` is per second. **Agent failures per minute, by reason** and **Planner routes per minute** each computed a per-second rate, titled themselves *per minute*, and set the axis unit to `reqps`, which Grafana renders as **req/s** — three claims about one number, with nothing to tell a reader which to believe.

  | panel | was | now |
  |---|---|---|
  | Agent failures per minute, by reason | `sum by (agent, reason) (rate(codeatlas_agent_failures_total[5m]))`, unit `reqps` | the same `* 60`, unit `cpm` |
  | Planner routes per minute | `sum by (route) (rate(codeatlas_planner_routes_total[5m]))`, unit `reqps` | the same `* 60`, unit `cpm` |

  `cpm` is Grafana's counts/min. `reqps` was wrong twice over on both: an agent failure is not a request, and neither is a planner route.

  **These are exactly the two panels 76246ed recorded as left with the same defect** and chose not to fix. *Agent runs per minute* was fixed there; it already multiplies by 60 and already reads `cpm`, and it is **untouched** here — it was named in the request for this change, but there was nothing left wrong with it, so the second panel of the pair is the one the earlier entry listed beside *Planner routes*.

  **The test that named panels by hand is gone.** It asserted the rule for two titles, which is why two more panels could carry the same defect for as long as they did. In its place is one test over **every** panel whose title says *per minute*: all five must multiply by 60, and none may use a per-second axis unit (`reqps`, `pps`, `cps`, `wps`, `iops`, `rps`, `ops`). A panel added later with this mistake now fails a test rather than being found by somebody reading a graph.

  A second test keeps the four **counting** panels on `cpm` specifically, and says in its own docstring why *Tokens per minute, by agent* is not one of them: tokens are counted per minute too, and that panel already multiplied by 60, but `cpm` would label its axis counts/min and a token is not a count of something that happened. `short` stays.

  **The test that every panel names a metric the app defines is unchanged**, as is every other panel on either dashboard
- Command: `python -m pytest tests/ -q` -> **1312 passed**, 1 skipped (`tests/test_agent_metrics.py` loses 1 test and gains 2); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (197 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (106 passed), `npx tsc --noEmit` (clean), `npm run lint` (0 errors, 28 warnings, the same ones as before). The file was re-parsed as JSON after editing and every panel's unit and expression printed back
- Dataset/repo: none. No provider was called
- Date: 2026-10-14
- Commit: 6feab58
- Notes: **Grafana was not started**, which was the instruction. Every claim here about how a panel reads is taken from the JSON and from Grafana's unit names, not from a screen; if a Grafana version renders `cpm` differently these panels are wrong in a way no test here can catch.
  **The new test's strength is its weakness.** It keys off the words "per minute" in a panel title, so a panel that computes a per-second rate and simply does not say "per minute" anywhere passes it. What it does guarantee is that the title cannot lie.
  **The unit list is a denylist.** `PER_SECOND_UNITS` holds the seven Grafana per-second ids worth guarding against; a per-second unit outside that list would pass. An allowlist was the alternative and would have had to be revised for every new panel
### Check: what a chat session actually spends, question by question, in both chat modes
- Value: the first run of `scripts/chat_latency_probe.py`. One session per mode against a real local server, the same eight questions in the same order, model `openai/gpt-oss-20b` on Groq, hash embeddings, itsdangerous. **The session token cap stopped both runs before question 8**, so the measurement is five questions in the default mode and six in grounded.

  **The committed default mode (legacy), five questions**

  | q | turns | rewrite | model calls | in | out | llm ms | per call ms | total ms |
  |---|---|---|---|---|---|---|---|---|
  | 1 | 0 | no | 2 | 2,882 | 1,520 | 2,843 | 1,863 / 980 | 2,994 |
  | 2 | 1 | no | 2 | 3,143 | 1,816 | 2,589 | 1,821 / 768 | 2,632 |
  | 3 | 2 | **yes** | 2 | 2,869 | 2,442 | 3,286 | 1,473 / 1,813 | 4,212 |
  | 4 | 3 | **yes** | 2 | 4,820 | 2,597 | 3,310 | 2,558 / 752 | 3,864 |
  | 5 | 4 | no | 2 | 3,465 | 1,373 | 2,528 | 1,384 / 1,144 | 2,553 |

  **Grounded mode, six questions**

  | q | turns | rewrite | model calls | in | out | llm ms | first token ms | total ms |
  |---|---|---|---|---|---|---|---|---|
  | 1 | 0 | no | 1 | 1,420 | 226 | 626 | 805 | 878 |
  | 2 | 1 | no | 1 | 1,553 | 130 | 568 | 555 | 613 |
  | 3 | 2 | **yes** | 1 | 1,481 | 946 | 2,079 | 1,005 | 2,512 |
  | 4 | 3 | **yes** | 1 | 2,895 | 1,158 | 1,606 | 1,526 | 2,334 |
  | 5 | 2 | no | 1 | 2,608 | 589 | 1,224 | 936 | 1,273 |
  | 6 | 2 | **yes** | 1 | 3,393 | 632 | 1,135 | 1,014 | 1,635 |

  **The premise did not reproduce. Latency did not rise with position in the session.** Legacy went 2,994 -> 2,632 -> 4,212 -> 3,864 -> 2,553 ms; the *last* question was the fastest. Grounded rose from under a second to 1.2-2.5 s, but its two cheapest questions are also the two that wrote the shortest answers (226 and 130 output tokens against 589-1,158 later). In both modes `llm` tracks **output length**, which is a property of the question, not of how many came before it.

  **Candidate 1, history growing the prompt: real, measured, and bounded.** The legacy path gives a controlled comparison for free, because each question makes two model calls over *the same snippets* - the retrieval summary, which is given no history, and the mentor, which is given all of it:

  | turns | retrieval call in | mentor call in | difference |
  |---|---|---|---|
  | 0 | 1,385 | 1,497 | 112 |
  | 1 | 1,465 | 1,678 | 213 |
  | 2 | 1,115 | 1,427 | 312 |
  | 3 | 1,439 | 2,399 | 960 |
  | 4 | 1,203 | 2,262 | 1,059 |

  The 112 at zero turns is the two prompt templates differing; above it the history costs about **950 tokens by the fourth turn**, close to the 1,500-token budget `chat_history_tokens` sets. It **cannot keep growing**: `chat_history_turns` is 4 and the store drops the oldest turns that do not fit, which the grounded run shows directly - `history_turns` went 0, 1, 2, 3, **2, 2**, falling as answers got longer. And the retrieval call's input is flat across the whole run (1,385 / 1,465 / 1,115 / 1,439 / 1,203) while the mentor's climbs, so the growth is history and not the snippets. The matching latency effect is **not visible**: the mentor call took 980, 768, 1,813, 752 and 1,144 ms as its prompt grew by a thousand tokens.

  **Candidate 2, the rewrite call: real, and the only field that marks the slow questions.** It ran on exactly the questions written to lean on the one before them. In legacy it cost 859 ms and 520 ms and 1,632 tokens over the run (**6.1%** of the session); in grounded, 392, 673 and 443 ms. The two legacy questions it ran on are the two slowest. It does not explain all of the gap - take the rewrite stage off and q3 and q4 are still 3,353 and 3,344 ms against 2,553-2,994 for the rest - but it is the only one of the five fields that moves with them.

  **Candidate 3, the per-minute limit: not seen, and this run cannot price it.** `retry_wait` is absent on all eleven questions and both server logs contain **zero** `Retrying request` lines. That is what the pacer was for: it held the trailing-60-second window under 8,000 tokens by waiting about 60 s between legacy questions. A visitor asking three questions in a minute would meet the limit this run was built to avoid, so **no retries happening here is not evidence that the limit does not cause them.**

  **Candidate 4, memory pressure: no support, and weakly measured.** The local stages do not grow: `embed_query` 0.1-0.4 ms, `rerank` 8-23 ms, `search` 0.5-0.8 ms after the first question. The one place a later question is *faster* than an earlier one is `search`, 122 ms (legacy) and 207 ms (grounded) on question 1 and under a millisecond thereafter - the BM25 index being built once and then reused. That is the opposite of the reported effect. **Nothing here samples process memory**, so this is an argument from "the work that would get slower did not", not a measurement of RSS.

  **The two modes, side by side.** Legacy spent **26,927 tokens over 12 model calls** for five questions; grounded spent **17,031 over 9 calls** for six. Per question that is 5,385 against 2,839, and a median total of 2,994 ms against 1,454 ms
- Command: in one shell, `$env:CODEATLAS_CHAT_MODE = "legacy"; $env:CODEATLAS_EMBEDDING_PROVIDER = "hash"; $env:CODEATLAS_LLM_PROVIDER = "groq"; python -m uvicorn codeatlas.app.main:app --host 127.0.0.1 --port 8000`, then in another `python scripts/chat_latency_probe.py --base-url http://127.0.0.1:8000 -n 8 --token-cap 24000 --tpm-limit 8000`; the server restarted with `CODEATLAS_CHAT_MODE = "grounded"` and the probe re-run with `--token-cap 13073` (what was left of the 40,000). Mode in both tables is read off `agents_used`, not off the command line
- Dataset/repo: pallets/itsdangerous, re-analysed by the probe at the start of each run; eight fixed questions, four of which lean on the turn before them. Model `openai/gpt-oss-20b` (Groq), `CODEATLAS_LLM_MAX_TOKENS` at its default 2048, hash embeddings with the committed defaults. **No Cloudflare call was made** - the embedding provider was pinned to hash for both servers
- Date: 2026-10-14
- Commit: 598bc15 (the probe); nothing in the repository changed to take this measurement
- Notes: **the 40,000-token cap was exceeded, by 3,958 tokens (9.9%).** The ledger went from 65,202 to 109,160 across the two runs: **43,958 tokens over 21 model calls**. The guard is a pre-flight check - it asks whether the session has spent less than the cap and then asks a question whose cost is only known once it has been paid - so it bounds the spend *before* the last question, not after it. Legacy stopped at 26,927 against 24,000 and grounded at 17,031 against 13,073. This is a defect in the guard as committed, not a surprise from the provider, and it is fixed in the next entry.
  **Five questions and six questions, not eight.** Both runs stopped cleanly on the cap, which is the guard working. It does mean the legacy table never gets past the fourth turn of history, which is exactly where `chat_history_turns` caps it anyway.
  **`llm_calls` does not count the rewrite**, which has its own stage; so a legacy row reading 2 calls with `rewrite` present was three calls to the provider. `in_tokens_each` does show all three, which is why the retrieval-versus-mentor table above can be built at all.
  **The attribution of the two legacy calls rests on their order**, retrieval before mentor in `handle_question_fast`, confirmed independently by prompt size: the retrieval prompt built offline for one of these questions is 5,622 characters and the mentor's 6,110, and the first and second `in_tokens_each` entries sit on the same side of that gap on every question.
  **One run of one session per mode.** The model is non-deterministic and output length drives most of the variation, so none of these timings should be read to three figures; what is solid is the direction of `in_tokens` per call, the presence and cost of the rewrite, and the absence of retries
### Fix: the probe's token cap reserves the next question, so it is a cap and not a tripwire
- Value: the guard asked whether the session had spent less than the cap and then asked a question whose cost is only known once it has been paid. So it bounded the spend *before* the last question and not after it, and the first run overran: **43,958 tokens under a cap of 40,000**, by 3,958 (9.9%), as 26,927 against 24,000 in the legacy run and 17,031 against 13,073 in the grounded one.

  `budget_guard` now takes a `reserve` -- what the next question is expected to cost -- and allows the run to continue only while `spent + reserve` still fits. The estimate is the pacer's own: **the most expensive question so far**, which is the only figure available that cannot be optimistic about what has already happened. Before the first question there is nothing to go on, so the pacer's standing figure of 5,000 stands in, which means a cap below 5,000 now refuses to start rather than overrunning it.

  Being at the cap exactly still stops the run. The reserve is an **additional** condition, `spent < cap and spent + reserve <= cap`, not a replacement: without the first half a guard called with no reserve would let a session that had spent exactly its cap ask one more question.

  The stop line now carries the reserve, so a run that stopped with budget left over says why it did
- Command: `python -m pytest tests/ -q` -> **1313 passed**, 1 skipped (`tests/test_chat_latency_probe.py` gains 1); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (197 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (106 passed), `npx tsc --noEmit` (clean), `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: none. **No provider was called** and the measurement in the previous entry was not re-run: the 43,958 figure there is what the old guard allowed, and re-running under the new one would cost another session's tokens to demonstrate arithmetic a test already covers
- Date: 2026-10-14
- Commit: adadcf2
- Notes: **the cap is still not a hard ceiling in the strict sense**, and cannot be with this design. It now holds whenever a question costs no more than the most expensive one before it; a question that costs far more than any of its predecessors can still cross the line, by the amount it exceeds that estimate. A true ceiling would need the provider to price a request before running it, or a budget enforced provider-side.
  **The reserve makes the run end earlier and spend less than the cap allows.** That is the intended trade: the previous entry's run would have stopped a question sooner in each mode and recorded four and five questions instead of five and six.
  **The ledger is the only thing counted against**, so a model call this machine made outside the probe -- another server, a test that bypassed the temp-file fixture -- lands in the same day's file. The baseline subtraction handles spend from *before* the run; it cannot handle spend from *during* it
### Check: the model call the default chat path spends on nothing, priced and traced (read-only)
- Value: 36ae774 recorded in passing that `handle_question_fast` never reads `retrieved.answer` and guessed the cost at "roughly a third of the default path's tokens". **Measured, it is 48.5%.** Nothing in the repository was changed by this entry.

  **Where the call is made.** `codeatlas/services/qa/answer_service.py:366-367` -- `chain.invoke({"question": ..., "context": render_snippets(snippets)})` inside `_format_answer`, reached from `AnswerService.answer` at `:341`. The model is there because `di.py:284` builds the orchestrator's `AnswerService` with `llm=get_llm_provider().get_chat_model()`; with `llm=None` the same method returns a list of file locations instead (`:361-362`), which is what grounded mode's service does.

  **What it receives.** The template at `answer_service.py:152-161`: a one-line system prompt (*"You are a senior engineer. Use provided code snippets to answer. Cite file paths and line ranges from the snippets."*) and a human message of the question followed by every retrieved snippet. For *"How does Signer create a signature?"* against itsdangerous, built offline with no model call, that prompt is **5,622 characters**. It is given **no conversation history** -- which is what made the history measurement in the previous entry possible.

  **Where its output goes.** Into `GroundedAnswer.answer` (`answer_service.py:346-352`), bound to `retrieved` at `orchestration.py:155`. The rest of `handle_question_fast` reads `retrieved.citations` (`:156`), `retrieved.snippets` (`:163`, `:170`) and `retrieved.note` (`:181`). **`retrieved.answer` is never read**, and the local goes out of scope when the function returns at `:172`.

  **Does anything downstream read it?** No. Two places in the whole repository read `GroundedAnswer.answer`, and neither is on this path: `orchestration.py:335`, the deep-mode `_retrieval_node`, which renders it into the step transcript; and `retrieval_agent.py:32`, the text `Agent.run` contract used by the planned graph and by `handle_generation`. Checked at runtime as well as by reading: with a fake model answering the first call with a sentinel string, the sentinel appears in **neither** the streamed answer, nor anywhere in the `done` event, nor in the mentor's prompt, while the second call's sentinel is the answer verbatim.

  **The prompts of the final answer call, with and without it.** Built offline from the real index for one question, no model call made:

  | | with the retrieval summary call | without it |
  |---|---|---|
  | system | the mentor's, unchanged | identical |
  | human | `Code snippets:` + five numbered snippets + `Question: ...` | identical |
  | characters | 6,110 | 6,110 |

  **They are byte-identical**, because `handle_question_fast` passes the mentor `retrieved.snippets` and never the summary. The summary is not an input to anything; removing the call removes a 5,622-character prompt and deletes its reply unread.

  **What removing it would change**, from the eleven-question run in the entry before last:

  | | now | without the call |
  |---|---|---|
  | model calls per question | 2 (3 with a rewrite) | 1 (2 with a rewrite) |
  | tokens, 5-question session | 26,927 | 13,857 -- **48.5% less** |
  | model time, same session | 14,556 ms | 5,457 ms -- **62.5% less** |
  | share of total request time | -- | the call was **56%** of all time spent in those five requests |
  | `agents_used` | `["retrieval", "mentor"]` | **unchanged** |
  | citations | from the snippets | **unchanged** |
  | the final prompt | 6,110 chars | **unchanged** |
  | answer content | the mentor's | same prompt, so same distribution; not bit-identical, because the model is not deterministic |

  Per-call figures, from `in_tokens_each`, `out_tokens_each` and `llm_each`:

  | q | wasted in | wasted out | wasted ms | mentor in | mentor out | mentor ms |
  |---|---|---|---|---|---|---|
  | 1 | 1,385 | 1,190 | 1,863 | 1,497 | 330 | 980 |
  | 2 | 1,465 | 1,485 | 1,821 | 1,678 | 331 | 768 |
  | 3 | 1,115 | 953 | 1,473 | 1,427 | 1,369 | 1,813 |
  | 4 | 1,439 | **2,048** | 2,558 | 2,399 | 346 | 752 |
  | 5 | 1,203 | 787 | 1,384 | 2,262 | 586 | 1,144 |

  On question 4 the discarded reply used **exactly 2,048 output tokens** -- the whole of `CODEATLAS_LLM_MAX_TOKENS` -- and was then thrown away.

  **Metrics that would move**: `codeatlas_agent_model_calls_total{agent="retrieval"}` would fall to zero; `codeatlas_agent_tokens_total{agent="retrieval", ...}` likewise; `codeatlas_stage_duration_seconds{endpoint="ask_stream", stage="model"}` would roughly halve; `codeatlas_agent_failures_total{agent="retrieval", reason="fallback_to_location_list"}` and the quota reasons recorded at `answer_service.py:375-377` would stop being reachable from this path. The on-disk token ledger would count about half as much per question. In the timing line, `llm_calls` and `llm_each` would disappear from a question with no rewrite, because one call needs no per-call list.

  **`agents_used` would not change**, which corrects the note at 36ae774. `agents_ran.append("retrieval")` happens at `orchestration.py:154`, before the call, and retrieval would still run -- it would still embed the query, search, fuse and rerank. It is the *summarising* that is spent on nothing, not the retrieval. The claim in that note belongs to the other option it describes, moving the search out of the graph into the controller, which would stop retrieval being an agent that ran.

  **Tests that would need changing**, four assertions in two files: `tests/test_timing.py:170` and `:218` (`llm_calls == 2`), `tests/test_conversation_memory.py:231` (the same), and `tests/test_conversation_memory.py:225`, which checks that the rewritten question reached the search by looking for it in the retrieval summary's prompt -- with no such prompt it would need another anchor. `tests/test_agents_used.py:63` and `:126` assert `["retrieval", "mentor"]` and would still pass.

  **The early file list would not change today**, and would become possible tomorrow. `retrieved_event` (`grounded_chat.py:135`) is sent only by the grounded path (`ask_controller.py:277` onward); the legacy path sends the bare stage name at `ask_controller.py:201`. Removing this call does not add the event. What it removes is the reason 36ae774 gave for legacy not having one -- "there is no point in that path that is both after retrieval and before a model call" -- because with the summary gone, that point is exactly where `_retrieve` returns, about 1.8 s earlier than the first token.

  **One thing removal would improve that is not on the list**: it halves the tokens a question puts into the provider's per-minute window, which makes the 8,000-token-per-minute limit roughly half as likely to bite -- candidate 3 of the latency diagnosis
- Command: read-only. The prompts were built with a scratch script that constructs `AnswerService(..., llm=None)` over the index already on disk and renders both templates with `format_messages`; the sentinel check ran the real `/ask/stream` against a two-file temporary index with `FakeListChatModel`. The per-call figures are the `in_tokens_each`, `out_tokens_each` and `llm_each` fields of the five `timing ask_stream` lines from the legacy run recorded two entries above. **Nothing in the repository was changed, and no provider was called**
- Dataset/repo: pallets/itsdangerous for the prompts; the five-question legacy session of 2026-10-14 for the token and timing figures
- Date: 2026-10-14
- Commit: none -- this entry changes no code
- Notes: **the 48.5% and 62.5% are one session of five questions**, and the discarded reply's length is the model's choice, so they will not hold to the decimal on another run. What does not depend on the sample is that the reply is read by nothing and that the final prompt does not contain it.
  **"Same distribution, not identical answers."** The mentor's prompt is unchanged, so nothing about what it is asked changes; but the two calls share a per-minute budget, so removing the first one also changes *when* the second is served, and the model is sampled at the configured temperature either way.
  **One behaviour would genuinely be lost.** `_format_answer` catches a provider refusal and turns it into the quota sentence with the locations beneath it (`answer_service.py:369-383`). On this path that handler is redundant -- the mentor has its own at `orchestration.py:164-170` -- but it is also the only thing that records `fallback_to_location_list` for the retrieval agent, so that metric would go quiet rather than go to zero for a good reason.
  **This entry does not recommend the removal.** It prices it. The change touches the default chat path, four test assertions and five metric series, and belongs in its own entry with its own before-and-after measurement
### Change: the default chat path no longer summarises a search nobody reads
- Value: the entry two above priced this call at **48.5% of a session's tokens and 62.5% of its model time**, traced its output to a local that fell out of scope, and showed the mentor's prompt is byte-identical without it. It is now gone from the default path.

  **What was removed.** `handle_question_fast` searched through `RetrievalAgent.retrieve`, which called `AnswerService.answer`, which asked the model to write a prose summary of the snippets it had found. The result went into `GroundedAnswer.answer`; the function then used `.citations`, `.snippets` and `.note` and returned. On one measured question the discarded reply used **the whole 2,048-token output budget**.

  **How.** `AnswerService.locate()` is `answer()` without that call -- the same search, snippets, citations and fallback note. Both now run through one `_grounded(..., summarise: bool)`, so they cannot drift. `locate`'s `answer` field holds the locations, which is **exactly what `answer()` returns when no model is attached to the service at all**; a test asserts those two strings are equal. `RetrievalAgent` grows the matching `locate`, and `_retrieve` asks for it when the caller does not want prose.

  **`handle_question_fast` split into `search()` and `answer_from()`**, with the old method calling both, so a streaming caller can send what the search found while the model is still writing. That is what the next entry uses.

  **The three readers of the summary text, all unchanged:**

  | reader | why it still wants the summary |
  |---|---|
  | `orchestration.py:_retrieval_node` (deep mode) | renders it into the step transcript a later agent reads |
  | `retrieval_agent.py:run` (the text `Agent` contract) | used by `handle_generation` and by a planned retrieval step |
  | `AnswerService.answer` itself | including the location-list fallback and the quota sentence it builds when the provider refuses |

  **What did not change:** `agents_used` is still `["retrieval", "mentor"]` -- retrieval still runs, still searches, still gets its `agent_run` timing and its `codeatlas_agent_runs_total` increment. Citations, snippets, the semantic-fallback note, the quota behaviour and the answer's prompt are all identical. An agent with no `locate` falls back to `retrieve`, so a stand-in implementing only the older method keeps working rather than quietly returning nothing.

  **The four assertions that had to move, and what each now means:**

  | where | was | now means |
  |---|---|---|
  | `test_timing.py` chat stages | `llm_calls == 2` | `llm_calls` **absent** -- one call per question, so no stage ran twice and `llm` is that call |
  | `test_timing.py` follow-up | `llm_calls == 2` | still absent: the rewrite is its own stage, so a follow-up is two calls under two names, not one name twice |
  | `test_conversation_memory.py` | `llm_calls == 2` | the same, for the three-calls-to-two case recorded earlier |
  | `test_conversation_memory.py` | the rewrite appears in the summary's prompt | that prompt no longer exists, so it reads the server's own reasoning step, **and** asserts no prompt carries the summary template at all |

  **Metric expectations.** `codeatlas_agent_model_calls_total{agent="retrieval"}` and `codeatlas_agent_tokens_total{agent="retrieval", ...}` no longer move on this path. `codeatlas_stage_duration_seconds{endpoint="ask_stream", stage="model"}` falls to one call's worth. `codeatlas_agent_failures_total{agent="retrieval", reason="fallback_to_location_list"}` is no longer reachable from the default path -- it still is from deep mode and from `answer()`, and `tests/test_agent_metrics.py` still covers that through `AnswerService.answer` directly. `codeatlas_agent_runs_total{agent="retrieval"}` and `codeatlas_agent_duration_seconds{agent="retrieval"}` are **unchanged**, which is the point: the agent ran.

  **Proved two ways.** `tests/test_retrieval_summary_removed.py` runs the default path twice with the same snippets and a different summary -- the second telling the model to ignore the snippets and look in a file that does not exist -- and asserts the mentor's prompt is byte-identical, then asserts that prompt in full. And a recording fake model counts the calls: **one per question, two with a rewrite, none carrying the summary template**
- Command: `python -m pytest tests/ -q` -> **1323 passed**, 1 skipped (was 1313; `tests/test_retrieval_summary_removed.py` is new and adds 10); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (198 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (106 passed), `npx tsc --noEmit` (clean), `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: none -- every test here uses a fake model over a real two-file index in a temporary directory. **No provider was called**
- Date: 2026-10-14
- Commit: 794fc3c
- Notes: **the identical call is still made in one place off this path, and is left alone.** `CodingMentorAgent.run` calls `self._answer_service.answer(...)` and then reads only `retrieved.snippets` -- the same waste, the same shape. It is the mentor's text `Agent` contract, reached from `handle_generation` and from a planned step, not from the default chat path, and changing it would move an admin endpoint's model-call count that nothing here measures. Recorded rather than quietly fixed or quietly left.
  **`locate`'s `answer` field is not empty, and that is a choice.** Filling it with the locations keeps every reader of `GroundedAnswer` working and makes the field mean the same thing it means with no model configured. An empty string would have been a second way for a reader to be surprised.
  **The duck-typing fallback hides a mistake.** `_retrieve` falls back from `locate` to `retrieve`, so an agent that forgets `locate` silently goes on paying for the summary rather than failing. The alternative -- requiring `locate` -- would break any stand-in written against the older contract, and several tests use one. The real `RetrievalAgent` has both, and the call-counting test is what would catch a regression
### Feature: the default chat mode names the files it found, before the model is asked
- Value: 36ae774 gave the early file list to grounded mode and said plainly why the default mode could not have one: *"there is no point in that path that is both after retrieval and before a model call"*, because the path summarised its own search through the model first. The previous entry removed that call. The point now exists, and the event goes out there.

  **The rule is unchanged, and is what decides this.** The early list is sent only where it is **guaranteed** to equal the final citation list. On this path it is, by construction rather than by argument: the controller holds the `GroundedAnswer` that `AgentOrchestrator.search` returned, sends `retrieved.snippets` as the event, and the `done` event's citations are `retrieved.citations` -- the same object, built from the same list, by the same search. A test asserts the two are equal.

  | path | what it sends early | why |
  |---|---|---|
  | grounded | stage, count and every location | `grounded_context` builds the snippets once; event, prompt and citations all read from that list |
  | **default (legacy)** | **the same** | `search` returns one `GroundedAnswer`; the controller sends its snippets and returns its citations |
  | deep | the stage name alone | retrieval happens inside the graph, behind a planner and whatever steps it chooses; at this point the citations do not exist |
  | general (no repository) | the stage name alone | there is no retrieval to report |

  **`retrieved_event` now takes the snippet list, not a `GroundedContext`.** It only ever read `.snippets`, and taking the list puts the promise where it belongs: a caller may send this event only while holding the list the citations are built from. The docstring says which two callers are, and why.

  **Order on the default path** is now `retrieving` -> `retrieved` -> `answering` -> tokens -> `done`, asserted as a list rather than as a set of pairwise comparisons.

  **The 404 for an unknown repository still comes before any event.** The guard runs before the stream opens, so an unknown repository is a real 404 and not a 200 with an error inside it. Asserted on this path as *the response carries no events at all*, plus the model was never asked -- an event added earlier in the path is exactly the kind of change that could have moved it.

  **No question text goes into the event**, asserted here as it was for grounded: a marker planted in the question reaches no status event, and each file entry carries `path`, `start_line` and `end_line` and nothing else.

  **No frontend change.** `codementor-ui/lib/streamStatus.ts` already renders this event and already said it arrives "only on a path where the server can promise they are the citations" -- which is still true, now of two paths instead of one
- Command: `python -m pytest tests/ -q` -> **1328 passed**, 1 skipped (was 1323; `tests/test_early_status_event.py` gains 6 and rewrites 1, and its `retrieved_event` unit tests take a list now); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (198 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (106 passed), `npx tsc --noEmit` (clean), `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: none. Every test uses a fake model over the real two-file index the grounded tests build in a temporary directory. **No provider was called**
- Date: 2026-10-14
- Commit: 9690592
- Notes: **the page was not opened in a browser.** The event is asserted at the endpoint and the renderer was already tested, but nothing here has seen the default mode draw a file list on a screen.
  **A defect found on this path and deliberately left.** `_answer_from` rebuilds the result without `note`, so the semantic-fallback sentence has never reached the browser in the default mode -- it predates this split, which only moved the code around it. It is visible only under the cloudflare provider, which the default is not, and fixing it is a behaviour change with its own before-and-after. There is a comment at the drop saying so.
  **Three orchestrator stand-ins in the tests had to learn `search` and `answer_from`**, because the controller now calls those. `handle_question_fast` remains the combined entry point and is still tested; it is no longer called from the controller, so a stand-in that implements only it would silently never be exercised by an endpoint test.
  **What is still not checked**: that the early list equals the citations is asserted per path, not enforced by a type. A third path could send the event while holding a different list, and only a test of that path would catch it
### Check: the default mode after the discarded call was removed, against the recorded figures
- Value: four questions, one session, local server, committed defaults (legacy chat mode, hash embeddings, `openai/gpt-oss-20b` on Groq, `CODEATLAS_LLM_MAX_TOKENS` 2048), paced under the per-minute limit, hard cap 12,000 tokens. **All four completed with 2,282 of the cap left.** The *was* columns are the first four questions of the five-question run recorded earlier today, which asked the same questions in the same order in one session.

  | q | calls | was | tokens | was | first token ms | was | total ms | was |
  |---|---|---|---|---|---|---|---|---|
  | 1 | 1 | 2 | 1,741 | 4,402 | 1,703 | 3,749 | 964 | 2,994 |
  | 2 | 1 | 2 | 1,907 | 4,959 | 1,138 | 2,628 | 1,154 | 2,632 |
  | 3 | **2** | 3 | 2,731 | 5,311 | 1,539 | 4,194 | 1,550 | 4,212 |
  | 4 | **2** | 3 | 3,339 | 7,417 | 1,421 | 3,855 | 1,428 | 3,864 |
  | **all** | **6** | **10** | **9,718** | **22,089** | | | **5,095** | **13,702** |

  `calls` counts every call to the provider, so the rewrite on questions 3 and 4 is in it. **The ledger agrees**: 6 calls, not 10.

  | | was | now | |
  |---|---|---|---|
  | provider calls | 10 | 6 | |
  | tokens | 22,089 | 9,718 | **-56.0%** |
  | input tokens | 13,714 | 7,703 | -43.8% |
  | output tokens | 8,375 | 2,015 | -75.9% |
  | time in the model | 12,028 ms | 3,609 ms | **-70.0%** |
  | time in the request | 13,702 ms | 5,095 ms | -62.8% |

  **The prediction was 11,009 tokens** -- the earlier run's per-call figures with the retrieval summary's share struck out. The actual is 9,718, **11.7% below it**, because answer length is the model's choice and it wrote shorter answers this time. The input side is the sounder half of the comparison: the removed call's prompt was the snippets, about 1,400 tokens every question, and input fell 43.8%.

  **The early file list lands long before the first token**, computed from the stage durations as `rewrite + embed_query + search + rerank`:

  | q | file list at | first token at |
  |---|---|---|
  | 1 | 210 ms | 953 ms |
  | 2 | 13 ms | 1,133 ms |
  | 3 | 440 ms | 1,530 ms |
  | 4 | 731 ms | 1,413 ms |

  Question 1's 210 ms is the BM25 index being built once; thereafter the search is under a millisecond and the wait is the follow-up rewrite where there is one. **The first token itself did not get earlier relative to the answer** -- this path still assembles the whole answer and then types it out four words at a time, so `first token ms` and `total ms` stay within about 20 ms of each other. What arrives early is the file list, not the answer.

  **Every line carries one model call.** `llm_calls` is absent from all four timing lines, and `in_tokens_each` appears only on questions 3 and 4, with two entries - the rewrite and the mentor. **No retries**: `retry_wait` is absent on all four and the server log holds zero `Retrying request` lines
- Command: in one shell `$env:CODEATLAS_CHAT_MODE = "legacy"; $env:CODEATLAS_EMBEDDING_PROVIDER = "hash"; $env:CODEATLAS_LLM_PROVIDER = "groq"; python -m uvicorn codeatlas.app.main:app --host 127.0.0.1 --port 8000`, in another `python scripts/chat_latency_probe.py --base-url http://127.0.0.1:8000 -n 4 --token-cap 12000 --tpm-limit 8000`. Mode read off `agents_used`, which said `legacy` on every row
- Dataset/repo: pallets/itsdangerous, re-analysed by the probe; the first four of the probe's eight fixed questions, two of which lean on the turn before them. **No Cloudflare call** - the embedding provider was pinned to hash
- Date: 2026-10-14
- Commit: 9690592 (the state measured); nothing changed to take the measurement
- Notes: **this is not a controlled comparison, and the output column is where that shows.** Output fell 75.9%, and only part of that is the removed call: its replies were about 4,800 of the earlier run's 8,375 output tokens, and the rest is the mentor writing shorter answers this time. Nothing here pins answer length, so the headline 56% is one run against one run.
  **The two runs were not simultaneous.** Both were on 2026-10-14 against the same provider and model, but a quieter provider would read as a win and a busier one as a regression, and nothing separates that from the change.
  **One session, four questions, no repeats and no error bars.** The earlier run reached five; the cap allowed four here because the cap was 12,000 rather than 24,000.
  **History is not comparable turn for turn** with the earlier run: the answers differ, so what the history occupies in the prompt differs. `history_turns` ran 0, 1, 2, 3 in both.
  **The per-minute limit is still unpriced.** Halving the tokens per question should make an 8,000-per-minute limit bite about half as often, and this run cannot show that, because the pacer again held the window under it - which is why there were no retries to count.
  **Nothing here looked at a browser.** That the file list arrives at 13-731 ms is read off the server's own stage durations; whether a visitor notices it is not measured
### Fix: the keyword-search note reaches the browser in the default chat mode
- Value: **this retracts a caveat recorded at 9690592.** That entry noted that `_answer_from` rebuilds its result without `note`, called it a defect that predated the split, and left it. It is fixed here. The old entry is not edited; this one supersedes it.

  **What was wrong.** `_answer_from` builds a new `AnswerResult` to add the conversation notes to `reasoning_steps`, and listed four of the five fields. `note` was the fifth, so `retrieval_note` in the `done` event was **always empty** in the default mode. Grounded mode and deep mode were never affected: neither rebuilds the result.

  **Why it matters here and not in a test.** When the semantic index cannot answer - the day's allowance is gone, the provider is in a cooldown, the API did not respond, or this repository has no semantic index - the question is answered from the hash index instead and the answer looks exactly like any other. One sentence distinguishes them. **The live server runs the cloudflare provider**, which is the only provider that can fall back at all, so the default mode is precisely where the sentence was needed and precisely where it was lost.

  **The fix is one field.** The comment describing the drop is gone.

  **The test gap this sat in.** The note was already tested at `AnswerService.retrieve_with_note`, and the endpoint was already tested with an index that cannot fail. Nothing covered the stretch between them, which is where it went missing. `tests/test_fallback_note.py` covers it: a real dual index over a real file, fake embedders, the semantic half unavailable in each documented way, and the note read out of the JSON the browser receives.

  | what | how many |
  |---|---|
  | every reason (`api`, `budget`, `cap`, `circuit`, `unindexed`) x three paths (default, grounded, deep) | 15 |
  | no note when the semantic index answered, on each path | 3 |
  | the reason's private detail and the provider's name reach neither | 5 |
  | a follow-up whose rewrite call runs before the search, with and without a fallback | 2 |
  | no question text in a fallback answer's event; default and deep agree | 2 |

  **Confirmed to bite.** With the field removed again, **13 of the 27 fail**, and they are the default-mode ones; grounded and deep keep passing, which is the right shape for a defect only one path had.

  **The exact `done` event, same question, same repository, two cases.** Fallback, with reason `budget`:

  ```json
  {"type": "done",
   "agents_used": ["retrieval", "mentor"],
   "citations": ["<tmp>/mod.py (lines 1-2) | def sign(value):     return value"],
   "reasoning_steps": ["Fast mode: retrieval + mentor (skipped the planner).",
                       "Retrieved 1 code snippet(s), cited as 1 citation(s).",
                       "Agents that ran: retrieval -> mentor."],
   "retrieval_note": "Today's semantic search allowance is used up, so this answer used keyword search.",
   "timings_ms": {"embed_query": 0.4, "embed_query_calls": 2, "embed_query_each": [0.0, 0.4],
                  "first_token_sent": 35.5, "history_turns": 0, "llm": 19.5, "rerank": 0.5,
                  "rewrite_ran": 0, "search": 8.9, "total": 49.5}}
  ```

  And the ordinary case, where the semantic index answered:

  ```json
  {"type": "done",
   "agents_used": ["retrieval", "mentor"],
   "citations": ["<tmp>/mod.py (lines 1-2) | def sign(value):     return value"],
   "reasoning_steps": ["Fast mode: retrieval + mentor (skipped the planner).",
                       "Retrieved 1 code snippet(s), cited as 1 citation(s).",
                       "Agents that ran: retrieval -> mentor."],
   "retrieval_note": "",
   "timings_ms": {"embed_query": 0.0, "first_token_sent": 8.6, "history_turns": 0,
                  "llm": 2.8, "rerank": 0.9, "rewrite_ran": 0, "search": 0.4, "total": 30.5}}
  ```

  **The two differ in `retrieval_note` and in one timing**: `embed_query_calls: 2`. The fallback case embeds the question twice - once with the embedder that then declared itself unavailable, once with the hash embedder that answered - so the repeat count is independent evidence that the fallback really happened, recorded without anyone having added a field for it.

  **No question text appears in either**, which is the reason they can be printed here at all
- Command: `python -m pytest tests/ -q` -> **1355 passed**, 1 skipped (was 1328; `tests/test_fallback_note.py` is new and adds 27); `python -m pytest tests/test_fallback_note.py -q` with `note=result.note` removed again -> **13 failed, 14 passed**; `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (199 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (106 passed), `npx tsc --noEmit` (clean), `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: none. Both embedders are fakes, the model is a fake, and the index is one file in a temporary directory. **No provider was called** - no Groq, no Cloudflare
- Date: 2026-10-14
- Commit: 54dcea1
- Notes: **`cap` is reachable in these tests but not from the search path today.** `REASONS` carries five keys; `retrieve_with_note` produces `budget`, `circuit` and `api` from an embedder that raises, and `unindexed` from there being no usable semantic index - including a repository over the document cap, which `_choose` reports as `unindexed` rather than as `cap`. The `cap` case here is driven by an embedder raising it, so what is proved is that *if* an embedder reports `cap`, its sentence reaches the browser. `cap` and `unindexed` share the same sentence, so a visitor could not tell them apart either way.
  **The citations in the printed events carry an absolute temporary path.** `_clean_display_path` strips only a `.codeatlas/repos/<uuid>/` prefix, and the test index is not under one. That is a property of the fixture, not of the server.
  **Nothing here was seen in a browser.** `codementor-ui` already renders `retrieval_note` and its tests are unchanged; what is asserted is that the field arrives populated, not that the page shows it.
  **The deeper shape is still unguarded.** The defect was a field-by-field rebuild that forgot one field, and nothing stops the next one. `dataclasses.replace` would have been immune, and is the obvious follow-up; it is not done here because this entry is the fix and its test, and changing how the result is rebuilt is a separate change
### Fix: the answer result is copied, so a field cannot be dropped by forgetting to name it
- Value: **this closes the follow-up the entry at 54dcea1 left open.** That entry fixed the dropped `note` by naming the fifth field, and said so plainly: "the defect was a field-by-field rebuild that forgot one field, and nothing stops the next one. `dataclasses.replace` would have been immune, and is the obvious follow-up". This is that follow-up. The earlier entries are not edited.

  **The change is one return statement.** `_answer_from` built a fresh result to add this conversation's notes to `reasoning_steps`:

  ```python
  return type(result)(
      answer=result.answer,
      citations=result.citations,
      reasoning_steps=steps,
      agents_used=result.agents_used,
      note=result.note,
  )
  ```

  and now copies it instead:

  ```python
  return replace(result, reasoning_steps=steps)
  ```

  `replace` is already this repository's idiom for the same job -- `app/di.py` and `services/eval/arrangements.py` both use it on `AppConfig` -- so nothing new is introduced. `AnswerResult` is a frozen dataclass, which is what makes the copy exact and what made the rebuild necessary in the first place.

  **Where else this type is rebuilt: nowhere.** The grep, run after the change:

  ```
  > git grep -n "type(result)(\|type(res" -- "*.py"
  (no matches)
  > git grep -n "AnswerResult(" -- "*.py"
  codeatlas/services/agents/orchestration.py:133:        return AnswerResult(
  codeatlas/services/agents/orchestration.py:189:        return AnswerResult(
  tests/test_result_fields_carried.py:59:    return AnswerResult(**MARKERS)
  tests/test_unknown_repo.py:50:        return AnswerResult(answer="ok", citations=[], reasoning_steps=[])
  tests/test_unknown_repo.py:54:        return AnswerResult(answer="ok", citations=[], reasoning_steps=[])
  tests/test_unknown_repo.py:64:        return AnswerResult(answer="ok", citations=[], reasoning_steps=[])
  ```

  The two in `orchestration.py` are **original constructions, not rebuilds**: line 133 builds the result from the graph's final state (`_result_from`) and line 189 from the fast path's own retrieval and mentor output (`answer_from`). Neither is handed an existing result and asked to reproduce it, so neither can lose a field by omission -- the omission would be a missing value, not a dropped one, and the dataclass's defaults are the specification for that. The three in `test_unknown_repo.py` are stubs. `type(result)(` was the only rebuild in the repository, and it is gone.

  **The test is about the shape, not about `note`.** `tests/test_result_fields_carried.py` names no field in its assertions. It enumerates `dataclasses.fields(AnswerResult)`, gives each a distinctive non-empty marker, drives the default path through `/ask/stream` with a fake orchestrator whose `search` and `answer_from` carry those markers, and checks each field arrived -- four of them in the `done` event, `answer` in the `token` events that preceded it. Every marker is non-empty on purpose: a field marked with its own default (`note=""`) is one a drop cannot be seen through, which is how the last one went missing.

  **It also fails for a field that does not exist yet.** `test_every_field_of_the_result_type_is_accounted_for` asserts the declared fields, the markers and the done-event keys are the same set, so a sixth field added to `AnswerResult` with no decision made about where the browser receives it fails before any of the behavioural tests run.

  **Confirmed to bite, both ways.**

  | what was put back | result of `pytest tests/test_result_fields_carried.py -q` |
  |---|---|
  | the field-by-field rebuild, with `note=` left off | **4 failed, 3 passed** |
  | a sixth field `sixth: str = ""` on `AnswerResult` | **1 failed** (the enumeration test, run alone) |

  The four are `test_no_field_is_lost_between_the_search_and_the_done_event`, `test_the_done_event_carries_no_field_under_its_own_name_by_accident`, `test_the_controller_changes_reasoning_steps_and_copies_the_rest` and `test_every_other_field_is_identical_to_what_the_orchestrator_returned`. Both experiments were reverted before the commit.

  **One test fake had to change with it.** `_Result` in `tests/test_grounded_chat.py` was a plain class with five attributes, which `replace` cannot copy. It is now a frozen dataclass with the same five fields in the same order, which is also what the controller's contract actually says the orchestrator returns -- the fake was looser than the thing it stood in for
- Command: `python -m pytest tests/ -q` -> **1362 passed**, 1 skipped (was 1355; `tests/test_result_fields_carried.py` is new and adds 7); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (200 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (106 passed), `npx tsc --noEmit` (clean), `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: none. The repository under test is three files written into a temporary directory by `tests/test_analyze_indexing.py`'s fake loader, the orchestrator is a stub and no model is built -- the provider handed to the app raises if asked for one. **No provider was called** - no Groq, no Cloudflare
- Date: 2026-10-15
- Commit: e201644
- Notes: **this is a guard, not a measurement.** Nothing here was timed, nothing was spent, and no behaviour changed for any question that was already answered correctly: with every field present, `replace` and the five-field rebuild produce equal objects. The value is entirely in what the next change cannot do.
  **The guard covers one path.** `_answer_from` is the default mode's; grounded mode and deep mode never rebuilt their results and are untouched, so the enumeration test exercises the default path only. A future rebuild introduced on either of the other two paths would not be caught by this file.
  **`AnswerResult` is the only result type guarded.** `GroundedAnswer`, `GenerateResult` and the explain result have no equivalent test. `GroundedAnswer` is the nearer risk: it is constructed in four places in `codeatlas/`, and `codeatlas/services/agents/orchestration.py:396` builds an empty one on a retrieval failure without naming `note` -- which is correct there, since a search that failed has nothing to report, but it is the same construction shape.
  **Nothing here was seen in a browser.** What is asserted is the content of the SSE events; `codementor-ui` is unchanged and its tests are unchanged
### Canary: a real 429, from a local server, must still reach `retry_wait`
- Value: **`retry_wait` is read out of another library's log line, and nothing was watching whether that line still exists.** `codeatlas/observability/timing.py` attaches a handler to the `openai` logger and reads the number of seconds out of `Retrying request to %s in %f seconds`, which the OpenAI-compatible client logs just before it sleeps through a 429. The sleep happens *inside* the model call, so without this there is nothing to see: the call is simply slow.

  **That line is a log message in a dependency, not an API.** It can be reworded, moved to another logger or dropped in a patch release. If it is, `retry_wait` becomes zero on every request for ever, and the only symptom is a model call that looks slow for no reason -- which is the question `retry_wait` exists to answer.

  **The two tests that already covered it could not catch this.** `tests/test_timing.py` logs the line *itself*:

  ```python
  sdk_logger.info("Retrying request to %s in %f seconds", "/chat/completions", 8.0)
  ```

  so what it proves is that the handler matches a string this repository wrote down. It would keep passing, unchanged and green, on a machine where the installed client had stopped emitting anything of the sort. The gap is not in the handler; it is that nothing compared the handler against the library.

  **So the new test drives the real client.** `tests/test_retry_wait_canary.py` starts a `ThreadingHTTPServer` on 127.0.0.1 on a port the OS picks, answers the first `POST /v1/chat/completions` with `429` and `Retry-After: 1` and the second with an ordinary completion body, and points the app's own client at it by setting `OPENAI_API_BASE` -- the variable the installed `langchain-openai` reads, which `LlmProvider` leaves alone. The model is built by `LlmProvider(...).get_chat_model()`, so it is the shipped path with the endpoint moved, not a client assembled in the test with different arguments. The retry is a real socket, the sleep is a real second, and the line being matched is the line the installed version logged.

  **The client honours `Retry-After` exactly** when it is between 0 and 60 -- `_calculate_retry_timeout` returns the header's value and skips its own jittered backoff -- so the figure is deterministic rather than approximate. Versions: `openai 1.109.1`, `langchain-openai 0.1.22`.

  **What was recorded, for one call:**

  | | |
  |---|---|
  | requests the local server received | `['/v1/chat/completions', '/v1/chat/completions']` |
  | the line the client logged | `openai._base_client` INFO `Retrying request to /chat/completions in 1.000000 seconds` |
  | `retry_wait` in the timings | `1000.0` |

  `llm >= retry_wait` is asserted too: the wait is inside the model call, which is why it has to be recorded separately to be visible at all.

  **Confirmed to bite, for each way the coupling can break.** Both experiments change the watcher's half of the coupling, which fails in exactly the way the library's half changing would:

  | what was changed in `_RetryWaitHandler` / `watch_provider_retries` | result of `pytest tests/test_retry_wait_canary.py -q` |
  |---|---|
  | the matched phrase, to `Retrying the request` (a reword upstream) | **4 failed, 2 passed** |
  | the watched logger, to `openai_client` (a moved logger upstream) | **5 failed, 1 passed** |

  Both were reverted before the commit; `git diff` on `codeatlas/observability/timing.py` is empty and no file outside `tests/` changed in this commit.

  The moved-logger case fails one test more than the reword, and the extra one is informative: `watch_provider_retries` is also what raises the provider logger to INFO. Point it at the wrong name and the record is never emitted at all, so the test that asserts on the client's real record has no record to assert on.

  **Two of the six say what a failure would mean** rather than only detecting it. They take the line the client really logged -- `record.getMessage()`, never a string written here -- and break it the ways a dependency can: a different verb, one extra word, a shortened unit, the number removed, and the same text under `openai_client._base_client`, `httpx` and `langchain_openai.chat_models.base`. None records a wait. The same line under `openai._base_client` still does, so the loop proves the logger name and not something incidental about running the line a second time.

  **No key, no network, nothing from the environment printed.** The key is the fixed string `canary-not-a-real-key`, present only because the client refuses to be constructed without one; the tests carry `@pytest.mark.builds_model_client`, the suite's existing opt-in for constructing a provider client. `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` and their lowercase spellings are cleared and `NO_PROXY` is set to `127.0.0.1,localhost`, so nothing can be routed off the machine. The assertion on the timing line never holds a value: it splits the line into `name=value` fields and calls `float()` on each value, which rules out any text at all -- the client's line names the URL it is retrying, and that must not cross over
- Command: `python -m pytest tests/ -q` -> **1368 passed**, 1 skipped (was 1362; `tests/test_retry_wait_canary.py` is new and adds 6); `python -m pytest tests/test_retry_wait_canary.py -q` -> 6 passed in 8.3s; the two experiments above; `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (201 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (106 passed), `npx tsc --noEmit` (clean), `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: none. The provider is a `ThreadingHTTPServer` in the test process answering two requests. **No provider was called** - no Groq, no Cloudflare, and nothing left 127.0.0.1
- Date: 2026-10-15
- Commit: 8416a02
- Notes: **this costs about a second of wall clock on every run.** `Retry-After: 1` is the smallest value that is both a plausible header and honoured exactly, and three of the six tests make the call, so the file takes about 8 seconds. `retry-after-ms` would make it instant and is read by this client version, but it is a vendor header rather than the standard one, and a canary that stops exercising the standard path to run faster is worth less than the second it saves.
  **It pins one client, on one machine.** What it proves is that *the installed* `openai` logs what the watcher reads. A different version in CI or in the image is a different answer, and this test is the thing that would say so -- which is the intent, but it does mean an upgrade can turn it red without anything in this repository having changed. That is a true report, not a flake.
  **The groq branch is not what is exercised.** `LlmProvider._build` hard-codes Groq's base URL, so it cannot be pointed at a local server without changing shipped code. The test uses the `openai` branch, which reads `OPENAI_API_BASE`. Both branches construct the same `ChatOpenAI` over the same `openai` client, and the retry and its log line live in that client, so the coupling under test is shared -- but the literal branch exercised is the openai one.
  **Nothing here measures how often retries actually happen.** Every recorded run of `chat_latency_probe.py` so far has had the pacer hold the window under the provider's limit, so `retry_wait` was 0 in all of them. This is the first time the field has been seen non-zero end to end, and it was made to happen rather than observed.
  **`watch_provider_retries` leaves its handler on the global `openai` logger** for the rest of the session, as it already did for `tests/test_timing.py`. The tests here add and remove their own recording handler, but the watcher's own is not removed, so the order tests run in could in principle matter. It did not: the file passes alone and in the full suite
### New: a blind comparison harness, so a person can score answers without knowing the arm
- Value: **nothing in this repository measures whether an answer is correct, and this does not either -- it lets a person do it without being told which setting wrote what.** `scripts/answer_smoke.py` asks two string questions per answer, is the expected file cited and does one hand-written word appear, and says in its own docstring that it does not measure quality. Every recorded comparison since has carried the same caveat: *"a difference of one or two passes between arms is not a finding"*. A person can judge an explanation. A person who knows which arm produced it is not judging the explanation.

  **Two modes with a person in between.**

  ```
  python scripts/blind_compare.py run --repo itsdangerous --limit 5
  # read sheet.md, fill in sheet.csv
  python scripts/blind_compare.py score --run-id default
  ```

  **An arm is a set of environment overrides**, the same variables a server would be started with. Only `CODEATLAS_CHAT_MODE` and `CODEATLAS_REASONING_EFFORT` are accepted, and anything else is refused by name rather than ignored -- *an override that is not applied is worse than one that is rejected*, because two arms that differ only in a setting nobody applies are one arm, and the run would report a dead heat it had never measured. The three default arms:

  | arm | overrides |
  |---|---|
  | `legacy` | `CODEATLAS_CHAT_MODE=legacy` |
  | `grounded` | `CODEATLAS_CHAT_MODE=grounded` |
  | `grounded-low` | `CODEATLAS_CHAT_MODE=grounded CODEATLAS_REASONING_EFFORT=low` |

  Each override is validated through the shipped validator -- `validate_chat_mode`, `validate_reasoning_effort` -- so an arm cannot describe a server that would refuse to start.

  **One real local uvicorn server per distinct chat mode, asked over a real socket**, as `chat_latency_probe` does and for the same reason: an in-process client hides the event loop, the executor and the connection. Two arms differing only in reasoning effort share a server, because that setting is fixed when the model client is built, not per request; the model is swapped per question through `reasoning_effort_compare.swap_model`, imported rather than written again.

  **The masking.** Per question, the arms are shuffled into A, B and C by `random.Random` seeded from `sha256(f"{seed}:{question_id}")` -- hashed with `hashlib` rather than by seeding `Random` with the string itself, so the order does not depend on how a Python version happens to hash one. **The seed is mixed with the question id**, so A is a different arm from one question to the next: a grader who worked out that A was always the same arm would have stopped being blind after the first look. Over 400 question ids the six orders of three arms came out 73/71/66/65/64/61, which is the flat distribution it should be.

  **The key is a different file in a different folder**, and no arm name appears in anything the grader opens:

  ```
  .codeatlas/blind-compare/<run-id>/
    raw/runs.json     every answer, with its arm, its cited files and its timings
    raw/key.json      which arm each of A, B, C is, per question
    sheet/sheet.md    the answers to read, under their labels
    sheet/sheet.csv   question_id, question, label, cited_files, correctness, cited_support, note
    summary.json      written by `score`
  ```

  **The scoring sheet is a CSV because a person fills it in.** Two columns of 0 to 2 -- correctness (*0 wrong or evasive, 1 partly right, 2 right*) and cited_support (*0 the cited files do not support it, 1 partly, 2 they do*) -- and a free-text note. The cited files are on the sheet itself, since one of the two scores is about them; the answers are in `sheet.md`, so scoring means reading the answer rather than a preview.

  **`score` prints the averages, the wins and the warning.** A question is won by the arm with the highest total of the two scores; **a draw at the top is a tie and is counted as one, not shared out**. Only questions scored under every arm count at all. The real output, from a hand-filled sheet over two questions:

  ```
  arm                  n  correctness_mean cited_support_mean  total_mean  wins
  legacy               2               1.5                1.5         3.0     1
  grounded             2               1.5                2.0         3.5     0
  grounded-low         2               1.0                1.5         2.5     0

  ties (no single highest total): 1
  ```

  That example is worth keeping for what it shows: **the arm with the best average won nothing.** `grounded` leads on `total_mean` and has zero wins, because its one strong question was a tie. Two summaries of the same six scores disagree about which arm is ahead, which is the whole reason the note below is printed every time.

  **The note is not optional and not a footnote.** `score` always prints, with the real n substituted:

  > *N question(s) scored by one person. A sample this size cannot separate small differences between arms: a gap of a few tenths of a point, or one or two wins, is what the same arms would produce twice in a row by chance. Treat anything short of a clear, repeated gap as no result, and read the notes rather than the averages.*

  It is also written into `summary.json`, so a figure copied out of that file carries it.

  **Spending is bounded by the guard that already exists.** `budget_guard` is imported from `chat_latency_probe` rather than written again, so the cap carries **the reservation fix** recorded at 2280: the run stops while there is still room for the next question rather than discovering its cost after paying it. The reserve is the pacer's own estimate, the most expensive question so far. The pacer keeps a trailing minute under the provider's allowance.

  **Any refusal ends the run**, which covers every way a 429 arrives: the app's own limiter answers with the status, and the provider's reaches the script as the sentence the app shows a visitor rather than as an exception. Carrying on would spend the cap on questions the provider is about to refuse too. A refused run is **not** kept as finished work -- it measured the provider's mood -- so a resume does it again rather than putting it on the sheet to be scored.

  **Resuming is the default, not a flag.** The run folder is keyed by `--run-id`, `raw/runs.json` is rewritten **after every single question**, and a second invocation with the same id skips what is already answered. A different id starts fresh. The index and state directories live inside the run folder, so a resumed run finds a warm index.

  **Nothing is written outside `.codeatlas/`.** `inside_writable_root` resolves the path first, so `--run-id ../../somewhere` is refused rather than taken literally. Nothing reads a credential: the key is checked for by name only and no value from the environment reaches a file, a log line or the terminal.

  **The tests drive it against a fake server.** `tests/test_blind_compare.py` is 25 tests over a `ThreadingHTTPServer` on 127.0.0.1 that speaks the app's SSE and bumps a token ledger of its own, so the cap is exercised through the real `budget_guard` and the real ledger rather than through a stub. **No model, no provider, no credential, and nothing off 127.0.0.1.**

  | what is proved | how |
  |---|---|
  | the shuffle is seeded and reproducible | two calls agree; a different seed gives a different set of orders; the order depends on the question as well as the seed |
  | the key never appears in the sheet | every arm name absent from `sheet.md` and `sheet.csv`, present in `key.json`, and the two in different folders |
  | resume skips finished runs | the fake server's call count does not move on a second `collect` |
  | the cap stops it | 8,000 spent under a 10,000 cap stops the run, because a third 4,000 would not have fit |
  | writing is after **every** run | the server records how many runs were on disk as each request arrived: `[0, 1, 2, 3, 4, 5]` |
  | a 429 ends it cleanly | the run stops, the rows already paid for are on disk, and the refused one is redone on resume |
  | a half-answered question is left off the sheet | an arm scored on a question the others never saw is not a comparison |
  | a tie is a tie | two arms at the top score no win between them |
  | a bad score is refused by name | `itsdangerous-1/B: correctness is 5; it must be 0, 1 or 2` |
- Command: `python -m pytest tests/ -q` -> **1393 passed**, 1 skipped (was 1368; `tests/test_blind_compare.py` is new and adds 25); `python scripts/blind_compare.py score --run-id cli-check` against a hand-filled sheet, which produced the table above, after which that run folder was deleted; `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (203 files); `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (106 passed), `npx tsc --noEmit` (clean), `npm run lint` (0 errors, 28 warnings, the same ones as before)
- Dataset/repo: none. **`scripts/blind_compare.py` has not been run against a provider.** Everything recorded here is from the fake server in the tests and from a hand-written sheet; no arm has been compared, no question has been asked of a model, and there is no result
- Date: 2026-10-15
- Commit: 717b1ca
- Notes: **there is no finding here, only an instrument.** The table above is made up. Nothing has been measured, and the first real run will need its own entry.
  **The cap is per invocation, not per run id.** `budget_guard` measures this process's spend as a delta on the ledger from the moment it started, which is what `chat_latency_probe` does. Resume three times with a 40,000 cap and 120,000 may be spent. The per-run-id total is in `raw/runs.json` to be read, but nothing enforces it.
  **One grader, one pass, no second opinion.** There is no way to measure whether the scoring itself is consistent -- the same person scoring the same sheet twice is not compared, and a second grader has nowhere to put their scores. That is the obvious next thing and is not done.
  **The blind is only as good as the answers.** If one arm's answers are recognisable by their shape -- much shorter, or always opening the same way -- the grader will learn which letter is which within a few questions and the masking will not stop them. Nothing detects that, and `grounded-low` is exactly the arm most likely to be recognisable.
  **A question's labels are stable across runs with the same seed**, which is deliberate for resuming and is a weakness for anyone scoring two runs of the same seed: A is the same arm in both. A second run meant to be scored independently should use a different `--seed`.
  **`raw/runs.json` is the key material**, not just the resume file: it carries every answer with its arm. Nothing stops a grader opening it. The separation is a folder and a sentence in `sheet.md`, not a lock.
  **The two scores are summed to decide a win**, which weights correctness and citation support equally. That is a choice, not a measurement, and a different weighting would move the wins column
### Fix: a wait of nothing is exactly 0.0, on a clock the pacer's tests own
- Value: **two tests that pass on every machine here fail on CI, and the difference is the resolution of the clock, not the code being wrong anywhere a run would notice.** `tests/test_chat_latency_probe.py::test_the_pacer_waits_only_when_the_window_is_full` and `::test_the_pacer_forgets_spend_older_than_the_window` each assert `pacer.wait() == 0.0` with nothing spent. CI (Linux, Python 3.11) returned **5.07e-06** and **3.06e-06**.

  **Where it was.** `Pacer` lives in `scripts/chat_latency_probe.py` and nowhere else; `scripts/blind_compare.py` imports it from there. It is a measurement script's spending guard. **Nothing under `codeatlas/` imports it** -- no live chat path, no app module, no server route -- so the tiny positive number was never a production bug, only a test that could not be true on both machines.

  **What it was.**

  ```python
  def wait(self) -> float:
      if self.limit <= 0:
          return 0.0
      started = time.monotonic()
      while self.in_window() + self.estimate() > self.limit and self.spends:
          time.sleep(1.0)
      return time.monotonic() - started
  ```

  When the loop body never runs, the return value is still a subtraction of two clock readings a few instructions apart -- *the cost of reading the clock twice*. Windows backs `time.monotonic()` with a counter too coarse to resolve that, so the two readings are the same number and the subtraction lands on exactly 0.0. Linux resolves nanoseconds, so it does not. **The test was never passing for the right reason here; it was passing because this machine cannot measure that interval.**

  **The fix is to stop measuring an interval that did not happen.** The fitting path returns the constant, and the subtraction is reached only after something has really been slept through:

  ```python
  def _over_the_limit(self) -> bool:
      return bool(self.spends) and self.in_window() + self.estimate() > self.limit


  def wait(self) -> float:
      if self.limit <= 0 or not self._over_the_limit():
          return 0.0
      started = self.clock()
      while self._over_the_limit():
          self.sleeper(self.poll_seconds)
      return self.clock() - started
  ```

  Deciding *whether* there is room still reads the clock -- a sliding window has to be dated against something -- but on the fitting path it never subtracts one reading from another, which is the only operation whose answer depended on the host.

  **`clock` and `sleeper` are injectable**, defaulting to `time.monotonic` and `time.sleep`, matching the `clock=` convention already used by `ConversationStore`, `SlidingWindowLimiter` and the indexing timeout. Nothing at any call site changes: `chat_latency_probe` and `blind_compare` both construct `Pacer` by keyword and pass neither.

  **Loosening the assertion to a tolerance was the obvious fix and is the wrong one.** `assert pacer.wait() < 0.001` would be green on both machines and would have stopped saying anything: the claim worth making is *the pacer did not wait*, not *the pacer waited very little*. A tolerance also hides the real failure it would next be asked to catch -- a pacer that waits a millisecond when it should wait a minute.

  | test | what it now pins |
  |---|---|
  | `test_the_pacer_waits_only_when_the_window_is_full` | 0.0 with nothing spent, and 0.0 with 3,000 spent against a limit of 8,000 -- exact, not lucky |
  | `test_the_pacer_forgets_spend_older_than_the_window` | the entry ages out by **the clock running**, not by reaching into `pacer.spends` and rewriting a timestamp |
  | `test_the_pacer_sleeps_until_the_spend_that_filled_the_window_ages_out` | **new, and the waiting path had no test at all**: 7,000 in a 60-second window against a limit of 8,000 takes 61 one-second polls and reports exactly `61.0`, with nothing sleeping |
  | `test_a_clock_fine_enough_to_time_its_own_readings_still_gives_exactly_zero` | **new**: a clock that advances 1us per *reading* is the smallest version of CI's, and `wait()` answers 0.0 across five consecutive calls while that clock keeps moving |

  **The CI failure reproduces on this machine.** A throwaway file that gives the module a 1-microsecond clock and runs the two tests' bodies fails against the old `Pacer` with `assert 1.9999999949504854e-06 == 0.0` -- the same shape of number CI reported -- and passes against the new one.
- Command: `python -m pytest -q` -> **1395 passed**, 1 skipped (was 1393; the two new pacer tests); `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (203 files), clean; `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (106 passed), `npx tsc --noEmit` (clean), `npm run lint` (0 errors, 28 warnings, the same ones as before). Run with `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY` and every `CLOUDFLARE_*` variable removed from the environment
- Dataset/repo: none. No provider was called and no server was started; the pacer is driven entirely by a fake clock
- Date: 2026-10-15
- Commit: e2cd720
- Notes: **this was a test bug, not a pacer bug.** No run of `chat_latency_probe` or `blind_compare` ever behaved differently because of the microseconds; the return value is printed as `f"{waited:.0f}s"` and used in a truthiness check, both of which a value of 5e-06 passes through harmlessly as a tiny nonzero. What it cost was a red CI.
  **`poll_seconds` is new and is the old hard-coded `1.0`.** It exists so the waiting test can state the number it expects rather than hard-coding the pacer's constant; no caller sets it.
  **`_over_the_limit` short-circuits on an empty window**, which the old loop condition did too -- `and self.spends` -- but *after* calling `in_window()`. Pruning an empty list is a no-op, so this is the same behaviour reached more cheaply, and the guard is still load-bearing: without it a `first_estimate` larger than `limit` would spin for ever rather than let through the one question that cannot fit.
  **61 polls, not 60.** The window keeps a spend while `at >= clock() - window_seconds`, so a spend leaves only once it is strictly more than 60 seconds old. The waiting test pins 61 deliberately; if that boundary ever changes the test should change with it rather than be widened
### Fix: the Cloudflare embedder times an attempt on the clock it was handed
- Value: **found by sweeping the suite for the same fault as the pacer's**: `CloudflareEmbeddingService` takes a `clock` and dates its circuit breaker against it, but `_call_with_retries` read `time.monotonic` directly. The seconds it reported came from a different clock than the one a caller injected.

  The cost was in the test. `test_the_provider_counts_its_own_calls_and_seconds` could not hand the service a fake, so it replaced `time.monotonic` **on the module** for the duration of the call and put it back in a `finally`, and then asserted only:

  ```python
  assert usage.seconds > 0
  ```

  `> 0` is the strongest claim a real clock supports, and it is **not true on every clock**: two fast local calls through a fake `post` can both land inside one tick of a counter that resolves 15 ms, and the answer is exactly 0.0. The patch was what kept that from happening, so the test depended on a global monkeypatch for its correctness and not just its convenience -- and the patch was invisible from the assertion.

  Both reads go through `self._clock` now. The fake goes in through the constructor, the module-level patch and its `finally` are gone, and the assertion is exact:

  ```python
  # Two batches, and each one reads the clock twice: 0.5 of fake time apiece.
  assert usage.seconds == 1.0
  ```

  **No default changes.** `self._clock` is `time.monotonic` unless a caller passes something else, and nothing in the app does.
- Command: `python -m pytest -q` -> **1395 passed**, 1 skipped, unchanged; `python -m pytest tests/test_semantic_observability.py tests/test_cloudflare_provider.py tests/test_cloudflare_probe.py tests/test_dual_index.py -q` -> 162 passed; `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (203 files), clean; `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (106 passed), `npx tsc --noEmit` (clean), `npm run lint` (0 errors, 28 warnings, the same ones as before). Run with `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY` and every `CLOUDFLARE_*` variable removed from the environment
- Dataset/repo: none. No Cloudflare call was made; the embedder is driven by the fake `post` the tests already use
- Date: 2026-10-15
- Commit: f45bffc
- Notes: **this one fails on a coarser clock, not a faster one** -- the opposite direction from the pacer, and worth saying because the sweep was looking for the pacer's shape. A measured duration compared against a constant is fragile at both ends: `== 0.0` breaks when the clock gets finer, `> 0` breaks when it gets coarser. Neither is a tolerance problem; both are a test measuring the host instead of the code
  **It was never wrong in a run.** `usage.seconds` is reported in the observability line and nothing branches on it, so an attempt timed against the global clock produced the same number a real run would want. What it broke was the ability to test it without reaching into the module
  **`time` is still imported** in `cloudflare_embedder.py`: it supplies the defaults for `clock` and `sleep`. The change is which clock the call path reads, not whether the module has one
### Change: the other pacer gets the same injectable clock, and its waiting path a first test
- Value: `scripts/answer_smoke.py` holds a second `Pacer`, the one `chat_mode_compare` and `reasoning_effort_compare` import. The sweep that followed the CI failure had to say whether it has the same fault. **It does not**, and the reason is worth writing down because it is the whole distinction:

  ```python
  def wait_for(self, estimate: int) -> float:
      waited = 0.0
      while self.window and self.spent_recently() + estimate > self.budget:
          ...
          waited += sleep_for
      return waited
  ```

  `waited` starts at the constant 0.0 and accumulates **the sleeps it asked for**, not a difference of two clock readings. Nothing on the no-wait path is measured, so `wait_for(...) == 0.0` is exact on a clock of any resolution and its four tests were right for the right reason. The probe's `wait()` returned `monotonic() - started` and was right only on a clock too coarse to disagree.

  **What the two did share was a waiting path no test reached.** For this one, reaching it meant sleeping for a real minute, so nothing did. With `clock` and `sleeper` injected -- defaults `time.monotonic` and `time.sleep`, and both callers construct `Pacer()` with no arguments -- it gets one: 6,000 in the window and 6,000 expected against a budget of 7,000 is a single sleep of 61 seconds, after which the window is empty and the question fits.

  **That test found dead code.** The sleep is `max(0.5, 61 - (clock() - oldest))`, and the floor is **unreachable**: `spent_recently` prunes an entry once it is 60 seconds old, so while there is anything left in the window to wait for, `61 - elapsed` is still above 1.0. It is noted in place and left alone. Dead is not wrong, and removing it would be a change to the pacer rather than to a test -- the sort of change that belongs in its own entry with its own reason.
- Command: `python -m pytest -q` -> **1396 passed**, 1 skipped (was 1395; one new test); `python -m pytest tests/test_answer_smoke.py tests/test_reasoning_effort_compare.py -q` -> 53 passed; `python -m ruff check .` and `python -m ruff format --check .` over the whole repository (203 files), clean; `python scripts/eval_retrieval.py --split test` -> overall hit@5 **0.850**, MRR@10 **0.778**, unchanged; in `codementor-ui`: `npm test` (106 passed), `npx tsc --noEmit` (clean), `npm run lint` (0 errors, 28 warnings, the same ones as before). Run with `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY` and every `CLOUDFLARE_*` variable removed from the environment
- Dataset/repo: none. No provider, no server; the pacer is driven entirely by a fake clock
- Date: 2026-10-15
- Commit: b0241ee
- Notes: **nothing here was failing.** This is consistency and coverage, not a fix, and it is recorded separately from the two fixes for that reason
  **Two tests stopped reaching into the object.** `pacer.window = [(time.monotonic() - 120, 6000)]` built the window by hand against the real clock; they call `record` and move the fake clock instead, which exercises `record` as well and states the ageing in seconds the test owns
  **The two pacers are still two pacers.** They have different fields (`budget`/`window` against `limit`/`spends`), different estimate rules and different waiting strategies -- one sleeps out the oldest entry, the other polls once a second. This change makes them consistent about the clock and nothing else; merging them is a bigger change than either of these entries, and the two scripts that would have to agree on an estimate rule have not been shown to want the same one

### Decision: the rule an overview-context change will be read by, written before the overview sets were scored
- Value: **no overview number exists when this entry is committed.** The overview sets (`eval/questions/overview/*.json`, 16 questions) and the scorer (`scripts/eval_overview.py`) are committed at 1199fa8 and 94b80ee; nothing has been run on the real checkouts. The only runs so far are the unit tests, which use a three-file repository written into a temporary folder.

  **Why a new set.** Every earlier question set asks about one fact in one or two files. The site's four starter chips ask something else - what the project does, which files matter, how it is laid out, what it uses - and on the live site "Summarize what this codebase does" was answered from `_json.py`, `url_safe.py`, `encoding.py` and a test file, with `signer.py` and `serializer.py` left out. Nothing in this file measures that kind of question, so a change aimed at it would have nothing to be read against.

  **What is measured, per question, on the context the default chat path would send** (top 5 snippets, then the mentor's prompt; see the docstring of `scripts/eval_overview.py` for what differs from the server):

  | metric | definition | direction |
  |---|---|---|
  | core-file coverage | core files present in the context / core files; a file counts once however many spans it has | higher is better |
  | noise share | slots that are a test file, a file under `docs/`, or a span overlapping an earlier slot of the same file / slots | lower is better |
  | manifest coverage | manifest files (`pyproject.toml`, `README.md`) present / manifest files, dependency questions only | reported, **not in the rule**; zero for unindexed files by construction |
  | prompt characters | characters of the formatted mentor prompt, no model call | reported, **not in the rule** |

  **The rule.** A change to what an overview question is given is adopted only if all three hold, each on the means over both repositories:

  * **dev (8 questions): mean core-file coverage is strictly higher than the incumbent's, *and***
  * **dev: mean noise share is not higher than the incumbent's, *and***
  * **held-out (the `test` split of this set, 8 questions): mean core-file coverage is not lower than the incumbent's.**

  It must also leave `python scripts/eval_retrieval.py --split test` printing the shipped default's numbers (hit@5 0.850, MRR@10 0.778): a change that moves the code-question numbers is a different decision and gets its own entry.

  **The held-out half is scored once.** One run for the incumbent and one per candidate, the numbers that come back are the numbers, and nothing is adjusted and re-scored on it. A candidate that fails is not tuned and tried again; that would make the held-out half a development set, which is what happened to the earlier held-out sets. Further tuning needs a new overview set written after these numbers are read.

  **Which candidate is the incumbent.** What the committed server runs for the hash provider: hash embeddings, `structured` records, BM25 fusion, top 5. The live site runs the cloudflare provider with whole records and no BM25; this script cannot reproduce that without API calls and so does not try
- Command: no run. This entry fixes the rule the next entry's data will be read by
- Dataset/repo: `eval/questions/overview/itsdangerous.json` and `flask.json`, 8 questions each (4 `dev`, 4 `test`), pinned at https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8. **Not yet scored under anything**
- Date: 2026-11-07
- Commit: decided at 94b80ee and committed on top of it; no code changed by this entry
- Notes: **core_files are one person's judgement, written from each repository's file listing and README without opening a source file, and that is the weakest part of this measurement.** Several are guesses from a file's name (`_json.py`, `encoding.py`, `wrappers.py`, `sansio/scaffold.py`) and the reasoning beside each says so. They were not chosen blind to retrieval: the default retrieval output for the four starter questions on both repositories had been looked at earlier in the same working session, before the files were written, so the starters' core files may lean toward what a good answer plainly needs rather than being independent of what the search returned.
  **Eight questions is very small.** One question is 0.125 of a mean, so the rule can turn on one question moving one file in or out. The per-repository tables are reported beside the overall ones for that reason.
  **The two halves are not independent in topic.** Each of the four topics (summary, files, architecture, dependencies) appears once in each half, as a starter in one and a paraphrase in the other, because a split by topic would have left one half with no dependency question. A change that helps "architecture" helps both halves, so held-out is a check against overfitting wording, not against overfitting topic.
  **Coverage counts files, not usefulness.** A context that holds `signer.py` through a one-line span counts the same as one that holds the whole class. The noise share is the check that a high coverage was not bought with slots that are mostly nothing

### Check: the incumbent default on the overview sets - core-file coverage 0.233 dev, 0.269 held-out, and over half the slots are noise
- Value: the shipped hash configuration (hash embeddings, `structured` records, BM25 fusion, top 5, stopwords dropped, 20 candidates) scored on `eval/questions/overview`, under the rule written at 6174e65. **No candidate is scored here and nothing is adopted; this is the number any later change has to beat.** The held-out half was scored once.

  | split | repo | n | core coverage | noise share | manifest | prompt chars |
  |---|---|---|---|---|---|---|
  | dev | itsdangerous | 4 | 0.400 | 0.450 | 0.000 | 5,333 |
  | dev | flask | 4 | 0.063 | 0.600 | 0.000 | 4,762 |
  | **dev** | **overall** | **8** | **0.233** | **0.525** | **0.000** | 5,048 |
  | held-out | itsdangerous | 4 | 0.425 | 0.600 | 0.000 | 4,658 |
  | held-out | flask | 4 | 0.113 | 0.550 | 0.000 | 5,295 |
  | **held-out** | **overall** | **8** | **0.269** | **0.575** | **0.000** | 4,976 |

  **What it shows.**
  * **Six of the sixteen contexts hold none of their core files** (flask 02, 03, 04, 05, 08 and itsdangerous 08). Eleven of sixteen have a noise share of 0.6 or more.
  * **The starters are not the worst.** "Show me the architecture overview" on flask is 0.80 noise: four of five slots are test files (`typing_route.py` twice, `test_cli.py` twice) and the fifth is a `cli.py` fragment. "What does this project do?" on flask is three spans of `tests/test_instance_config.py`, `docs/conf.py` and a one-line `globals.py` span.
  * **itsdangerous is better than flask on both numbers**, and the best single result is "What are the most important files?" on itsdangerous: 1.00 coverage, 0.20 noise (`serializer.py` twice, `signer.py`, `timed.py`, and one overlapping `serializer.py` span). Why this one question did well was not investigated; with eight questions it is one result, not a pattern.
  * **Overlap is real but is not the main noise.** Overlapping spans are the largest single reason in itsdangerous (`timed.py:72-108` beside `71-108`; `signer.py:48-64` beside `62-64`); tests are the largest in flask.
  * **Manifest coverage is 0.000 everywhere, by construction**: `pyproject.toml` and `README.md` are not in `_SUFFIX_MAP`, so no record points at them. It cannot move unless something other than retrieval supplies them.
  * **Prompt size is about 5,000 characters of a 6,000 cap**, roughly 1,250 tokens at the repository's 4-characters-per-token figure, in line with the "about 1,400 tokens every question" of snippets recorded at 9690592. A snippet that does not fit is dropped whole, which is why flask's "most important files" kept three of five.

  **The shipped default's code-question numbers are unchanged**: `scripts/eval_retrieval.py --split test` prints hit@5 0.850 and MRR@10 0.778 (itsdangerous 0.800 / 0.828, flask 0.900 / 0.729) at 6174e65. Nothing in this branch touches a code path.

  **The live site does not run this configuration.** It runs the cloudflare provider with whole records and no BM25, and this run cannot reproduce that without API calls, which were not made. The live symptom (answers from `_json.py`, `url_safe.py`, `encoding.py` and a test file) is a different set of files from any recorded here, so these numbers show that the failure exists under the committed hash default too, not how large it is on the site
- Command: `.\.venv\Scripts\python.exe scripts/eval_overview.py --split dev`, then once `.\.venv\Scripts\python.exe scripts/eval_overview.py --split test`; and `.\.venv\Scripts\python.exe scripts/eval_retrieval.py --split test` for the unchanged code-question numbers. No server, no model, no network; the pinned checkouts were already in `.codeatlas/eval-repos`
- Dataset/repo: `eval/questions/overview/*.json`, 16 questions, https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8
- Date: 2026-11-07
- Commit: 6174e65 (the state measured); the scripts and question files are unchanged since 94b80ee and 1199fa8
- Notes: **eight questions per split, one repository's worth of judgement in the core files.** A mean moves by 0.125 when one question moves from 0 to 1, and the core files were chosen from file names and a README (see the previous entry). Treat 0.233 and 0.269 as the same number: the held-out half is not independent of the dev half in topic, and the difference between them is smaller than one question.
  **`prefix_metadata` puts the file path into each embedded text**, so a path word such as "tests" or "docs" can pull those files toward any question that shares a word with it; this run does not separate that from the keyword rerank, and no setting was changed to find out.
  **The scorer builds its own in-memory index** as the retrieval eval does, not the server's on-disk one, and skips the follow-up rewrite an overview question never needs. It imports `_PROMPT` and `_numbered` from `coding_mentor_agent.py` because the final prompt is assembled inside the call that invokes the model and nothing public stops short of it

### Change: the overview labels corrected from the files' source, and the incumbent rescored under them
- Value: **the core_files and manifest_files in `eval/questions/overview/*.json` were corrected after they were first written (1199fa8), from reading each file's source, and the incumbent was rescored under the corrected labels so that any later candidate is read against the same ones.** The held-out half was already scored once under the old labels (the entry at c7587f4); **this second held-out scoring of the unchanged incumbent is a re-baseline, not a new selection**, and no candidate is involved.

  **What was changed, each reason from the source** (the old labels were written from file names and READMEs; these were checked by opening the files):

  | repo | topic | change | reason read in the source |
  |---|---|---|---|
  | itsdangerous | dependencies | add `signer.py` | imports `hashlib` and `hmac`, the actual cryptographic dependency |
  | itsdangerous | dependencies | drop `README.md` from the manifest | it names no library or dependency |
  | itsdangerous | dependencies | `pyproject.toml` kept, reason now "declares no runtime dependencies" | it has no `dependencies` key, only dev and docs groups; the earlier reason was wrong |
  | itsdangerous | read first | add `__init__.py` | 17 re-exports in one short file, the quickest map of the public API |
  | itsdangerous | architecture | add `exc.py` | the public exception hierarchy `BadData` -> `BadSignature` -> `BadTimeSignature` -> `SignatureExpired` |
  | flask | summary | add `sansio/scaffold.py` | `Scaffold.route` (line 344) is the `@app.route` decorator the README example uses |
  | flask | most important files, architecture | add `sansio/blueprints.py` (keep `blueprints.py`) | `BlueprintSetupState` and `register_blueprint` live there; `blueprints.py` is a thin subclass of it |
  | flask | architecture | add `globals.py` | `current_app`, `g`, `request` and `session` are `LocalProxy` objects over context variables |
  | flask | dependencies | add `cli.py` | imports `click`, a declared dependency, for `FlaskGroup` and `run_command` |

  **No retrieval result was used to choose any of these.** That is a statement about the method, not a guarantee of independence: output of this same search on the starter questions had been looked at earlier in the working session, so the corrections were not made by someone who had never seen what retrieval returns.

  **Left out, and why.**
  * `encoding.py` was **not** added to architecture, because of circularity: the planned brief ranks files by import in-degree, `encoding.py` is imported by four sibling modules, and adding it would have credited the brief for surfacing a file the labels were bent toward.
  * `url_safe.py` was not added to the itsdangerous dependency set (its `zlib` use is real but optional), and `signals.py` and `sessions.py` were not added to flask's, because `pyproject.toml` already names blinker and itsdangerous.
  * **`exc.py` was added, and it is the most-imported file in itsdangerous** (imported by `signer`, `serializer`, `timed`, `url_safe`, `encoding` and `__init__`). It was added on the content of the file, as the public exception tree, but a brief ranking by in-degree will credit it for that reason too. `globals.py` and `sansio/scaffold.py` in flask may be in the same position; their in-degree was not counted. For that reason the step that evaluates the brief reports coverage two ways: counting only the final snippets, and counting snippets plus files the brief names.

  **The incumbent under the corrected labels** (hash embeddings, `structured` records, BM25, top 5; same settings and contexts as before):

  | split | repo | n | core coverage | was | noise share | manifest |
  |---|---|---|---|---|---|---|
  | dev | itsdangerous | 4 | 0.438 | 0.400 | 0.450 | 0.000 |
  | dev | flask | 4 | 0.050 | 0.063 | 0.600 | 0.000 |
  | **dev** | **overall** | **8** | **0.244** | 0.233 | **0.525** | **0.000** |
  | held-out | itsdangerous | 4 | 0.500 | 0.425 | 0.600 | 0.000 |
  | held-out | flask | 4 | 0.169 | 0.113 | 0.550 | 0.000 |
  | **held-out** | **overall** | **8** | **0.335** | 0.269 | **0.575** | **0.000** |

  **Only the core-coverage column moved.** Noise share, manifest coverage and prompt characters are identical to the previous entry for all sixteen questions, which is the check that the contexts did not change: the same search produced the same snippets and only the labels differ. The shipped code-question numbers are unchanged: `scripts/eval_retrieval.py --split test` prints hit@5 0.850 and MRR@10 0.778.

  **Why coverage rose, and what that does not mean.** Most of the held-out gain, 0.269 to 0.335, is two questions whose contexts already held a newly-labelled file: itsdangerous "What frameworks and libraries are used?" now credits `signer.py` (0 to 0.33), and flask's same question now credits `cli.py` (0 to 0.33). Nothing about retrieval improved. A higher baseline is a different ruler, not a better search, and the old and new columns must not be compared as if they were two runs of one metric
- Command: `.\.venv\Scripts\python.exe scripts/eval_overview.py --split dev`, then `.\.venv\Scripts\python.exe scripts/eval_overview.py --split test`, and `.\.venv\Scripts\python.exe scripts/eval_retrieval.py --split test`. No server, no model, no network
- Dataset/repo: `eval/questions/overview/*.json` at https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8
- Date: 2026-11-07
- Commit: 9611ca2 (the state measured, with the corrected labels); scripts unchanged since 94b80ee
- Notes: **the rule at 6174e65 is unchanged** and any candidate is now read against the 0.244 dev and 0.335 held-out above, not against the earlier figures.
  **Eight questions per split.** One question moving from 0 to 1 is 0.125 of a mean, so the 0.011 dev change is noise-sized and the held-out change is two questions' worth.
  **The core lists are still one reader's judgement.** They are now checked against source for the files named above, but `__init__.py`, `exc.py` and `globals.py` were each argued from content and could be argued out

### Feature: overview_brief.py, a deterministic description of a repository, built and not yet used by anything
- Value: `codeatlas/services/qa/overview_brief.py` builds a text block of at most 3,500 characters from the repository on disk, with no model call: a capped file tree, the files other files import most, dependency names, and the README's opening. **It is not wired into any chat path and has no setting**; a test asserts that nothing under `codeatlas/` imports it. Every chat path behaves exactly as before, and `scripts/eval_retrieval.py --split test` still prints hit@5 0.850 and MRR@10 0.778.

  **What it holds.** At most 40 paths with sizes (hidden, tests, docs, examples, vendored, generated, lock, binary and secret-looking files left out; top-level files first, then code shallowest-first); up to 8 files ranked by import in-degree, from the existing `ImportGraphBuilder` plus a resolver that maps the module names it returns to files; dependency **names only** from `pyproject.toml` and `requirements*.txt`; the first 1,500 characters of the README, with HTML-only lines dropped and key-like strings replaced.

  **Safety.** Every file is opened only after `files_controller._safe_join`, the check `/files/content` uses; files over 1,000,000 bytes or containing a NUL are not read. The block opens by saying it is data to describe and not instructions, the README sits between `<<<README_DATA` and `README_DATA>>>`, and a marker typed inside the README is defused. A path with whitespace in it and a dependency entry that is not a plain package name cannot carry a sentence in. It never raises: with no import graph it is the tree, the dependency names and the README; with nothing readable it is an empty string.

  **The two pinned repositories** (at the corrected-label commit's checkouts):

  | repo | characters | files shown | most-imported lines | dependencies line |
  |---|---|---|---|---|
  | itsdangerous | 2,568 | 13 of 13 | 7 (the 8th file is imported by none) | declares no runtime dependencies |
  | flask | 3,252 | 30 of 30 | 8 | blinker, click, itsdangerous, jinja2, markupsafe, werkzeug (+ 2 optional) |

  **Import in-degree of every labelled core file, among the code files in the brief's scope** (8 files in itsdangerous, 24 in flask; tests, docs and examples are neither importers nor targets). "In top 8" is membership in the brief's most-imported list, which is by in-degree alone.

  | repo | file | rank | in-degree | in top 8 | topics that label it |
  |---|---|---|---|---|---|
  | itsdangerous | `exc.py` | 1/8 | 6 | yes | architecture |
  | itsdangerous | `encoding.py` | 2/8 | 5 | yes | dependencies |
  | itsdangerous | `serializer.py` | 3/8 | 3 | yes | summary, files, read first, architecture |
  | itsdangerous | `signer.py` | 4/8 | 3 | yes | summary, files, read first, architecture, dependencies |
  | itsdangerous | `timed.py` | 5/8 | 2 | yes | summary, files, read first, architecture |
  | itsdangerous | `_json.py` | 6/8 | 1 | yes | dependencies |
  | itsdangerous | `url_safe.py` | 7/8 | 1 | yes | summary, architecture |
  | itsdangerous | `__init__.py` | 8/8 | 0 | no | read first, architecture |
  | flask | `globals.py` | 1/24 | 12 | yes | architecture |
  | flask | `wrappers.py` | 3/24 | 9 | yes | dependencies |
  | flask | `__init__.py` | 4/24 | 8 | yes | summary, read first |
  | flask | `sansio/app.py` | 5/24 | 7 | yes | files, read first, architecture |
  | flask | `app.py` | 6/24 | 6 | yes | summary, files, read first, architecture |
  | flask | `ctx.py` | 7/24 | 5 | yes | architecture |
  | flask | `sansio/scaffold.py` | 8/24 | 5 | yes | summary, files, architecture |
  | flask | `templating.py` | 11/24 | 4 | no | summary, dependencies |
  | flask | `cli.py` | 12/24 | 3 | no | summary, dependencies |
  | flask | `blueprints.py` | 14/24 | 2 | no | files, architecture |
  | flask | `sansio/blueprints.py` | 18/24 | 2 | no | files, architecture |

  **What this means for scoring the brief.** In itsdangerous the most-imported list holds 7 of the 8 code files, and the tree lists all 13 files, so "named in the brief" covers almost every itsdangerous label by construction: seven of its eight labelled files are in the list **only because of in-degree, and in-degree is nearly everything in a package that small**. Flask discriminates: seven of its eleven labelled files are in the list and four are not (`templating.py`, `cli.py` and both `blueprints.py` files). `exc.py`, `globals.py` and `sansio/scaffold.py` are all in the list, ranked 1, 1 and 8, so the brief will be credited for them for exactly the reason the labels were flagged. `sansio/scaffold.py` sits on the edge: it is tied at 5 with `ctx.py` and takes the 8th place only because of the path order used to break ties. A later evaluation should read the flask rows and the itsdangerous rows separately, and not average a near-automatic itsdangerous gain into the headline
- Command: `.\.venv\Scripts\python.exe -W ignore -c "from pathlib import Path; from codeatlas.services.qa.overview_brief import build_overview_brief as b; [print(n, len(b(Path(p)))) for n, p in (('itsdangerous', '.codeatlas/eval-repos/itsdangerous-672971d66a2e'), ('flask', '.codeatlas/eval-repos/flask-d73fa1cdcbd8'))]"` prints the two lengths; the in-degree ranks come from `import_ranking` on the same two folders; tests with `.\.venv\Scripts\python.exe -m pytest tests/test_overview_brief.py`. No server, no model, no network
- Dataset/repo: https://github.com/pallets/itsdangerous 672971d66a2e and https://github.com/pallets/flask d73fa1cdcbd8; the labels are those of `eval/questions/overview/*.json` at 9611ca2
- Date: 2026-11-07
- Commit: 893c9da
- Notes: **nothing here is a result about answer quality.** This entry builds an input and counts files; whether a model answers an overview question better with the block in front of it needs model calls, which were not made.
  **The README text is untrusted input and the framing is a request, not a barrier.** The marker and the opening sentence make it hard for the README to close the frame or pass as the system's voice, and a test checks both; a model may still follow text it was told to treat as data, and nothing in this module can prevent that.
  **The secret screen is a short list of patterns.** It replaced the itsdangerous README's example token (`eyJ...`) with `[redacted]` and left the signature half behind it; it would miss a credential shaped like none of them. Secret-looking file names are left out of the tree by name, not by content.
  **The containment helper is imported from a controller.** `_safe_join` lives in `files_controller.py`, a module this branch must not edit, so it is imported inside the function that needs it (a top-level import would be a cycle once the agents import this module). Moving it to a shared utility is the right fix and touches that controller, so it is left as a follow-up for after batch-14. If the helper is renamed, the containment tests fail and the brief is empty rather than uncontained.
  **The symlink test was skipped on this machine** (creating a symlink needs a privilege Windows withholds by default), so the claim that a link pointing outside the repository is not followed rests on `_safe_join` and on the test that replaces it with a function returning None, not on a link actually created here.
  **Timing is one run.** itsdangerous took 1,243 ms and flask 77 ms in the same process, the first carrying the one-off import of the parser and `networkx`; the brief has not been timed on a 5,000-file repository, and nothing is cached, so it would be rebuilt for every overview question
