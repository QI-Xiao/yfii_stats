import json
import datetime

import peewee
import requests
# from web3 import Web3, EthereumTesterProvider
from web3.auto.infura import w3

from abi_json.ERC20 import erc20Abi
from abi_json.v2.vault import vaultAbi
from abi_json.v2.strategy import strategyAbi

from configs.v2 import config
from configs.config_django import mysql_kwargs


# 自定义机枪池配置
# id 获取法币报价字段名
vaults = [
  {
    'name': 'usdt',
    id: 'tether',
  },
  {
    "name": 'ycrv',
    id: 'curve-fi-ydai-yusdc-yusdt-ytusd',
    "curveName": 'y',
  },
  {
    "name": 'dai',
    id: 'dai',
  },
  {
    "name": 'tusd',
    id: 'true-usd',
  },
  {
    "name": 'usdc',
    id: 'usd-coin',
  },
  {
    'name': 'eth',
    id: 'ethereum',
  }
]


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
        id = (item.get('id') or name).lower()
        usd = balancePrice = 0
        try:
            usd = res_json[id]['usd'] or 0
            balancePrice = toFixed(balance * usd, 2)
        except Exception as e:
            print(192, e)
        dic_one = {
            'price': {'usd': usd},
            'balancePrice': balancePrice,
        }
        dic_one.update(item)
        lst_all.append(dic_one)

    return lst_all


def toFixed(num, fixed=None):
    return round(num, fixed)


#  获取配置文件
def getVaultsConfig():
    return config.data


#  初始化合约
def initContract(item):
    # w3 = Web3('https://mainnet.infura.io/v3/30636a84ebb34a1f8d0966c88134ade3')
    print('w3.isConnected()', w3, w3.isConnected())
    tokenContract = w3.eth.contract(abi=erc20Abi, address=item['token'])
    vaultContract = w3.eth.contract(abi=vaultAbi, address=item['vault'])
    strategyContract = None
    if item.get('strategy'):
        strategyContract = w3.eth.contract(abi=strategyAbi, address=item['strategy'])
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
            'yfiiAPY': yfiiAPY  # toFixed(yfiiAPY, 4),
        }
        one_dic.update(item)
        apyBackList.append(one_dic)
    return apyBackList


# 合并机枪池配置至本地配置
def getVaultsList():
    config = getVaultsConfig()
    print(config)
    commonBack = []
    for item in config:
        init_con = initContract(item)
        print('initContract(config[0])', init_con)
        #  初始化合约
        tokenContract, vaultContract, strategyContract = init_con
        #  获取币种信息
        tokenInfo = getTokenInfo(tokenContract, item)
        #  获取池子名称
        assetName = (getAssetName(vaultContract)) or item['assetName']
        print('tokenInfo', tokenInfo, '\nassetName', assetName)
        #  获取池子余额
        balance = getBalance(vaultContract, tokenInfo)
        print('\nbalance', balance)
        #  获取策略名称
        strategyName = ''
        strategyBalance = 0
        if item.get('strategy'):
            strategyName = getStrategyName(strategyContract)

        for index, fi in enumerate(vaults):
            if fi['name'] == item['name']:
                break
        else:
            index = -1
        # vaultsData = vaults[index] if index > -1 else {}

        oneBack = {
            'assetName': assetName,
            'strategyName': strategyName,
            'balance': balance,
        }
        # print('item, vaultsData', item, vaultsData)
        oneBack.update(item)
        # oneBack.update(vaultsData)

        commonBack.append(oneBack)

    # print('commonBack', commonBack)
    priceBackData = fetchTokenPrice(commonBack)
    # print('priceBackData:', priceBackData)
    apyBackData = getStrategyAPY(priceBackData)
    # print('apyBackData:', apyBackData)
    oldPoolData = getOldPoolData()
    oldPoolData.extend(apyBackData)

    print(172, oldPoolData)

    # with open('test_data.json', 'w') as f:
    #     f.write(json.dumps(oldPoolData))

    return json.dumps(oldPoolData)


# 一池和二池
def getOldPoolData():
    res = requests.get('https://api.coinmarketcap.com/data-api/v1/farming/yield/latest').json()
    farmingProjects = res['data']['farmingProjects']
    for oldPoolIndex, fi in enumerate(farmingProjects):
        if fi['name'] == 'yfii.finance':
            break
    else:
        oldPoolIndex = -1
    oldPoolAllData = farmingProjects[oldPoolIndex]['poolList']
    data_0 = oldPoolAllData[0]
    data_1 = oldPoolAllData[1]
    oldPoolData = [{
        'Strategy': "0xb81D3cB2708530ea990a287142b82D058725C092",
        'assetName': data_0['name'],
        'balancePrice': data_0['totalStake'],
        'id': data_0['id'],
        'name': data_0['pair'],
        'strategyName': data_0['name'],
        'token': "0xdF5e0e81Dff6FAF3A7e52BA697820c5e32D806A8",
        'vault': "0xb81D3cB2708530ea990a287142b82D058725C092",
        'yfiiWeeklyROI': toFixed(data_0['weeklyROI'], 4),
        'yfiiAPY': toFixed(data_0['yearlyROI'], 4)
    },
    {
        'Strategy': "0xAFfcD3D45cEF58B1DfA773463824c6F6bB0Dc13a",
        'assetName': data_1['name'],
        'balancePrice': data_1['totalStake'],
        'id': data_1['id'],
        'name': data_1['pair'],
        'strategyName': data_1['name'],
        'token': "0x16cAC1403377978644e78769Daa49d8f6B6CF565",
        'vault': "0xAFfcD3D45cEF58B1DfA773463824c6F6bB0Dc13a",
        'yfiiWeeklyROI': toFixed(data_1['weeklyROI'], 4),
        'yfiiAPY': toFixed(data_1['yearlyROI'], 4)
    }]
    return oldPoolData


db = peewee.MySQLDatabase(**mysql_kwargs)


class Abi_tokenjson(peewee.Model):
    text = peewee.TextField(verbose_name='文本')
    created_time = peewee.DateTimeField(verbose_name='创建时间')

    class Meta:
        database = db


if __name__ == '__main__':
    text_json = getVaultsList()

    db.connect()

    item = Abi_tokenjson.create(
        text=text_json, created_time=datetime.datetime.now()
    )
    item.save()
    db.close()
