import os
from getpass import getpass
from subprocess import run

from frappeclient import FrappeClient

ERPNEXT_URL = 'https://erp.alyf.cloud' # Bitte anpassen!
PRINT_STYLE_PATH = 'print_style/print_style'
PRINT_FORMATS = {
	# 'Dateiname': 'Name des Print Format in ERPNext'
	'quotation.html': 'Angebot', # Bitte anpassen!
	'sales_invoice.html': 'Ausgangsrechnung', # Bitte anpassen!
	'sales_order.html': 'Kundenauftrag' # Bitte anpassen!
}

def update_css():
	input_path = PRINT_STYLE_PATH + '.scss'
	output_path = PRINT_STYLE_PATH + '.css'
	run(['sass', '--style=compressed', input_path, output_path], check=True)
	return output_path

def main():
	password = getpass()
	username = input('Username: ')

	css = None
	css_path = update_css()
	with open(css_path) as css_file:
		css = css_file.read()

	client = FrappeClient(url=ERPNEXT_URL, username=username, password=password)
	with os.scandir('print_format') as it:
		for entry in it:
			html = None

			if entry.name not in PRINT_FORMATS:
				continue

			with open(entry.path) as html_file:
				html = html_file.read()

			client.update({
				'doctype': 'Print Format',
				'name': PRINT_FORMATS.get(entry.name),
				'html': html,
				'css': css
			})

if __name__ == '__main__':
	main()
