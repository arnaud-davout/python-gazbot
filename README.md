# python-gazbot

Automated family **gazette** bot: fetches contributions sent to a dedicated mailbox, compiles them into a single PDF newsletter, and sends it back to the subscriber list. A reminder mode can also be used to nudge contributors who haven't written yet.

## Features
- Reads contributions from an IMAP inbox.
- Generates a PDF gazette with per-contributor titles, a participation rate header, and a list of contributors.
- Embeds images directly in the PDF (both inline images referenced in the HTML body and images sent as attachments).
- Re-sends non-image attachments alongside the gazette email.
- Sends reminder emails to contributors who haven't written during the current cycle.

## Requirements
- Python >= 3.8
- [wkhtmltopdf](https://wkhtmltopdf.org/) (must be installed and available on `PATH`)
- Python packages listed in `requirements.txt` ([pdfkit](https://pypi.org/project/pdfkit/))

## Installation
Set up the virtual environment and install dependencies:
```bash
./venvsetup.sh
source .venv/bin/activate
```

## Address file
The bot takes a plain-text address file where each line maps a contributor name to one or more email addresses, using `;` as a separator:
```
alice@example.com,alice.work@example.com;Alice
bob@example.com;Bob
```
- Left side: comma-separated list of allowed sender addresses.
- Right side: contributor display name used in the gazette.

## Usage

### Direct send (default, e.g. self-hosted mail server with working reverse DNS)
Omit all `--smtp_*` arguments. The bot will submit through the IMAP host on port 587 with STARTTLS, reusing the IMAP credentials for authentication, and using `HOST_ADDRESS` (defined at the top of `gazbot.py`) as the `From` field. Authentication is still required (otherwise the server refuses to relay to external recipients); reverse DNS only matters so that the resulting outgoing email isn't rejected by the destination.
```bash
python gazbot.py \
  --server imap.example.com \
  --username gazette@example.com \
  --password <imap-password> \
  --address addresses.txt \
  [--gazette 1 | --reminder <days>]
```

### Through an SMTP relay (e.g. ISP without reverse DNS)
Provide the `--smtp_*` arguments; the bot will connect on port 587 with STARTTLS and authenticate:
```bash
python gazbot.py \
  --server imap.example.com \
  --username gazette@example.com \
  --password <imap-password> \
  --address addresses.txt \
  --smtp_server smtp.example.com \
  --smtp_username gazette@example.com \
  --smtp_password <smtp-password> \
  --smtp_sender gazette@example.com \
  [--gazette 1 | --reminder <days>]
```

### Modes
- `--gazette 1`: fetch recent contributions, build the PDF gazette, email it to all subscribers, then clean up the workspace.
- `--reminder <days>`: send a reminder email to contributors who have not written during the current window.

Only messages received within the last `MAX_DELTA_DAYS` days (15 by default, see `gazbot.py`) from known senders are included.

## How contributions are parsed
For each email, the bot walks the MIME tree and handles each part:
- `text/html` → used as the body (preferred over plain text).
- `text/plain` → used as the body if no HTML part is present.
- `image/*` → saved to `data/images/` and embedded in the PDF:
  - inline images (with a `Content-ID`) replace the matching `cid:` reference in the HTML body;
  - images without a `Content-ID` are appended at the end of the contributor's section.
- Other attachments → saved to `data/attachments/` and re-attached to the outgoing gazette email.

## Output layout
During a run the bot uses two directories:
- `data/` — scratch workspace (HTML, PDF, images, attachments). Deleted at the end of a successful run.
- `publish/Gazette_<YYYY_MM_DD>/` — the generated HTML is archived here after each run.

## Key dates (HOWTO)
See [HOWTO.md](HOWTO.md) for the contributor-facing rules (subject line, deadlines, size limits, reminder schedule).

## Project layout
- `gazbot.py` — main entry point and `GazBot` class.
- `send_email.py` — SMTP helper used to send the gazette and reminders.
- `style.css` — stylesheet applied when rendering the PDF.
- `venvsetup.sh`, `setup.py`, `requirements.txt` — environment setup.
- `HOWTO.md` — contributor guide (French).
