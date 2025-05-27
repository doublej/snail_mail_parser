from ruamel.yaml import YAML
from markdown_it import MarkdownIt

def save_output(letter, settings):
    """
    Save the LLM response as YAML and Markdown in the output directory.
    """
    out_dir = settings.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Prepare data dict for YAML
    data = {
        "id": letter.id,
        "sender": letter.sender,
        "date_sent": letter.date_sent,
        "subject": letter.subject,
        "type": letter.type,
        "content": letter.content,
        "qr_payloads": letter.qr_payloads,
        "payment": {
            "iban": letter.payment.iban,
            "amount": letter.payment.amount,
            "due_date": letter.payment.due_date
        }
    }

    # Write YAML file
    yaml_path = out_dir / f"{letter.id}.yaml"
    yaml = YAML()
    with open(yaml_path, 'w') as yf:
        yaml.dump(data, yf)

    # Prepare Markdown content with metadata header
    md_lines = []
    md_lines.append("---")
    md_lines.append(f"id: {letter.id}")
    md_lines.append(f"sender: {letter.sender}")
    md_lines.append(f"date_sent: {letter.date_sent}")
    md_lines.append(f"subject: {letter.subject}")
    md_lines.append(f"type: {letter.type}")
    md_lines.append("qr_payloads:")
    for payload in letter.qr_payloads:
        md_lines.append(f"  - {payload}")
    md_lines.append("payment:")
    md_lines.append(f"  iban: {letter.payment.iban}")
    md_lines.append(f"  amount: {letter.payment.amount}")
    md_lines.append(f"  due_date: {letter.payment.due_date}")
    md_lines.append("---\n")
    md_lines.append(letter.content)

    md_text = "\n".join(md_lines)
    # Optionally render with markdown-it-py (not strictly required)
    md = MarkdownIt()
    _ = md.render(md_text)  # Ensures formatting is valid

    # Write Markdown file
    md_path = out_dir / f"{letter.id}.md"
    with open(md_path, 'w') as mf:
        mf.write(md_text)
