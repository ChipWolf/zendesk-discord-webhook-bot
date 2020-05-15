import datetime
import hashlib
import logging
import os
import pickle
import sys
import time
import traceback
import urllib

import pytz
from dateutil import parser
from zenpy import Zenpy

from discordWebhooks import Attachment, Field, Webhook

sys.path.append(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))

logging.basicConfig()
logger = logging.getLogger('ZDWB')
logger.setLevel(logging.INFO)

if os.environ['ZDWB_HISTORY_MINUTES']:
    history_minutes = int(os.environ['ZDWB_HISTORY_MINUTES'])
else:
    history_minutes = 0

url = os.environ['ZDWB_DISCORD_WEBHOOK']

sleep = 15

creds = {
    'email': os.environ['ZDWB_ZENDESK_EMAIL'],
    'token': os.environ['ZDWB_ZENDESK_TOKEN'],
    'subdomain': os.environ['ZDWB_ZENDESK_SUBDOMAIN']
}

status_color = {
    'new': '#F5CA00',
    'open': '#E82A2A',
    'pending': '#59BBE0',
    'hold': '#000000',
    'solved': '#828282',
    'closed': '#DDDDDD'
}

default_icon = "https://d1eipm3vz40hy0.cloudfront.net/images/logos/favicons/favicon.ico"

zenpy = Zenpy(**creds)

tickets = {}

# Check if we know the last timestamp Zendesk was audited from
if os.path.isfile('lza.p') is True:  # lza = Last Zendesk Audit
    lza = pickle.load(open('lza.p', 'rb'))
    first_run = False
else:
    lza = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    first_run = True

logger.info('Last Zendesk Audit: {}'.format(lza))

pickle.dump(lza, open('lza.p', 'wb'))


def get_gravatar(email):
    # This will return the default Gravatar icon if the user has no Gravatar
    try:
        avatar = "https://www.gravatar.com/avatar/"
        avatar += hashlib.md5(email.encode("utf8").lower()).hexdigest()
    except AttributeError:
        logger.warning('User object contains no email')
    return avatar


def get_user(id):
    output = {}

    # 0 is used for Zendesk automation/system actions
    if id > 0:
        user = zenpy.users(id=id)
        output['name'] = user.name
        output['email'] = user.email

        # If the user has no Zendesk profile photo, use Gravatar
        if user.photo is not None:
            output['avatar'] = user.photo['content_url']
        else:
            output['avatar'] = get_gravatar(user.email)
    else:
        output['name'] = "Zendesk System"
        output['email'] = "support@zendesk.com"
        output['avatar'] = default_icon

    return output

def build_text_field(name, body, at):
    # Replace repeated newlines with a single newline
    while "\n\n" in body:
        body = body.replace("\n\n", "\n")

    field = Field(name, body, False)

    at.addField(field)

    return at

def build_status_field(name, event, at):
    previous_status = event['previous_value'].title()
    current_status = event['status'].title()

    status_change = '{} to {}'.format(
        previous_status,
        current_status
    )

    field = Field(name, status_change, True)

    at.addField(field)

    return at

def build_tags_field(name, tags, wrap, at):
    if len(tags) > 0: 
        wrap_rev = ''.join(reversed(wrap))

        output = '{}{}'.format(wrap)
        output += '{}{}\n{}{}'.format(wrap_rev, wrap).join(map(str, tags))
        output += '{}{}'.format(wrap_rev)
        
        field = Field(name, '{}'.format(output), True)

        at.addField(field)

    return at

def build_assignee_field(name, ticket, at):
    assignee_name = ticket.assignee.name
    assignee_email = ticket.assignee.email

    assignee_info = '{} ({})'.format(
        assignee_name,
        assignee_email
    ) # output: Richard Hendricks (richard.hendricks@piedpiper.com)

    field = Field(name, assignee_info, True)

    at.addField(field)

    return at

def build_type_field(name, event)
    type_name = event['type']
    type_name = '`{}`'.format(type_name)

    field = Field(name, type_name, True)

    at.addField(field)

    return at

def build_request_attachment(ticket, requester):
    color = status_color[ticket.status]

    requester_avatar = requester['avatar']
    requester_info = '{} ({})'.format(
        requester['name'],
        requester.['email']
    ) # output: Richard Hendricks (richard.hendricks@piedpiper.com)

    ticket_status = ticket.status.title()
    ticket_created_at = int(parser.parse(ticket.created_at).strftime('%s'))
    # TODO: enable configurable timezone, currently UTC

    ticket_title = '[#{}] {}'.format(
        ticket.id,
        ticket.raw_subject
    )

    ticket_url = "https://{}.zendesk.com/agent/#/tickets/{}".format(
        creds['subdomain'],
        ticket.id
    )

    return Attachment(
        author_name=requester_info,
        author_icon=requester_avatar,
        color=color,
        title=ticket_title,
        title_link=ticket_url,
        footer=ticket_status,
        ts=ticket_created_at
    )

def handle_comment_event(event, at):
    for comment in zenpy.tickets.comments(ticket.id):
        if comment.id == event['id']:
            at = build_text_field("Comment", comment.body, at)     

    return at

def handle_change_event(event, at):
    if 'status' in event.keys():
        at = build_status_field("Status Change", child, at)

    elif 'tags' in event.keys():
        at = build_tags_field("Removed Tags", event['removed_tags'], '~~`', at)
        # output: ~~`removed-tag`~~

        at = build_tags_field("Added Tags", event['added_tags'], '`', at)
        # output: `added-tag`

    elif 'assignee_id' in event.keys():
        at = build_assignee_field("Assigned", ticket, at)

    elif 'type' in event.keys():
        at = build_type_field("Type Change", event, at)

    else:
        logger.warning('{} change event not supported'.format(child['event_type']))

    return at

def handle_child_event(event, at)
    if event['event_type'] == 'Comment':
        at = handle_comment_event(event, at)

    elif event['event_type'] == 'Change':
        at = handle_change_event(event, at)

    else:
        logger.warning('{} event not supported'.format(child['event_type']))
    
    return at

def build_update_attachment(ticket, updater):
    color = status_color[ticket.status]

    updater_avatar = updater['avatar']
    updater_info = '{} ({})'.format(
        updater['name'],
        updater['email']
    ) # output: Richard Hendricks (richard.hendricks@piedpiper.com)
    

    ticket_updated_at = int(parser.parse(event.created_at).strftime('%s'))

    at = Attachment(
        color=color,
        footer=updater_info,
        footer_icon=updater_avatar,
        ts=ticket_updated_at
    )

    for child in event.child_events:
        at = handle_child_event(child, at)
    
    return at

def build_webhook(event):
    ticket = zenpy.tickets(id=event.ticket_id)

    requester = get_user(ticket.requester_id)
    updater = get_user(event.updater_id)

    # Initialize an empty Discord Webhook object with the specified Webhook URL
    wh = Webhook(url, "", "", "")

    at = build_request_attachment(ticket, requester)

    # If this event is triggered by a new ticket, post it
    for child in event.child_events:
        if child['event_type'] == 'Create':
            if first_run is False:
                wh = Webhook(url, "@here, New Ticket!", "", "")

            field = build_text_field("Description", ticket.description)
            at.addField(field)

            wh.addAttachment(at)
            wh.post()

            return

    wh.addAttachment(at)

    at = build_update_attachment(ticket, updater)

    wh.addAttachment(at)

    logger.debug('Posting to Discord')
    
    r = wh.post()

    if r.text != 'ok':
        logger.error(r)

    return

def handle_event(event):
    try:
        build_webhook(event)
    except Exception as e:
        if "RecordNotFound" in str(e):
            pass
        else:
            logger.error(traceback.print_exc())
    
    return

def handle_events(ts):
    for event in zenpy.tickets.events(ts):
        logger.debug('{}: incoming {} event'.format(
            event.id,
            event.event_type
        ))

        for child in event.child_events:
            logger.debug('{}:{} incoming child {} event'.format(
                event.id,
                child['id'],
                child['event_type']
            ))

        post_webhook(event)
    
    return

if first_run is True:
    today = datetime.datetime.utcnow()
    past = today - datetime.timedelta(minutes=history_minutes)
    past =  past.replace(tzinfo=pytz.UTC)

    handle_events(past)

while True:
    handle_events(lza)

    lza = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    lza = lza.replace(tzinfo=pytz.UTC)

    pickle.dump(lza, open('lza.p', 'wb'))

    logger.debug('Sleeping for {} seconds'.format(sleep))
    time.sleep(sleep)
