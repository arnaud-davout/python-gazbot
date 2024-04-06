# -*- coding: utf-8 -*-
import imaplib
import email
from email.message import EmailMessage
from email.header import decode_header
import os, shutil
import argparse
from datetime import date
import pdfkit
from send_email import send_mail

MAX_DELTA_DAYS = 15
HOST_ADDRESS = '"GazBot" <gazette@famille.davout.net>'

__VERSION__ = "1.0"
GITHUB = "https://github.com/arnaud-davout/python-gazbot"
HOWTO = "https://github.com/arnaud-davout/python-gazbot/blob/main/HOWTO.md"
SIGNATURE = '<br><br><br>---<br>PyGazetteBot v' + __VERSION__ + ' | <a href=' + HOWTO + '>Gazette HOW-TO</a> | <a href=' + GITHUB + '>GitHub</a>'

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
        self._publish_dir = 'publish'
        self._attachments_dir = os.path.join(self._workspace, 'attachments')
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

    def get_part_filename(self, msg: EmailMessage):
        filename = msg.get_filename()
        if decode_header(filename)[0][1] is not None:
            filename = decode_header(filename)[0][0].decode(decode_header(filename)[0][1])
        return filename

    def get_adresses(self, address_filepath):
        f=open(address_filepath,'r')
        for line in f:
            self.adresses[line.strip('\n').split(':')[1]] = line.strip('\n').split(':')[0].split(',')
        f.close()

    def get_addresses_ok(self):
        self.adresses_ok = self.adresses.copy()
        status, messages = self.imap.select("INBOX")
        message_count = int(messages[0])
        message_count_limit = 30

        for _idx in range(message_count, max(0,message_count-message_count_limit), -1):
            res, msg = self.imap.fetch(str(_idx), "(RFC822)")

            for response in msg:
                if isinstance(response, tuple):
                    msg = email.message_from_bytes(response[1])
                    subject, encoding = decode_header(msg["Subject"])[0]

                    _, encoding = decode_header(msg.get("From"))[0]
                    for _idx in decode_header(msg.get("From")):
                        _from, _ = _idx
                        if isinstance(_from, bytes):
                            if encoding:
                                _from = _from.decode(encoding)
                        if '@' in _from:
                            received_from = _from

                    datestring = decode_header(msg.get("Date"))[0][0]
                    received_date = email.utils.parsedate_to_datetime(datestring).date()
                    delta_days = self.today-received_date
                    
                    for _contributor in self.adresses:
                        address = self.adresses[_contributor]
                        for _addr in address:
                            if _addr in received_from  and _contributor in self.adresses_ok and delta_days.days < MAX_DELTA_DAYS:
                                del self.adresses_ok[_contributor]
                                print(received_from, " wrote his gaz")

    
    def save_gazette(self):
        status, messages = self.imap.select("INBOX")
        message_count = int(messages[0])
        message_count_limit = 30
        gazette_title = '<h1><b>Gazette du '+self.today.strftime("%d/%m/%Y")+'</b></h1>'
        gazette_head = '<head><meta charset="utf-8">'+gazette_title+'</head><br>'
        gazette_body = "<body>"

        # stats
        gaz_month_stat = ((len(self.adresses)-len(self.adresses_ok))/len(self.adresses))*100
        if (gaz_month_stat< 34):
            gaz_stats = '<h2><b><label>Taux de participation : </b></label><label style="color:#FF0000;">{:.2f}%</h2></label>'.format(gaz_month_stat)
        elif (gaz_month_stat>34 and gaz_month_stat<67):
            gaz_stats = '<h2><b><label>Taux de participation : </b></label><label style="color:#FFA500;">{:.2f}%</h2></label>'.format(gaz_month_stat)
        elif (gaz_month_stat>67 and gaz_month_stat<100):
            gaz_stats = '<h2><b><label>Taux de participation : </b></label><label style="color:#FFFF00;">{:.2f}%</h2></label>'.format(gaz_month_stat)
        else:
            gaz_stats = '<h2><b><label>Taux de participation : </b></label><label style="color:#008000;">{:.2f}%</h2></label>'.format(gaz_month_stat)
        print("gaz_month_stat : {}/{}".format(len(self.adresses_ok),len(self.adresses)))
        print("gaz_month_stat (%) : {:.2f}".format(gaz_month_stat))

        list_name_ok = ''

        # body
        for _idx in range(message_count, max(0,message_count-message_count_limit), -1):
            res, msg = self.imap.fetch(str(_idx), "(RFC822)")
            body = None
            html_body = False

            for response in msg:
                if isinstance(response, tuple):
                    msg = email.message_from_bytes(response[1])
                    subject, encoding = decode_header(msg["Subject"])[0]

                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding)

                    _, encoding = decode_header(msg.get("From"))[0]
                    for _idx in decode_header(msg.get("From")):
                        _from, _ = _idx
                        if isinstance(_from, bytes):
                            if encoding:
                                _from = _from.decode(encoding)
                        if '@' in _from:
                            received_from = _from

                    datestring = decode_header(msg.get("Date"))[0][0]
                    received_date = email.utils.parsedate_to_datetime(datestring).date()
                    delta_days = self.today-received_date

                    known_sender = False
                    _idx = 0
                    for _contributor in self.adresses:
                        address = self.adresses[_contributor]
                        for _addr in address:
                            if _addr in received_from:
                                known_sender=True
                                sender_name = _contributor
                            _idx += 1

                    if known_sender and delta_days.days < MAX_DELTA_DAYS:
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
                                body = part.get_payload(decode=True).decode(part.get_content_charset())
                                print('text/html body:')
                                print(body)
                                html_body = True
                            elif content_type == "text/plain" and not html_body:
                                body = part.get_payload(decode=True).decode(part.get_content_charset())
                                print('text/plain body:')
                                print(body)
                                body = body.replace('\n', '<br>')
                            elif content_disposition == 'attachment':
                                filename = self.get_part_filename(part)
                                if filename:
                                    filepath = os.path.join(self._attachments_dir, filename)
                                    print('attachment found:')
                                    print(filename)
                                    with open(filepath, "wb") as f:
                                        f.write(part.get_payload(decode=True))
            if body != None:
                list_name_ok += sender_name + '<br>'
                gazette_body += '<b><label>'+subject+'</label> </b><br>'+body+'<br><br>'
            print("="*100)
        
        gazette_body += '</body>'
        gaz_name_list = '<br><b><label>Contributeurs : <br></b></label><i>'+list_name_ok+'</i><br><br><br>'
            
        gazette_filepath = os.path.join(self._workspace, self.today.strftime("Gazette_%d_%m_%Y"))  
        self.gazette_pdf = gazette_filepath+'.pdf'  
        self.gazette_html = gazette_filepath+'.html'
        with open(gazette_filepath+'.html' , "w") as f:
            f.write(gazette_head+gaz_stats+gaz_name_list+gazette_body)
        replace_in_file(self.gazette_html, 'iso-8859-1', 'utf-8')
        pdfkit.from_file(self.gazette_html, self.gazette_pdf, css='style.css', options={
                                                                'page-size': 'Letter',
                                                                'margin-top': '0.75in',
                                                                'margin-right': '0.75in',
                                                                'margin-bottom': '0.75in',
                                                                'margin-left': '0.75in',
                                                                })
        self.imap.close()
        self.imap.logout()

    def send_gazette(self):
        sender = HOST_ADDRESS
        receivers = self.adresses
        subject = 'Gazette du '+self.today.strftime("%d/%m/%Y")
        body = 'Voici la gazette du '+self.today.strftime("%d/%m/%Y") + SIGNATURE
        attachments = [self.gazette_pdf]
        for attach in os.listdir(self._attachments_dir):
            attachments.append(os.path.join(self._attachments_dir, attach))
        print('Sending gazette to {}'.format(receivers))
        send_mail(send_from=sender, send_to=receivers, subject=subject, message=body, files=attachments,
                  server=self.server, username=self.username, password=self.password)
    
    def clean_workdir(self):
        gaz_dir = os.path.join(self._publish_dir,'Gazette_'+self.today.strftime("%Y_%m_%d"))
        if not os.path.exists(gaz_dir):
            os.mkdir(gaz_dir)
        os.rename(self.gazette_html, os.path.join(gaz_dir, os.path.basename(self.gazette_html)))
        shutil.rmtree(self._workspace)

    def send_reminder(self, remaining_days=0):
        sender = HOST_ADDRESS
        receivers = []
        for _tabs in self.adresses_ok.values():
            for addr in _tabs:
                receivers.append(addr)
        subject = 'Rappel Gazette : J-{}'.format(remaining_days)
        body = "Ceci est un mail automatique vous rappelant qu'il vous reste {} jours pour écrire votre gazette !<br><br><b>Note:</b> vous n'auriez pas reçu ce mail si vous aviez envoyé votre gazette !".format(remaining_days) + SIGNATURE
        print('Sending {} day reminder to {}'.format(remaining_days, receivers))
        send_mail(send_from=sender, send_to=receivers, subject=subject, message=body, server=self.server, 
                  username=self.username, password=self.password)


def get_parser():
    parser = argparse.ArgumentParser(description="Gazbot")
    parser.add_argument('--server', '-s', required=True, help="Adress of the mail server")
    parser.add_argument('--username', '-u', required=True, help="Username of the mail account")
    parser.add_argument('--password', '-p', required=True, help="Password of the mail account")
    parser.add_argument('--address', '-a', required=True, help="Address file")
    parser.add_argument('--gazette', '-g', required=False, help="Send dazette")
    parser.add_argument('--reminder', '-r', required=False, help="send reminder")
    return parser


if __name__ == "__main__":
    parser = get_parser()
    args = parser.parse_args()

    gazbot=GazBot(server=args.server, username=args.username, password=args.password)
    gazbot.get_adresses(address_filepath=args.address)
    if args.gazette:
        gazbot.get_addresses_ok()
        gazbot.save_gazette()
        gazbot.send_gazette()
        gazbot.clean_workdir()
    elif args.reminder:
        gazbot.get_addresses_ok()
        gazbot.send_reminder(remaining_days=args.reminder)