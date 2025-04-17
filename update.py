from configparser import ConfigParser
from getpass import getpass
from pathlib import Path
from subprocess import run

import typer
from dotenv import dotenv_values

from frappeclient import FrappeClient


def abspath(relpath: str) -> Path:
    return Path(__file__).parent / relpath


def get_css(input_path: Path) -> str:
    return run(
        ["sass", "--style=compressed", input_path], check=True, capture_output=True
    ).stdout.decode()


def get_credentials(
    base_url: str | None,
    username: str | None,
    password: str | None,
) -> tuple[str, str, str]:
    env = dotenv_values(".env")
    base_url = base_url or env.get("BASE_URL")
    username = username or env.get("USER")
    password = password or env.get("PASSWORD")

    while not base_url:
        base_url = input("Base URL: ")

    while not username:
        username = input("Username: ")

    while not password:
        password = getpass()

    return base_url, username, password


def print_format_dict(
    print_format_name: str,
    doctype: str,
    module: str | None,
    html: str,
    css: str,
    is_standard: bool,
) -> dict:
    data = {
        "doctype": "Print Format",
        "name": print_format_name,
        "doc_type": doctype,
        "custom_format": 1,
        "html": html,
        "css": css,
        "print_format_type": "Jinja",
        "standard": "Yes" if is_standard else "No",
    }
    if module:
        data["module"] = module

    return data


def sync(client: FrappeClient, print_format: dict) -> None:
    if client.get_list(
        "Print Format", fields=["name"], filters={"name": print_format["name"]}
    ):
        client.update(print_format)
    else:
        client.insert(print_format)


def main(
    base_url: str = None,
    username: str = None,
    password: str = None,
    config_file: str = None,
    only_template: str = None,
):
    base_url, username, password = get_credentials(username, password, base_url)
    client = FrappeClient(url=base_url, username=username, password=password)

    config = ConfigParser()
    config.read(abspath(config_file or "config.ini"))
    css = get_css(abspath(config.get("DEFAULT", "ScssFile")))
    for print_format_name in config.sections():
        file_path = abspath(config.get(print_format_name, "TemplateFile"))

        if only_template and Path(only_template).name != file_path.name:
            continue

        print(f"Syncing {file_path.name} -> Print Format '{print_format_name}'")
        sync(
            client,
            print_format_dict(
                print_format_name,
                doctype=config.get(print_format_name, "DocType"),
                module=config.get(print_format_name, "Module", fallback=None),
                html=file_path.read_text(),
                css=css,
                is_standard=config.getboolean(print_format_name, "IsStandard"),
            ),
        )


if __name__ == "__main__":
    typer.run(main)
