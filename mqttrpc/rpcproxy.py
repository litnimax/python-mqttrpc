import logging
import os
from tinyrpc.exc import RPCError

logger = logging.getLogger(__name__)

class RPCProxy(object):

    def __init__(self, client, destination, one_way=False):
        self.client = client
        self.reply_topic = 'rpc/{}/{}/reply'.format(client.client_uid, destination)
        self.destination = destination
        self.one_way = one_way

    def __del__(self):
        if self.client._connected_state.is_set() and \
                            self.reply_topic in self.client.subscriptions:
            self.client.subscriptions.remove(self.reply_topic)
            self.client.loop.create_task(
                self.client.unsubscribe([self.reply_topic])
            )


    def __getattr__(self, name):
        proxy_func = lambda *args, **kwargs: self.client._call(
                         self.destination,
                         name,
                         args,
                         kwargs,
                         one_way=self.one_way
                     )

        return proxy_func


class OdooRPCProxy(RPCProxy):
    # We should define class variables so that __getattr__ will not be called
    user_id = None # Odoo username id
    db = '' # Odoo database
    username = '' # Odoo username name
    password = '' # Odoo password 


    def __init__(self, client, destination, user_id=None, one_way=False):
        super().__init__(client, destination, one_way=one_way)
        # You can specify odoo username uid to make requests without username call.
        self.user_id = user_id if user_id else os.environ.get('ODOO_USER_ID', None)
    
    async def login(self, db, username, password):
        self.db = db
        self.username = username
        self.password = password
        user_id = await self.call(service='common', method='login', 
                         args=[db, username, password])
        self.user_id = int(user_id)
        if not user_id:
            raise RPCError(
                'Odoo login failed, db: {}, username: {}, password: {}'.format(
                    db, username, password))
        logger.debug('Odoo login: user_id={}'.format(user_id))
        return user_id
        

    def search(self, model, domain, offset=0, limit=None, order=None):
        logger.debug('search {} domain {}'.format(model, domain))
        return self.call(service='object', method='execute',
                args=[self.db, self.user_id, self.password, model, 'search', 
                      domain, offset, limit, order])


    def search_count(self, model, domain):
        logger.debug('search_count {} domain {}'.format(model, domain))
        return self.call(service='object', method='execute',
                args=[self.db, self.user_id, self.password, model, 'search_count', 
                      domain, 0, None, None, 1])


    def search_read(self, model, domain, fields=[],
                                         offset=0, limit=None, order=None):
        logger.debug('search_read {} {} {}'.format(model, domain, fields))
        return self.call(service='object', method='execute',
                args=[self.db, self.user_id, self.password, model, 'search_read', 
                      domain, fields, offset, limit, order])


    def read(self, model, ids, fields=[]):
        logger.debug('read {} {} {}'.format(model, ids, fields))
        return self.call(service='object', method='execute',
                args=[self.db, self.user_id, self.password, model, 'read', 
                      ids, fields])


    def write(self, model, rec_id, vals, context={}):
        logger.debug('write {} {} {}'.format(model, vals, context))
        return self.call(service='object', method='execute',
                args=[self.db, self.user_id, self.password, model, 'write',
                      rec_id, vals])


    def create(self, model, vals, context=None):
        logger.debug('create {} vals {}'.format(model, vals))
        return self.call(service='object', method='execute',
                args=[self.db, self.user_id, self.password, model, 
                     'create', vals, context or {}])


    def unlink(self, model, ids):
        logger.debug('unlink {} {}'.format(model, ids))
        return self.call(service='object', method='execute',
                args=[self.db, self.user_id, self.password, model, 'unlink', ids])


    def execute(self, model, method, *args, **kwargs):
        logger.debug('execute {} {}'.format(model, method, args, kwargs))
        return self.call(service='object', method='execute',
            args=[self.db, self.user_id, self.password, model, method, args, kwargs])

