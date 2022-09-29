import os
import pathlib
from getpass import getpass
from subprocess import run

import typer
from frappeclient import FrappeClient

ERPNEXT_URL = "https://master.alyf.cloud"  # TODO: eigene URL eintragen
PRINT_STYLE_PATH = "print_style/print_style"
PRINT_FORMATS = {
	# 'Dateiname': 'Name des Print Format in ERPNext'
	# TODO: die verwendeten Namen anpassen oder auskommentieren
	"quotation.jinja": "Angebot",
	"sales_order.jinja": "Auftragsbestätigung",
	"sales_invoice.jinja": "Ausgangsrechnung",
	"delivery_note.jinja": "Lieferschein",
	"purchase_order.jinja": "Bestellung",
	"request_for_quotation.jinja": "Angebotsanfrage",
}
LETTER_HEAD = ("letter_head.jinja", "ALYF GmbH")


def get_updated_css(input_path: str, output_path: str) -> str:
	typer.echo(f"Building CSS {input_path} -> {output_path}")
	run(["sass", "--style=compressed", f"{PRINT_STYLE_PATH}.scss", output_path], check=True)
	return pathlib.Path(output_path).read_text()


def update_print_format(client: FrappeClient, source_path, css: str, target_name: str):
	typer.echo(f"Syncing {source_path} -> Print Format '{target_name}'")
	client.update(
		{
			"doctype": "Print Format",
			"name": target_name,
			"html": pathlib.Path(source_path).read_text(),
			"css": css,
		}
	)


def update_letter_head(client: FrappeClient, source_path: str, target_name: str):
	typer.echo(f"Syncing {source_path} -> Letter Head '{target_name}'")

	return client.update(
		{
			"doctype": "Letter Head",
			"name": target_name,
			"footer": pathlib.Path(source_path).read_text(),
		}
	)


def main(username: str = None, password: str = None):
	while not username:
		username = input("Username: ")

	while not password:
		password = getpass()

	css = get_updated_css(f"{PRINT_STYLE_PATH}.scss", f"{PRINT_STYLE_PATH}.css")
	client = FrappeClient(url=ERPNEXT_URL, username=username, password=password)
	with os.scandir("print_format") as it:
		for entry in it:
			if entry.name not in PRINT_FORMATS:
				continue

			print_format_name = PRINT_FORMATS.get(entry.name)
			update_print_format(client, entry.path, css, print_format_name)

	update_letter_head(client, *LETTER_HEAD)


if __name__ == "__main__":
	typer.run(main)
