import webbrowser
import markdown
import pandas as pd
import os
import re

import resend
import typer
from rich import print
from dotenv import load_dotenv

load_dotenv()
resend.api_key = os.environ["RESEND_API_KEY"]


def extract_vars(template_str: str) -> set[str]:
    pattern = r"\{\{(.*?)\}\}"
    return set(re.findall(pattern, template_str))


def interpolate_vars(template_str: str, val_dict: dict[str, str]) -> str:
    res = template_str
    for key, val in val_dict.items():
        res = res.replace(f"{{{{{key}}}}}", val)
    return res


def error(msg: str):
    print(f"    [red]error:[/red] {msg}")
    exit(1)


def warn(msg: str):
    print(f"    [yellow]warn:[/yellow] {msg}")


def info(msg: str):
    print(f"    [green]info:[/green] {msg}")


def main():
    csv: str = typer.prompt("❓ Data CSV", default="./data/form.csv")
    info(f"loading {csv}")

    df = pd.read_csv(csv)
    email_key: str = typer.prompt("\n❓ Email key in CSV", default="Email")
    df.drop_duplicates(subset=[email_key])

    template = typer.prompt("\n❓ Email template:", default="./data/email.temp.md")
    info(f"reading {template}")
    with open(template, "r") as file:
        template = file.read()

    vars = extract_vars(template)
    unresolved_vars = vars.difference(set(df.keys()))
    if len(unresolved_vars) > 0:
        error(f"unresolved variables found in template: {list(unresolved_vars)}")

    title_template = typer.prompt("\n❓ Email title template")

    info("generating emails")
    final_emails: dict[str, tuple[str, str]] = {}
    for _, row in df.iterrows():
        val_dict = {var: row[var] for var in vars}
        interpolated_body = interpolate_vars(template, val_dict)
        interpolated_title = interpolate_vars(title_template, val_dict)
        final_emails[row[email_key]] = (interpolated_title, interpolated_body)

    (sample_email, sample_email_content) = next(iter(final_emails.items()))
    sample_path = os.path.abspath(f"./tmp/{sample_email}.html")
    if not os.path.exists("./tmp"):
        os.mkdir("./tmp")
    with open(sample_path, "w") as file:
        sample_html = markdown.markdown(sample_email_content[1])
        file.write(sample_html)

    typer.prompt(
        "\n👀 Press enter to open preview...",
        default="",
        hide_input=True,
        show_default=False,
    )
    webbrowser.open(f"file://{sample_path}")

    typer.confirm(
        "\n❓ Do you want to continue and send emails", default=False, abort=True
    )

    params: list[resend.Emails.SendParams] = []
    email_pattern = r"^((?!\.)[\w\-_.]*[^.])(@\w+)(\.\w+(\.\w+)?[^.\W])$"

    for email, content in iter(final_emails.items()):
        if re.fullmatch(email_pattern, email) is None:
            warn(f"invalid email address: {email}")
            continue

        html = markdown.markdown(content[1])
        params.append(
            {
                "from": os.environ["SENDER"],
                "to": [email],
                "subject": content[0],
                "html": html,
            }
        )

    res = resend.Batch.send(params)
    print(f"😁 All emails sent successfully!\n{res}")


if __name__ == "__main__":
    typer.run(main)
