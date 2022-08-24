import os
import pathlib
from getpass import getpass
from subprocess import run

import typer
from frappeclient import FrappeClient

ERPNEXT_URL = "https://erp.alyf.cloud"  # TODO: eigene URL eintragen
PRINT_STYLE_PATH = "print_style/print_style"
PRINT_FORMATS = {
	# 'Dateiname': 'Name des Print Format in ERPNext'
	# TODO: die verwendeten Namen anpassen oder auskommentieren
	"quotation.html": "Angebot",
	"sales_order.html": "Kundenauftrag",
	"sales_invoice.html": "Ausgangsrechnung",
	"delivery_note.html": "Lieferschein",
	"purchase_order.html": "Bestellung",
	"request_for_quotation.html": "Angebotsanfrage",
}


def update_css():
	input_path = f"{PRINT_STYLE_PATH}.scss"
	output_path = f"{PRINT_STYLE_PATH}.css"
	run(["sass", "--style=compressed", input_path, output_path], check=True)
	return output_path


def main(username: str = None, password: str = None):
	while not username:
		username = input("Username: ")

	while not password:
		password = getpass()

	css = None
	css_path = update_css()
	css = pathlib.Path(css_path).read_text()
	client = FrappeClient(url=ERPNEXT_URL, username=username, password=password)
	with os.scandir("print_format") as it:
		for entry in it:
			html = None

			if entry.name not in PRINT_FORMATS:
				continue

			html = pathlib.Path(entry.path).read_text()
			client.update(
				{
					"doctype": "Print Format",
					"name": PRINT_FORMATS.get(entry.name),
					"html": html,
					"css": css,
				}
			)


if __name__ == "__main__":
	typer.run(main)
