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