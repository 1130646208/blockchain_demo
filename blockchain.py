#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2020/6/22 17:23
# @Author  : wsx
# @File    : blockchain.py
# @Software: PyCharm
# @Function: ...

# {
#     "index": 0,
#     "timestamp": "",
#     "transactions": [
#         {
#             "sender": "",
#             "recipient": "",
#             "amount": 5,
#
#         },
#     ],
#     "proof": "",
#     "previous_hash": "",
#
# }
import hashlib
import time
import json
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request
from argparse import ArgumentParser


class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.new_block(proof=100, previous_hash=1)

    def register_node(self, url: str):
        parsed_url = urlparse(url)
        self.nodes.add(parsed_url.netloc)

    def new_block(self, proof, previous_hash=None):
        block = {
            "index": len(self.chain) + 1,
            "timestamp": time.time(),
            "transactions": self.current_transactions,
            "proof": proof,
            "previous_hash": previous_hash or self.hash(self.chain[-1]),
        }
        # 清空当前交易, 因为已经打包
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount) -> int:
        self.current_transactions.append(
            {
                "sender": sender,
                "recipient": recipient,
                "amount": amount,
            }
        )
        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_proof: int) -> int:
        proof = 0
        while not self.valid_proof(last_proof, proof):
            proof += 1
        print(proof)
        return proof

    def valid_proof(self, last_proof: int, proof: int) -> bool:
        return hashlib.sha256(f'{last_proof}{proof}'.encode()).hexdigest()[0:4] == '0000'

    def resolve_confilics(self) -> bool:
        neighbours = self.nodes
        new_chain = None
        self_length = len(self.chain)
        for node in neighbours:
            response = requests.get(f"http://{node}/chain")
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                if self_length < length and self.valid_chain(chain):
                    new_chain = chain
                    # self_length = length

        if new_chain:
            self.chain = new_chain
            return True

        return False

    def valid_chain(self, chain) -> bool:
        current_index = 1
        last_block = chain[0]

        while current_index < len(chain):
            current_block = chain[current_index]

            if not current_block['previous_hash'] == self.hash(last_block):
                return False
            if not self.valid_proof(last_block['proof'], current_block['proof']):
                return False

            last_block = current_block
            current_index += 1

        print('yes')
        return True


app = Flask(__name__)
blockchain = Blockchain()
node_identifier = str(uuid4()).replace('-', '')


@app.route('/index', methods=['GET'])
def index():
    return 'hello blockchain'


@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)
    blockchain.new_transaction(sender=0,
                               recipient=node_identifier,
                               amount=14)
    blockchain.new_block(proof, previous_hash=None)
    response = {
        "message": 'new block forged',
        "index": blockchain.last_block['index'],
        "transactions": blockchain.last_block['transactions'],
        "proof": blockchain.last_block['proof']
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    print(values)
    required = ['sender', 'recipient', 'amount']
    if not values:
        return "Missing values", 400
    # 检查是否required中的东西, values中是否都有
    if not all(k in values for k in required):
        return "Missing values", 400

    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    response = {"message": f'transaction will be added to block {index}'}
    # 一般post请求正常返回201, 错误返回400
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        "chain": blockchain.chain,
        "length": len(blockchain.chain)
    }
    return jsonify(response), 200


# 注册的节点信息{"nodes": ["http://127.0.0.1:5001"]}
@app.route('/nodes/register', methods=["POST"])
def register_nodes():
    values = request.get_json()
    nodes = values.get("nodes")

    if not nodes:
        response = {
            "message": "please add a node"
        }
    else:
        for node in nodes:
            blockchain.register_node(node)

        response = {
            "message": "New nodes added.",
            "total": list(blockchain.nodes)
        }

    return jsonify(response), 201


@app.route('/nodes/resolve', methods=["GET"])
def consensus():
    replaced = blockchain.resolve_confilics()
    if replaced:
        response = {
            "message": "chain is replaced",
            "new chain": blockchain.chain
        }
    else:
        response = {
            "message": "chain is authorized."
        }

    return jsonify(response), 200


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen')
    args = parser.parse_args()
    port = args.port
    app.run(host='0.0.0.0', port=port)

