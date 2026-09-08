"""Real Zola compatibility tests, using only the Python standard library.

Every consumer and every article below is a synthetic regression fixture. Builds
run in disposable directories, never in the checkout. Set ZOLA_BIN to select a
binary; set THEME_ROOT to rerun this same suite against an older theme checkout.
"""
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

THEME_ROOT = Path(os.environ.get("THEME_ROOT", Path(__file__).resolve().parents[1])).resolve()
ZOLA = os.environ.get("ZOLA_BIN", "zola")
BASE_URL = "https://example.test"
CONFIG = '''base_url = "https://example.test"
title = "Synthetic compatibility site"
description = "Synthetic site description"
theme = "archie-zola"
default_language = "en"
taxonomies = [{name = "tags"}]
'''


class Element:
    def __init__(self, tag, attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    @property
    def text(self):
        return " ".join(" ".join(
            child.text if isinstance(child, Element) else child
            for child in self.children
        ).split())

    def find(self, tag=None, class_=None, **attrs):
        found = []
        for child in self.children:
            if not isinstance(child, Element):
                continue
            if ((tag is None or child.tag == tag)
                    and (class_ is None or class_ in child.attrs.get("class", "").split())
                    and all(child.attrs.get(key) == value for key, value in attrs.items())):
                found.append(child)
            found.extend(child.find(tag, class_, **attrs))
        return found


class Document(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        element = Element(tag, attrs)
        self.stack[-1].children.append(element)
        if tag not in self.VOID:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def article(title="Synthetic article", date: str = "2026-01-01", description=None,
            tags=None, extra="", body="Synthetic fixture body.", front=""):
    # Fixture values are deliberately controlled literals, not user input.
    lines = ['title = "{}"'.format(title)]
    if date:
        lines.append("date = " + date)
    if description is not None:
        lines.append('description = "{}"'.format(description))
    lines.append(front)
    if tags:
        lines.extend(["[taxonomies]", "tags = " + repr(tags).replace("'", '"')])
    if extra:
        lines.extend(["[extra]", extra])
    return "+++\n" + "\n".join(lines) + "\n+++\n\n" + body + "\n"


class ThemeBuildTests(unittest.TestCase):
    def temporary(self):
        temporary = tempfile.TemporaryDirectory(prefix="archie-zola-test-")
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def build(self, root):
        result = subprocess.run(
            [ZOLA, "build", "--output-dir", str(root / "generated")],
            cwd=root, text=True, capture_output=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((root / "generated/index.html").is_file())
        return root / "generated"

    def consumer(self, files=None, config="", posts=True):
        root = self.temporary()
        theme = root / "themes/archie-zola"
        theme.mkdir(parents=True)
        for name in ("templates", "static", "sass"):
            if (THEME_ROOT / name).is_dir():
                shutil.copytree(THEME_ROOT / name, theme / name)
        shutil.copy2(THEME_ROOT / "theme.toml", theme / "theme.toml")
        (root / "config.toml").write_text(CONFIG + config, encoding="utf-8")
        fixture_files = {"content/_index.md": '+++\nsort_by = "date"\n+++\n'}
        if posts:
            fixture_files["content/posts/_index.md"] = (
                '+++\nsort_by = "date"\ntemplate = "posts.html"\n+++\n'
            )
        fixture_files.update(files or {})
        for name, content in fixture_files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return self.build(root)

    def document(self, output, path="index.html"):
        target = output / path
        self.assertTrue(target.is_file(), str(target))
        return Document(target.read_text(encoding="utf-8")).root

    def hrefs(self, document, **attrs):
        return [element.attrs.get("href") for element in document.find("a", **attrs)]

    def assert_local_link(self, output, href, prefix):
        parsed = urlsplit(href)
        self.assertEqual(parsed.netloc, "example.test", href)
        path = unquote(parsed.path)
        self.assertTrue(path.startswith(prefix), href)
        self.assertTrue((output / path.lstrip("/") / "index.html").is_file(), href)

    def test_zola_version_meets_minimum(self):
        result = subprocess.run([ZOLA, "--version"], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        version = re.search(r"\bzola (\d+)\.(\d+)\.(\d+)", result.stdout)
        if version is None:
            self.fail(result.stdout)
        self.assertGreaterEqual(tuple(map(int, version.groups())), (0, 23, 4))

    def test_minimal_consumer_uses_english_defaults_without_extra(self):
        output = self.consumer({"content/posts/hello.md": article(description="Synthetic preview")})
        home = self.document(output)
        self.assertEqual(home.find("html")[0].attrs.get("lang"), "en")
        self.assertIn("Synthetic article", home.text)
        self.assertIn("Read more", home.text)
        self.assertIn("minute read", home.text)
        self.assertEqual(len(home.find("a", class_="readmore")), 1)
        self.assertFalse(home.find("a", class_="soc"))

    def test_posts_archive_links_to_each_post(self):
        output = self.consumer({
            "content/posts/one.md": article("Synthetic first", date="2026-01-02"),
            "content/posts/two.md": article("Synthetic second"),
        })
        archive = self.document(output, "posts/index.html")
        for slug, title in (("one", "Synthetic first"), ("two", "Synthetic second")):
            anchors = [a for a in archive.find("a") if a.text == title]
            self.assertEqual(len(anchors), 1)
            self.assertEqual(anchors[0].attrs["href"], BASE_URL + "/posts/" + slug + "/")
            self.assertIn(title, self.document(output, "posts/" + slug + "/index.html").text)

    def test_non_ascii_page_and_tag_urls_resolve(self):
        # Zola normally transliterates slugs; safe mode deliberately exercises
        # Unicode URLs instead of mistaking the default slugifier for a bug.
        output = self.consumer({
            "content/posts/中文.md": article("Synthetic Unicode", tags=["中文", "café"])
        }, config='[slugify]\npaths = "safe"\ntaxonomies = "safe"\n')
        home = self.document(output)
        page_link = next(a.attrs["href"] for a in home.find("a") if a.text == "Synthetic Unicode")
        self.assert_local_link(output, page_link, "/posts/")
        self.assertIn("中文", unquote(page_link))
        page = self.document(output, unquote(urlsplit(page_link).path).lstrip("/") + "index.html")
        for tag in ("中文", "café"):
            links = [a.attrs["href"] for a in page.find("a") if a.text == tag]
            self.assertEqual(len(links), 1, tag)
            self.assert_local_link(output, links[0], "/tags/")
        cloud = self.document(output, "tags/index.html")
        self.assertIn("All tags", cloud.text)
        tag_links = self.hrefs(cloud.find(class_="tag-cloud")[0])
        self.assertEqual(len(tag_links), 2)
        for href in tag_links:
            self.assert_local_link(output, href, "/tags/")
            term = self.document(output, unquote(urlsplit(href).path).lstrip("/") + "index.html")
            self.assertIn(page_link, self.hrefs(term))

    def test_markdown_summary_is_html_not_escaped_text(self):
        output = self.consumer({"content/posts/summary.md": article(
            body="Synthetic **bold preview** with [a link](https://example.org/).\n\n<!-- more -->\n\nSynthetic hidden remainder."
        )})
        description = self.document(output).find(class_="description")[0]
        self.assertEqual(description.find("strong")[0].text, "bold preview")
        self.assertIn("https://example.org/", self.hrefs(description))
        self.assertNotIn("<p>", description.text)
        self.assertNotIn("<strong>", description.text)
        self.assertNotIn("Synthetic hidden remainder", description.text)
        self.assertFalse(any(p.find("p") for p in description.find("p")), "Nested paragraphs are invalid HTML")

    def test_read_more_state_does_not_leak_between_posts(self):
        output = self.consumer({
            "content/posts/plain.md": article("Synthetic no preview", date="2026-01-03"),
            "content/posts/description.md": article("Synthetic description", date="2026-01-02", description="Synthetic description text"),
            "content/posts/summary.md": article("Synthetic summary", body="Synthetic preview.\n\n<!-- more -->\n\nSynthetic remainder."),
        })
        items = self.document(output).find(class_="list-item")
        self.assertEqual(len(items), 3)
        self.assertIn("Synthetic no preview", items[0].text)
        for item, expected in zip(items, (0, 1, 1)):
            self.assertEqual(len(item.find("a", class_="readmore")), expected, item.text)

    def test_undated_page_has_no_fabricated_date(self):
        # Zola excludes undated pages from a date-sorted section before render.
        output = self.consumer({
            "content/_index.md": "+++\n+++\n",
            "content/about.md": article("Synthetic undated page", date=""),
        })
        page = self.document(output, "about/index.html")
        self.assertIn("Synthetic undated page", page.text)
        self.assertFalse(page.find("time"))
        meta = page.find("article")[0].find(class_="meta")
        self.assertTrue(all(not element.text for element in meta), [e.text for e in meta])
        self.assertNotRegex(page.find("article")[0].text, r"\b(?:1970|0000)-\d\d-\d\d\b")

    def test_author_name_without_social_url_is_plain_text(self):
        output = self.consumer({"content/posts/author.md": article(
            extra='author = {name = "Synthetic Author"}', description="Synthetic preview"
        )})
        for path in ("index.html", "posts/author/index.html"):
            doc = self.document(output, path)
            self.assertIn("Synthetic Author", doc.text)
            self.assertFalse([a for a in doc.find("a") if a.text == "Synthetic Author"])

    def test_author_social_url_and_footer_social_are_optional(self):
        output = self.consumer({"content/posts/author.md": article(
            extra='author = {name = "Synthetic Linked Author", social = "https://example.org/author"}',
            description="Synthetic preview"
        )}, config='''[extra]
social = [{name = "Synthetic network", icon = "github", url = "https://example.org/social"}]
''')
        for path in ("index.html", "posts/author/index.html"):
            doc = self.document(output, path)
            self.assertIn("https://example.org/author", self.hrefs(doc))
            self.assertIn("https://example.org/social", self.hrefs(doc, class_="soc"))
            self.assertTrue(any("feather" in e.attrs.get("src", "") for e in doc.find("script")))

    def test_metadata_overrides_are_not_duplicated_or_leaked(self):
        output = self.consumer({
            "content/posts/override.md": article(description="Synthetic normal description", extra='''meta = [
  {property = "og:title", content = "Synthetic override title"},
  {property = "og:description", content = "Synthetic override OG description"},
  {name = "description", content = "Synthetic override description"},
  {name = "robots", content = "noindex"}
]'''),
            "content/posts/normal.md": article("Synthetic normal title", description="Synthetic default description"),
        })
        override = self.document(output, "posts/override/index.html")
        normal = self.document(output, "posts/normal/index.html")
        for key, value, expected in (
            ("property", "og:title", "Synthetic override title"),
            ("property", "og:description", "Synthetic override OG description"),
            ("name", "description", "Synthetic override description"),
            ("name", "robots", "noindex"),
        ):
            metas = override.find("meta", **{key: value})
            self.assertEqual([m.attrs.get("content") for m in metas], [expected])
        self.assertEqual([m.attrs.get("content") for m in normal.find("meta", property="og:title")], ["Synthetic normal title"])
        self.assertEqual([m.attrs.get("content") for m in normal.find("meta", name="description")], ["Synthetic default description"])
        self.assertFalse(normal.find("meta", name="robots"))

    def test_metadata_uses_site_description_when_page_has_none(self):
        output = self.consumer({"content/posts/plain.md": article()})
        for path in ("index.html", "posts/plain/index.html"):
            doc = self.document(output, path)
            self.assertEqual([m.attrs.get("content") for m in doc.find("meta", name="description")], ["Synthetic site description"])
            self.assertEqual([m.attrs.get("content") for m in doc.find("meta", property="og:description")], ["Synthetic site description"])

    def test_custom_css_and_js_are_linked_and_copied(self):
        output = self.consumer({
            "static/css/synthetic-custom.css": "/* Synthetic test asset. */\n",
            "static/js/synthetic-custom.js": "// Synthetic test asset.\n",
        }, config='''[extra]
custom_css = ["css/synthetic-custom.css"]
custom_js = ["js/synthetic-custom.js"]
''')
        doc = self.document(output)
        self.assertEqual(len(doc.find("link", href=BASE_URL + "/css/synthetic-custom.css")), 1)
        self.assertEqual(len(doc.find("script", src=BASE_URL + "/js/synthetic-custom.js")), 1)
        self.assertTrue((output / "css/synthetic-custom.css").is_file())
        self.assertTrue((output / "js/synthetic-custom.js").is_file())

    def test_mode_styles_and_toggle_script_preserve_behavior(self):
        for mode in ("light", "dark", "auto", "toggle"):
            with self.subTest(mode=mode):
                output = self.consumer(config='[extra]\nmode = "' + mode + '"\nuseCDN = false\n')
                doc = self.document(output)
                dark = doc.find("link", id="darkModeStyle")
                self.assertEqual(len(dark), int(mode != "light"))
                if dark:
                    self.assertEqual(dark[0].attrs.get("href"), BASE_URL + "/css/dark.css")
                    self.assertEqual("disabled" in dark[0].attrs, mode == "toggle")
                    self.assertEqual(dark[0].attrs.get("media"), "(prefers-color-scheme: dark)" if mode == "auto" else None)
                toggles = doc.find("a", id="dark-mode-toggle")
                scripts = doc.find("script", src=BASE_URL + "/js/themetoggle.js")
                self.assertEqual(len(toggles), int(mode == "toggle"))
                self.assertEqual(len(scripts), int(mode == "toggle"))
                if toggles:
                    self.assertEqual(toggles[0].attrs.get("onclick"), "toggleTheme()")
                    self.assertTrue((output / "js/themetoggle.js").is_file())
                    self.assertTrue(doc.find("script", src=BASE_URL + "/js/feather.min.js"))

    def test_pagination_has_real_previous_and_next_destinations(self):
        output = self.consumer({
            "content/_index.md": '+++\nsort_by = "date"\npaginate_by = 1\n+++\n',
            "content/first.md": article("Synthetic newest", date="2026-01-03"),
            "content/second.md": article("Synthetic middle", date="2026-01-02"),
            "content/third.md": article("Synthetic oldest"),
        })
        for path, title, previous, next_ in (
            ("index.html", "Synthetic newest", None, "Synthetic middle"),
            ("page/2/index.html", "Synthetic middle", "Synthetic newest", "Synthetic oldest"),
            ("page/3/index.html", "Synthetic oldest", "Synthetic middle", None),
        ):
            doc = self.document(output, path)
            items = doc.find(class_="list-item")
            self.assertEqual(len(items), 1)
            self.assertIn(title, items[0].text)
            for label, expected in (("Previous", previous), ("Next", next_)):
                links = doc.find("a", **{"aria-label": label})
                self.assertEqual(len(links), int(expected is not None), path + " " + label)
                for link in links:
                    self.assertIn(label, link.text)
                    self.assert_local_link(output, link.attrs["href"], "/")
                    destination = unquote(urlsplit(link.attrs["href"]).path).lstrip("/") + "index.html"
                    target_items = self.document(output, destination).find(class_="list-item")
                    self.assertEqual(len(target_items), 1)
                    self.assertIn(expected, target_items[0].text)

    def multilingual(self, locale, translations=""):
        return self.consumer({
            "content/posts/hello.md": article("Synthetic English only", tags=["中文"], description="Synthetic English preview"),
            "content/_index." + locale + ".md": '+++\nsort_by = "date"\n+++\n',
            "content/posts/_index." + locale + ".md": '+++\nsort_by = "date"\ntemplate = "posts.html"\n+++\n',
            "content/posts/hello." + locale + ".md": article("Synthetic localized only", tags=["中文"], description="Synthetic localized preview"),
        }, config='\n[languages.' + locale + ']\ntaxonomies = [{name = "tags"}]\n' + translations)

    def test_multilingual_content_and_tags_use_current_language(self):
        output = self.multilingual("fr", '''
[extra.translations]
[[extra.translations.fr]]
show_more = "Lire la suite"
previous_page = "Précédent"
next_page = "Suivant"
posted_on = "le"
posted_by = "Publié par"
read_time = "minute de lecture"
all_tags = "Toutes les étiquettes"
menus = [{name = "Accueil synthétique", url = "/fr/", weight = 1}]
''')
        english = self.document(output)
        self.assertIn("Synthetic English only", english.text)
        self.assertNotIn("Synthetic localized only", english.text)
        french = self.document(output, "fr/index.html")
        self.assertEqual(french.find("html")[0].attrs.get("lang"), "fr")
        self.assertIn("Lire la suite", french.text)
        self.assertIn("Accueil synthétique", french.text)
        self.assertNotIn("Synthetic English only", french.text)
        cloud = self.document(output, "fr/tags/index.html")
        cloud_links = self.hrefs(cloud.find(class_="tag-cloud")[0])
        self.assertEqual(len(cloud_links), 1)
        self.assert_local_link(output, cloud_links[0], "/fr/tags/")
        term_path = unquote(urlsplit(cloud_links[0]).path).lstrip("/") + "index.html"
        for path in ("fr/index.html", "fr/posts/index.html", term_path):
            doc = self.document(output, path)
            links = [a.attrs["href"] for a in doc.find("a") if a.text == "Synthetic localized only"]
            self.assertTrue(links, path)
            for link in links:
                self.assert_local_link(output, link, "/fr/posts/")
            self.assertNotIn("Synthetic English only", doc.text)
        page = self.document(output, "fr/posts/hello/index.html")
        tag_links = [a.attrs["href"] for a in page.find("a") if a.text == "中文"]
        self.assertEqual(len(tag_links), 1)
        self.assert_local_link(output, tag_links[0], "/fr/tags/")
        self.assertIn("Toutes les étiquettes", self.document(output, "fr/tags/index.html").text)

    def test_missing_locale_translation_falls_back_to_english(self):
        output = self.multilingual("de")
        doc = self.document(output, "de/index.html")
        self.assertEqual(doc.find("html")[0].attrs.get("lang"), "de")
        self.assertIn("Read more", doc.text)
        self.assertIn("minute read", doc.text)
        self.assertIn("Synthetic localized only", doc.text)
        self.assertNotIn("Synthetic English only", doc.text)
        self.assertIn("All tags", self.document(output, "de/tags/index.html").text)
        page = self.document(output, "de/posts/hello/index.html")
        links = [a.attrs["href"] for a in page.find("a") if a.text == "中文"]
        self.assertEqual(len(links), 1)
        self.assert_local_link(output, links[0], "/de/tags/")

    def test_empty_posts_section_builds_without_phantom_posts(self):
        output = self.consumer()
        for path in ("index.html", "posts/index.html"):
            doc = self.document(output, path)
            self.assertFalse(doc.find(class_="list-item"))
            self.assertFalse(doc.find("a", class_="readmore"))

    def test_site_without_posts_section_builds(self):
        output = self.consumer(posts=False)
        doc = self.document(output)
        self.assertIn("Synthetic compatibility site", doc.text)
        self.assertFalse(doc.find(class_="list-item"))

    def test_repository_demo_builds_in_fresh_temporary_output(self):
        root = self.temporary()
        for name in ("config.toml", "theme.toml"):
            shutil.copy2(THEME_ROOT / name, root / name)
        for name in ("content", "templates", "static", "sass", "themes"):
            if (THEME_ROOT / name).is_dir():
                shutil.copytree(THEME_ROOT / name, root / name)
        output = self.build(root)
        self.assertTrue(self.document(output).find("html"))
        self.assertTrue((output / "posts/index.html").is_file())


if __name__ == "__main__":
    unittest.main()
