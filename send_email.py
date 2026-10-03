# -*- coding: utf-8 -*-
import os
import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from os.path import basename


def send_mail(send_from, send_to, subject, message, files=None,
              server=os.getenv('SMTP_SERVER', 'localhost'), port=int(os.getenv('SMTP_PORT', 587)), username=os.getenv('GAZBOT_USERNAME', ''), password=os.getenv('GAZBOT_PASSWORD', ''),
              use_tls=True):
    """Compose and send email with provided info and attachments.

    Args:
        send_from (str): from name
        send_to (list[str]): to name(s)
        subject (str): message title
        message (str): message body
        files (list[str]): list of file paths to be attached to email
        server (str): mail server host name
        port (int): port number
        username (str): server auth username
        password (str): server auth password
        use_tls (bool): use TLS mode
    """
    files = files or []
    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    msg['Reply-To'] = "gazette@famille.davout.net"

    msg.attach(MIMEText(message, 'html'))

    for path in files:
        with open(path, "rb") as _file:
            part = MIMEApplication(
                _file.read(),
                Name=basename(path)
            )
        part['Content-Disposition'] = 'attachment; filename="%s"' % basename(path)
        msg.attach(part)
        print("Sending file {}".format(Path(path).name))

    with smtplib.SMTP(server, port) as smtp:
        if use_tls:
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.sendmail(send_from, send_to, msg.as_string())
