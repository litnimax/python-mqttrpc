import os

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
            logger.warning(
                'Odoo login failed, db: {}, login: {}, password: {}'.format(
                    db, login, password))
        return uid
        

    def execute(self, model, method, params):
        if not self.uid:
            raise Exception('Not logged in')
        return self.call(service='object', method='execute',
                args=[self.db, self.uid, self.password, model, method, params])

