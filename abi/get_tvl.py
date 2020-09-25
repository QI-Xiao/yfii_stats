import json
import datetime

import peewee
import requests
from web3 import Web3, HTTPProvider
from web3.auto.infura import w3

from pool4 import getDATA
from abi_json.ERC20 import erc20Abi
from abi_json.v2.vault import vaultAbi
from abi_json.v2.strategy import strategyAbi

from configs.v2.config import dataeth, databsc
from configs.config_django import mysql_kwargs


# 自定义机枪池配置
# id 获取法币报价字段名
# vaults = [
#   {
#     'name': 'usdt',
#     'id': 'tether',
#   },
#   {
#     "name": 'ycrv',
#     'id': 'curve-fi-ydai-yusdc-yusdt-ytusd',
#     "curveName": 'y',
#   },
#   {
#     "name": 'dai',
#     'id': 'dai',
#   },
#   {
#     "name": 'tusd',
#     'id': 'true-usd',
#   },
#   {
#     "name": 'usdc',
#     'id': 'usd-coin',
#   },
#   {
#     'name': 'eth',
#     'id': 'ethereum',
#   }
# ]


# // 获取名称方法
def getName(contract):
    name = contract.functions.getName().call()
    return name


# // 获取池内余额
def getBalance(contract, tokenInfo):
    decimals = tokenInfo['decimals']
    balance = 0
    try:
        balance = contract.functions.balance().call()
        print('balance is:', balance)
    except Exception as e:
        print('get balance error:', e)

    decimalsValue = 10**decimals
    # // console.log(133, name, decimals, balanceValue);
    return toFixed(balance/decimalsValue, 0)


# 获取法币报价
def fetchTokenPrice(data):
    tokens = [(item.get('id') or item['name']).lower() for item in data]
    yfii_id = 'yfii-finance'
    tokens.append(yfii_id)
    # print('token', tokens)
    try:
        res = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=%s&vs_currencies=usd' % ','.join(tokens))
        res_json = res.json()
    except:
        print('fetchTokenPrice request failed')
        return

    lst_all = []
    for item in data:
        name = item.get('name')
        balance = item.get('balance')
        id_coin = (item.get('id') or name).lower()
        usd = 0
        balancePrice = '0'
        try:
            usd = res_json[id_coin]['usd'] or 0
            balancePrice = toFixed(float(balance) * usd, 2)
        except Exception as e:
            print(192, e)
        dic_one = {
            'price': {'usd': usd},
            'balancePrice': balancePrice,
        }
        dic_one.update(item)
        lst_all.append(dic_one)

    try:
        yfii_price = res_json[yfii_id]['usd']
    except:
        yfii_price = 0

    return lst_all, yfii_price


def toFixed(num, fixed=None):
    return str(round(num, fixed))


#  初始化合约
def initContract(item):
    if item.get('source') == 'bsc':
        w333 = Web3(HTTPProvider('https://bsc-dataseed2.binance.org'))
    else:
        w333 = w3
    # print('w333.isConnected()', w333, w333.isConnected())
    tokenContract = w333.eth.contract(abi=erc20Abi, address=item['token'])
    vaultContract = w333.eth.contract(abi=vaultAbi, address=item['vault'])
    strategyContract = None
    if item.get('Strategy'):
        strategyContract = w333.eth.contract(abi=strategyAbi, address=item['Strategy'])
    return tokenContract, vaultContract, strategyContract


# 获取必要 token 信息
def getTokenInfo(contract, item=None):
    name = symbol = item['name'] if item else ''
    totalSupply = '0'
    decimals = '18'
    # print('contract', contract, contract.functions.name().call())

    try:
        # for MKR name&symbol 不标准
        name = contract.functions.name().call()
        symbol = contract.functions.symbol().call()
        # print('name:', name, symbol)
    except Exception as e:
        print('e:', e)

    try:
        totalSupply = contract.functions.totalSupply().call()
        decimals = contract.functions.decimals().call()
        # print('totalSupply', totalSupply)
    except Exception as e:
        print('getTokenInfo', e)

    return {
        'name': name,
        'symbol': symbol,
        'totalSupply': totalSupply,
        'decimals': decimals
    }


#  获取机枪池名称
def getAssetName(contract):
    name = contract.functions.name().call()
    return name


#  获取策略名称
def getStrategyName(contract):
    name = getName(contract)
    if name and 'yfii:Strategy:' in name:
        return name.split('yfii:Strategy:')[1]
    return name


#  获取年华率
def getStrategyAPY(lst):
    res = requests.get('https://api.dfi.money/apy.json').json()
    apyBackList = []
    for item in lst:
        name = item['name']
        yfiiAPY = res[name]
        one_dic = {
            'yfiiAPY': yfiiAPY.rstrip('%')
        }
        one_dic.update(item)
        apyBackList.append(one_dic)
    return apyBackList


# 合并机枪池配置至本地配置
def getVaultsList():
    commonBack = []

    for item in dataeth + databsc:
        init_con = initContract(item)
        print('initContract(config[0])', init_con)
        #  初始化合约
        tokenContract, vaultContract, strategyContract = init_con
        # print('tokenContract, vaultContract, strategyContract', tokenContract, vaultContract, strategyContract)
        #  获取币种信息
        tokenInfo = getTokenInfo(tokenContract, item)
        #  获取池子名称
        assetName = getAssetName(vaultContract) or item.get('assetName', '')
        print('tokenInfo', tokenInfo, '\nassetName', assetName)
        #  获取池子余额
        balance = getBalance(vaultContract, tokenInfo)
        print('\nbalance', balance)
        #  获取策略名称
        strategyName = ''
        strategyBalance = 0
        if item.get('Strategy'):
            strategyName = getStrategyName(strategyContract)
        # print('strategyName', strategyName)

        # for index, fi in enumerate(vaults):
        #     if fi['name'] == item['name']:
        #         break
        # else:
        #     index = -1
        # vaultsData = vaults[index] if index > -1 else {}
        # print('vaultsData', vaultsData)

        oneBack = {
            'assetName': assetName,
            'strategyName': strategyName,
            'balance': balance,
        }
        oneBack.update(item)

        commonBack.append(oneBack)

    # print('commonBack', commonBack)
    priceBackData, yfii_price = fetchTokenPrice(commonBack)
    # print('priceBackData:', priceBackData)
    apyBackData = getStrategyAPY(priceBackData)
    # print('apyBackData:', apyBackData)
    oldPoolData = getOldPoolData(yfii_price)

    tvl = []
    for pool in oldPoolData:
        tvl.append({
            'name': pool['name'],
            'tvl': float(pool['balancePrice']),
            'apy': float(pool['yfiiAPY']),
            'staked': pool['volume'],
        })

    oldPoolData.extend(apyBackData)

    print(172, oldPoolData)

    created_time = datetime.datetime.now() + datetime.timedelta(hours=8)
    # with open('test_data.json', 'w') as f:
    #     f.write(json.dumps(oldPoolData))

    text_vault = json.dumps({'data': oldPoolData, 'created_time': str(created_time)})
    text_3pool = json.dumps({'data': tvl, 'created_time': str(created_time)})
    return text_vault, text_3pool


# 一池-四池
def getOldPoolData(yfii_price):
    res = requests.get('https://api.coinmarketcap.com/data-api/v1/farming/yield/latest').json()
    farmingProjects = res['data']['farmingProjects']
    for oldPoolIndex, fi in enumerate(farmingProjects):
        if fi['name'] == 'yfii.finance':
            break
    else:
        oldPoolIndex = -1

    # print('oldPoolIndex', oldPoolIndex)
    oldPoolAllData = farmingProjects[oldPoolIndex]['poolList']
    data_0 = oldPoolAllData[0]
    data_1 = oldPoolAllData[1]

    data_4 = getDATA()

    oldPoolData = [
        {
            'Strategy': "0xb81D3cB2708530ea990a287142b82D058725C092",
            'assetName': data_0['name'],
            'balancePrice': toFixed(data_0['totalStake'], 2),
            'id': data_0['id'],
            'name': 'yearn.finance',
            'strategyName': data_0['name'],
            'token': "0xdF5e0e81Dff6FAF3A7e52BA697820c5e32D806A8",
            'vault': "0xb81D3cB2708530ea990a287142b82D058725C092",
            'yfiiWeeklyROI': toFixed(data_0['weeklyROI'], 4),
            'yfiiAPY': toFixed(data_0['yearlyROI'], 4),
            'source': 'eth',
            'sourceUrl': 'https://yfii.finance/',
        },
        {
            'Strategy': "0xAFfcD3D45cEF58B1DfA773463824c6F6bB0Dc13a",
            'assetName': data_1['name'],
            'balancePrice': toFixed(data_1['totalStake'], 2),
            'id': data_1['id'],
            'name': 'Balancer Pool',
            'strategyName': data_1['name'],
            'token': "0x16cAC1403377978644e78769Daa49d8f6B6CF565",
            'vault': "0xAFfcD3D45cEF58B1DfA773463824c6F6bB0Dc13a",
            'yfiiWeeklyROI': toFixed(data_1['weeklyROI'], 4),
            'yfiiAPY': toFixed(data_1['yearlyROI'], 4),
            'source': 'eth',
            'sourceUrl': 'https://yfii.finance/',
        },
        {
            'Strategy': "0xf1750B770485A5d0589A6ba1270D9FC354884D45",
            'assetName': 'YFII',
            # 'balancePrice': toFixed(data_1['totalStake'], 2),
            # 'id': data_1['id'],
            'name': 'Governance',
            # 'strategyName': data_1['name'],
            'token': "0xa1d0E215a23d7030842FC67cE582a6aFa3CCaB83",
            'yfiiWeeklyROI': '0',
            'yfiiAPY': '0',
            'yfii_price': yfii_price,
            'source': 'eth',
            'sourceUrl': 'https://yfii.finance/',
        },
        {
            'Strategy': "0x3d367c9529f260b0661e1c1e91167c9319ee96ca",
            'assetName': 'yfii Tether USD',
            'token': "0x72Cf258c852Dc485a853370171d46B9D29fD3184",
            'name': 'pool4',
            'yfiiWeeklyROI': toFixed(data_4.get('YFIWeeklyROI', 0), 4),
            'yfiiAPY': toFixed(data_4.get('apy', 0), 4),
            'volume': data_4.get('totalStakedAmount', 0),
            'balancePrice': toFixed(data_4.get('TVL', 0), 2),
            'source': 'eth',
            'sourceUrl': 'https://dfi.money/',
        }
    ]

    for pool in oldPoolData[0:3]:  # 前三个池子
        getPoolVol(pool)

    return oldPoolData


# 单个池子的抵押量和tvl
def getPoolVol(pool):
    strategy = pool['Strategy']
    decimals = 10 ** 18
    contract = w3.eth.contract(abi=erc20Abi, address=pool['token'])
    balance = contract.functions.balanceOf(strategy).call()
    volume = balance / decimals
    pool['volume'] = volume
    if strategy == "0xf1750B770485A5d0589A6ba1270D9FC354884D45":  # pool 3
        pool["balancePrice"] = toFixed(volume * pool['yfii_price'], 2)


db = peewee.MySQLDatabase(**mysql_kwargs)


class Abi_tokenjson(peewee.Model):
    text = peewee.TextField(verbose_name='文本')
    text_3pool = peewee.TextField(verbose_name='文本_3pool')
    created_time = peewee.DateTimeField(verbose_name='创建时间')

    class Meta:
        database = db


if __name__ == '__main__':
    text_vault, text_3pool = getVaultsList()

    db.connect()

    item = Abi_tokenjson.create(
        text=text_vault,
        text_3pool=text_3pool,
        created_time=datetime.datetime.now() + datetime.timedelta(hours=8)
    )
    item.save()
    db.close()
    # from web3 import Web3
    #
    # print(Web3.toChecksumAddress('0x0316eb71485b0ab14103307bf65a021042c6d380'))