# Azeroth Chronicles companion uploader

A tiny, dependency-free Python script that uploads your `AzerothChronicles.lua` SavedVariables file to your
Azeroth Chronicles server whenever World of Warcraft writes it (logout, `/reload`, exit).

It **only reads that one text file**. It never reads game memory, injects into the client, or interacts
with gameplay.

```bash
python azchron_companion.py setup --server https://your-server.example --token act_xxxxxxxx
python azchron_companion.py watch
```

Create the upload token on the website under **Integrations → Companion upload tokens**. Tokens can only
upload data and can be revoked at any time. Uploads are idempotent, so re-uploading never duplicates events.

Commands: `setup`, `upload [--force]`, `watch [--interval 10] [--upload-on-start]`, `status`.
The config (including the token) is stored in `~/.azeroth-chronicles-companion.json` with `0600` permissions.
