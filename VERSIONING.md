# Versioning — NCOF Platform API

## Scheme

**Semantic Versioning** (`MAJOR.MINOR.PATCH`):

| Change | Bump | Example |
|--------|------|---------|
| Breaking API change | MAJOR | `1.8.0` → `2.0.0` |
| New features, backward compatible | MINOR | `1.8.0` → `1.9.0` |
| Bug fixes only | PATCH | `1.8.0` → `1.8.1` |

## Where the version lives

| File | Purpose |
|------|---------|
| `VERSION` | Canonical version string |
| `app/main.py` → FastAPI `version=` | Served on `/health` and `/ready` |
| `CHANGELOG.md` | Human-readable history |
| Git tag `v1.8.0` | Immutable release marker (create on GitHub Releases) |

## Tagging a release (GitHub UI)

1. Open https://github.com/seyi-qing/ncof-platform/releases/new  
2. Tag: `v1.8.0` (create new tag on `main`)  
3. Title: `NCOF API v1.8.0`  
4. Paste the matching section from `CHANGELOG.md`  
5. Publish release  

## CLI (if you have git push access)

```bash
git checkout main
git pull
# after VERSION bump is committed:
git tag -a v1.8.0 -m "NCOF API v1.8.0"
git push origin v1.8.0
```

## Compatibility with the web app

| API | Web (recommended) |
|-----|-------------------|
| 1.8.x | 2.1.x |
| 1.7.x | 2.0.x |
