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
        if self.reply_topic in self.client.subscriptions:
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


# You can specify odoo login uid to make requests without login call.
ODOO_LOGIN_UID = os.environ.get('USER_UID') 

class OdooRPCProxy(RPCProxy):

    def __init__(self, client, destination, uid=None, one_way=False):
        super().__init__(client, destination, one_way=one_way)
        self.uid = uid if uid else ODOO_LOGIN_UID
    
    async def login(self, db, login, password):
        self.db = db
        self.login = login
        self.password = password
        uid = await self.call(service='common', method='login', 
                         args=[db, login, password])
        self.uid = int(uid)
        if not uid:
            raise RPCError(
                'Odoo login failed, db: {}, login: {}, password: {}'.format(
                    db, login, password))
        logger.debug('Odoo login: uid={}'.format(uid))
        return uid
        


    def search(self, model, domain, offset=0, limit=None, order=None):
        logger.debug('search {} domain {}'.format(model, domain))
        return self.call(service='object', method='execute',
                args=[self.db, self.uid, self.password, model, 'search', 
                      domain, offset, limit, order])


    def search_count(self, model, domain):
        logger.debug('search_count {} domain {}'.format(model, domain))
        return self.call(service='object', method='execute',
                args=[self.db, self.uid, self.password, model, 'search_count', 
                      domain, 0, None, None, 1])


    def search_read(self, model, domain, fields=[],
                                         offset=0, limit=None, order=None):
        logger.debug('search_read {} {} {}'.format(model, domain, fields))
        return self.call(service='object', method='execute',
                args=[self.db, self.uid, self.password, model, 'search_read', 
                      domain, fields, offset, limit, order])


    def read(self, model, ids, fields=[]):
        logger.debug('read {} {} {}'.format(model, ids, fields))
        return self.call(service='object', method='execute',
                args=[self.db, self.uid, self.password, model, 'read', 
                      ids, fields])


    def create(self, model, vals, context=None):
        logger.debug('create {} vals {}'.format(model, vals))
        return self.call(service='object', method='execute',
                args=[self.db, self.uid, self.password, model, 
                     'create', vals, context or {}])


    def unlink(self, model, ids):
        logger.debug('unlink {} {}'.format(model, ids))
        return self.call(service='object', method='execute',
                args=[self.db, self.uid, self.password, model, 'unlink', ids])


    def execute(self, model, method, *args, **kwargs):
        logger.debug('execute {} {}'.format(model, method, args, kwargs))
        return self.call(service='object', method='execute',
            args=[self.db, self.uid, self.password, model, method, args, kwargs])

