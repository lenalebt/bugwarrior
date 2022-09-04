import datetime
import logging

import requests
import typing_extensions
from dateutil.tz import tzutc

from bugwarrior import config
from bugwarrior.services import IssueService, Issue, ServiceClient

log = logging.getLogger(__name__)


class FlatasticConfig(config.ServiceConfig, prefix='flatastic'):
    service: typing_extensions.Literal['flatastic']
    email: str
    password: str

    include_board_ids: config.ConfigList = config.ConfigList([])
    exclude_board_ids: config.ConfigList = config.ConfigList([])

    import_labels_as_tags: bool = False
    label_template: str = '{{label}}'
    only_if_assigned: str = None


# there is no API documentation, but you can open the webapp at https://www.flatastic-app.com/webapp/ and
# use your browser toolbar to have a look at the API calls
class FlatasticClient(ServiceClient):
    def __init__(self, email, password):
        self.email = email
        self.password = password

        login_data = requests.post('https://api.flatastic-app.com/index.php/api/auth/login',
                                   data={'email': self.email, 'password': self.password}).json()

        self.session = requests.session()
        self.session.auth = (self.email, self.password)
        self.session.headers.update({
            'Accept': 'application/json',
            'X-API-KEY': login_data['X-API-KEY'],
        })

    def get_chores(self):
        response = self.session.get('https://api.flatastic-app.com/index.php/api/chores')
        return response.json()


class FlatasticIssue(Issue):
    ID = 'flatasticid'
    TITLE = 'flatastictitle'
    DETAILS = 'flatasticdetails'
    CURRENT_USER = 'flatasticcurrentuser'
    POINTS = 'flatasticpoints'
    LAST_DONE_DATE = 'flatasticlastdonedate'
    NEXT_EXECUTION_TIME = 'flatasticnextexecution'

    UDAS = {
        ID: {
            'type': 'numeric',
            'label': 'Flatastic Chore ID',
        },
        TITLE: {
            'type': 'string',
            'label': 'Flatastic Title',
        },
        DETAILS: {
            'type': 'string',
            'label': 'Flatastic Details',
        },
        CURRENT_USER: {
            'type': 'numeric',
            'label': 'Flatastic Current User',
        },
        POINTS: {
            'type': 'numeric',
            'label': 'Flatastic Points',
        },
        LAST_DONE_DATE: {
            'type': 'date',
            'label': 'Flatastic Last Done Date',
        },
        NEXT_EXECUTION_TIME: {
            'type': 'date',
            'label': 'Flatastic Next Execution Time',
        }
    }

    UNIQUE_KEY = (ID,)

    def to_taskwarrior(self):
        return {
            'project': '',
            'priority': self.get_priority(),
            'tags': self.get_tags(),
            'entry': datetime.datetime.fromtimestamp(self.record.get('lastDoneDate'), tz=tzutc()),
            'due': (datetime.datetime.now(tz=tzutc()).replace(second=0, microsecond=0) + datetime.timedelta(
                seconds=self.record.get('timeLeftNext'))).replace(second=0, microsecond=0),

            self.ID: self.record['id'],
            self.TITLE: self.record['title'],
            self.DETAILS: self.record['details'],
            self.CURRENT_USER: self.record['currentUser'],
            self.POINTS: self.record['points'],
            self.LAST_DONE_DATE: datetime.datetime.fromtimestamp(self.record['lastDoneDate'], tz=tzutc()),
            self.NEXT_EXECUTION_TIME: (datetime.datetime.now(tz=tzutc()).replace(second=0, microsecond=0) +
                                       datetime.timedelta(seconds=self.record.get('timeLeftNext'))).replace(second=0,
                                                                                                            microsecond=0),
        }

    def get_tags(self):
        return self.get_tags_from_labels([])

    def get_default_description(self):
        return self.build_default_description(title=self.record['title'])


class FlatasticService(IssueService):
    ISSUE_CLASS = FlatasticIssue
    CONFIG_SCHEMA = FlatasticConfig

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.client = FlatasticClient(
            email=self.config.email,
            password=self.config.password
        )

    def get_service_metadata(self):
        return {
            'import_labels_as_tags': self.config.import_labels_as_tags,
            'label_template': self.config.label_template,
            'only_if_assigned': self.config.only_if_assigned,
        }

    def get_owner(self, issue):
        return str(issue[issue.CURRENT_USER])

    def issues(self):
        for chore in self.client.get_chores():
            issue = self.get_issue_for_record(chore)
            if self.include(issue):
                yield issue
