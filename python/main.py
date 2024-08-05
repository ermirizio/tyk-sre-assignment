import sys
import argparse
import schedule
import time
from kubernetes import client, config
from threading import Thread
from app import app

def check_kubernetes_status(api_client,verbose=False):
    try:
        version = app.get_kubernetes_version(api_client)
        if verbose:
            print(f"Kubernetes API server version: {version}")
    except Exception as e:
        print(f"Failed to get Kubernetes version: {e}")

def start_server(address):
    try:
        app.start_server(address)
    except KeyboardInterrupt:
        print("Server terminated")

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
    check_kubernetes_status(api_client,True)
          
    # Schedule the recurrent task
    schedule.every(args.interval).seconds.do(check_kubernetes_status, api_client)

    # Start the HTTP server in a separate thread
    server_thread = Thread(target=start_server, args=(args.address,))
    server_thread.start()

    # Main loop to run the scheduled tasks
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("Recurrent task terminated")
        server_thread.join()  # Ensure the server thread is cleaned up properly
