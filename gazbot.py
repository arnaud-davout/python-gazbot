# -*- coding: utf-8 -*-
import imaplib
import email
from email.message import EmailMessage
from email.header import decode_header, make_header
from email.utils import parseaddr
import os, shutil
import argparse
import re
import uuid
from datetime import date
import pdfkit
from send_email import send_mail

MAX_DELTA_DAYS = 15
HOST_ADDRESS = '"GazBot" <gazette@famille.davout.net>'

__VERSION__ = "1.0"
GITHUB = "https://github.com/arnaud-davout/python-gazbot"
HOWTO = "https://github.com/arnaud-davout/python-gazbot/blob/main/HOWTO.md"
SIGNATURE = '<br><br><br>---<br>PyGazetteBot v' + __VERSION__ + ' | <a href=' + HOWTO + '>Gazette HOW-TO</a> | <a href=' + GITHUB + '>GitHub</a>'

# Tags whose entire content is stripped (active content / external loaders).
_UNSAFE_BLOCK_TAGS = ('script', 'iframe', 'object', 'embed', 'applet', 'style')
# Standalone tags that only load resources or trigger navigation.
_UNSAFE_VOID_TAGS = ('link', 'meta', 'base')


def sanitize_html(html):
    """Strip active/exfiltration vectors from untrusted email HTML.

    Email bodies come from arbitrary senders and are later rendered to PDF by
    wkhtmltopdf with local-file access enabled. Without this, a crafted email
    can execute JavaScript and exfiltrate local files (see pdfkit CVE). We
    remove scripts, external loaders, inline event handlers and dangerous URI
    schemes while preserving ordinary formatting. The app inserts its own
    trusted ``file://`` images *after* sanitization, so stripping ``file:``
    here only affects attacker-supplied content.
    """
    if not html:
        return html
    # Drop unsafe blocks together with their content.
    for tag in _UNSAFE_BLOCK_TAGS:
        html = re.sub(r'<{0}\b[^>]*>.*?</{0}>'.format(tag), '',
                      html, flags=re.IGNORECASE | re.DOTALL)
        # Also drop a dangling/self-closed opening tag with no matching close.
        html = re.sub(r'<{0}\b[^>]*/?>'.format(tag), '',
                      html, flags=re.IGNORECASE)
    # Drop resource-loading / navigation void tags.
    for tag in _UNSAFE_VOID_TAGS:
        html = re.sub(r'<{0}\b[^>]*/?>'.format(tag), '',
                      html, flags=re.IGNORECASE)
    # Strip inline event handlers, e.g. onclick="..." / onload='...'.
    html = re.sub(r'\son\w+\s*=\s*"[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r"\son\w+\s*=\s*'[^']*'", '', html, flags=re.IGNORECASE)
    html = re.sub(r'\son\w+\s*=\s*[^\s>]+', '', html, flags=re.IGNORECASE)
    # Neutralise dangerous URI schemes in attacker-supplied markup.
    html = re.sub(r'(javascript|vbscript|file|data)\s*:', 'blocked:',
                  html, flags=re.IGNORECASE)
    return html


def safe_join(directory, filename):
    """Join an untrusted filename into ``directory`` without escaping it.

    Attachment/image filenames come from arbitrary emails and must not be able
    to traverse out of the workspace (e.g. ``../../.ssh/authorized_keys`` or an
    absolute path). Returns the safe absolute path, or ``None`` if the filename
    is empty or would resolve outside ``directory``.
    """
    base = os.path.basename(filename or '')
    if base in ('', '.', '..'):
        return None
    directory_abs = os.path.abspath(directory)
    candidate = os.path.abspath(os.path.join(directory_abs, base))
    if os.path.commonpath([directory_abs, candidate]) != directory_abs:
        return None
    return candidate


def parse_from_address(raw_from):
    """Return the lowercased email address from a raw (possibly RFC2047) From header."""
    decoded = str(make_header(decode_header(raw_from or '')))
    _name, addr = parseaddr(decoded)
    return addr.lower()


def parse_addresses(lines):
    """Parse address-file lines into ``{contributor_name: [addresses]}``.

    Each non-empty line is ``addr1,addr2,...:Name``. Blank lines and lines
    without a ``:`` separator are ignored.
    """
    result = {}
    for line in lines:
        line = line.strip()
        if not line or ':' not in line:
            continue
        addresses, name = line.rsplit(':', 1)
        result[name.strip()] = [a.strip() for a in addresses.split(',') if a.strip()]
    return result


class GazBot:
    def __init__(self, server, username, password, smtp_server=None, smtp_username=None, smtp_password=None, smtp_sender=None):
        self.imap = imaplib.IMAP4_SSL(server)
        self.server = server
        self.username = username
        self.password = password
        if smtp_server:
            self.smtp_server = smtp_server
            self.smtp_port = 587
            self.smtp_use_tls = True
            self.smtp_username = smtp_username or ''
            self.smtp_password = smtp_password or ''
        else:
            self.smtp_server = server
            self.smtp_port = 587
            self.smtp_use_tls = True
            self.smtp_username = username
            self.smtp_password = password
        self.smtp_sender = smtp_sender or HOST_ADDRESS
        self._smtp_kwargs = dict(server=self.smtp_server, port=self.smtp_port,
                                 username=self.smtp_username, password=self.smtp_password,
                                 use_tls=self.smtp_use_tls)
        self.imap.login(username, password)
        self._workspace = 'data'
        self._publish_dir = 'publish'
        self._attachments_dir = os.path.join(self._workspace, 'attachments')
        self._images_dir = os.path.join(self._workspace, 'images')
        self.gazette_pdf = ''
        self.gazette_html = ''
        self.today = date.today()
        self.adresses = {}
        self.adresses_ok = {}
        if not os.path.exists(self._workspace):
            os.mkdir(self._workspace)
        if not os.path.exists(self._publish_dir):
            os.mkdir(self._publish_dir)
        if not os.path.exists(self._attachments_dir):
            os.mkdir(self._attachments_dir)
        if not os.path.exists(self._images_dir):
            os.mkdir(self._images_dir)

    def get_part_filename(self, msg: EmailMessage):
        filename = msg.get_filename()
        if filename is None:
            return None
        decoded = decode_header(filename)[0]
        if decoded[1] is not None:
            filename = decoded[0].decode(decoded[1])
        return filename

    def get_adresses(self, address_filepath):
        with open(address_filepath, 'r') as f:
            self.adresses = parse_addresses(f)

    def get_addresses_ok(self):
        self.adresses_ok = self.adresses.copy()
        self._eligible_messages = []
        status, messages = self.imap.select("INBOX")
        message_count = int(messages[0])
        message_count_limit = 30

        for seqnum in range(message_count, max(0, message_count - message_count_limit), -1):
            res, msg_data = self.imap.fetch(str(seqnum), "(BODY.PEEK[HEADER.FIELDS (FROM DATE)])")

            for response in msg_data:
                if not isinstance(response, tuple):
                    continue
                msg = email.message_from_bytes(response[1])

                received_from = parse_from_address(msg.get("From", ""))

                datestring = decode_header(msg.get("Date"))[0][0]
                received_date = email.utils.parsedate_to_datetime(datestring).date()
                delta_days = self.today - received_date

                if delta_days.days >= MAX_DELTA_DAYS:
                    continue

                for _contributor, addresses in self.adresses.items():
                    if any(received_from == a.lower() for a in addresses):
                        self._eligible_messages.append((seqnum, _contributor))
                        if _contributor in self.adresses_ok:
                            del self.adresses_ok[_contributor]
                            print(received_from, " wrote his gaz")
                        break

    
    def save_gazette(self):
        gazette_title = '<h1><b>Gazette du '+self.today.strftime("%d/%m/%Y")+'</b></h1>'
        gazette_body = ""

        total_contributors = len(self.adresses)
        if total_contributors == 0:
            gaz_month_stat = 0.0
        else:
            gaz_month_stat = ((total_contributors - len(self.adresses_ok)) / total_contributors) * 100
        if gaz_month_stat < 34:
            color = '#FF0000'
        elif gaz_month_stat < 67:
            color = '#FFA500'
        elif gaz_month_stat < 100:
            color = '#FFFF00'
        else:
            color = '#008000'
        gaz_stats = '<h2><b><label>Taux de participation : </b></label><label style="color:{};">{:.2f}%</h2></label>'.format(color, gaz_month_stat)
        print("gaz_month_stat : {}/{}".format(total_contributors - len(self.adresses_ok), total_contributors))
        print("gaz_month_stat (%) : {:.2f}".format(gaz_month_stat))

        list_name_ok = ''

        for seqnum, sender_name in self._eligible_messages:
            res, msg_data = self.imap.fetch(str(seqnum), "(RFC822)")
            body = None
            html_body = False
            subject = ''
            received_from = ''
            datestring = ''
            inline_images = {}
            extra_images = []

            for response in msg_data:
                if not isinstance(response, tuple):
                    continue
                msg = email.message_from_bytes(response[1])
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or 'utf-8', errors='replace')

                received_from = parse_from_address(msg.get("From", ""))

                datestring = decode_header(msg.get("Date"))[0][0]

                print("Subject:", subject)
                print("From:", received_from)
                print("Date:", datestring)
                if msg.is_multipart():
                    message_list = msg.walk()
                else:
                    message_list = [msg]

                for part in message_list:
                    content_type = part.get_content_type()
                    content_disposition = part.get_content_disposition()

                    if content_type == "text/html":
                        charset = part.get_content_charset() or 'utf-8'
                        body = part.get_payload(decode=True).decode(charset, errors='replace')
                        print('text/html body:')
                        print(body)
                        html_body = True
                    elif content_type == "text/plain" and not html_body:
                        charset = part.get_content_charset() or 'utf-8'
                        body = part.get_payload(decode=True).decode(charset, errors='replace')
                        print('text/plain body:')
                        print(body)
                        body = body.replace('\n', '<br>')
                    elif content_type.startswith("image/"):
                        filename = self.get_part_filename(part)
                        img_path = safe_join(self._images_dir, filename) if filename else None
                        if img_path is None:
                            ext = content_type.split("/")[-1].split(";")[0] or 'img'
                            filename = 'img_{}.{}'.format(uuid.uuid4().hex, ext)
                            img_path = os.path.join(os.path.abspath(self._images_dir), filename)
                        print('image found:', filename)
                        payload = part.get_payload(decode=True)
                        if payload:
                            with open(img_path, "wb") as f:
                                f.write(payload)
                            content_id = part.get("Content-ID", "")
                            if content_id:
                                content_id = content_id.strip().strip("<>")
                                inline_images[content_id] = img_path
                            else:
                                extra_images.append(img_path)
                    elif content_disposition == 'attachment':
                        filename = self.get_part_filename(part)
                        filepath = safe_join(self._attachments_dir, filename) if filename else None
                        if filepath is None:
                            print('skipping attachment with unsafe/empty filename:', filename)
                            continue
                        print('attachment found:')
                        print(filename)
                        with open(filepath, "wb") as f:
                            f.write(part.get_payload(decode=True))
            if body is not None:
                # Sanitize untrusted sender content before embedding it. Trusted
                # file:// image references are added by the app afterwards.
                body = sanitize_html(body)
                safe_subject = sanitize_html(subject)
                for cid, path in inline_images.items():
                    file_url = 'file://' + path
                    body = body.replace('cid:' + cid, file_url)
                for path in extra_images:
                    body += '<br><img src="file://{}" style="max-width:100%;">'.format(path)
                list_name_ok += sender_name + '<br>'
                gazette_body += '<b><label>'+safe_subject+'</label> </b><br>'+body+'<br><br>'
            print("="*100)

        gaz_name_list = '<br><b><label>Contributeurs : <br></b></label><i>'+list_name_ok+'</i><br><br><br>'
        document = ('<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
                    + gazette_title + gaz_stats + gaz_name_list + gazette_body
                    + '</body></html>')

        gazette_filepath = os.path.join(self._workspace, self.today.strftime("Gazette_%d_%m_%Y"))
        self.gazette_pdf = gazette_filepath+'.pdf'
        self.gazette_html = gazette_filepath+'.html'
        with open(gazette_filepath+'.html', "w", encoding='utf-8') as f:
            f.write(document)
        pdfkit.from_file(self.gazette_html, self.gazette_pdf, css='style.css', options={
                                                                'page-size': 'Letter',
                                                                'margin-top': '0.75in',
                                                                'margin-right': '0.75in',
                                                                'margin-bottom': '0.75in',
                                                                'margin-left': '0.75in',
                                                                'enable-local-file-access': None,
                                                                'disable-javascript': None,
                                                                'load-error-handling': 'ignore',
                                                                'load-media-error-handling': 'ignore',
                                                                })

    def close(self):
        self.imap.logout()

    def send_gazette(self):
        receivers = []
        for _tabs in self.adresses.values():
            for addr in _tabs:
                receivers.append(addr)
        subject = 'Gazette du '+self.today.strftime("%d/%m/%Y")
        body = 'Voici la gazette du '+self.today.strftime("%d/%m/%Y") + SIGNATURE
        attachments = [self.gazette_pdf]
        for attach in os.listdir(self._attachments_dir):
            attachments.append(os.path.join(self._attachments_dir, attach))
        print('Sending gazette to {}'.format(receivers))
        send_mail(send_from=self.smtp_sender, send_to=receivers, subject=subject, message=body,
                  files=attachments, **self._smtp_kwargs)
    
    def clean_workdir(self):
        gaz_dir = os.path.join(self._publish_dir,'Gazette_'+self.today.strftime("%Y_%m_%d"))
        if not os.path.exists(gaz_dir):
            os.mkdir(gaz_dir)
        os.rename(self.gazette_html, os.path.join(gaz_dir, os.path.basename(self.gazette_html)))
        shutil.rmtree(self._workspace)

    def send_reminder(self, remaining_days=0):
        receivers = []
        for _tabs in self.adresses_ok.values():
            for addr in _tabs:
                receivers.append(addr)
        subject = 'Rappel Gazette : J-{}'.format(remaining_days)
        body = "Ceci est un mail automatique vous rappelant qu'il vous reste {} jours pour écrire votre gazette !<br><br><b>Note:</b> vous n'auriez pas reçu ce mail si vous aviez envoyé votre gazette !".format(remaining_days) + SIGNATURE
        print('Sending {} day reminder to {}'.format(remaining_days, receivers))
        send_mail(send_from=self.smtp_sender, send_to=receivers, subject=subject, message=body,
                  **self._smtp_kwargs)


def get_parser():
    # Credentials default to environment variables so secrets are never exposed
    # on the command line (visible via `ps`). CLI flags remain as an override.
    parser = argparse.ArgumentParser(description="Gazbot")
    parser.add_argument('--server', '-s', default=os.environ.get('GAZBOT_SERVER'), help="Address of the mail server (env: GAZBOT_SERVER)")
    parser.add_argument('--username', '-u', default=os.environ.get('GAZBOT_USERNAME'), help="Username of the mail account (env: GAZBOT_USERNAME)")
    parser.add_argument('--password', '-p', default=os.environ.get('GAZBOT_PASSWORD'), help="Password of the mail account (env: GAZBOT_PASSWORD)")
    parser.add_argument('--address', '-a', default=os.environ.get('GAZBOT_ADDRESS_FILE'), help="Address file (env: GAZBOT_ADDRESS_FILE)")
    parser.add_argument('--gazette', '-g', action='store_true', help="Send the gazette")
    parser.add_argument('--reminder', '-r', type=int, default=None, help="Send a reminder for the given number of remaining days")
    parser.add_argument('--smtp_server', default=os.environ.get('SMTP_SERVER'), help="Address of the SMTP relay server (env: SMTP_SERVER; if omitted, the IMAP host is reused on port 587 with STARTTLS and the IMAP credentials)")
    parser.add_argument('--smtp_username', default=os.environ.get('SMTP_USERNAME'), help="Username of the SMTP relay account (env: SMTP_USERNAME; defaults to the IMAP username when --smtp_server is omitted)")
    parser.add_argument('--smtp_password', default=os.environ.get('SMTP_PASSWORD'), help="Password of the SMTP relay account (env: SMTP_PASSWORD; defaults to the IMAP password when --smtp_server is omitted)")
    parser.add_argument('--smtp_sender', default=os.environ.get('SMTP_SENDER'), help="Address of the sender field (env: SMTP_SENDER; defaults to the built-in HOST_ADDRESS)")
    return parser


if __name__ == "__main__":
    parser = get_parser()
    args = parser.parse_args()

    for required in ('server', 'username', 'password', 'address'):
        if not getattr(args, required):
            parser.error("--{0} is required (or set the corresponding environment variable)".format(required))

    gazbot=GazBot(server=args.server, username=args.username, password=args.password, smtp_server=args.smtp_server, smtp_username=args.smtp_username, smtp_password=args.smtp_password, smtp_sender=args.smtp_sender)
    try:
        gazbot.get_adresses(address_filepath=args.address)
        if args.gazette:
            gazbot.get_addresses_ok()
            gazbot.save_gazette()
            gazbot.send_gazette()
            gazbot.clean_workdir()
        elif args.reminder is not None:
            gazbot.get_addresses_ok()
            gazbot.send_reminder(remaining_days=args.reminder)
    finally:
        gazbot.close()
