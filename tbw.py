# -*- coding: utf-8 -*-
from collections import Counter
from pythark import Delegate, Block  # You can import multiple things in one line too
import time
import json
import os.path
import subprocess
from datetime import datetime

tbw_rewards = {}  # blank dictionary for rewards
block = 0  # set default block to 0, will update from call or json later
block_count = 0  # running counter for payouts


def parse_config():
    """
    Parse the config.json file and return the result.
    """
    with open('config.json') as data_file:
        data = json.load(data_file)
             
    return data

def allocate(lb, pk):
    data = parse_config()

    # create temp log / export output for block  rewards
    log = {}
    json_export = {}
    rewards_check = 0
    voter_check = 0
    delegate_check = 0
    
    # get voters / share / block reward same time
    d = Delegate(network)
    block_voters = d.get_voters(pk)
    
    # check if new voters first before allocating - need to create new key in dict
    new_voter(block_voters)
    
    # get total votes
    approval = sum(int(item['balance']) for item in block_voters['accounts']) 
    
    # get block reward
    block_reward = int(lb['blocks'][0]['reward'])
    fee_reward = int(lb['blocks'][0]['totalFee'])
    total_reward = int(lb['blocks'][0]['totalForged'])
    
    #EXPERIMENTAL
    # calculate delegate/reserve/other shares
    for k,v in data['keep'].items():
        if k == 'reserve':
            keep = (int(block_reward * v)) + int(fee_reward)
        else:
            keep = (int(block_reward * v))
            
        #assign  shares to log and rewards tracking
        keep_addr = data['pay_addresses'][k]
        log[keep_addr] = keep
        tbw_rewards[keep_addr]['unpaid'] += keep
        
        #increment delegate_check for double check
        delegate_check +=keep
    
    # calculate voter share
    vshare = block_reward * data['voter_share']
    
    # loop through the current voters and assign share
    for i in block_voters['accounts']:

        # convert balance from str to int
        i['balance'] = int(i['balance'])
    
        # filter out 0 balances for processing
        if i['balance'] > 0:
            i['share_weight'] = i['balance'] / approval # calc share rate
            i['reward'] = int(i['share_weight'] * vshare)  # calculate block reward
            log[i['address']] = i['reward']  # populate log for block export records
            tbw_rewards[i['address']]['unpaid'] += i['reward']  # add voter reward to unpaid tally in main tbw_rewards_dict
            
            # voter and rewards check
            voter_check += 1
            rewards_check += i['reward']

    print("""Processed Block: {0}\n
    Voters processed: {1}
    Voters Rewards: {2}
    Delegate Reward: {3}
    Voter + Delegate Rewards: {4}
    Total Block Rewards: {5}""".format(last_block_height, voter_check, rewards_check, delegate_check, (rewards_check + delegate_check), total_reward))

    with open('output/log/' + (str(last_block_height)) + '.json', 'w') as f:
        json.dump(tbw_rewards, f)
    
    # check to see if log file exists
    if not os.path.exists('output/log/result.json'):  # does not exists so create
        # create a json export for the block rewards for initial file
        json_export[last_block_height] = log
        # append log to json file for future use
        with open('output/log/result.json', 'a') as fp:
            json.dump(json_export, fp)
            
    else:  # read and add block as key
        with open('output/log/result.json') as f:
            json_decoded = json.load(f)
        
        json_decoded[last_block_height] = log
        
        with open('output/log/result.json', 'w') as f:
            json.dump(json_decoded, f)
            
# function to check if a new block was created
def new_block(l, n):
    if (n - l) > 0:
        global block
        block = n
        return True
    else:
        return False
    
# function to check for new voters
def new_voter(v):
    for i in v['accounts']:
        test = i['address'] in tbw_rewards.keys()
        if not test:
            tbw_rewards[i['address']] = {'unpaid': 0, 'paid': 0}
            
def manage_folders():
    # Rewrited it, now it handles it like it should, don't do anything if the directorys already exists thanks to the
    # exist_ok parameter, and if one of the directory doesn't exists, creates it.
    sub_names = ["log", "payment", "error"]
    for sub_name in sub_names:
        os.makedirs(os.path.join('output', sub_name), exist_ok=True)

def missed_block(b, i):
    # get last blocks by interval
    if i < 101:
        mcheck = b.get_blocks(limit=i, generatorPublicKey=pubKey)
        a = [i['height'] for i in mcheck['blocks']]
    else:
        a = []
        interval = i

        #get number of pages to retrieve
        divis = interval // 100
        remain = interval % 100

        #initialize page limit at 100 and offset to 0
        l = 100
        off = 0

        for i in range(divis+1):
        #first run assuming more than 100 records
            if i == 0:
            page = b.get_blocks(limit=l, generatorPublicKey="029fa2d85a912d2f9ee52878aff77de67d4580875d149cb97677a7e76e93328bd5")
            tmp = [i['height'] for i in page['blocks']]
            a += tmp
            off += 100

        #process last
        elif i == divis:
            page = b.get_blocks(limit=remain, offset=off, generatorPublicKey="029fa2d85a912d2f9ee52878aff77de67d4580875d149cb97677a7e76e93328bd5")
            tmp = [i['height'] for i in page['blocks']]
            a += tmp

            #process everything else
        else:
            page = b.get_blocks(limit=l, offset=off, generatorPublicKey="029fa2d85a912d2f9ee52878aff77de67d4580875d149cb97677a7e76e93328bd5")
            tmp = [i['height'] for i in page['blocks']]
            a += tmp
            off += 100
        
    # get last processed blocks by interval
    tmp = get_block_count()
    i = int(i) * -1;
    b = tmp[i:]
    
    # look for difference
    diff = set(a).symmetric_difference(set(b))
    # if empty set we processed all blocks
    if not diff:
        print("all blocks in payrun")
    # we missed a block to process somewhere
    else: 
        d = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f = open('output/error/missingblock.txt', 'a')
        f.write(d+' '+ 'Oops! We missed a block somewhere. Go investigate '+'\n')
        f.close()
                  
def get_highest_block():
    with open('output/log/result.json') as json_data:
        test = json.load(json_data)
        # get all blocks in a list and get hightest one
        l = [int(i) for i in test]
        last_processed_block = str((max(l)))
    return last_processed_block

def get_block_count():
    with open('output/log/result.json') as json_data:
        test = json.load(json_data)
        # get all blocks in a list and get hightest one
        l = [int(i) for i in test]
    return sorted(l)

def initialize():
    global block
    global tbw_rewards
    global block_count

    # import config
    data = parse_config()

    # check for block logs and payment folders on start up
    manage_folders()

    # get publicKey
    pubKey = data['publicKey']

    # get voters
    d = Delegate(data['network'])
    block_voters = d.get_voters(pubKey)
    
    # check if first run
    if block == 0:
        # check to see if the file already exists - means tbw was already running and got restarted
        if os.path.exists('output/log/result.json'):
            # open results file and get highest block processed
            last_processed_block = get_highest_block()
            # now open the block-tbw to get the last known balances and input to tbw_rewards to start
            tbw_rewards = json.load(open('output/log/' + last_processed_block + '.json'))
            # set last block to most recent one from files
            block = int(last_processed_block)
            block_count = len(get_block_count())
            
            #check for new reserve addresses 
            for k,v in data['pay_addresses'].items():
                if v not in tbw_rewards.keys():
                    tbw_rewards[v] = {'unpaid': 0, 'paid': 0}
            
        else:  # initialize paid/unpaid records for voters
            for i in block_voters['accounts']:
                tbw_rewards[i['address']] = {'unpaid': 0, 'paid': 0}
            # initialize paid/unpaid records for reserve account
            for k,v in data['pay_addresses'].items():
                tbw_rewards[v] = {'unpaid': 0, 'paid': 0}
            
def payout():
    data = parse_config()
    
    min = data['min_payment'] * 100000000
   
    # initialize pay_run
    unpaid = {}  # payment file
    
    # count number of transactions greater than payout threshold
    tx_count = len({k: v for k, v in tbw_rewards.items() if v['unpaid'] > min})
    # calculate tx fees needed to cover run in satoshis
    transaction_fee = 10000000
    tx_fees = tx_count * transaction_fee
   
    # generate pay file
    for k, v in tbw_rewards.items():
        if v['unpaid'] > min:
            # process voters and non-reserve address
            if k != data['pay_addresses']['reserve']:
                unpaid[k] = v['unpaid']
                                
                # subtract unpaid amount and add to paid
                v['paid'] += v['unpaid']  # add unpaid to paid column
                v['unpaid'] -= v['unpaid']  # zero out unpaid
    
            # process delegate share
            else:
                # pay delegate
                net_pay = v['unpaid']-tx_fees
                unpaid[k] = net_pay
                    
                # subtract unpaid amount and add to paid
                v['paid'] += v['unpaid']  # add unpaid to paid column
                v['unpaid'] -= v['unpaid']  # zero out unpaid
        
    # dump
    with open('unpaid.json', 'w') as f:
        json.dump(unpaid, f)
        
    # call process to run payments
    subprocess.Popen(['python3', 'payment.py'])

if __name__ == '__main__':
    initialize()

    config = parse_config()
    network = config['network']
    pubKey = config['publicKey']
    while True:
        b = Block(network)
        #temp fix to catch attribute error
        try:
            last_block = b.get_blocks(limit=1, generatorPublicKey=pubKey)
        except:
            errfile = open("output/error/error.txt", "w")
            errfile.write(str(block))
            errfile.close()
            # set block to last block found to continue on
            last_block = {'blocks':[{'height': block}]}
        
        last_block_height = last_block['blocks'][0]['height']
        check = new_block(block, last_block_height)
        
        if check:
            block_count += 1
            print("Current block count : {0}".format(block_count))
            allocate(last_block, pubKey)
            print('\n' + 'Waiting for the next block....' + '\n')
            
                    #set pay flag to help prevent dup payments
            file = open('flag.txt', 'w')
            file.write('N')
            file.close()    

        else:
            time.sleep(7)

        if block_count % config['interval'] == 0:
            # use unpaid check to ensure payment function doesnt run miltiple times in divisible block
            value = sum(map(Counter, tbw_rewards.values()), Counter())
            total = value['unpaid']

            file = open('flag.txt', 'r')
            flag = file.read()
            file.close()

            if total > 0 and flag == 'N':
                #check for any missed blocks                
                missed_block(b, config['interval'])
                print('Payout started !')
                payout()
                
                #set payout flag to yes until next block
                f = open('flag.txt', 'w')
                f.write('Y')
                file.close()
