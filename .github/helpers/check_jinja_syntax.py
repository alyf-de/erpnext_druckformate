# Thanks to Vasili Syrakis and Ben on StackOverflow
# https://stackoverflow.com/a/37939821

from jinja2 import Environment, FileSystemLoader


def main():
	env = Environment(loader=FileSystemLoader("./print_format"))
	for template in env.list_templates():
		t = env.get_template(template)
		env.parse(t)


if __name__ == "__main__":
	main()
