import json
import datetime

import peewee
import requests
from web3 import Web3, HTTPProvider
from web3.auto.infura import w3

from poolReward import pool4_and_farm
from abi_json.ERC20 import erc20Abi
from abi_json.v2.vault import vaultAbi
from abi_json.v2.strategy import strategyAbi

from configs.v2.config import dataeth, databsc
from configs.config_django import mysql_kwargs


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
            usd = (res_json[id_coin]['usd'] if name != 'husd3crv' else res_json['curve-fi-ydai-yusdc-yusdt-ytusd']['usd']) or 0
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


#  获取策略名称
def getStrategyName(contract):
    name = contract.functions.getName().call()
    if name and 'yfii:Strategy:' in name:
        return name.split('yfii:Strategy:')[1]
    return name


#  获取年华率
def getStrategyAPY(lst):
    res = requests.get('https://api.dfi.money/apy.json').json()
    apyBackList = []
    for item in lst:
        name = item['name']
        if name == 'husd3crv':
            name = 'husd'
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
        assetName = tokenContract.functions.name().call() or item.get('assetName', '')
        print('tokenInfo', tokenInfo, '\nassetName', assetName)
        #  获取池子余额
        balance = getBalance(vaultContract, tokenInfo)
        print('\nbalance', balance)
        #  获取策略名称
        strategyName = ''
        strategyBalance = 0
        if item.get('Strategy'):
            strategyName = getStrategyName(strategyContract)

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

    data_4, data_farm_pools, data_2, data_lp_origin, pool5 = pool4_and_farm()

    oldPoolData = getOldPoolData(yfii_price, data_4, data_2)

    data_stake_pools = []
    for pool in oldPoolData:
        data_stake_pools.append({
            'name': pool['name'],
            'tvl': float(pool['balancePrice']),
            'apy': pool['yfiiAPY'] + '%',
            'staked': pool['volume'],
        })

    data_stake_pools.append({
        'name': pool5['name'],
        'tvl': pool5['tvl'],
        'apy': pool5['apy'],
        'staked': pool5['staked'],
    })

    oldPoolData.extend(apyBackData)

    yfii_mefi = data_farm_pools[0]
    oldPoolData.append(
        {
            "yfiiAPY": yfii_mefi['apy'].rstrip('%'),
            "price": {
                "usd": yfii_mefi['price']
            },
            "balancePrice": toFixed(yfii_mefi['tvl'], 2),
            "assetName": yfii_mefi.get("assetName", "MEET.ONE Finance"),
            "strategyName": "",
            "balance": toFixed(yfii_mefi['staked'], 0),
            "token": "0x1a969239e12f07281f8876d11afcee081d872adf",
            "Strategy": "0x6A77c0c917Da188fBfa9C380f2E60dd223c0c35a",
            "vault": "",
            "name": "yfii-mefi",
            "StrategyName": "",
            "source": "eth",
            "sourceUrl": "https://dfi.money/"
        }
    )

    data_lp_pools = [{'name': i['name'], 'apy': i["yfiiAPY"]+'%'} for i in data_lp_origin]
    oldPoolData.extend(data_lp_origin)

    print(172, oldPoolData)

    created_time_str = str(datetime.datetime.now() + datetime.timedelta(hours=8))
    # with open('test_data.json', 'w') as f:
    #     f.write(json.dumps(oldPoolData))

    text_vault = json.dumps({'data': oldPoolData, 'created_time': created_time_str})
    text_stake = json.dumps({'data': data_stake_pools, 'created_time': created_time_str})
    text_farm = json.dumps({'data': data_farm_pools, 'created_time': created_time_str})
    text_lp = json.dumps({'data': data_lp_pools, 'created_time': created_time_str})
    return text_vault, text_stake, text_farm, text_lp


# 一池-四池
def getOldPoolData(yfii_price, data_4, data_2):
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
    # data_1 = oldPoolAllData[1]

    oldPoolData = [
        {
            'Strategy': "0xb81D3cB2708530ea990a287142b82D058725C092",
            'assetName': "Curve.fi yDAI/yUSDC/yUSDT/yTUSD", # w3.eth.contract(abi=erc20Abi, address="0xdF5e0e81Dff6FAF3A7e52BA697820c5e32D806A8").functions.name().call(),
            'balancePrice': toFixed(data_0['totalStake'], 2),
            'id': data_0['id'],
            'name': 'yearn.finance',
            'strategyName': data_0['name'],
            'token': "0xdF5e0e81Dff6FAF3A7e52BA697820c5e32D806A8",
            'vault': "0xb81D3cB2708530ea990a287142b82D058725C092",
            'yfiiWeeklyROI': toFixed(data_0['weeklyROI'], 2),
            'yfiiAPY': toFixed(data_0['yearlyROI'], 2),
            'source': 'eth',
            'sourceUrl': 'https://old.dfi.money/',
        },
        {
            'Strategy': "0xAFfcD3D45cEF58B1DfA773463824c6F6bB0Dc13a",
            'assetName': "Balancer Pool Token",  #w3.eth.contract(abi=erc20Abi, address="0x16cAC1403377978644e78769Daa49d8f6B6CF565").functions.name().call(),
            'balancePrice': toFixed(data_2['tvl'], 2),
            # 'id': data_1['id'],
            'name': 'Balancer Pool',
            'strategyName': "Balancer YFII-DAI",
            'token': "0x16cAC1403377978644e78769Daa49d8f6B6CF565",
            'vault': "0xAFfcD3D45cEF58B1DfA773463824c6F6bB0Dc13a",
            'yfiiWeeklyROI': toFixed(data_2['WeeklyROI'], 2),
            'yfiiAPY': data_2['apy'].rstrip('%'),
            'source': 'eth',
            'sourceUrl': 'https://old.dfi.money/',
            'volume': data_2['staked']
        },
        {
            'Strategy': "0xf1750B770485A5d0589A6ba1270D9FC354884D45",
            'assetName': "YFII.finance", #w3.eth.contract(abi=erc20Abi, address="0xa1d0E215a23d7030842FC67cE582a6aFa3CCaB83").functions.name().call(),
            # 'balancePrice': toFixed(data_1['totalStake'], 2),
            # 'id': data_1['id'],
            'name': 'Governance',
            # 'strategyName': data_1['name'],
            'token': "0xa1d0E215a23d7030842FC67cE582a6aFa3CCaB83",
            'yfiiWeeklyROI': '0',
            'yfiiAPY': '0',
            'yfii_price': yfii_price,
            'source': 'eth',
            'sourceUrl': 'https://old.dfi.money/',
        },
        {
            'Strategy': "0x3d367c9529f260b0661e1c1e91167c9319ee96ca",
            'assetName': data_4.get('assetName', 'yfii Tether USD'),
            'token': "0x72Cf258c852Dc485a853370171d46B9D29fD3184",
            'name': 'pool4',
            'yfiiWeeklyROI': toFixed(data_4.get('WeeklyROI', 0), 2),
            'yfiiAPY': data_4.get('apy', '0').rstrip('%'),
            'volume': data_4.get('staked', 0),
            'balancePrice': toFixed(data_4.get('tvl', 0), 2),
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
    if strategy == '0xAFfcD3D45cEF58B1DfA773463824c6F6bB0Dc13a':
        return
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
    text_farm = peewee.TextField(verbose_name='文本_farm')
    text_lp = peewee.TextField(verbose_name='文本_lp')
    created_time = peewee.DateTimeField(verbose_name='创建时间')

    class Meta:
        database = db


if __name__ == '__main__':
    text_vault, text_3pool, text_farm, text_lp = getVaultsList()

    db.connect()

    item = Abi_tokenjson.create(
        text=text_vault,
        text_3pool=text_3pool,
        text_farm=text_farm,
        text_lp=text_lp,
        created_time=datetime.datetime.now() + datetime.timedelta(hours=8)
    )
    item.save()
    db.close()
    # from web3 import Web3
    #
    # print(Web3.toChecksumAddress('0x0316eb71485b0ab14103307bf65a021042c6d380'))