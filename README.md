# ERPNext-Druckformate nach DIN 5008

> Entwickelt und getestet für ERPNext `version-13`. (Kann mit kleinen Anpassungen auch für andere Versionen verwendet werden.)

* `letter_head.html`: HTML und CSS für die Fußzeile.
* `print_style/print_style.scss`: Einheitliches CSS für alle Druckformate.
* `print_format/*.jinja`: Jinja HTML-Template für den jeweiligen DocType.

## Abhängigkeiten

[Sass](https://sass-lang.com/install) wird benötigt, um das SCSS zu CSS zu kompilieren (`npm install -g sass` oder `brew install sass/sass/sass`).

Der folgende Befehl erzeugt die Datei `print_style.css` im Ordner `print_style`:

```
sass --style=compressed print_style/print_style.scss print_style/print_style.css
```

## Migrating into a Frappe app (recommended)

Instead of syncing print formats over REST with `update.py`, you can scaffold them directly into a Frappe app. The print formats then live in the app, are versioned with it, and are re-installed on every `bench migrate` (and `bench install-app`).

### One-shot migration with `frappe-pf-init`

This repo ships a CLI that takes any erpnext_druckformate-style print-format repo (this one or a fork) and scaffolds a `print_format_sources/` folder into a target Frappe app. Run it from inside the print-format repo and pass the target app's repo root:

```bash
# In a clone of this repo (or any conforming print-format repo):
uvx --from git+https://github.com/alyf-de/erpnext_druckformate frappe-pf-init /path/to/your_frappe_app
```

What it does:

- Reads `config.ini`, copies referenced templates from `print_format/` to `<app>/<app>/print_format_sources/`.
- Compiles `print_style/*.scss` to `<app>/<app>/print_format_sources/print_formats.css` (no Node/brew dep — uses `libsass`). Output is expanded (multi-line) so it stays readable in Desk's Print Format editor.
- Generates a Pythonic `<app>/<app>/print_format_sources/config.py` with one entry per format.
- Drops in a small builder (`print_formats.py`) that reads the config + templates and imports them into Frappe via `import_doc`.
- Adds `sync_print_formats` to `after_migrate` and `after_install` in `<app>/<app>/hooks.py`. Existing hook entries are preserved: a string-form value (`after_install = "..."`) is expanded to a list with both entries; an existing list is appended to. Already-present entries are detected and skipped.
- Writes a `.synced` marker (source repo URL + commit + timestamp) for traceability.

The migrator never touches `install.py` — installing the print formats on `bench install-app` is handled by the `after_install` hook entry in `hooks.py`, so it works equally well for apps that don't have an `install.py`.

Flags:

- `--source PATH` — point at a different print-format repo (default: current directory).
- `--dry-run` — print the planned changes without writing.
- `--force` — overwrite an existing `print_format_sources/` folder.

### What you need in your source repo

For the migrator to work, the source repo must follow this layout (this is the layout of `erpnext_druckformate` itself):

- `config.ini` at the repo root — `[Section]` titles become **Print Format** names, with required `DocType` and `TemplateFile` keys.
- `print_format/*.jinja` — the templates referenced by `config.ini`.
- `print_style/*.scss` — one shared SCSS file (compiled into `print_formats.css` in the target).

### Source-repo layout (assumed by `frappe-pf-init`)

```
<source-repo>/
    config.ini             # [Section] DocType=... TemplateFile=print_format/foo.jinja
    print_format/*.jinja
    print_style/*.scss     # one shared file
```

### Target-app layout (after migration)

```
<app>/<app>/print_format_sources/
    __init__.py
    config.py              # generated from config.ini
    print_formats.py       # builder + sync_print_formats() (after_migrate hook)
    print_formats.css      # compiled from print_style/*.scss
    *.jinja                # copied from print_format/
    .synced                # source repo URL + commit + timestamp
```

### Post-install checklist

The migrator can't move app-side helpers your templates may rely on. After running:

1. **Custom Jinja helpers.** If your templates use functions like `split_quill` or other custom filters, expose them via your app's `jinja` hook (see Frappe docs).
2. **Trim** any print formats from `config.py` that you don't want to ship (the source repo may include more than your app needs).
3. **Run** `bench --site <site> migrate` to verify the formats land cleanly in Desk.
4. **Note**: the migrator is one-shot — re-running against the same target requires `--force`. To pull future updates from the source repo, do a manual `git diff` of the source's `print_format/` against your `<app>/<app>/print_format_sources/`.

---

## Legacy: `update.py` (REST sync)

The script `update.py` can be used to automatically update your print formats in ERPNext (without copy + paste). Prefer the migrator above when starting a new project; `update.py` remains useful for ad-hoc updates against a running site.

### Setup

1. Create a virtual environment:

    ```
    python3.10 -m venv env
    ```

2. Activate the virtual environment:

    ```
    source env/bin/activate # Linux / MacOS
    env\Scripts\activate # Windows
    ```

3. Install dependencies:

    ```
    pip install -r requirements.txt
    ```

4. Copy `.env.example` into `.env` and set your `BASE_URL`, `USER` and `PASSWORD`.

### Usage

Your virtual environment needs to be activated before running the script. If it's not, run `source env/bin/activate` again.

If everything is configured correctly, you can just run `python update.py`.

For more detailed configuration options, run `python update.py --help`.

### VSCode Integration

VSCode can automatically push print formats to your ERPNext instance. For this, you'll need to set up your environment as described above and install the extension [File Watcher](https://marketplace.visualstudio.com/items?itemName=appulate.filewatcher).

When you change one of the templates, just this one template will be synced to the server.

When you change the SCSS file, all templates will be synced, since they all use the same CSS.

### Windows compatibility

On Windows, the sass compilation from Python might not work. This can be possibly fixed by editing `update.py` like this:

```diff
def get_css(input_path: Path) -> str:
    return run(
-        ["sass", "--style=compressed", input_path], check=True, capture_output=True
+        ["sass", "--style=compressed", input_path], check=True, capture_output=True, shell=True
    ).stdout.decode()
```

## Einrichtung

1. Neuen **Letter Head** (dt. Briefkopf) erstellen

    1. Den Inhalt von `letter_head.jinja` in das Feld "Footer HTML" kopieren.

        ![Letter Head](docs/letter_head.png)

    2. Einen Briefkopf als Bild oder HTML hinterlegen

2. **Company** (dt. Unternehmen) öffnen und

   1. Den im vorigen Schritt erstellten **Letter Head** als "Default Letter Head" hinterlegen.
   2. Eine Adresse für das Unternehmen hinzufügen. Diese erscheint im Druckformat als Absender.

3. **Address Template** für die Zielländer anlegen. Der Einfachheit halber kann ein **Address Template** für das eigene Land und ein weiteres für alle anderen Länder angelegt werden.

    **Germany**:

    ```jinja
    {{ address_line1 }}<br>
    {% if address_line2 %}{{ address_line2 }}<br>{% endif -%}
    {{ pincode }} {{ city }}<br>
    ```

    **All Countries** (_Is Default_ aktivieren):

    ```jinja
    {{ address_line1 }}<br>
    {% if address_line2 %}{{ address_line2 }}<br>{% endif -%}
    {% if pincode %}{{ pincode }} {% endif -%}{{ city }}<br>
    {% if state %}{{ state }}<br>{% endif -%}
    {{ country | upper }}
    ```

4. **Print Format** (dt. Druckformat) für **Quotation** (dt. Angebot), **Sales Invoice** (dt. Verkaufsrechnung) und **Sales Order** (dt. Auftrag) anlegen. Hierzu den Inhalt der jeweiligen Datei aus dem Order `print_format` und das CSS aus `print_style/print_style.css` kopieren.

    ![Print Format](docs/print_format.png)

5. Über **Customize Form** (dt. Formular anpassen) das "Default Print Format" für den jeweiligen DocType hinterlegen


## Anpassung und Entwicklung

### Print Style

Es ist wichtig, dass möglichst jeder CSS-Block im Scope von `.print-format` und damit auf das Druckformat beschränkt ist. Andernfalls wirkt sicher der Stil auf das gesamte System aus.

### Jinja

Alle Druckformate sind [Jinja Templates](https://jinja.palletsprojects.com/en/2.11.x/templates/). Das heißt, es kann über das dictionary `doc` auf alle Felder des DocTypes zugegriffen werden. Bei Rechnungen steckt hinter `{{ doc.due_date }}` beispielsweise das Fälligkeitdatum und hinter `{{ doc.name }}` die Rechnungsnummer. Der Befehl `{{ doc.get_formatted('due_date') }}` gibt das Fälligkeitdatum (oder jedes andere Feld) schön formatiert aus (24.12.2020 statt 2020-12-24, € 10,00 statt 10.0, etc.).

Außerdem können einige Python- und Frappe-Funktionen genutzt werden. Beipielsweise hinterlegt `{% set company = frappe.get_doc("Company", doc.company) %}` alle Daten des zugehörigen Unternehmens in der variable `company`. Danach könnte beispielsweise die dort hinterlegte Website mit `{{ company.website }}` eingefügt werden.

Frappe stellt einige eigene Variablen wie `footer` oder `print_settings` zur Verfügung, die in jedem Print Format genutzt werden können. Eine Auflistung der verfügbaren Variablen und Funktionen finden sich hier:

- [Frappe Jinja API](https://frappeframework.com/docs/v13/user/en/api/jinja)
- [safe_exec.py](https://github.com/frappe/frappe/blob/version-13/frappe/utils/safe_exec.py)
- [printview.py](https://github.com/frappe/frappe/blob/4c6b58da2699189e6992707254f7a95f5c7df64a/frappe/www/printview.py#L148-L157).

Weitere Dateien, die dem Verständnis, der Inspiration oder Fehlersuche dienen können:

- [standard.css](https://github.com/frappe/frappe/blob/8b7c976f680b2aac1b33cf45720beaf653ccdad0/frappe/templates/styles/standard.css)

    CSS für das Standard-Druckformat

- [standard.html](https://github.com/frappe/frappe/blob/8b7c976f680b2aac1b33cf45720beaf653ccdad0/frappe/templates/print_formats/standard.html)

    Jinja-Template für das Standard-Druckformat

### Übersetzungen

Alle Dokumente sollten mehrsprachig funktionieren. Hier wird insbesondere auf Deutsch und Englisch geachtet.

Kurze Begriffe können mit `_("Translate me!")` übersetzt werden. Hierbei ist in der Regel der englische Begriff als Grundlage verwenden, der dann bei Bedarf ad-hoc ins Deutsche übersetzt wird.

Sätze und längere Texte können per if-Statement übersetzt werden:

```jinja
{% if frappe.lang == "de" %}
    <p>Sehr geehrte Damen und Herren,<p>
{% else %}
    <p>Dear Sir or Madam,<p>
{% endif %}
```

## Unterstützung erhalten

Wenn Sie Unterstützung bei der Anpassung der Druckformate benötigen, kontaktieren Sie uns gerne. Alle Kontaktdaten finden Sie auf [unserer Webseite](https://alyf.de).
