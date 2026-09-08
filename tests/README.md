# Real Zola compatibility tests

Run from the repository root with Python's standard library (no pip install):

```sh
python3 -m unittest discover -s tests -v
```

Zola 0.23.4 or newer must be on `PATH`. To select an explicit executable:

```sh
ZOLA_BIN=/absolute/path/to/zola python3 -m unittest discover -s tests -v
```

The suite builds synthetic consumer sites and parses their generated HTML. It
also copies and builds the repository demo. Fixtures, copied themes and build
output live in automatically cleaned temporary directories; the checkout's
`public/` is never reused or deleted. A missing binary or failed build is a test
failure, not a skip. No fixture content represents real authors or articles.

Coverage includes theme English defaults without `[extra]`, archives, Unicode
page/tag URLs, rendered Markdown summaries, independent read-more state, undated
pages, optional author/social fields, metadata overrides without duplication,
custom assets, four display modes, pagination, localized content and tag links,
missing translation fallback, and empty/missing posts sections.

## Negative control against another checkout

`THEME_ROOT` selects the source theme and demo, not the location of the tests.
This permits running the current suite against an old or deliberately broken
checkout without changing the current working tree:

```sh
THEME_ROOT=/absolute/path/to/old-checkout \
ZOLA_BIN=/absolute/path/to/zola-0.23.4 \
python3 -m unittest discover -s tests -v -k minimal_consumer
```

The historical `f47231e` checkout is expected to fail with the legacy macro-call
parse error in `templates/page.html`, while the migrated checkout passes.

## Fixture conventions

- Multilingual fixtures use `[languages.fr]` / `[languages.de]` with a separate
  taxonomy configuration for each language, plus translated `_index.fr.md` /
  `_index.de.md` files. See [Zola's multilingual schema](https://www.getzola.org/documentation/content/multilingual/).
- Theme labels intentionally use the theme's existing
  `[[extra.translations.fr]]` interface, not Zola's unrelated string translation
  map. German deliberately has no theme translation entry to test fallback.
- Zola normally transliterates Unicode slugs. The Unicode URL fixture explicitly
  selects `[slugify] paths = "safe"` and `taxonomies = "safe"`; other fixtures
  follow rendered permalinks rather than guessing the slugifier's result.
- The undated page belongs to an unsorted section: Zola excludes undated pages
  from date-sorted sections before templates get a chance to render them.

CI runs on pushes and pull requests, using Python 3.12 and the official Linux
Zola 0.23.4 archive with its pinned published SHA-256 digest. It runs this suite
and a separate repository demo build; it does not deploy anything.
