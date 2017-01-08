import sys
import os
import time, datetime
import urllib, hashlib
import pickle
import traceback
from dateutil import parser
from zenpy import Zenpy
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))
from discordWebhooks import Webhook, Attachment, Field

# CONFIGS

url = "<discord webhook url>"

creds = {
    'email' : 'user@example.org',
    'token' : '<zendesk token>',
    'subdomain' : '<zendesk subdomain>'
}

# END CONFIGS

status_color = {
    'new' : '#F5CA00',
    'open' : '#E82A2A',
    'pending' : '#59BBE0',
    'hold' : '#000',
    'solved' : '#828282',
    'closed' : '#ddd'
}

zenpy = Zenpy(**creds)

tickets = {}

if os.path.isfile('lza.p') is True: # lza = Last Zendesk Audit
    lza = pickle.load(open('lza.p','rb'))
else:
    first_run = True
    lza = datetime.datetime.utcnow()

print(lza)

pickle.dump(lza,open('lza.p','wb'))

def get_gravatar(email):
    default = "https://{}.zendesk.com/images/favicon_2.ico".format(creds['subdomain'])
    avatar = "https://www.gravatar.com/avatar/" + hashlib.md5(email.encode("utf8").lower()).hexdigest() + "?"
    avatar += urllib.parse.urlencode({'d':default})
    return avatar

def post_webhook(event):
    try:
        ticket = zenpy.tickets(id=event.ticket_id)
        requester = zenpy.users(id=ticket.requester_id)
        if event.updater_id > 0:
            updater = zenpy.users(id=event.updater_id)
            updater_name = updater.name
            updater_email = updater.email
        else:
            updater_name = "Zendesk System"
            updater_email = "support@zendesk.com"

        if requester.photo is not None:
            avatar = requester.photo.content_url
        else:
            avatar = get_gravatar(requester.email)

        wh = Webhook(url, "", "", "")

        at = Attachment(
            author_name = '{} ({})'.format(requester.name,requester.email),
            author_icon = avatar,
            color = status_color[ticket.status],
            title = '[Ticket #{}] {}'.format(ticket.id,ticket.raw_subject),
            title_link = "https://{}.zendesk.com/agent/#/tickets/{}".format(creds['subdomain'],ticket.id),
            footer = ticket.status.title(),
            ts = int(parser.parse(ticket.created_at).strftime('%s')))

        for child in event._child_events:
           if child['event_type'] == 'Create':
               if first_run is True:
                   wh = Webhook(url, "", "", "")
               else:
                   wh = Webhook(url, "@here, New Ticket!", "", "")
               description = ticket.description
               while "\n\n" in description:
                   description = description.replace("\n\n", "\n")
               field = Field("Description", ticket.description, False)
               at.addField(field)
               wh.addAttachment(at)
               wh.post()
               return

        wh.addAttachment(at)

        if int(event.updater_id) < 0:
            at = Attachment(
                color = status_color[ticket.status],
                footer = "Zendesk System",
                footer_icon = "https://{}.zendesk.com/images/favicon_2.ico".format(creds['subdomain']),
                ts = int(parser.parse(event.created_at).strftime('%s')))
        else:
            at = Attachment(
                color = status_color[ticket.status],
                footer = '{} ({})'.format(updater_name,updater_email),
                footer_icon = get_gravatar(updater_email),
                ts = int(parser.parse(event.created_at).strftime('%s')))

        for child in event._child_events:
           if child['event_type'] == 'Comment':
               for comment in zenpy.tickets.comments(ticket.id).values:
                    if comment['id'] == child['id']:
                        comment_body = comment['plain_body']
                        while "\n\n" in comment_body:
                            comment_body = comment_body.replace("\n\n","\n")
                        field = Field("New Comment", comment['plain_body'], False)
                        at.addField(field)
           elif child['event_type'] == 'Change':
               if 'status' not in child.keys():
                   if 'tags' in child.keys():
                       if len(child['removed_tags']) > 0:
                           removed_tags = '~~`'
                           removed_tags += '`~~\n~~`'.join(map(str,child['removed_tags']))
                           removed_tags += '`~~'
                           field=Field("Tags Removed", '{}'.format(removed_tags), True)
                           at.addField(field)
                       if len(child['added_tags']) > 0:
                           added_tags = '`'
                           added_tags += '`\n`'.join(map(str,child['added_tags']))
                           added_tags += '`'
                           field=Field("Tags Added", '{}'.format(added_tags), True)
                           at.addField(field)
                   elif 'assignee_id' in child.keys():
                       field=Field("Assigned", '{}'.format(ticket.assignee.name,ticket.assignee.email), True)
                       at.addField(field)
                   elif 'type' in child.keys():
                       field=Field("Type Change", '`{}`'.format(child['type']), True)
                       at.addField(field)
                   else:
                       print(child)
               else:
                   field = Field("Status Change", "{} from {}".format(child['status'].title(),child['previous_value'].title()), True)
                   at.addField(field)
           else:
               print("Event not handled")

        wh.addAttachment(at)
        i = 0
        while i < 4:
           r = wh.post()
           i += 1
           if r.text is not 'ok':
               if r.headers['X-RateLimit-Remaining'] == 0:
                   now = int(time.time())
                   then = int(r.headers['X-RateLimit-Reset'])
                   ttw = then - now # ttw = Time To Wait
                   if ttw > 0:
                       print("Hit Rate Limit, sleeping for {}".format(str(ttw)))
                       time.sleep(ttw)
               else:
                   break
           time.sleep(1)

    except Exception as e:
        if "RecordNotFound" in str(e):
            pass
        else:
            traceback.print_exc()

if first_run is True:
    for event in zenpy.tickets.events("1970-01-01T00:00:00Z"):
        post_webhook(event)

while True:
    for event in zenpy.tickets.events(lza):
        post_webhook(event)
    lza = datetime.datetime.utcnow()
    pickle.dump(lza,open('lza.p','wb'))
    time.sleep(5)
