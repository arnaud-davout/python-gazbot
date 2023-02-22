import imaplib
import email
from email.message import EmailMessage
from email.header import decode_header
import webbrowser
import os
import argparse


class GazBot:
    def __init__(self, server, username, password):
        self.imap = imaplib.IMAP4_SSL(server)
        self.imap.login(username, password)

    def clean(self, text):
        return "".join(c if c.isalnum() else "_" for c in text)

    def get_part_filename(self, msg: EmailMessage):
        filename = msg.get_filename()
        if decode_header(filename)[0][1] is not None:
            filename = decode_header(filename)[0][0].decode(decode_header(filename)[0][1])
        return filename

    
    def get_messages(self):
        status, messages = self.imap.select("INBOX")
        message_count = int(messages[0])
        message_count_limit = 30

        for _idx in range(message_count, max(0,message_count-message_count_limit), -1):
            res, msg = self.imap.fetch(str(_idx), "(RFC822)")

            for response in msg:
                if isinstance(response, tuple):
                    msg = email.message_from_bytes(response[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding)
                    From, encoding = decode_header(msg.get("From"))[0]
                    if isinstance(From, bytes):
                        From = From.decode(encoding)
                    print("Subject:", subject)
                    print("From:", From)
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = part.get_content_disposition()
                            if content_type == "text/plain" and content_disposition != 'attachment':
                                if part.get_payload(decode=True) is not None:
                                    body = part.get_payload(decode=True).decode()
                                    print('text/plain body:')
                                    print(body)
                            elif content_disposition == 'attachment':
                                filename = self.get_part_filename(part)
                                if filename:
                                    folder_name = self.clean(subject)
                                    if not os.path.isdir(folder_name):
                                        os.mkdir(folder_name)
                                    filepath = os.path.join(folder_name, filename)
                                    print('attachment found:')
                                    print(filename)
                                    open(filepath, "wb").write(part.get_payload(decode=True))
                    else:
                        content_type = msg.get_content_type()
                        body = msg.get_payload(decode=True).decode()
                        if content_type == "text/plain":
                            print(body)
                    if content_type == "text/html":
                        folder_name = self.clean(subject)
                        if not os.path.isdir(folder_name):
                            os.mkdir(folder_name)
                        filename = "index.html"
                        filepath = os.path.join(folder_name, filename)
                        print('text/html body:')
                        print(body)
                        open(filepath, "w").write(body)
                        webbrowser.open(filepath)
                    print("="*100)
        self.imap.close()
        self.imap.logout()

def get_parser():
    parser = argparse.ArgumentParser(description="Gazbot")
    parser.add_argument('--server', '-s', required=True, help="Adress of the mail server")
    parser.add_argument('--username', '-u', required=True, help="Username of the mail account")
    parser.add_argument('--password', '-p', required=True, help="Password of the mail account")
    return parser


if __name__ == "__main__":
    parser = get_parser()
    args = parser.parse_args()

    gazbot=GazBot(server=args.server, username=args.username, password=args.password)
    gazbot.get_messages()