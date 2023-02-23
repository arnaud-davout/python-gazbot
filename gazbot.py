# -*- coding: utf-8 -*-
import imaplib
import email
from email.message import EmailMessage
from email.header import decode_header
import os
import argparse
from datetime import date
import pdfkit
from send_email import send_mail

MAIL_MESSAGE = """From: {}
To: {}
MIME-Version: 1.0
Content-type: text/html
Subject: SMTP HTML e-mail test

{}
"""

def replace_in_file(filepath, to_replace, replacement):
    with open(filepath, 'r') as file :
        filedata = file.read()
    filedata = filedata.replace(to_replace, replacement)
    with open(filepath, 'w') as file:
        file.write(filedata)


class GazBot:
    def __init__(self, server, username, password):
        self.imap = imaplib.IMAP4_SSL(server)
        self.server = server
        self.username = username
        self.password = password
        self.imap.login(username, password)
        self._workspace = 'data'
        self.gazette_path = ''
        self.today = date.today()
        if not os.path.exists(self._workspace):
            os.mkdir(self._workspace)

    def get_part_filename(self, msg: EmailMessage):
        filename = msg.get_filename()
        if decode_header(filename)[0][1] is not None:
            filename = decode_header(filename)[0][0].decode(decode_header(filename)[0][1])
        return filename
    
    def save_gazette(self):
        status, messages = self.imap.select("INBOX")
        message_count = int(messages[0])
        message_count_limit = 30
        gazette_title = '<font size="+3"><label style="color:firebrick;"><b>Gazette du '+self.today.strftime("%d/%m/%Y")+'</b></label> </font><br><br><br>';
        gazette_body = ""

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
                        message_list = msg.walk()
                    else:
                        message_list = [msg]

                    for part in message_list:
                        content_type = part.get_content_type()
                        content_disposition = part.get_content_disposition()

                        if content_type == "text/html":
                            body = part.get_payload(decode=True).decode(part.get_content_charset())
                            print('text/html body:')
                            print(body)
                            gazette_body += '<b><label style="color:steelblue;">'+subject+'</label> </b><br>'+body+'<br><br>'
                        elif content_disposition == 'attachment':
                            filename = self.get_part_filename(part)
                            if filename:
                                filepath = os.path.join(self._workspace, filename)
                                print('attachment found:')
                                print(filename)
                                with open(filepath, "wb") as f:
                                    f.write(part.get_payload(decode=True))

                    print("="*100)
            
            gazette_filepath = os.path.join(self._workspace, self.today.strftime("Gazette_%d_%m_%Y"))    
            with open(gazette_filepath+'.html' , "w") as f:
                f.write(gazette_title+gazette_body)
            replace_in_file(gazette_filepath+'.html', 'iso-8859-1', 'utf-8')
            pdfkit.from_file(gazette_filepath+'.html', gazette_filepath+'.pdf')
            self.gazette_path = gazette_filepath+'.pdf'

        self.imap.close()
        self.imap.logout()

    def send_gazette(self):
        sender = 'gazette@famille.davout.net'
        receivers = ['arnaud.davout@gmail.com', 'arnaud@davout.net']
        subject = 'Gazette du '+self.today.strftime("%d/%m/%Y")
        body = 'Voici la gazette du '+self.today.strftime("%d/%m/%Y")
        for receiver in receivers:
            print('Sending gazette to '+receiver)
            send_mail(send_from=sender, send_to=receiver, subject=subject, message=body, files=[self.gazette_path],
            server=self.server, username=self.username, password=self.password)


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
    gazbot.save_gazette()
    gazbot.send_gazette()