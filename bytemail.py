import email
import re
import smtplib
import imaplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from platform import python_version
from typing import Union
from datetime import datetime


class ByteMail:
    def __init__(self, user: str, password: str, server: str = None):
        self._server_smtp = smtplib.SMTP_SSL(
            'smtp.mail.ru' if not server else f'smtp.{server}')
        self._server_imap = imaplib.IMAP4_SSL(
            'imap.mail.ru' if not server else f'imap.{server}')
        self.user = user
        self._latest_email_id = None
        self._time = None
        self.__password = password
        self._login()

    def __del__(self):
        self._server_smtp.close()
        try:
            self._server_imap.close()
        except imaplib.IMAP4.error:
            pass

    def _login(self):
        # try:
        self._server_smtp.login(self.user, self.__password)
        # self._server_imap.login(self.user, self.__password)
        # except smtplib.SMTPAuthenticationError:
        #     print('## Authentication failed')
        #     sys.exit(1)

    def sendto(self, data: bytes, recipients: Union[str, list],
               subject: str = None) -> None:
        """
        USAGE

        you (or the bot) need to fill in the data what you actualy want to send
        and the email address(the email address of the person or bot
        that you want to send the data to)
        """
        sender = self.user

        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = f'Python script <{sender}>'
        msg['To'] = ', '.join(recipients) if isinstance(recipients,
                                                        list) else recipients
        msg['Reply-To'] = sender
        msg['Return-Path'] = sender
        msg['X-Mailer'] = f"Python/({python_version()})"

        part_file = MIMEBase('application',
                             'octet-stream; name="{}"'.format('data'))
        part_file.set_payload(data)
        part_file.add_header('Content-Disposition', 'data')
        encoders.encode_base64(part_file)

        self.__send_attach(msg, part_file)

        self._server_smtp.sendmail(sender, recipients, msg.as_string())

    def receive(self, since: float = None, deleted: bool = True) -> list:
        self._server_imap.select()
        result, data = self._server_imap.search(None, "ALL")
        ids = data[0]
        id_list = ids.split()
        try:
            if self._latest_email_id is None:
                self._latest_email_id = id_list[-1]
                data = self._get_data(self._latest_email_id)
                self._time = data[-1]
                if since is None:
                    self._latest_email_id = str(
                        int(self._latest_email_id) - 1).encode()
                    self._server_imap.store(id_list[-1], '+FLAGS', '\\Deleted')
                    return [data[:-1]] if data[0] else []
        except IndexError:
            return []

        def out(x, s):
            return x > s

        if since is None or since > self._time:
            id_list = id_list[
                      id_list.index(
                          self._latest_email_id) + 1:]
        else:
            id_list = id_list[id_list.index(self._latest_email_id)::-1]

            def out(x, s):
                return x < s

        payload_list = []
        cnt = 0
        for item in id_list:
            data = self._get_data(item)
            if since and out(data[-1], since):
                break
            if data[0]:
                if since is None or since > self._time:
                    if deleted:
                        cnt += 1
                        self._server_imap.store(item, '+FLAGS', '\\Deleted')
                    self._time = data[-1]
                    self._latest_email_id = item
                payload_list.append(data[:-1])
        self._latest_email_id = int(self._latest_email_id) - cnt
        self._latest_email_id = str(
            self._latest_email_id if self._latest_email_id > 0 else 0).encode()
        return payload_list

    def _get_data(self, email_id):
        result, data = self._server_imap.fetch(email_id,
                                               "(RFC822)")
        raw_email = data[0][1]
        raw_email_string = raw_email.decode('utf-8')
        email_message = email.message_from_string(raw_email_string)
        payload = None
        for part in email_message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue
            if part.get('Content-Disposition') == 'data':
                payload = part.get_payload(decode=True)
                break
        return (payload, re.findall(re.compile("<(.+)>"),
                                    email_message.get('From'))[0],
                datetime.strptime(email_message.get('Date').rstrip(' (UTC)'),
                                  "%a, %d %b %Y %H:%M:%S %z"
                                  ).timestamp()
                )

    @staticmethod
    def __send_attach(msg: MIMEMultipart, *args):
        for item in args:
            if item is not None:
                msg.attach(item)
