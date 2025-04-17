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

## Update script

The script `update.py` can be used to automatically update your print formats in ERPNext (without copy + paste).

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
