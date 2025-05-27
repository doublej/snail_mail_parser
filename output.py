from ruamel.yaml import YAML
from markdown_it import MarkdownIt
from llm import LetterLLMResponse, DocumentType # Import necessary types
from enum import Enum # For isinstance check

def save_output(letter: LetterLLMResponse, settings): # Add type hint
    """
    Save the LLM response as YAML and Markdown in the output directory.
    """
    out_dir = settings.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Handle payment information safely for YAML data
    payment_data_yaml = {}
    if letter.payment is not None:
        payment_data_yaml = {
            "iban": letter.payment.iban,
            "amount": letter.payment.amount,
            "due_date": letter.payment.due_date
        }
    else:
        payment_data_yaml = {
            "iban": None,
            "amount": None,
            "due_date": None
        }
    
    # Serialize letter.type to its value if it's an Enum instance
    letter_type_value = letter.type.value if isinstance(letter.type, Enum) else letter.type

    # Prepare data dict for YAML
    data = {
        "id": letter.id,
        "sender": letter.sender,
        "date_sent": letter.date_sent,
        "subject": letter.subject,
        "type": letter_type_value, # Use serialized value
        "content": letter.content,
        "qr_payloads": letter.qr_payloads,
        "payment": payment_data_yaml, # Use safely constructed payment_data_yaml
        "is_multipage_explicit": letter.is_multipage_explicit,
        "is_information_complete": letter.is_information_complete,
        "belongs_to_open_doc_id": letter.belongs_to_open_doc_id
    }

    # Write YAML file
    yaml_path = out_dir / f"{letter.id}.yaml"
    yaml = YAML()
    with open(yaml_path, 'w', encoding='utf-8') as yf: # Added encoding
        yaml.dump(data, yf)

    # Prepare Markdown content with metadata header
    md_lines = []
    md_lines.append("---")
    md_lines.append(f"id: {letter.id}")
    md_lines.append(f"sender: {letter.sender}")
    md_lines.append(f"date_sent: {letter.date_sent}")
    md_lines.append(f"subject: {letter.subject}")
    md_lines.append(f"type: {letter_type_value}") # Use serialized value
    md_lines.append("qr_payloads:")
    # Pydantic model should ensure qr_payloads is a list, but check for None if it could be optional
    if letter.qr_payloads is not None:
        for payload in letter.qr_payloads:
            md_lines.append(f"  - {payload}")
    else:
        md_lines.append("  - None") # Or handle as empty list as appropriate
    
    # Handle payment information safely for Markdown
    md_lines.append("payment:")
    if letter.payment is not None:
        md_lines.append(f"  iban: {letter.payment.iban if letter.payment.iban is not None else 'None'}")
        md_lines.append(f"  amount: {letter.payment.amount if letter.payment.amount is not None else 'None'}")
        md_lines.append(f"  due_date: {letter.payment.due_date if letter.payment.due_date is not None else 'None'}")
    else:
        md_lines.append(f"  iban: None")
        md_lines.append(f"  amount: None")
        md_lines.append(f"  due_date: None")

    # Add multi-page fields to Markdown metadata
    md_lines.append(f"is_multipage_explicit: {letter.is_multipage_explicit}")
    md_lines.append(f"is_information_complete: {letter.is_information_complete}")
    md_lines.append(f"belongs_to_open_doc_id: {letter.belongs_to_open_doc_id if letter.belongs_to_open_doc_id is not None else 'None'}")

    md_lines.append("---\n")
    md_lines.append(letter.content if letter.content is not None else "") # Ensure content is not None

    md_text = "\n".join(md_lines)
    
    # The markdown-it rendering was for validation and can be removed as per instructions.
    # md = MarkdownIt()
    # _ = md.render(md_text) 

    # Write Markdown file
    md_path = out_dir / f"{letter.id}.md"
    with open(md_path, 'w', encoding='utf-8') as mf: # Added encoding
        mf.write(md_text)
