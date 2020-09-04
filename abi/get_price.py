import datetime
from web3.auto.infura import w3
import peewee

from configs.config_django import mysql_kwargs

with open('public/abi/yfii/iUSDT.json') as f:
    abi = f.read()

assert w3.isConnected()
pool3 = w3.eth.contract(abi=abi, address='0x72Cf258c852Dc485a853370171d46B9D29fD3184')

origin_price = pool3.functions.getPricePerFullShare().call()
# print(origin_price, type(origin_price))

db = peewee.MySQLDatabase(**mysql_kwargs)


class Abi_tokenprice(peewee.Model):
    name = peewee.CharField(verbose_name='名称', max_length=20)
    signal = peewee.CharField(verbose_name='signal', max_length=20)
    origin_price = peewee.BigIntegerField(verbose_name='原始价格')
    roi_week = peewee.FloatField('roi_week')
    created_time = peewee.DateTimeField(verbose_name='创建时间')

    class Meta:
        database = db


now = datetime.datetime.now()
yesterday = now - datetime.timedelta(days=1)
start_time = yesterday - datetime.timedelta(minutes=35)
end_time = yesterday + datetime.timedelta(minutes=35)

db.connect()

old_one = Abi_tokenprice.select().where(
    (Abi_tokenprice.created_time < end_time) & (Abi_tokenprice.created_time > start_time)
)

if not old_one:
    old_price = 1000664946236559139
else:
    old_price = old_one[0].origin_price

roi_week = (origin_price / old_price - 1) * 100

item = Abi_tokenprice.create(
    name='iUSDT', signal='iUSDT', origin_price=origin_price, roi_week=roi_week, created_time=datetime.datetime.now()
)
item.save()
db.close()
