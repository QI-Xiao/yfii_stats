from django.shortcuts import render
from django.http import HttpResponse, JsonResponse, Http404

import json
import requests
# from web3 import Web3, EthereumTesterProvider
from web3.auto.infura import w3

from abi_json.ERC20 import erc20Abi
from abi_json.vault import vaultAbi
from abi_json.strategy import strategyAbi

from configs import config


# 自定义机枪池配置
# id 获取法币报价字段名
vaults = [
  {
    'name': 'SNX',
    'id': 'havven',
  },
  {
    'name': 'LEND',
    'id': 'ethlend',
  },
  {
    'name': 'MKR',
    'id': 'maker',
  },
  {
    'name': 'YFI',
    'id': 'yearn-finance',
  },
  {
    'name': 'COMP',
    'id': 'compound-coin',
  },
  {
    'name': 'WBTC',
    'id': 'wrapped-bitcoin',
  },
  {
    'name': 'YCRV',
    'id': 'curve-fi-ydai-yusdc-yusdt-ytusd',
    'curveName': 'y',
  },
  {
    'name': 'YFII',
    'id': 'yfii-finance',
  },
  {
    'name': 'USDC',
    'id': 'usd-coin',
  },
  {
    'name': 'CCRV(cDAI+cUSDC)',
    'id': 'curve-fi-ydai-yusdc-yusdt-ytusd',
    'curveName': 'compound',
  },
]


# 策略池配置
STRATEGYPOOLS = {
  "GRAP": {
    #  池子名称 => 对应 /public/abi/${name}
    'strategyNameType': 'grap',
    #  挖出币的交易所 id => 对应 /public/configs/coingecko-coin.json 相应的 id
    'vaultToken': 'grap-finance',
  },
  "ZOMBIE.FINANCE": {
    'strategyNameType': 'zombie',
    'vaultToken': 'zombie-finance',
  },
  "YFII.finance": {
    'strategyNameType': 'yfii',
    'vaultToken': 'yfii-finance',
  },
}


#  获取配置文件
def getVaultsConfig():
    return config.data


# 获取 Strategy 配置
def getStrategyPool(strategyName):
    _, name = strategyName.split(':')
    return STRATEGYPOOLS[name]


# 合并机枪池配置至本地配置
def getVaultsList():
    config = getVaultsConfig()
    print(config)
    commonBack = []
    for item in config[9:10]:
        print('initContract(config[0])', initContract(item))
        #  初始化合约
        tokenContract, vaultContract, strategyContract = initContract(item)
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
        if item['strategy']:
            strategyName = getStrategyName(strategyContract)
            #  获取策略池内余额
            strategyBalance = getStrategyBalance(strategyContract, tokenInfo)
            print('strategyName, strategyBalance', strategyName, strategyBalance)
        for index, fi in enumerate(vaults):
            if fi['name'] == item['name']:
                break
        else:
            index = -1
        vaultsData = vaults[index] if index > -1 else {}

        oneBack = {
            'assetName': assetName,
            'strategyName': strategyName,
            'balance': balance,
            'strategyBalance': strategyBalance,
            'strategyContract': strategyContract,
            'vaultContract': vaultContract,
        }
        oneBack.update(item)
        oneBack.update(vaultsData)

        commonBack.append(oneBack)

    print('commonBack', commonBack)
    priceBackData = fetchTokenPrice(commonBack)
    print('priceBackData:', priceBackData)
    apyBackData = getStrategyAPY(priceBackData)
    print('apyBackData:', apyBackData)

    with open('test_data.json', 'w') as f:
        f.write(json.dumps(apyBackData))

    return apyBackData


#  初始化合约
def initContract(item):
    # w3 = Web3('https://mainnet.infura.io/v3/30636a84ebb34a1f8d0966c88134ade3')
    print('w3.isConnected()', w3, w3.isConnected())
    tokenContract = w3.eth.contract(abi=erc20Abi, address=item['token'])
    vaultContract = w3.eth.contract(abi=vaultAbi, address=item['vault'])
    strategyContract = None
    if item['strategy']:
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
    name = getName(contract)
    print('name', name)
    if name and ('yfii:Vault:' in name):
        return name.split('yfii:Vault:')[1]
    return name


# // 获取名称方法
def getName(contract):
    name = contract.functions.getName().call()
    return name


#  获取策略名称
def getStrategyName(contract):
    name = getName(contract)
    if name and 'yfii:Strategy:' in name:
        return name.split('yfii:Strategy:')[1]
    return name


#  获取年华率
def getStrategyAPY(lst):
    apyBackList = []
    for item in lst:
        name = item['name']
        curveName = item.get('curveName')
        balance = item['balance']
        strategy = item['strategy']
        strategyName = item['strategyName']
        strategyContract = item['strategyContract']
        yfiiDailyAPY = 0
        yfiiWeeklyAPY = 0
        yfiiAPY = 0
        pool = None
        print('strategyContract', strategyContract)
        try:
            pool = strategyContract.functions.pool().call()
            print('pool:', pool)
        except Exception as e:
            print('getStrategyAPY error:', e)
        item['strategyContract'] = str(item['strategyContract'])
        item['vaultContract'] = str(item['vaultContract'])

        if pool:
            print('strategyName:', strategyName)
            strategy_dic = getStrategyPool(strategyName)
            print('strategy_dic', strategy_dic)
            strategyNameType = strategy_dic['strategyNameType']
            vaultToken = strategy_dic['vaultToken']

            pool_dic = getPoolInfo(pool, strategyNameType, name)
            rewardRate = pool_dic['rewardRate']
            totalSupply = pool_dic['totalSupply']
            # 产出
            daily_reward = rewardRate * 86400
            weekly_reward = rewardRate * 604800
            year_reward = rewardRate * 31536000
            # 产出比例
            daily_rewardPerToken = daily_reward / totalSupply
            weekly_rewardPerToken = weekly_reward / totalSupply
            year_rewardPerToken = year_reward / totalSupply

            # 挖出币价格
            print('lst:', lst)
            strategyPrice = getTokenPrice(lst, vaultToken)

            #  本金币价格
            vaultPrice = getTokenPrice(lst, name)
            #  ROI = 日产出占比 & 挖出币的价格 * 100 / 本金
            yfiiDailyROI = (daily_rewardPerToken * strategyPrice * 100) / vaultPrice
            yfiiWeeklyROI = (weekly_rewardPerToken * strategyPrice * 100) / vaultPrice
            yfiiYearROI = (year_rewardPerToken * strategyPrice * 100) / vaultPrice

            # APY
            yfiiDailyAPY = ((1 + yfiiDailyROI / 100) ** 365 - 1) * 100
            yfiiWeeklyAPY = ((1 + yfiiWeeklyROI / 100) ** 52 - 1) * 100
            yfiiAPY = yfiiYearROI

#         console.log(177);
#         console.log(name, 'rewardRate', rewardRate);
#         console.log(name, 'totalSupply', totalSupply);
#         console.log(name, 'reward', daily_reward, weekly_reward);
#         console.log(
#           name,
#           'rewardPerToken',
#           daily_rewardPerToken,
#           weekly_rewardPerToken,
#         );
#         console.log(name, 'price', strategyPrice, vaultPrice);
#         console.log(name, 'ROI', yfiiDailyROI, yfiiWeeklyROI);
#         console.log(
#           name,
#           'Daily ROI in USD',
#           `${toFixed(yfiiDailyROI, 4)}%`,
#         );
#         console.log(
#           name,
#           'APY (Daily)',
#           `${toFixed(((1 + yfiiDailyROI / 100) ** 365 - 1) * 100, 4)}%`,
#         );
#         console.log(
#           name,
#           'Weekly ROI in USD',
#           `${toFixed(yfiiWeeklyROI, 4)}%`,
#         );
#         console.log(
#           name,
#           'APY (Weekly)',
#           `${toFixed(((1 + yfiiWeeklyROI / 100) ** 52 - 1) * 100, 4)}%`,
#         );
#         console.log(
#           name,
#           'APY (unstable)',
#           `${toFixed(yfiiAPY, 4)}%`,
#         );
            one_dic = {
                'yfiiDailyROI': toFixed(yfiiDailyROI, 4),
                'yfiiWeeklyROI': toFixed(yfiiWeeklyROI, 4),
                'yfiiDailyAPY': toFixed(yfiiDailyAPY, 4),
                'yfiiWeeklyAPY': toFixed(yfiiWeeklyAPY, 4),
                'yfiiAPY': toFixed(yfiiAPY, 4),
            }
            one_dic.update(item)
            apyBackList.append(one_dic)
            continue

        #  Curve 池年华计算
        if 'Curve' in strategyName:
            yfiiAPY = getCurveAPY(curveName)[0]
            one_dic = {
                'yfiiAPY': yfiiAPY,
            }
            one_dic.update(item)
            apyBackList.append(one_dic)
            continue

    return apyBackList


#  获取投资池子 & totalSupply
def getPoolInfo(pool, strategy, token):
    poolConract = None
    with open('public/abi/%s/%s.json' %(strategy, token)) as f:
        abi = f.read()
    # print('getPoolInfo abi:', pool, strategy, token, abi)

    try:
        poolConract = w3.eth.contract(abi=abi, address=pool)
        # print('getPoolInfo poolConract', poolConract)
    except Exception as e:
        print('error:', e)

    rewardRate = None
    totalSupply = None

    if poolConract:
        rewardRate = poolConract.functions.rewardRate().call()
        totalSupply = poolConract.functions.totalSupply().call()

    # print('rewardRate, totalSupply:', rewardRate, totalSupply)
    return {
        'rewardRate': rewardRate / 1e18,
        'totalSupply': totalSupply / 1e18
    }


#  获取 Curve 池子年化率
def getCurveAPY(token):
    res = requests.get('https://www.curve.fi/raw-stats/apys.json').json()
    yfiiDailyAPY = None
    yfiiWeeklyAPY = None
    yfiiAPY = None
    print('res', res)
    try:
        yfiiDailyAPY = res['apy']['day'][token]
        yfiiWeeklyAPY = res['apy']['week'][token]
        yfiiAPY = res['apy']['total'][token]
    except Exception as e:
        print(e)

    print(token, yfiiDailyAPY, yfiiWeeklyAPY)
    # # // return [toFixed(yfiiDailyAPY * 100, 4), toFixed(yfiiWeeklyAPY * 100, 4)];
    return [toFixed(yfiiAPY * 100), 4]


# # // 获取策略目标池子地址
# def getPool(contract):
#     pool = None
#
#     if (contract.methods.pool):
#         pool = await contract.methods.pool().call()
#
#     return pool

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


# // 获取策略池内余额
def getStrategyBalance(contract, tokenInfo):
    decimals = tokenInfo['decimals']
    strategyBalance = 0
    try:
        strategyBalance = contract.functions.balanceOf().call()
        print('get strategyBalance:', strategyBalance)
    except Exception as e:
        print('strategyBalance error:', e)
    decimalsValue = 10**decimals
    return toFixed(strategyBalance/decimalsValue, 0)

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


# // 遍历获取 token 价格
def getTokenPrice(lst, token):
    for index, item in enumerate(lst):
        if token == item['name']:
            break
    else:
        index = -1
    usd = 0

    if index > -1:
        price = lst[index]['price']
        usd = price['usd']
    else:
        print('console.log(435, token);', token)
        try:
            res = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=%s&vs_currencies=usd' %token)
            data = res.json()
            usd = data[token]['usd']
        except Exception as e:
            print('getTokenPrice error:', e)

    return usd


def toFixed(num, fixed=None):
    return round(num, fixed)

getVaultsList()
