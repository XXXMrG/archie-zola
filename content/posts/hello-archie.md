+++
title = "Hello archie"
date = "2022-05-14"
description = "See how to config your archie theme"

[taxonomies]
tags = ["showcase"]

[extra]
author = { name = "XXXMRG", social= "https://github.com/XXXMrG" }
+++

## Demo

---

The Main branch source code hosted on <https://archie-zola.vercel.app/>

### ScreenShot

![screenshot light](/screenshot/screenshot-light.png)

![screenshot dark](/screenshot/screenshot-dark.png)

## Installation

---

First download this theme to your themes directory:

```bash
cd themes
git clone https://github.com/XXXMrG/archie-zola.git
```

or add as a git submodule:

```bash
git submodule add https://github.com/XXXMrG/archie-zola.git  themes/archie-zola
```

and then enable it in your config.toml:

```toml
theme = "archie-zola"
```

## Feature

---

- Pagination
- Tags
- Auto Dark Mode(based on system theme)
- Dark/Light Mode toggle

in the planning stage：

- [ ] Google Analytics Script
- [ ] Custom CSS & JS
- [ ] Twitter Cards & Youtube video

## Config

---

### Theme config

Cause Zola limited custom config must under the `extra` field, so there are some different with the origin theme:

Demo website config.toml:

```toml
# control dark mode: auto | dark | toggle
mode = "toggle"

# subtitle will show under the title in index page
subtitle = "A zola theme forked from [archie](https://github.com/athul/archie)"

# if set true, will use external CDN resource to load font and js file
useCDN = false

favicon = "/icon/favicon.png"

# show in the footer
copyright = "keith"

# config your Google Analysis ID
ga = "XXXX-XXXXX"

# optional: config your i18n entry
[extra.translations]
languages = [{name = "en", url = "/"}]

# config multi-language menu and other text
[[extra.translations.en]]
show_more = "Read more ⟶"
previous_page = "← Previous"
next_page = "Next →"
posted_on = "on "
posted_by = "Published by"
read_time = "minute read"
all_tags = "All tags"
menus = [
    { name = "Home", url = "/", weight = 2 },
    { name = "All posts", url = "/posts", weight = 2 },
    { name = "About", url = "/about", weight = 3 },
    { name = "Tags", url = "/tags", weight = 4 },
]

# config social icon info in the footer
[[extra.social]]
icon = "github"
name = "GitHub"
url = "https://github.com/XXXMrG/archie-zola"

[[extra.social]]
icon = "twitter"
name = "Twitter"
url = "https://github.com/your-name/"

[[extra.social]]
icon = "gitlab"
name = "GitLab"
url = "https://gitlab.com/your-name/"

```

### Latex math formula support

This theme support latex math formula, by using [KaTeX](https://katex.org/).

You can enable it by add `katex_enable = true` in the `extra` section of config.toml:

```toml
[extra]
katex_enable = true
```

After that, you can use latex math formula in your markdown file:

$$
{x: \mathbf{Num},\ y: \mathbf{Num} \over x + y : \mathbf{Num} }\ (\text{N-Add})
$$

You can also use inline and block-style:

1. \\( \KaTeX \\) inline
2. \\[ \KaTeX \\]
3. $$ \KaTeX $$

### Content config

**In content/posts/\_index.md. I use Zola config: transparent = true to implement the pagination**

In Zola, you can use config in the \_index.md to control pagination and sort post list:

```toml
paginate_by = 3
sort_by = "date"

[taxonomies]
tags = ["FE", "Rust"]

[extra]
author = { name = "XXXMRG", social= "https://github.com/XXXMrG" }
```

## Extension

Follow this [doc](https://www.getzola.org/documentation/themes/extending-a-theme/) to extend theme.

## Contributing

---

Thank you very much for considering contributing to this project!

We appreciate any form of contribution:

- New issues (feature requests, bug reports, questions, ideas, ...)
- Pull requests (documentation improvements, code improvements, new features, ...)[^zolawebsite]

[^zolawebsite]: Website: [zola](https://getzola.org), GitHub: [getzola/zola](https://github.com/getzola/zola)
