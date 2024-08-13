import sys
import argparse
import schedule
import time
import logging
from kubernetes import client, config
from threading import Thread
from app import app
from app.logger import logger , log_level_map

def check_kubernetes_status(api_client,logLevel='debug'):

    level = log_level_map.get(logLevel.lower() , logging.DEBUG)

    try:
        version = app.get_kubernetes_version(api_client)
        logger.log(level,f"Kubernetes API server version: {version}")
    except Exception as e:
        logger.error(f"Failed to get Kubernetes version: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tyk SRE Assignment",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-k", "--kubeconfig", type=str, default="",
                        help="Path to kubeconfig, leave empty for in-cluster")    
    parser.add_argument("-a", "--address", type=str, default=":8080",
                        help="HTTP server listen address")
    parser.add_argument("-i", "--interval", type=int, default=10,
                        help="Interval in minutes for checking Kubernetes status")
    args = parser.parse_args()

    if args.kubeconfig:
        config.load_kube_config(config_file=args.kubeconfig)
    else:
        config.load_incluster_config()

    api_client = client.ApiClient()
    check_kubernetes_status(api_client,'info')
          
    schedule.every(args.interval).seconds.do(check_kubernetes_status, api_client)

    server_thread = Thread(target=app.start_server, args=(args.address, api_client))
    server_thread.start()

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Recurrent task terminated")
        server_thread.join()




