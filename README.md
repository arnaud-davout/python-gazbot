# python-gazbot

## Automated gazette bot

Requirements :
- Python >= 3.8
- wkhtmltopdf - https://wkhtmltopdf.org/
- pdfkit - https://pypi.org/project/pdfkit/

Install virtual environment:
```bash
./venvsetup.sh
```

Use :
- Setup an address file
- Have a mail server up and running
- Launch gazbot:
```python
usage: gazbot.py [-h] --server SERVER --username USERNAME --password PASSWORD --address ADDRESS [--gazette GAZETTE] [--reminder REMINDER]
```

## Image handling
Images sent by contributors are embedded directly in the generated PDF:
- Inline images in the HTML body (referenced via `cid:`) are resolved and rendered in place.
- Images sent as attachments are appended at the end of their author's section.
- Non-image attachments keep their previous behavior and are re-sent alongside the gazette email.