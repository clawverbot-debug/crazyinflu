# Character Lab API & MCP

Base URL: `https://character-lab-research.netlify.app`

Every call needs the key, sent one of two ways:
- `Authorization: Bearer <API_KEY>`
- `x-api-key: <API_KEY>`

The key lives in `~/.config/viral-spy/api_key`. Without the `API_KEY` variable set on Netlify, every call answers 503.

## REST (GET, JSON)

| Endpoint | What it returns |
|---|---|
| `/api/v1` | Index of endpoints |
| `/api/v1/characters?min_score=90&media_buyer_only=1&with_videos=1` | Every character: id, name, handle, profile name, bio, breakout score, profile picture, HD image, video count |
| `/api/v1/characters/:id` | One character in full (id `otto` or handle `herr.otto`): traits, GPT Image 2 prompt, bio, bio link with UTM, location tag, captions, hashtags, images, profile picture, videos (4K, 480p, source, posting slot, caption) |
| `/api/v1/videos?character=barry` | Every generated video ready to post |
| `/api/v1/sources?bucket=buzz\|hit&business_only=1` | Fresh source clips to copy (views, views/hour, scene, business fit, trimmed clip URL) |
| `/api/v1/radar` | Live radar queue (scanned on demand) |
| `/api/v1/playbook` | Everything learned for posting: `rules` (UTC windows, cadence by account age, flops, captions, bios, video), `learned` (live from our own accounts: median views by post hour, account age, caption variant, duration, phone, plus per-account stats) and `research` (honeymoon curve, cadence of the top accounts) |
| `/api/v1/schedule?account=prime_banwavebarry` | Per pool account: age in days, posts in the last 24 h, today's rule, next recommended post time (UTC) and the next unposted video with its caption |
| `/api/v1/knowledge` (`?format=md` for raw markdown) | The full posting knowledge pack: everything learned, for a posting tool or an LLM |
| `/api/v1/posts?account=` | Posts logged by the posting tool |
| `/api/v1/data` | List of research blocks |
| `/api/v1/data/:block` | One block: `cadence`, `traits`, `scenes`, `honeymoon`, `tricks`, `wave`, `hitflop`, `accounts`… |

Example:

```bash
curl -H "Authorization: Bearer $(cat ~/.config/viral-spy/api_key)" https://character-lab-research.netlify.app/api/v1/characters/otto
```

## Generation for the team (write, paid with the owner's credits)

| Call | Does |
|---|---|
| `POST /api/v1/generate/image` `{prompt, ref_urls?, aspect_ratio?, resolution?}` | GPT Image 2 through kie.ai. Text only, or 1 to 4 https reference images to keep a character exact. Returns `task_id`. |
| `GET /api/v1/generate/image/:task_id` | `state` (waiting, generating, success, fail) and `urls` |
| `POST /api/v1/scan` `{hashtags: [...], per_tag?}` | Apify Instagram scan of recent reels, up to 12 hashtags and 5 to 30 reels each. Each run is capped at $2, and the scan is refused once the month reaches `RADAR_MAX_USD`. Returns `scan_id`. |
| `GET /api/v1/scan/:scan_id?max_age_hours=72` | Reels ranked by views per hour (URL, video, views, age, caption) |
| `GET /api/v1/usage` | What you used today, your quotas and your recent actions |

**Keys.**
- Each collaborator gets their own key: the owner runs `python3 collab_key.py add <name>`, which stores the keys in the Netlify variable `API_KEYS`.
- Calls are logged with the person's name.
- Default quotas per person per day: 40 images (`GEN_IMG_DAILY`) and 3 scans (`GEN_SCAN_DAILY`). The owner key has no quota.

**Higgsfield videos are not available through this API.** Higgsfield has no API key, only a personal login. To share video generation, add collaborators to the owner's Higgsfield team workspace; they then generate with their own login on the shared credits.

MCP tools: `generate_image`, `get_image`, `start_scan`, `get_scan`, `my_usage`.

## Logging posts (write)

`POST /api/v1/posts` with JSON `{account, video_4k, reel_url, caption, posted_at, trial_reel, phone}`.
- Only `account` is required; `posted_at` defaults to now.
- The video is matched by its `video_4k` URL, which links the post to its character and caption variant.
- Call it after every post: the schedule then skips videos already posted, and the learnings group views by caption variant using real data.

## MCP server

Endpoint: `POST https://character-lab-research.netlify.app/mcp`. It speaks Streamable HTTP with JSON-RPC 2.0 and handles `initialize`, `tools/list`, `tools/call` and `ping`.

The 16 tools are:
- `list_characters`
- `get_character`
- `list_videos`
- `list_sources`
- `get_radar`
- `get_playbook`
- `get_schedule`
- `get_knowledge`
- `log_post`
- `list_posts`
- `get_insights`

Add it to Claude Code:

```bash
claude mcp add --transport http character-lab https://character-lab-research.netlify.app/mcp --header "Authorization: Bearer $(cat ~/.config/viral-spy/api_key)"
```

Any MCP client works: give it the URL and the `Authorization` header.

## Data freshness

`dist/characters.json` and `dist/data.json` are rebuilt by `python3 build_data.py`, which also runs `export_characters.mjs`, then deployed with:

```bash
netlify deploy --dir dist --functions netlify/functions --prod --site character-lab-research --no-build
```

The radar data is live, stored in Netlify Blobs.
