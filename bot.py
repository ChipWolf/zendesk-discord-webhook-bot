import sys
import os
import time, datetime, pytz
import urllib, hashlib
import pickle
import traceback
import logging
from dateutil import parser
from zenpy import Zenpy
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))
from discordWebhooks import Webhook, Attachment, Field

logging.basicConfig()
logger = logging.getLogger('ZDWB')
logger.setLevel(logging.INFO)

if os.environ['ZDWB_HISTORY_MINUTES']:
    history_minutes = int(os.environ['ZDWB_HISTORY_MINUTES'])
else:
    history_minutes = 0

url = os.environ['ZDWB_DISCORD_WEBHOOK']

creds = {
    'email' : os.environ['ZDWB_ZENDESK_EMAIL'],
    'token' : os.environ['ZDWB_ZENDESK_TOKEN'],
    'subdomain' : os.environ['ZDWB_ZENDESK_SUBDOMAIN']
}

status_color = {
    'new' : '#F5CA00',
    'open' : '#E82A2A',
    'pending' : '#59BBE0',
    'hold' : '#000000',
    'solved' : '#828282',
    'closed' : '#DDDDDD'
}

default_icon = "https://d1eipm3vz40hy0.cloudfront.net/images/logos/favicons/favicon.ico"

zenpy = Zenpy(**creds)

tickets = {}

# Check if we know the last timestamp Zendesk was audited from
if os.path.isfile('lza.p') is True: # lza = Last Zendesk Audit
    lza = pickle.load(open('lza.p','rb'))
    first_run = False
else:
    lza = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    first_run = True

logger.info('Last Zendesk Audit: {}'.format(lza))

pickle.dump(lza,open('lza.p','wb'))

def get_gravatar(email):
    # This will display the default Gravatar icon if the user has no Gravatar
    avatar = "https://www.gravatar.com/avatar/" + hashlib.md5(email.encode("utf8").lower()).hexdigest()
    return avatar

def post_webhook(event):
    try:
        ticket = zenpy.tickets(id=event.ticket_id)
        requester = zenpy.users(id=ticket.requester_id)

        # Updater ID 0 is generally for Zendesk automation/non-user actions
        if event.updater_id > 0:
            updater = zenpy.users(id=event.updater_id)
            updater_name = updater.name
            updater_email = updater.email
        else:
            updater_name = "Zendesk System"
            updater_email = "support@zendesk.com"

        # If the user has no Zendesk profile photo, use Gravatar
        if requester.photo is not None:
            avatar = requester.photo['content_url']
        else:
            avatar = get_gravatar(requester.email)

        # Initialize an empty Discord Webhook object with the specified Webhook URL
        wh = Webhook(url, "", "", "")

        # Prepare the base ticket info embed (attachment)
        at = Attachment(
            author_name = '{} ({})'.format(requester.name,requester.email),
            author_icon = avatar,
            color = status_color[ticket.status],
            title = '[Ticket #{}] {}'.format(ticket.id,ticket.raw_subject),
            title_link = "https://{}.zendesk.com/agent/#/tickets/{}".format(creds['subdomain'],ticket.id),
            footer = ticket.status.title(),
            ts = int(parser.parse(ticket.created_at).strftime('%s'))) # TODO: always UTC, config timezone

        # If this is a new ticket, post it, ignore the rest.
        # This will only handle the first 'Create' child event
        # I have yet to see any more than one child event for new tickets
        for child in event.child_events:
           if child['event_type'] == 'Create':
               if first_run is True:
                   wh = Webhook(url, "", "", "")
               else:
                   wh = Webhook(url, "@here, New Ticket!", "", "")


               description = ticket.description

               # Strip any double newlines from the description
               while "\n\n" in description:
                   description = description.replace("\n\n", "\n")

               field = Field("Description", ticket.description, False)
               at.addField(field)

               wh.addAttachment(at)
               wh.post()

               return

        wh.addAttachment(at)

        # Updater ID 0 is either Zendesk automation or non-user actions
        if int(event.updater_id) < 0:
            at = Attachment(
                color = status_color[ticket.status],
                footer = "Zendesk System",
                footer_icon = default_icon,
                ts = int(parser.parse(event.created_at).strftime('%s')))
        else:
            at = Attachment(
                color = status_color[ticket.status],
                footer = '{} ({})'.format(updater_name,updater_email),
                footer_icon = get_gravatar(updater_email),
                ts = int(parser.parse(event.created_at).strftime('%s')))

        for child in event.child_events:
           if child['event_type'] == 'Comment':
               for comment in zenpy.tickets.comments(ticket.id):
                    if comment.id == child['id']:
                        comment_body = comment.body

                        while "\n\n" in comment_body:
                            comment_body = comment_body.replace("\n\n","\n")

                        field = Field("Comment", comment_body, False)
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
                       logger.debug(child)
               else:
                   field = Field("Status Change", "{} to {}".format(child['previous_value'].title(), child['status'].title()), True)
                   at.addField(field)
           else:
               logger.error("Event not handled")

        wh.addAttachment(at)

        i = 0
        while i < 4:
           logger.debug('Posting to Discord')
           r = wh.post()
           i += 1
           if r.text != 'ok':
               logger.error(r)
               logger.info('Discord webhook retry {}/3'.format(i))
           else:
               break
           time.sleep(1)

    except Exception as e:
        if "RecordNotFound" in str(e):
            pass
        else:
            logger.error(traceback.print_exc())

if first_run is True:
    today = datetime.datetime.utcnow() - datetime.timedelta(minutes=history_minutes)
    for event in zenpy.tickets.events(today.replace(tzinfo=pytz.UTC)):
        logger.debug('Incoming Zendesk Event')
        logger.debug(event.event_type)
        for child in event.child_events:
            logger.debug('Child Event')
            logger.debug(child['event_type'])
        post_webhook(event)

while True:
    for event in zenpy.tickets.events(lza):
        post_webhook(event)
    lza = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    pickle.dump(lza,open('lza.p','wb'))
    time.sleep(15)
