import socketserver
import json
from kubernetes import client
from http.server import BaseHTTPRequestHandler
from .logger import logger
from kubernetes.client import V1NetworkPolicy, V1NetworkPolicySpec, V1LabelSelector, V1NetworkPolicyIngressRule, V1NetworkPolicyPeer, V1ObjectMeta

class CustomTCPServer(socketserver.TCPServer):
    def __init__(self, server_address, RequestHandlerClass, api_client, bind_and_activate=True):
        self.api_client = api_client
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)

def start_server(address, api_client):
    """
    Launches an HTTP server with handlers defined by AppHandler class and blocks until it's terminated.

    Expects an address in the format of `host:port` to bind to.

    Throws an underlying exception in case of error.
    """
    try:
        host, port = address.split(":")
    except ValueError:
        logger.error("Invalid server address format")
        return

    with CustomTCPServer((host, int(port)), AppHandler, api_client) as httpd:
        logger.info(f"Server listening on {address}")
        httpd.serve_forever()
        
class AppHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Handles POST requests"""
        if self.path == "/create-network-policy":
            self.create_network_policy()
        else:
            self.send_error(404)

    def create_network_policy(self):
        """Handles network policy creation via a POST request"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        policy_name = data.get("policy_name")
        namespace = data.get("namespace")
        pod_labels = data.get("pod_labels", {})

        try:
            create_network_policy(self.server.api_client, policy_name, namespace, pod_labels)
            self.respond(200, json.dumps({"status": "OK", "message": "NetworkPolicy created successfully"}))
        except Exception as e:
            self.respond(500, json.dumps({"status": "Failed", "message": str(e)}))


    def do_GET(self):
        """Catch all incoming GET requests"""
        if self.path == "/healthz":
            self.healthz()
        elif self.path == "/version":
            self.version()
        elif self.path == "/deployments":
            self.get_deployments()         
        else:
            self.send_error(404)

    def healthz(self):
        """Responds with the health status of the application"""
        self.respond(200, "ok")

    def version(self):
        """Responds with the health status of the application"""
        self.respond(200, get_kubernetes_version(self.server.api_client))        

    def get_deployments(self):
        """Fetch and respond with the status of deployments and their respective namespaces"""
        deployments_info = self.fetch_deployments_info()
        
        status = "Ok" if all(deploy['status'] == "Ok" for deploy in deployments_info) else "Failed"
        
        response = {
            "Status": status,
            "Deployments": deployments_info
        }
        self.respond(200, response)

    def fetch_deployments_info(self):
        """Fetch the list of deployments with their respective namespaces"""
        deployments_info = []
        try:
            apps_v1 = client.AppsV1Api(self.server.api_client)
            deployments = apps_v1.list_deployment_for_all_namespaces().items
            for deployment in deployments:
                namespace = deployment.metadata.namespace
                name = deployment.metadata.name
                desired_replicas = deployment.spec.replicas
                available_replicas = deployment.status.available_replicas or 0

                deployment_status = "Ok" if desired_replicas == available_replicas else "Failed"
                deployments_info.append({
                    "namespace": namespace,
                    "name": name,
                    "status": deployment_status,
                    "desired_replicas": desired_replicas,
                    "available_replicas": available_replicas
                })
            logger.info("Fetched deployments info successfully.")
        except Exception as e:
            logger.error(f"Error fetching deployments: {e}")
            deployments_info.append({
                "namespace": "Unknown",
                "name": "Error fetching deployments",
                "status": f"Failed: {str(e)}",
                "desired_replicas": None,
                "available_replicas": None
            })

        return deployments_info    

    def respond(self, status: int, content: dict):
        """Writes content and status code to the response socket"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        self.wfile.write(bytes(json.dumps(content), "UTF-8"))

def create_network_policy(api_client, policy_name, namespace, pod_labels):
    """
    Creates a Kubernetes NetworkPolicy in the specified namespace.

    Parameters:
    - api_client: The Kubernetes API client
    - policy_name: The name of the NetworkPolicy
    - namespace: The namespace where the policy will be applied
    - pod_labels: A dictionary of labels to select pods in the namespace
    """
    network_policy = V1NetworkPolicy(
        metadata=V1ObjectMeta(name=policy_name, namespace=namespace),
        spec=V1NetworkPolicySpec(
            pod_selector=V1LabelSelector(match_labels=pod_labels),
            policy_types=["Ingress","Egress"])
    )

    networking_v1 = client.NetworkingV1Api(api_client)
    try:
        networking_v1.create_namespaced_network_policy(namespace=namespace, body=network_policy)
        logger.info(f"NetworkPolicy {policy_name} created successfully in namespace {namespace}.")
    except client.exceptions.ApiException as e:
        logger.error(f"Failed to create NetworkPolicy: {e}")
        raise e


def get_kubernetes_version(api_client: client.ApiClient) -> str:
    """
    Returns a string GitVersion of the Kubernetes server defined by the api_client.

    If it can't connect an underlying exception will be thrown.
    """
    version = client.VersionApi(api_client).get_code()
    return version.git_version

def check_deployments_health(api_client: client.ApiClient) -> bool:
    """
    Checks if all deployments have the desired number of healthy pods.

    Returns:
        bool: True if all deployments are healthy, False otherwise.
    """
    v1_apps = client.AppsV1Api(api_client)
    deployments = v1_apps.list_deployment_for_all_namespaces().items

    all_healthy = True
    for deployment in deployments:
        desired_replicas = deployment.spec.replicas
        available_replicas = deployment.status.available_replicas or 0

        if available_replicas < desired_replicas:
            print(f"Deployment {deployment.metadata.name} in namespace {deployment.metadata.namespace} is unhealthy.")
            print(f"Desired: {desired_replicas}, Available: {available_replicas}")
            all_healthy = False
        else:
            print(f"Deployment {deployment.metadata.name} in namespace {deployment.metadata.namespace} is healthy.")

    return all_healthy