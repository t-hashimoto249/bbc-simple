# -*- coding: utf-8 -*-
"""
Copyright (c) 2017 quvox.net

This code is based on that in bbc-1 (https://github.com/beyond-blockchain/bbc1.git)
"""
import gevent
from gevent import monkey
monkey.patch_all()
import bson
import base64
import binascii
import os
import subprocess

import sys
sys.path.append("../../")
from bbc_simple.core import bbc_app, bbclib
from bbc_simple.core.message_key_types import KeyType
from bbc_simple.logger.fluent_logger import get_fluent_logger

from argparse import ArgumentParser
from datetime import timedelta
from functools import update_wrapper
from flask import Flask, jsonify, request, make_response, current_app
from flask_cors import CORS

PID_FILE = "/tmp/bbc_admin_app_rest.pid"

http = Flask(__name__)
CORS(http)
flog = get_fluent_logger(name="bbc_app_rest")


def get_id_binary(jsondata, keystr):
    idstr = jsondata.get(keystr, None)
    if idstr is None:
        return None
    return binascii.a2b_hex(idstr)


def get_encoded_bson_txobj(txdat):
    txobj = bbclib.BBcTransaction(deserialize=txdat, format_type=bbclib.BBcFormat.FORMAT_BSON)
    return base64.b64encode(txobj.serialize_bson(no_header=True)).decode()


def crossdomain(origin=None, methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, str):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, str):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods
        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp
            h = resp.headers
            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)

    return decorator


@http.route('/domain_setup', methods=['POST', 'OPTIONS'])
@crossdomain(origin='*', headers=['Content-Type'])
def domain_setup():
    json_data = request.json
    domain_id = binascii.a2b_hex(json_data.get('domain_id'))
    config = json_data.get('config', None)
    qid = bbcapp.domain_setup(domain_id, config=config)
    retmsg = bbcapp.callback.sync_by_queryid(qid, timeout=5)
    if retmsg is None:
        return jsonify({'error': 'No response'}), 400
    msg = {'result': retmsg[KeyType.result]}
    if KeyType.reason in retmsg:
        msg['reason'] = retmsg[KeyType.reason]
    flog.debug({'cmd': 'domain_setup', 'result': retmsg[KeyType.result]})
    return jsonify(msg), 200


@http.route('/domain_close/<domain_id_str>', methods=['GET', 'OPTIONS'])
@crossdomain(origin='*', headers=['Content-Type'])
def domain_close(domain_id_str=None):
    try:
        domain_id = binascii.a2b_hex(domain_id_str)
    except:
        return jsonify({'error': 'invalid request'}), 500
    qid = bbcapp.domain_close(domain_id)
    retmsg = bbcapp.callback.sync_by_queryid(qid, timeout=5)
    if retmsg is None:
        return jsonify({'error': 'No response'}), 400
    msg = {'result': retmsg[KeyType.result]}
    if KeyType.reason in retmsg:
        msg['reason'] = retmsg[KeyType.reason]
    flog.debug({'cmd': 'domain_close', 'result': retmsg[KeyType.result]})
    return jsonify(msg), 200


@http.route('/gather_signatures', methods=['POST', 'OPTIONS'])
@crossdomain(origin='*', headers=['Content-Type'])
def gather_signatures():
    json_data = request.json
    transaction = json_data.get('transaction')
    reference_obj = json_data.get('reference_obj')
    destinations = json_data.get('destinations')
    flog.debug({'result': 'User registered successfully'})
    return jsonify({'message': 'User registered successfully'}), 200


@http.route('/sendback_signature', methods=['POST', 'OPTIONS'])
@crossdomain(origin='*', headers=['Content-Type'])
def sendback_signature():
    json_data = request.json
    dest_user_id = json_data.get('dest_user_id')
    transaction_id = json_data.get('transaction_id')
    ref_index = json_data.get('ref_index')
    signature = json_data.get('signature')
    query_id = json_data.get('query_id')
    flog.debug({'result': 'User registered successfully'})
    return jsonify({'message': 'User registered successfully'}), 200


@http.route('/sendback_denial_of_sign', methods=['POST', 'OPTIONS'])
@crossdomain(origin='*', headers=['Content-Type'])
def sendback_denial_of_sign():
    json_data = request.json
    dest_user_id = json_data.get('dest_user_id')
    transaction_id = json_data.get('transaction_id')
    reason_text = json_data.get('reason_text')
    query_id = json_data.get('query_id')
    flog.debug({'result': 'User registered successfully'})
    return jsonify({'message': 'User registered successfully'}), 200


@http.route('/insert_transaction/<domain_id_str>', methods=['POST', 'OPTIONS'])
@crossdomain(origin='*', headers=['Content-Type'])
def insert_transaction(domain_id_str=None):
    json_data = request.json
    try:
        domain_id = binascii.a2b_hex(domain_id_str)
        bbcapp.set_domain_id(domain_id)
        source_user_id = get_id_binary(json_data, 'source_user_id')
        bbcapp.set_user_id(source_user_id)
        bbcapp.register_to_core()
    except:
        return jsonify({'error': 'invalid request'}), 500
    txobj = bbclib.BBcTransaction(format_type=bbclib.BBcFormat.FORMAT_BSON)
    txdat = base64.b64decode(json_data.get('transaction_bson'))
    txobj.deserialize_bson(txdat)
    qid = bbcapp.insert_transaction(txobj)
    retmsg = bbcapp.callback.sync_by_queryid(qid, timeout=5)
    if retmsg is None:
        return jsonify({'error': 'No response'}), 400
    bbcapp.unregister_from_core()
    msg = {'result': 'success',
           'transaction_id': retmsg[KeyType.transaction_id].hex()}
    flog.debug(msg)
    return jsonify(msg), 200


@http.route('/search_transaction/<domain_id_str>', methods=['POST', 'OPTIONS'])
@crossdomain(origin='*', headers=['Content-Type'])
def search_transaction(domain_id_str=None):
    json_data = request.json
    try:
        domain_id = binascii.a2b_hex(domain_id_str)
        bbcapp.set_domain_id(domain_id)
        source_user_id = get_id_binary(json_data, 'source_user_id')
        bbcapp.set_user_id(source_user_id)
        bbcapp.register_to_core()
        txid = get_id_binary(json_data, 'transaction_id')
    except:
        return jsonify({'error': 'invalid request'}), 500
    qid = bbcapp.search_transaction(txid)
    retmsg = bbcapp.callback.sync_by_queryid(qid, timeout=5)
    if retmsg is None:
        return jsonify({'error': 'No response'}), 400

    bbcapp.unregister_from_core()

    msg = {'result': 'success',
           'transaction_bson': get_encoded_bson_txobj(retmsg[KeyType.transaction_data])}
    flog.debug(msg)
    return jsonify(msg), 200


@http.route('/search_transaction_with_condition/<domain_id_str>', methods=['POST', 'OPTIONS'])
@crossdomain(origin='*', headers=['Content-Type'])
def search_transaction_with_condition(domain_id_str=None):
    json_data = request.json
    try:
        domain_id = binascii.a2b_hex(domain_id_str)
        bbcapp.set_domain_id(domain_id)
        source_user_id = get_id_binary(json_data, 'source_user_id')
        bbcapp.set_user_id(source_user_id)
        bbcapp.register_to_core()
        asset_group_id = get_id_binary(json_data, 'asset_group_id')
        asset_id = get_id_binary(json_data, 'asset_id')
        user_id = get_id_binary(json_data, 'user_id')
        count = json_data.get('count', 1)
    except:
        return jsonify({'error': 'invalid request'}), 500
    qid = bbcapp.search_transaction_with_condition(asset_group_id=asset_group_id, asset_id=asset_id,
                                                   user_id=user_id, count=count)
    retmsg = bbcapp.callback.sync_by_queryid(qid, timeout=5)
    if retmsg is None:
        return jsonify({'error': 'No response'}), 400

    bbcapp.unregister_from_core()

    tx_ok = list()
    if KeyType.transactions in retmsg:
        for txdat in retmsg[KeyType.transactions]:
            tx_ok.append(get_encoded_bson_txobj(txdat))
    tx_ng = list()
    if KeyType.compromised_transactions in retmsg:
        for txdat in retmsg[KeyType.compromised_transactions]:
            tx_ng.append(get_encoded_bson_txobj(txdat))
    msg = {'result': 'success',
           'transaction_bsons': tx_ok,
           'transaction_compromised_bsons': tx_ng
           }
    flog.debug(msg)
    return jsonify(msg), 200


@http.route('/traverse_transactions/<domain_id_str>', methods=['POST', 'OPTIONS'])
@crossdomain(origin='*', headers=['Content-Type'])
def traverse_transactions(domain_id_str=None):
    json_data = request.json
    try:
        domain_id = binascii.a2b_hex(domain_id_str)
        bbcapp.set_domain_id(domain_id)
        source_user_id = get_id_binary(json_data, 'source_user_id')
        bbcapp.set_user_id(source_user_id)
        bbcapp.register_to_core()
        transaction_id = get_id_binary(json_data, 'transaction_id')
        asset_group_id = get_id_binary(json_data, 'asset_group_id')
        user_id = get_id_binary(json_data, 'user_id')
        direction = json_data.get('direction', 0)
        hop_count = json_data.get('hop_count', 3)
    except:
        return jsonify({'error': 'invalid request'}), 500
    qid = bbcapp.traverse_transactions(transaction_id=transaction_id, asset_group_id=asset_group_id, user_id=user_id,
                                       direction=direction, hop_count=hop_count)
    retmsg = bbcapp.callback.sync_by_queryid(qid, timeout=5)
    if retmsg is None:
        return jsonify({'error': 'No response'}), 400
    elif KeyType.reason in retmsg:
        msg = {'error': retmsg[KeyType.reason].decode()}
        flog.debug(msg)
        return jsonify(msg), 400

    bbcapp.unregister_from_core()

    include_all_flag = retmsg[KeyType.all_included]
    tx_tree = list()
    for level in retmsg[KeyType.transaction_tree]:
        tx_level = list()
        for txdat in level:
            tx_level.append(get_encoded_bson_txobj(txdat))
        tx_tree.append(tx_level)
    msg = {'result': 'success',
           'include_all_flag': include_all_flag,
           'transaction_tree': tx_tree
           }
    flog.debug(msg)
    return jsonify(msg), 200


def start_server(host="127.0.0.1", cport=9000, wport=3000):
    global bbcapp
    bbcapp = bbc_app.BBcAppClient(host=host, port=cport)
    #context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    #context.load_cert_chain(os.path.join(argresult.ssl, "cert1.pem"), os.path.join(argresult.ssl, "privkey1.pem"))
    #http.run(host='0.0.0.0', port=argresult.waitport, ssl_context=context)
    http.run(host='0.0.0.0', port=wport)


def daemonize(pidfile=PID_FILE):
    """
    デーモン化する
    :param pidfile:
    :return:
    """
    pid = os.fork()
    if pid > 0:
        os._exit(0)
    os.setsid()
    pid = os.fork()
    if pid > 0:
        f2 = open(pidfile, 'w')
        f2.write(str(pid) + "\n")
        f2.close()
        os._exit(0)
    os.umask(0)


def parser():
    usage = 'python {} [--addr <string>] [--waitport <number>] [--coreport <number>] [-t <string>] [--ssl <string>] ' \
            '[--log <filename>] [--verbose_level <string>] [--daemon] [--kill] [--help]'.format(__file__)
    argparser = ArgumentParser(usage=usage)
    argparser.add_argument('--address', type=str, default="127.0.0.1", help='IP address of core node')
    argparser.add_argument('--waitport', type=int, default=3000, help='waiting http port')
    argparser.add_argument('--coreport', type=int, default=9000, help='TCP port of core node')
    argparser.add_argument('-t', '--token', type=str, default="keys/token", help='Key directory for token')
    argparser.add_argument('--ssl', type=str, default="keys/zettant.com", help='Key directory for SSL')
    argparser.add_argument('-l', '--log', type=str, default="-", help='log filename/"-" means STDOUT')
    argparser.add_argument('-d', '--daemon', action='store_true', help='run in background')
    argparser.add_argument('-k', '--kill', action='store_true', help='kill the daemon')
    argparser.add_argument('-v', '--verbose_level', type=str, default="debug",
                           help='log level all/debug/info/warning/error/critical/none')
    args = argparser.parse_args()
    return args


if __name__ == '__main__':
    argresult = parser()
    if argresult.kill:
        subprocess.call("kill `cat " + PID_FILE + "`", shell=True)
        subprocess.call("rm -f " + PID_FILE, shell=True)
        sys.exit(0)
    if not os.path.exists(os.path.join(argresult.ssl, "cert1.pem")):
        print("No cert file for SSL is found!")
        sys.exit(0)
    if not os.path.exists(os.path.join(argresult.ssl, "privkey1.pem")):
        print("No private key file for SSL is found!")
        sys.exit(0)
    if not os.path.exists(os.path.join(argresult.token, "server_privatekey.pem")):
        print("No private key for token is found!")
        sys.exit(0)
    if not os.path.exists(os.path.join(argresult.token, "server_publickey.pem")):
        print("No public key for token is found!")
        sys.exit(0)

    if argresult.daemon:
        daemonize()

    start_server(argresult.address, argresult.coreport, argresult.waitport)
